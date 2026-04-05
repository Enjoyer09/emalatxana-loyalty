# modules/analytics.py — EXACT PATCHED FINAL v4.3
import streamlit as st
import pandas as pd
import datetime
import time
import json
import logging
from decimal import Decimal

from database import run_query, run_action, run_transaction, get_setting, set_setting
from modules.finance import get_shift_finance_snapshot, process_shift_handover, process_z_report
from utils import (
    get_logical_date,
    get_shift_range,
    get_baku_now,
    log_system,
    safe_decimal,
    send_z_report_email
)

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def get_sale_refund_summary(sale_id):
    refunds = run_query(
        "SELECT COALESCE(SUM(refund_amount), 0) AS refunded_total, COUNT(*) AS refund_count "
        "FROM refunds WHERE original_sale_id=:sid",
        {"sid": sale_id}
    )
    if refunds.empty:
        return Decimal("0"), 0
    row = refunds.iloc[0]
    return safe_decimal(row.get('refunded_total')), int(row.get('refund_count') or 0)


def parse_items_for_display(items_str):
    if not items_str or items_str == "Table Order":
        return items_str
    try:
        items = json.loads(items_str)
        return ", ".join([f"{i['item_name']} x{i['qty']}" for i in items])
    except:
        return items_str


@st.dialog("🔄 Satış Ləğvi / Refund")
def show_refund_dialog(sale_id):
    sale = run_query("SELECT * FROM sales WHERE id=:id", {"id": sale_id})
    if sale.empty:
        st.error("Satış tapılmadı!")
        return

    row = sale.iloc[0]
    sale_total = Decimal(str(row['total']))
    refunded_so_far, refund_count = get_sale_refund_summary(sale_id)
    remaining_refundable = max(Decimal("0"), sale_total - refunded_so_far)

    if row.get('status') == 'VOIDED' or remaining_refundable <= Decimal("0.00"):
        st.warning("Bu satış artıq ləğv edilib!")
        return

    if refund_count > 0:
        st.info(
            f"Əvvəlki refundlar: **{refunded_so_far:.2f} ₼** | "
            f"Qalan refund limiti: **{remaining_refundable:.2f} ₼**"
        )

    st.markdown(f"**Satış #{row['id']}** — {row['created_at']}")
    try:
        items = json.loads(row['items'])
        for item in items:
            st.write(f"  • {item['item_name']} ×{item['qty']}")
    except:
        st.write(f"  {row['items'][:80]}")

    st.markdown(f"**Məbləğ:** {float(row['total']):.2f} ₼ | **Ödəniş:** {row['payment_method']}")
    st.markdown("---")

    refund_type = st.radio("Ləğv Növü:", [
        "🔴 TAM LƏĞV (Void) — Bütün məbləğ geri",
        "🟡 QİSMƏN REFUND — Müəyyən məbləğ"
    ], key="refund_type_radio")
    is_full_void = "TAM" in refund_type

    if is_full_void:
        refund_amount = remaining_refundable
        st.info(f"Geri qaytarılacaq: **{refund_amount:.2f} ₼**")
    else:
        refund_amount = Decimal(str(
            st.number_input(
                "Geri qaytarılan məbləğ (₼):",
                min_value=0.01,
                max_value=float(remaining_refundable),
                value=float(remaining_refundable),
                step=0.5
            )
        ))

    return_to_stock = st.checkbox("📦 Məhsulları anbara geri qaytar", value=True)

    reason = st.selectbox("Ləğv Səbəbi:", [
        "Müştəri fikrini dəyişdi",
        "Səhv sifariş vuruldu",
        "Məhsul keyfiyyətsiz idi",
        "Test / Sınaq sifarişi",
        "Digər"
    ])
    reason_detail = st.text_input("Əlavə açıqlama (istəyə bağlı):")
    full_reason = reason + (f" — {reason_detail}" if reason_detail.strip() else "")

    st.markdown("---")
    st.error("⚠️ Bu əməliyyat geri qaytarıla bilməz!")

    if st.button("✅ LƏĞVİ TƏSDİQLƏ", type="primary", use_container_width=True, key="confirm_refund_btn"):
        now = get_baku_now()
        u = st.session_state.user
        is_test = row.get('is_test', False)
        actions = []
        refunded_total_after = refunded_so_far + refund_amount

        new_status = 'VOIDED' if refunded_total_after >= sale_total else 'PARTIAL_REFUND'
        actions.append((
            "UPDATE sales SET status=:s WHERE id=:id",
            {"s": new_status, "id": sale_id}
        ))

        actions.append((
            "INSERT INTO refunds (original_sale_id, refund_amount, reason, refund_type, items_returned_to_stock, created_by, created_at) "
            "VALUES (:sid, :amt, :reason, :rtype, :stock, :user, :time)",
            {
                "sid": sale_id,
                "amt": str(refund_amount),
                "reason": full_reason,
                "rtype": "VOID" if new_status == 'VOIDED' else "PARTIAL_REFUND",
                "stock": return_to_stock,
                "user": u,
                "time": now
            }
        ))

        if not is_test and refund_amount > 0:
            pm = row['payment_method']
            source = "Kassa" if pm in ['Nəğd', 'Cash'] else "Bank Kartı"
            actions.append((
                "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id) "
                "VALUES ('out', 'Refund / Ləğv', :a, :src, :desc, :u, :t, FALSE, :sid)",
                {
                    "a": str(refund_amount),
                    "src": source,
                    "desc": f"Satış #{sale_id} ləğvi: {full_reason}",
                    "u": u,
                    "t": now,
                    "sid": sale_id
                }
            ))

        if return_to_stock and not is_test and is_full_void:
            try:
                parsed = json.loads(row['items'])
                for item in parsed:
                    recs = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m", {"m": item.get('item_name')})
                    for _, rc in recs.iterrows():
                        qty_return = Decimal(str(rc['quantity_required'])) * Decimal(str(item.get('qty', 1)))
                        actions.append((
                            "UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:n",
                            {"q": str(qty_return), "n": rc['ingredient_name']}
                        ))
            except Exception as e:
                logger.warning(f"Stock return error: {e}")

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

        try:
            run_transaction(actions)
            log_system(
                u,
                "REFUND_CREATED",
                {
                    "sale_id": sale_id,
                    "amount": str(refund_amount),
                    "refund_type": "VOID" if new_status == 'VOIDED' else "PARTIAL",
                    "reason": full_reason,
                    "return_to_stock": return_to_stock
                }
            )
            st.success(f"✅ Satış #{sale_id} uğurla ləğv edildi! Məbləğ: {refund_amount:.2f} ₼")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")


