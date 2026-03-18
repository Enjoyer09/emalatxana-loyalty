# modules/analytics.py — PATCHED v3.0 (+ Refund System + Staff Performance)
import streamlit as st
import pandas as pd
import datetime
import time
import json
import logging
from decimal import Decimal, ROUND_HALF_UP

from database import run_query, run_action, run_transaction, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system, safe_decimal

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def parse_items_for_display(items_str):
    if not items_str or items_str == "Table Order":
        return items_str
    try:
        items = json.loads(items_str)
        return ", ".join([f"{i['item_name']} x{i['qty']}" for i in items])
    except:
        return items_str


# ============================================================
# REFUND/VOID MODAL (YENİ — Dünya Praktikası)
# ============================================================
@st.dialog("🔄 Satış Ləğvi / Refund")
def show_refund_dialog(sale_id):
    sale = run_query("SELECT * FROM sales WHERE id=:id", {"id": sale_id})
    if sale.empty:
        st.error("Satış tapılmadı!")
        return

    row = sale.iloc[0]

    # Artıq ləğv edilib?
    if row.get('status') == 'VOIDED':
        st.warning("Bu satış artıq ləğv edilib!")
        return

    # Satış detalları
    st.markdown(f"**Satış #{row['id']}** — {row['created_at']}")
    try:
        items = json.loads(row['items'])
        for item in items:
            st.write(f"  • {item['item_name']} ×{item['qty']}")
    except:
        st.write(f"  Məhsullar: {row['items'][:80]}")

    st.markdown(f"**Məbləğ:** {float(row['total']):.2f} ₼ | **Ödəniş:** {row['payment_method']}")
    st.markdown("---")

    # Refund tipi
    refund_type = st.radio("Ləğv Növü:", [
        "🔴 TAM LƏĞV (Void) — Bütün məbləğ geri",
        "🟡 QİSMƏN REFUND — Müəyyən məbləğ geri"
    ], key="refund_type_radio")

    is_full_void = "TAM" in refund_type

    if is_full_void:
        refund_amount = Decimal(str(row['total']))
    else:
        refund_amount = Decimal(str(
            st.number_input("Geri qaytarılan məbləğ (₼):", min_value=0.01, max_value=float(row['total']), value=float(row['total']), step=0.5)
        ))

    # Stoka qaytar?
    return_to_stock = st.checkbox("📦 Məhsulları anbara geri qaytar", value=True)

    # Səbəb
    reason = st.selectbox("Ləğv Səbəbi:", [
        "Müştəri fikrini dəyişdi",
        "Səhv sifariş vuruldu",
        "Məhsul keyfiyyətsiz idi",
        "Test / Sınaq sifarişi",
        "Digər"
    ])
    reason_detail = st.text_input("Əlavə açıqlama (istəyə bağlı):", "")
    full_reason = f"{reason}" + (f" — {reason_detail}" if reason_detail.strip() else "")

    st.markdown("---")
    st.error("⚠️ Bu əməliyyat geri qaytarıla bilməz!")

    if st.button("✅ LƏĞVİ TƏSDİQLƏ", type="primary", use_container_width=True, key="confirm_refund"):
        now = get_baku_now()
        u = st.session_state.user
        is_test = row.get('is_test', False)
        actions = []

        # 1. Satışı VOIDED et (silinmir!)
        if is_full_void:
            actions.append((
                "UPDATE sales SET status='VOIDED' WHERE id=:id",
                {"id": sale_id}
            ))
        else:
            actions.append((
                "UPDATE sales SET status='PARTIAL_REFUND' WHERE id=:id",
                {"id": sale_id}
            ))

        # 2. Refund qeydi yarat
        actions.append((
            "INSERT INTO refunds (original_sale_id, refund_amount, reason, refund_type, items_returned_to_stock, created_by, created_at) "
            "VALUES (:sid, :amt, :reason, :rtype, :stock, :user, :time)",
            {
                "sid": sale_id,
                "amt": str(refund_amount),
                "reason": full_reason,
                "rtype": "VOID" if is_full_void else "PARTIAL_REFUND",
                "stock": return_to_stock,
                "user": u,
                "time": now
            }
        ))

        # 3. Finance — geri qaytarma
        if not is_test and refund_amount > 0:
            pm = row['payment_method']
            source = "Kassa" if pm in ['Nəğd', 'Cash'] else "Bank Kartı"
            actions.append((
                "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                "VALUES ('out', 'Refund / Ləğv', :a, :src, :desc, :u, :t, FALSE)",
                {
                    "a": str(refund_amount),
                    "src": source,
                    "desc": f"Satış #{sale_id} ləğvi: {full_reason}",
                    "u": u,
                    "t": now
                }
            ))

            # Bank komissiyasını da geri al (əgər kartla idisə)
            if pm in ['Kart', 'Card'] and is_full_void:
                min_comm = Decimal(str(get_setting("bank_comm_min", "0.60")))
                pct_comm = Decimal(str(get_setting("bank_comm_pct", "0.02")))
                original_comm = max(min_comm, (Decimal(str(row['total'])) * pct_comm).quantize(Decimal("0.01")))
                actions.append((
                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                    "VALUES ('in', 'Refund Komissiya Qaytarma', :a, 'Bank Kartı', :desc, :u, :t, FALSE)",
                    {"a": str(original_comm), "desc": f"Satış #{sale_id} komissiya qaytarma", "u": u, "t": now}
                ))

        # 4. Stoka qaytar
        if return_to_stock and not is_test:
            try:
                parsed = json.loads(row['items'])
                for item in parsed:
                    recs = run_query(
                        "SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m",
                        {"m": item.get('item_name')}
                    )
                    for _, rc in recs.iterrows():
                        qty_return = Decimal(str(rc['quantity_required'])) * Decimal(str(item.get('qty', 1)))
                        actions.append((
                            "UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:n",
                            {"q": str(qty_return), "n": rc['ingredient_name']}
                        ))
            except Exception as e:
                logger.warning(f"Stock return parse failed: {e}")

        # 5. Müştəri ulduzlarını geri al (əgər varsa)
        if not is_test and row.get('customer_card_id') and is_full_void:
            try:
                parsed = json.loads(row['items'])
                coffee_count = sum([i['qty'] for i in parsed if i.get('is_coffee')])
                if coffee_count > 0:
                    actions.append((
                        "UPDATE customers SET stars = GREATEST(0, stars - :s) WHERE card_id=:cid",
                        {"s": coffee_count, "cid": row['customer_card_id']}
                    ))
            except:
                pass

        # EXECUTE
        try:
            run_transaction(actions)
            log_system(u, f"REFUND: sale_id={sale_id}, amount={refund_amount}, type={'VOID' if is_full_void else 'PARTIAL'}, reason={full_reason}, stock_returned={return_to_stock}")
            st.success(f"✅ Satış #{sale_id} uğurla ləğv edildi! Məbləğ: {refund_amount:.2f} ₼")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")
            logger.error(f"Refund failed: {e}", exc_info=True)


# ============================================================
# ANALİTİKA SƏHİFƏSİ
# ============================================================
def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")

    # AI Analiz
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Analitika Audit"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin.")
            elif genai is None:
                st.warning("google-generativeai paketi quraşdırılmayıb.")
            else:
                if st.button("🔍 Dataları Skan Et", use_container_width=True):
                    with st.spinner("AI oxuyur..."):
                        try:
                            genai.configure(api_key=api_key)
                            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else 'models/gemini-pro')
                            model = genai.GenerativeModel(chosen_model)
                            recent = run_query(
                                "SELECT SUM(total) as t_rev, SUM(cogs) as t_cogs FROM sales "
                                "WHERE created_at >= current_date - interval '7 days' AND (is_test IS NULL OR is_test=FALSE) AND (status IS NULL OR status='COMPLETED')"
                            )
                            if not recent.empty and recent.iloc[0]['t_rev']:
                                rev = safe_decimal(recent.iloc[0]['t_rev'])
                                cogs = safe_decimal(recent.iloc[0]['t_cogs'])
                                prompt = f"Biznes analitik: Son 7 gün satış: {rev} AZN. COGS: {cogs} AZN. Mənfəət: {rev-cogs} AZN. Qısa rəy."
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background:#1e2226;padding:15px;border-left:5px solid #28a745;'>{response.text}</div>", unsafe_allow_html=True)
                            else:
                                st.info("Data yoxdur.")
                        except Exception as e:
                            st.error(f"Xəta: {e}")

    # Tarix filteri
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())

    ts_start = datetime.datetime.combine(d1, datetime.time(0, 0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23, 59))

    query = """
        SELECT s.*, c.stars as current_stars, c.type as cust_type 
        FROM sales s 
        LEFT JOIN customers c ON s.customer_card_id = c.card_id 
        WHERE s.created_at BETWEEN :s AND :e
    """
    params = {"s": ts_start, "e": ts_end}

    if st.session_state.role == 'staff':
        query += " AND s.cashier = :u"
        params["u"] = st.session_state.user
    query += " ORDER BY s.created_at DESC"

    sales = run_query(query, params)

    if not sales.empty:
        if 'is_test' not in sales.columns:
            sales['is_test'] = False
        if 'status' not in sales.columns:
            sales['status'] = 'COMPLETED'
        sales['status'] = sales['status'].fillna('COMPLETED')

        real_sales = sales[(sales['is_test'] != True) & (sales['status'] == 'COMPLETED')].copy()
        voided_sales = sales[sales['status'].isin(['VOIDED', 'PARTIAL_REFUND'])].copy()

        if 'cogs' not in real_sales.columns:
            real_sales['cogs'] = 0.0

        # Metrikalar
        total_rev = safe_decimal(real_sales['total'].sum())
        total_cogs = safe_decimal(real_sales['cogs'].sum())

        card_mask = real_sales['payment_method'].isin(['Card', 'Kart'])
        card_total = safe_decimal(real_sales.loc[card_mask, 'total'].sum())
        bank_fee = (card_total * Decimal("0.02")).quantize(Decimal("0.01"))
        gross_profit = total_rev - total_cogs - bank_fee

        cash_sales = safe_decimal(real_sales[real_sales['payment_method'].isin(['Cash', 'Nəğd'])]['total'].sum())
        void_count = len(voided_sales)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ümumi Satış", f"{total_rev:.2f} ₼")
        c2.metric("Nağd", f"{cash_sales:.2f} ₼")
        c3.metric("Kart", f"{card_total:.2f} ₼")
        c4.metric("Maya (COGS)", f"{total_cogs:.2f} ₼")
        c5.metric("Brutto Mənfəət", f"{gross_profit:.2f} ₼")

        # Void/Refund statistikası
        if void_count > 0:
            refund_total = safe_decimal(voided_sales['total'].sum())
            st.warning(f"⚠️ Bu dövrdə **{void_count}** ləğv/refund edilmiş satış var (Cəm: {refund_total:.2f} ₼)")

        st.divider()
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Çeklər", "☕ Məhsullar", "🔄 Ləğvlər", "👥 Staff"])

        # ============================================================
        # ÇEKLƏR TAB
        # ============================================================
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            sales_disp['Status'] = sales_disp['status'].apply(
                lambda x: '🔴 LƏĞV' if x == 'VOIDED' else '🟡 QİSMƏN' if x == 'PARTIAL_REFUND' else '✅'
            )
            sales_disp['Oxunaqlı_Səbət'] = sales_disp['items'].apply(parse_items_for_display)

            cols_to_disp = ['id', 'created_at', 'cashier', 'Oxunaqlı_Səbət', 'original_total', 'discount_amount', 'total', 'payment_method', 'Status', 'Test?']
            if 'cogs' in sales_disp.columns:
                cols_to_disp.insert(-2, 'cogs')

            display_df = sales_disp[[c for c in cols_to_disp if c in sales_disp.columns]].copy()
            display_df.insert(0, "Seç", False)

            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_ed_v3",
                column_config={
                    "cashier": "İşçi",
                    "Oxunaqlı_Səbət": "Sifariş",
                    "original_total": "Brutto",
                    "discount_amount": "Endirim",
                    "total": "Net",
                    "cogs": "Maya",
                    "payment_method": "Ödəniş",
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                }
            )

            sel_ids = edited_sales[edited_sales["Seç"]]['id'].tolist()

            if st.session_state.role in ['admin', 'manager'] and len(sel_ids) > 0:
                col_b1, col_b2, col_b3 = st.columns(3)

                if len(sel_ids) == 1:
                    # Refund düyməsi
                    if col_b1.button("🔄 Ləğv Et / Refund", type="primary", use_container_width=True):
                        show_refund_dialog(int(sel_ids[0]))

                    # Düzəliş
                    if col_b2.button("✏️ Düzəliş", use_container_width=True):
                        st.session_state.sale_edit_id = int(sel_ids[0])
                        st.rerun()

                # Köhnə "Sil" düyməsi artıq yoxdur — əvəzinə Refund var!

            # Düzəliş modal
            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    @st.dialog("✏️ Çek Redaktəsi")
                    def edit_dialog(r):
                        with st.form("ed_f"):
                            e_t = st.number_input("Yekun Məbləğ", value=float(r['total']))
                            pm_options = ["Nəğd", "Kart", "Staff", "Cash", "Card"]
                            pm_idx = pm_options.index(r['payment_method']) if r['payment_method'] in pm_options else 0
                            e_p = st.selectbox("Ödəniş", pm_options, index=pm_idx)
                            if st.form_submit_button("Yadda Saxla"):
                                run_action("UPDATE sales SET total=:t, payment_method=:p WHERE id=:id",
                                           {"t": str(Decimal(str(e_t))), "p": e_p, "id": r['id']})
                                log_system(st.session_state.user, f"SALE_EDIT: id={r['id']}, new_total={e_t}")
                                st.session_state.sale_edit_id = None
                                st.success("Dəyişdi!")
                                time.sleep(1)
                                st.rerun()
                    edit_dialog(s_res.iloc[0])

        # ============================================================
        # MƏHSULLAR TAB
        # ============================================================
        with tab2:
            item_counts = {}
            for items_str in real_sales['items']:
                if isinstance(items_str, str) and items_str != "Table Order":
                    try:
                        parsed = json.loads(items_str)
                        for item in parsed:
                            n = item.get('item_name')
                            item_counts[n] = item_counts.get(n, 0) + item.get('qty', 0)
                    except:
                        pass
            if item_counts:
                chart_df = pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).sort_values('Say', ascending=False)
                st.bar_chart(chart_df.set_index('Məhsul'))
            else:
                st.info("Data yoxdur.")

        # ============================================================
        # LƏĞVLƏR TAB (YENİ)
        # ============================================================
        with tab3:
            st.markdown("### 🔄 Ləğv və Refund Tarixçəsi")

            refunds = run_query(
                "SELECT r.*, s.total as original_total, s.cashier as original_cashier, s.payment_method "
                "FROM refunds r LEFT JOIN sales s ON r.original_sale_id = s.id "
                "WHERE r.created_at BETWEEN :s AND :e ORDER BY r.created_at DESC",
                {"s": ts_start, "e": ts_end}
            )

            if not refunds.empty:
                # Ləğv statistikası
                r1, r2, r3 = st.columns(3)
                r1.metric("Ləğv Sayı", len(refunds))
                r2.metric("Ləğv Məbləği", f"{safe_decimal(refunds['refund_amount'].sum()):.2f} ₼")
                r3.metric("Stoka Qaytarılan", f"{len(refunds[refunds['items_returned_to_stock'] == True])}")

                st.dataframe(
                    refunds[['id', 'original_sale_id', 'refund_amount', 'reason', 'refund_type', 'items_returned_to_stock', 'created_by', 'created_at']],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "original_sale_id": "Orijinal Satış #",
                        "refund_amount": st.column_config.NumberColumn("Məbləğ", format="%.2f ₼"),
                        "reason": "Səbəb",
                        "refund_type": "Növ",
                        "items_returned_to_stock": "Stoka Qaytarıldı?",
                        "created_by": "Kim Ləğv Etdi",
                        "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                    }
                )

                # Ən çox ləğv edən işçi
                if st.session_state.role == 'admin':
                    st.markdown("**📊 Ləğv Statistikası (İşçi üzrə):**")
                    by_user = refunds.groupby('created_by').agg(
                        sayi=('id', 'count'),
                        meblegi=('refund_amount', 'sum')
                    ).sort_values('sayi', ascending=False)
                    st.dataframe(by_user, use_container_width=True)
            else:
                st.success("✅ Bu dövrdə heç bir ləğv/refund yoxdur.")

        # ============================================================
        # STAFF PERFORMANS TAB (YENİ)
        # ============================================================
        with tab4:
            st.markdown("### 👥 Staff Performans Hesabatı")

            if st.session_state.role in ['admin', 'manager']:
                staff_stats = run_query(f"""
                    SELECT 
                        cashier,
                        COUNT(*) as satis_sayi,
                        SUM(total) as toplam_satis,
                        AVG(total) as orta_cek,
                        SUM(discount_amount) as toplam_endirim,
                        SUM(CASE WHEN payment_method IN ('Nəğd', 'Cash') THEN total ELSE 0 END) as nagd,
                        SUM(CASE WHEN payment_method IN ('Kart', 'Card') THEN total ELSE 0 END) as kart,
                        SUM(CASE WHEN payment_method = 'Staff' THEN total ELSE 0 END) as staff_benefit,
                        SUM(cogs) as toplam_cogs
                    FROM sales 
                    WHERE created_at BETWEEN :s AND :e 
                    AND (is_test IS NULL OR is_test=FALSE)
                    AND (status IS NULL OR status='COMPLETED')
                    GROUP BY cashier
                    ORDER BY toplam_satis DESC
                """, {"s": ts_start, "e": ts_end})

                if not staff_stats.empty:
                    for _, staff in staff_stats.iterrows():
                        with st.container(border=True):
                            st.markdown(f"#### 👤 {staff['cashier']}")
                            sc1, sc2, sc3, sc4 = st.columns(4)
                            sc1.metric("Satış Sayı", int(staff['satis_sayi']))
                            sc2.metric("Toplam", f"{float(staff['toplam_satis']):.2f} ₼")
                            sc3.metric("Orta Çek", f"{float(staff['orta_cek']):.2f} ₼")
                            sc4.metric("Endirim", f"{float(staff['toplam_endirim']):.2f} ₼")

                            sc5, sc6, sc7, sc8 = st.columns(4)
                            sc5.metric("Nağd", f"{float(staff['nagd']):.2f} ₼")
                            sc6.metric("Kart", f"{float(staff['kart']):.2f} ₼")
                            sc7.metric("Staff Benefit", f"{float(staff['staff_benefit']):.2f} ₼")
                            profit = float(staff['toplam_satis']) - float(staff['toplam_cogs'] or 0)
                            sc8.metric("Mənfəət", f"{profit:.2f} ₼")

                    # Void/Refund per staff
                    void_stats = run_query(
                        "SELECT created_by, COUNT(*) as cnt, SUM(refund_amount) as total_refund "
                        "FROM refunds WHERE created_at BETWEEN :s AND :e GROUP BY created_by",
                        {"s": ts_start, "e": ts_end}
                    )
                    if not void_stats.empty:
                        st.markdown("**🔄 Ləğv Statistikası (İşçi üzrə):**")
                        st.dataframe(void_stats, hide_index=True, use_container_width=True)
                else:
                    st.info("Bu dövrdə satış yoxdur.")
            else:
                st.info("Bu bölmə yalnız admin/manager üçündür.")
    else:
        st.info("Məlumat tapılmadı.")