def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")

    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Analitika Audit"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI üçün API Key daxil edin.")
            elif genai is None:
                st.warning("google-generativeai quraşdırılmayıb.")
            else:
                if st.button("🔍 Dataları Skan Et", use_container_width=True):
                    with st.spinner("AI analiz edir..."):
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
                                prompt = f"Biznes analitik: Son 7 gün satış: {rev} AZN. COGS: {cogs} AZN. Mənfəət: {rev-cogs} AZN. Qısa professional rəy ver."
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background:#1e2226;padding:15px;border-left:5px solid #28a745;border-radius:8px;'>{response.text}</div>", unsafe_allow_html=True)
                            else:
                                st.info("Data yoxdur.")
                        except Exception as e:
                            st.error(f"Xəta: {e}")

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
        if 'is_test' not in sales.columns: sales['is_test'] = False
        if 'status' not in sales.columns: sales['status'] = 'COMPLETED'
        sales['status'] = sales['status'].fillna('COMPLETED')
        if 'discount_amount' not in sales.columns: sales['discount_amount'] = 0.0
        if 'current_stars' not in sales.columns: sales['current_stars'] = None
        if 'cust_type' not in sales.columns: sales['cust_type'] = None
        if 'customer_card_id' not in sales.columns: sales['customer_card_id'] = None

        real_sales = sales[(sales['is_test'] != True) & (sales['status'] != 'VOIDED')].copy()
        voided_sales = sales[sales['status'].isin(['VOIDED', 'PARTIAL_REFUND'])].copy()

        if 'cogs' not in real_sales.columns:
            real_sales['cogs'] = 0.0

        refunds = run_query(
            """
            SELECT r.original_sale_id, COALESCE(SUM(r.refund_amount), 0) AS refunded_amount
            FROM refunds r
            LEFT JOIN sales s ON r.original_sale_id = s.id
            WHERE r.created_at BETWEEN :s AND :e
              AND (s.is_test IS NULL OR s.is_test = FALSE)
            GROUP BY r.original_sale_id
            """,
            {"s": ts_start, "e": ts_end}
        )
        refund_map = {}
        if not refunds.empty:
            refund_map = {
                int(row['original_sale_id']): safe_decimal(row['refunded_amount'])
                for _, row in refunds.iterrows()
                if row.get('original_sale_id') is not None
            }

        real_sales['refund_amount'] = real_sales['id'].apply(lambda sale_id: refund_map.get(int(sale_id), Decimal("0")))
        real_sales['net_revenue'] = real_sales.apply(
            lambda row: max(Decimal("0"), safe_decimal(row['total']) - safe_decimal(row['refund_amount'])),
            axis=1
        )

        total_rev = safe_decimal(real_sales['net_revenue'].sum())
        total_cogs = safe_decimal(real_sales['cogs'].sum())
        card_mask = real_sales['payment_method'].isin(['Card', 'Kart'])
        card_total = safe_decimal(real_sales.loc[card_mask, 'net_revenue'].sum())
        bank_fee = safe_decimal(run_query(
            """
            SELECT COALESCE(SUM(amount), 0) AS s
            FROM finance
            WHERE category='Bank Komissiyası'
              AND source='Bank Kartı'
              AND created_at BETWEEN :s AND :e
              AND (is_test IS NULL OR is_test=FALSE)
              AND (is_deleted IS NULL OR is_deleted=FALSE)
            """,
            {"s": ts_start, "e": ts_end}
        ).iloc[0]['s'])
        gross_profit = total_rev - total_cogs - bank_fee
        cash_sales = safe_decimal(real_sales[real_sales['payment_method'].isin(['Cash', 'Nəğd'])]['net_revenue'].sum())
        void_count = len(voided_sales)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ümumi Satış", f"{total_rev:.2f} ₼")
        c2.metric("Nağd", f"{cash_sales:.2f} ₼")
        c3.metric("Kart", f"{card_total:.2f} ₼")
        c4.metric("Maya (COGS)", f"{total_cogs:.2f} ₼")
        c5.metric("Brutto Mənfəət", f"{gross_profit:.2f} ₼")

        if void_count > 0:
            refund_total = safe_decimal(voided_sales['total'].sum())
            st.warning(f"⚠️ {void_count} ləğv/refund edilmiş satış (Cəm: {refund_total:.2f} ₼)")

        st.divider()
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Çeklər", "☕ Məhsullar", "🔄 Ləğvlər", "👥 Staff"])

        with tab1:
            sales_disp = sales.copy()
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            sales_disp['Status'] = sales_disp['status'].apply(
                lambda x: '🔴 LƏĞV' if x == 'VOIDED' else '🟡 QİSMƏN' if x == 'PARTIAL_REFUND' else '✅'
            )
            sales_disp['Oxunaqlı_Səbət'] = sales_disp['items'].apply(parse_items_for_display)

            cols_to_disp = [
                'id', 'created_at', 'cashier', 'customer_card_id', 'current_stars', 'cust_type',
                'Oxunaqlı_Səbət', 'original_total', 'discount_amount', 'total'
            ]
            if 'cogs' in sales_disp.columns:
                cols_to_disp.append('cogs')
            cols_to_disp.extend(['payment_method', 'Status', 'Test?'])

            avail = [c for c in cols_to_disp if c in sales_disp.columns]
            display_df = sales_disp[avail].copy()
            display_df.insert(0, "Seç", False)

            edited_sales = st.data_editor(
                display_df,
                hide_index=True,
                use_container_width=True,
                key="sales_ed_v3_fix",
                column_config={
                    "cashier": "İşçi",
                    "customer_card_id": "Müştəri QR",
                    "current_stars": "Ulduz",
                    "cust_type": "Tip",
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
                col_b1, col_b2 = st.columns(2)
                if len(sel_ids) == 1:
                    if col_b1.button("🔄 Ləğv Et / Refund", type="primary", use_container_width=True):
                        show_refund_dialog(int(sel_ids[0]))
                    if col_b2.button("✏️ Düzəliş", use_container_width=True):
                        st.session_state.sale_edit_id = int(sel_ids[0])
                        st.rerun()

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

        with tab3:
            st.markdown("### 🔄 Ləğv və Refund Tarixçəsi")
            try:
                refunds = run_query(
                    "SELECT r.*, s.total as original_total, s.cashier as original_cashier, s.payment_method "
                    "FROM refunds r LEFT JOIN sales s ON r.original_sale_id = s.id "
                    "WHERE r.created_at BETWEEN :s AND :e ORDER BY r.created_at DESC",
                    {"s": ts_start, "e": ts_end}
                )
                if not refunds.empty:
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Ləğv Sayı", len(refunds))
                    r2.metric("Ləğv Məbləği", f"{safe_decimal(refunds['refund_amount'].sum()):.2f} ₼")
                    returned = len(refunds[refunds['items_returned_to_stock'] == True]) if 'items_returned_to_stock' in refunds.columns else 0
                    r3.metric("Stoka Qaytarılan", returned)

                    st.dataframe(
                        refunds[['id', 'original_sale_id', 'refund_amount', 'reason', 'refund_type', 'items_returned_to_stock', 'created_by', 'created_at']],
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "original_sale_id": "Satış #",
                            "refund_amount": st.column_config.NumberColumn("Məbləğ", format="%.2f ₼"),
                            "reason": "Səbəb",
                            "refund_type": "Növ",
                            "items_returned_to_stock": "Stoka Qaytarıldı?",
                            "created_by": "Kim Ləğv Etdi",
                            "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                        }
                    )
                else:
                    st.success("✅ Bu dövrdə heç bir ləğv/refund yoxdur.")
            except Exception as e:
                st.warning(f"Ləğv tarixçəsi yüklənmədi: {e}")

        with tab4:
            st.markdown("### 👥 Staff Performans Hesabatı")
            if st.session_state.role in ['admin', 'manager']:
                try:
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
                                sc2.metric("Toplam", f"{float(staff['toplam_satis'] or 0):.2f} ₼")
                                sc3.metric("Orta Çek", f"{float(staff['orta_cek'] or 0):.2f} ₼")
                                sc4.metric("Endirim", f"{float(staff['toplam_endirim'] or 0):.2f} ₼")
                    else:
                        st.info("Bu dövrdə satış yoxdur.")
                except Exception as e:
                    st.error(f"Staff statistikası yüklənmədi: {e}")
def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    snapshot = get_shift_finance_snapshot()
    log_date_z = snapshot["log_date"]
    sh_start_z = snapshot["shift_start"]
    sh_end_z = snapshot["shift_end"]
    q_cond_sales = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (status IS NULL OR status='COMPLETED')"
    params = {"d": sh_start_z, "e": sh_end_z}
    s_cash = snapshot["cash_sales"]
    s_card = snapshot["card_sales"]
    s_cogs = snapshot["cogs"]
    f_out = snapshot["cash_out"]
    f_in = snapshot["cash_in"]
    opening_limit = snapshot["opening_balance"]
    expected_cash = snapshot["expected_cash"]
    refund_count = snapshot["refund_count"]

    if st.session_state.role == 'staff':
        my_sales = run_query(
            f"SELECT * FROM sales WHERE cashier=:u {q_cond_sales} ORDER BY created_at DESC",
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
        c2.metric("Nağd Satış (Split daxil)", f"{s_cash:.2f} ₼")
        c3.metric("Kart Satış (Split daxil)", f"{s_card:.2f} ₼")

        st.markdown("---")
        c4, c5, c6 = st.columns(3)
        c4.metric("Mədaxil (Satışsız)", f"{f_in:.2f} ₼")
        c5.metric("Məxaric (Xərc)", f"{f_out:.2f} ₼")
        c6.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")

        if st.session_state.role in ['admin', 'manager']:
            gross_profit = s_cash + s_card - s_cogs
            st.markdown(f"**COGS:** {s_cogs:.2f} ₼ | **Mənfəət:** {gross_profit:.2f} ₼ | **Ləğvlər:** {refund_count}")

        with st.expander("💸 GÜNLÜK MAAŞ/AVANS ÖDƏ"):
            with st.form("salary_form_z_fix"):
                users_df = run_query("SELECT username FROM users")
                emp = st.selectbox("İşçi", users_df['username'].tolist() if not users_df.empty else [])
                amt = st.number_input("Məbləğ", min_value=0.0)
                if st.form_submit_button("💰 Ödə"):
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, created_by, description, created_at) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', :u, :d, :t)",
                        {"a": str(Decimal(str(amt))), "u": st.session_state.user, "d": f"{emp} avans", "t": get_baku_now()}
                    )
                    log_system(st.session_state.user, "SALARY_PAID", {"employee": emp, "amount": amt})
                    st.success("Ödənildi!")
                    time.sleep(1)
                    st.rerun()

    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "x_report": 
            pass # Handle in separate logic if needed, or inline below
        elif d_type == "z_report": 
            pass
        # st.stop() can be called here depending on your routing architecture.

    cx, cz = st.columns(2)
    if cx.button("🤝 X-Hesabat", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_dialog():
            st.info(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual = st.number_input("Kassadakı nağd:", value=float(expected_cash))
            if st.button("Təsdiqlə", type="primary"):
                actual_d = Decimal(str(actual))
                try:
                    process_shift_handover(actual, st.session_state.user)
                    st.success("Təhvil verildi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")
        x_dialog()

    if cz.button("🔴 Z-Hesabat", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat")
        def z_dialog():
            st.write(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual_z = st.number_input("Yeşikdəki bütün nağd (AZN):", value=float(expected_cash), step=1.0)
            cash_drop = st.number_input("İnkassasiya (Rəhbərə çatan):", min_value=0.0, max_value=float(actual_z), value=0.0, step=10.0)
            
            default_wage = Decimal("25.0") if st.session_state.role in ['manager', 'admin'] else Decimal("20.0")
            wage = st.number_input("Maaş (AZN):", value=float(default_wage), min_value=0.0)

            next_open = Decimal(str(actual_z)) - Decimal(str(cash_drop)) - Decimal(str(wage))
            st.write(f"**Sabaha qalan açılış balansı (Xırda):** {next_open:.2f} ₼")

            if st.button("✅ Günü Bağla", type="primary"):
                try:
                    result = process_z_report(actual_z, cash_drop, wage, st.session_state.user, close_current_shift=True)
                    set_setting("last_z_report_time", get_baku_now().isoformat())

                    try:
                        report_date = str(log_date_z)
                        summary = {
                            "cash_sales": float(s_cash),
                            "card_sales": float(s_card),
                            "total_sales": float(s_cash + s_card),
                            "total_cogs": float(s_cogs),
                            "gross_profit": float((s_cash + s_card) - s_cogs),
                            "expected_cash": float(expected_cash),
                            "refunds_count": int(refund_count),
                            "generated_by": st.session_state.user
                        }
                        ok, msg = send_z_report_email(report_date, summary)
                        if ok:
                            log_system(st.session_state.user, "Z_REPORT_EMAIL_SENT", {"report_date": report_date, "result": "success"})
                        else:
                            log_system(st.session_state.user, "Z_REPORT_EMAIL_FAILED", {"report_date": report_date, "error": msg})
                            st.warning(f"PDF yaradıldı, amma e-mail göndərilmədi: {msg}")
                    except Exception as mail_e:
                        st.warning(f"E-mail xətası: {mail_e}")
                        log_system(st.session_state.user, "Z_REPORT_EMAIL_EXCEPTION", {"error": str(mail_e)})

                    st.success("GÜN BAĞLANDI!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")
        z_dialog()