# ============================================================
# Z-HESABAT SƏHİFƏSİ (VOIDED satışları çıxarır)
# ============================================================
def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)

    # VOIDED satışları çıxar
    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (status IS NULL OR status='COMPLETED')"
    q_cond_finance = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (is_deleted IS NULL OR is_deleted = FALSE)"
    params = {"d": sh_start_z, "e": sh_end_z}

    s_cash = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {q_cond}", params).iloc[0]['s'])
    s_card = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {q_cond}", params).iloc[0]['s'])
    try:
        s_cogs = safe_decimal(run_query(f"SELECT SUM(cogs) as s FROM sales WHERE 1=1 {q_cond}", params).iloc[0]['s'])
    except:
        s_cogs = Decimal("0")

    f_out = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond_finance}", params).iloc[0]['s'])
    f_in = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {q_cond_finance}", params).iloc[0]['s'])

    opening_limit = safe_decimal(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + s_cash + f_in - f_out

    # Refund count
    refund_count = run_query(
        "SELECT COUNT(*) as c FROM refunds WHERE created_at>=:d AND created_at<:e",
        {"d": sh_start_z, "e": sh_end_z}
    ).iloc[0]['c'] or 0

    if st.session_state.role == 'staff':
        my_sales = run_query(
            f"SELECT * FROM sales WHERE cashier=:u {q_cond} ORDER BY created_at DESC",
            {"u": st.session_state.user, "d": sh_start_z, "e": sh_end_z}
        )
        if not my_sales.empty:
            my_sales['items'] = my_sales['items'].apply(parse_items_for_display)
            m1, m2, m3 = st.columns(3)
            m1.metric("Mənim Satışım", f"{safe_decimal(my_sales['total'].sum()):.2f} ₼")
            m2.metric("Nağd", f"{safe_decimal(my_sales[my_sales['payment_method'].isin(['Nəğd', 'Cash'])]['total'].sum()):.2f} ₼")
            m3.metric("Kart", f"{safe_decimal(my_sales[my_sales['payment_method'].isin(['Kart', 'Card'])]['total'].sum()):.2f} ₼")
            st.dataframe(my_sales[['id', 'created_at', 'items', 'total', 'payment_method']], hide_index=True, use_container_width=True)
        else:
            st.warning("Bu növbədə satışınız yoxdur.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Kassa Açılış", f"{opening_limit:.2f} ₼")
        c2.metric("Nağd Satış", f"{s_cash:.2f} ₼")
        c3.metric("Kart Satış", f"{s_card:.2f} ₼")

        st.markdown("---")
        c4, c5, c6 = st.columns(3)
        c4.metric("Mədaxil (Satışsız)", f"{f_in:.2f} ₼")
        c5.metric("Məxaric (Xərc)", f"{f_out:.2f} ₼")
        c6.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")

        if st.session_state.role in ['admin', 'manager']:
            gross_profit = s_cash + s_card - s_cogs
            st.markdown(f"**COGS:** {s_cogs:.2f} ₼ | **Mənfəət:** {gross_profit:.2f} ₼ | **Ləğvlər:** {refund_count}")

        # Maaş
        with st.expander("💸 GÜNLÜK MAAŞ/AVANS ÖDƏ"):
            with st.form("salary_form_fix"):
                users_df = run_query("SELECT username FROM users")
                emp = st.selectbox("İşçi", users_df['username'].tolist() if not users_df.empty else [])
                amt = st.number_input("Məbləğ", min_value=0.0)
                if st.form_submit_button("💰 Ödə"):
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, created_by, description, created_at) "
                        "VALUES ('out', 'Maaş/Avans', :a, 'Kassa', :u, :d, :t)",
                        {"a": str(Decimal(str(amt))), "u": st.session_state.user, "d": f"{emp} avans", "t": get_baku_now()}
                    )
                    log_system(st.session_state.user, f"SALARY: {emp}, {amt}")
                    st.success("Ödənildi!")
                    time.sleep(1)
                    st.rerun()

    # X/Z Hesabat
    cx, cz = st.columns(2)
    if cx.button("🤝 X-Hesabat", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_dialog():
            st.info(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual = st.number_input("Kassadakı nağd:", value=float(expected_cash))
            if st.button("Təsdiqlə", type="primary"):
                actual_d = Decimal(str(actual))
                diff = actual_d - expected_cash
                now = get_baku_now()
                u = st.session_state.user
                actions = []
                if abs(diff) > Decimal("0.01"):
                    c_type = 'in' if diff > 0 else 'out'
                    cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
                    actions.append(("INSERT INTO finance (type,category,amount,source,description,created_by,created_at,is_test) VALUES (:t,:c,:a,'Kassa','X-Hesabat fərq',:u,:time,FALSE)",
                                    {"t":c_type,"c":cat,"a":str(abs(diff)),"u":u,"time":now}))
                actions.append(("INSERT INTO shift_handovers (handed_by,expected_cash,actual_cash,created_at) VALUES (:h,:e,:a,:t)",
                                {"h":u,"e":str(expected_cash),"a":str(actual_d),"t":now}))
                try:
                    run_transaction(actions)
                    set_setting("cash_limit", str(actual_d))
                    log_system(u, f"X_REPORT: expected={expected_cash}, actual={actual_d}")
                    st.success("Təhvil verildi!")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")
        x_dialog()

    if cz.button("🔴 Z-Hesabat", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat")
        def z_dialog():
            st.write(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual_z = st.number_input("Sabahkı açılış:", value=float(expected_cash))
            default_wage = Decimal("25.0") if st.session_state.role in ['manager', 'admin'] else Decimal("20.0")
            wage = st.number_input("Maaş (AZN):", value=float(default_wage), min_value=0.0)
            if st.button("✅ Günü Bağla", type="primary"):
                actual_d = Decimal(str(actual_z))
                wage_d = Decimal(str(wage))
                u = st.session_state.user
                now = get_baku_now()
                is_t = st.session_state.get('test_mode', False)
                diff = actual_d - (expected_cash - wage_d)
                actions = []
                if abs(diff) > Decimal("0.01"):
                    c_type = 'in' if diff > 0 else 'out'
                    cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
                    actions.append(("INSERT INTO finance (type,category,amount,source,description,created_by,created_at,is_test) VALUES (:t,:c,:a,'Kassa','Z-Hesabat fərq',:u,:time,FALSE)",
                                    {"t":c_type,"c":cat,"a":str(abs(diff)),"u":u,"time":now}))
                actions.append(("INSERT INTO finance (type,category,amount,source,description,created_by,subject,created_at,is_test) VALUES ('out','Maaş/Avans',:a,'Kassa','Smen sonu maaş',:u,:subj,:time,:tst)",
                                {"a":str(wage_d),"u":u,"subj":u,"time":now,"tst":is_t}))
                actions.append(("INSERT INTO z_reports (total_sales,cash_sales,card_sales,total_cogs,actual_cash,generated_by,created_at) VALUES (:ts,:cs,:crs,:cogs,:ac,:gb,:t)",
                                {"ts":str(s_cash+s_card),"cs":str(s_cash),"crs":str(s_card),"cogs":str(s_cogs),"ac":str(actual_d),"gb":u,"t":now}))
                try:
                    run_transaction(actions)
                    set_setting("cash_limit", str(actual_d))
                    log_system(u, f"Z_REPORT: wage={wage_d}, next={actual_d}")
                    st.success("GÜN BAĞLANDI!")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")
        z_dialog()
