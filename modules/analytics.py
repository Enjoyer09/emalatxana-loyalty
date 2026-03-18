# modules/analytics.py — PATCHED v2.0
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


def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")

    # ============================================================
    # AI ANALİZ (Orijinal)
    # ============================================================
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Analitika Audit (Satış Tendensiyaları və Mənfəət)"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin (Ayarlar bölməsindən).")
            elif genai is None:
                st.warning("google-generativeai paketi quraşdırılmayıb.")
            else:
                if st.button("🔍 Dataları Skan Et və Mənfəəti Analiz Et", use_container_width=True):
                    with st.spinner("AI satış datalarını oxuyur..."):
                        try:
                            genai.configure(api_key=api_key)
                            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else 'models/gemini-pro')
                            model = genai.GenerativeModel(chosen_model)
                            recent = run_query(
                                "SELECT SUM(total) as t_rev, SUM(cogs) as t_cogs FROM sales "
                                "WHERE created_at >= current_date - interval '7 days' AND (is_test IS NULL OR is_test=FALSE)"
                            )
                            if not recent.empty and recent.iloc[0]['t_rev']:
                                rev = safe_decimal(recent.iloc[0]['t_rev'])
                                cogs = safe_decimal(recent.iloc[0]['t_cogs'])
                                profit = rev - cogs
                                prompt = f"Sən biznes analitikisən. Son 7 günün satışı: {rev} AZN. Maya dəyəri (COGS): {cogs} AZN. Brutto mənfəət: {profit} AZN. Bu rəqəmləri dəyərləndir və mənfəət marjası haqqında qısa və professional rəy bildir."
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background: #1e2226; padding: 15px; border-left: 5px solid #28a745;'>{response.text}</div>", unsafe_allow_html=True)
                            else:
                                st.info("Kifayət qədər data yoxdur.")
                        except Exception as e:
                            st.error(f"Xəta: {e}")
                            logger.error(f"AI analytics failed: {e}", exc_info=True)

    # ============================================================
    # TARİX FİLTRİ (Orijinal)
    # ============================================================
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

    # ============================================================
    # METRİKLƏR (Orijinal + Decimal)
    # ============================================================
    if not sales.empty:
        if 'is_test' not in sales.columns:
            sales['is_test'] = False
        real_sales = sales[sales['is_test'] != True].copy()
        if 'cogs' not in real_sales.columns:
            real_sales['cogs'] = 0.0

        bank_fee_rate = Decimal("0.02")
        
        # Decimal hesablamalar
        total_rev = safe_decimal(real_sales['total'].sum())
        total_cogs = safe_decimal(real_sales['cogs'].sum())
        
        # Bank fee hesablama
        card_mask = real_sales['payment_method'].isin(['Card', 'Kart'])
        card_total = safe_decimal(real_sales.loc[card_mask, 'total'].sum())
        total_bank_fee = (card_total * bank_fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        gross_profit = total_rev - total_cogs - total_bank_fee

        cash_sales = safe_decimal(real_sales[real_sales['payment_method'].isin(['Cash', 'Nəğd'])]['total'].sum())
        card_sales = card_total

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ümumi Satış", f"{total_rev:.2f} ₼")
        c2.metric("Nağd", f"{cash_sales:.2f} ₼")
        c3.metric("Kart", f"{card_sales:.2f} ₼")
        c4.metric("Maya (COGS)", f"{total_cogs:.2f} ₼")
        c5.metric("Brutto Mənfəət", f"{gross_profit:.2f} ₼")

        st.divider()
        tab1, tab2 = st.tabs(["📋 Çeklər", "☕ Məhsullar"])

        # ============================================================
        # ÇEKLƏR TAB (Orijinal)
        # ============================================================
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Net'] = sales_disp.apply(
                lambda x: float(x['total']) * 0.98 if x['payment_method'] in ['Card', 'Kart'] else float(x['total']),
                axis=1
            )
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            sales_disp['Oxunaqlı_Səbət'] = sales_disp['items'].apply(parse_items_for_display)

            cols_to_disp = ['id', 'created_at', 'cashier', 'customer_card_id', 'current_stars', 'Oxunaqlı_Səbət', 'original_total', 'discount_amount', 'total']
            if 'cogs' in sales_disp.columns:
                cols_to_disp.append('cogs')
            cols_to_disp.extend(['payment_method', 'Test?'])

            display_df = sales_disp[cols_to_disp].copy()
            display_df.insert(0, "Seç", False)

            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_ed_v_final",
                column_config={
                    "cashier": "İşçi (Staff)",
                    "customer_card_id": "Müştəri QR",
                    "current_stars": "Ulduz",
                    "Oxunaqlı_Səbət": "Sifariş Detalı",
                    "original_total": "Brutto",
                    "discount_amount": "Endirim",
                    "total": "Net Ödəniş",
                    "cogs": "Maya",
                    "payment_method": "Ödəniş",
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                }
            )

            sel_s_ids = edited_sales[edited_sales["Seç"]]['id'].tolist()
            if st.session_state.role in ['admin', 'manager'] and len(sel_s_ids) > 0:
                col_b1, col_b2 = st.columns(2)
                if len(sel_s_ids) == 1 and col_b1.button("✏️ Düzəliş"):
                    st.session_state.sale_edit_id = int(sel_s_ids[0])
                    st.rerun()
                if col_b2.button("🗑️ Satışları Sil"):
                    st.session_state.sales_to_delete = sel_s_ids
                    st.rerun()

            # ============================================================
            # SATIŞ DÜZƏLİŞ MODAL (Orijinal + Audit)
            # ============================================================
            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    @st.dialog("✏️ Çek Redaktəsi")
                    def edit_dialog(r):
                        with st.form("ed_f"):
                            old_total = float(r['total'])
                            old_pm = r['payment_method']
                            
                            e_t = st.number_input("Yekun Məbləğ", value=old_total)
                            pm_options = ["Nəğd", "Kart", "Staff", "Cash", "Card"]
                            pm_idx = pm_options.index(old_pm) if old_pm in pm_options else 0
                            e_p = st.selectbox("Ödəniş", pm_options, index=pm_idx)
                            
                            if st.form_submit_button("Yadda Saxla"):
                                run_action(
                                    "UPDATE sales SET total=:t, payment_method=:p WHERE id=:id",
                                    {"t": str(Decimal(str(e_t))), "p": e_p, "id": r['id']}
                                )
                                log_system(
                                    st.session_state.user,
                                    f"SALE_EDIT: id={r['id']}, old_total={old_total}, new_total={e_t}, old_pm={old_pm}, new_pm={e_p}"
                                )
                                st.session_state.sale_edit_id = None
                                st.success("Dəyişdi!")
                                time.sleep(1)
                                st.rerun()

                    edit_dialog(s_res.iloc[0])

            # ============================================================
            # SATIŞ SİLMƏ MODAL (Orijinal + Transaction + Audit)
            # ============================================================
            if st.session_state.get('sales_to_delete'):
                @st.dialog("⚠️ Satışı Sil")
                def del_dialog():
                    reason = st.selectbox("Silinmə Səbəbi:", [
                        "Səhv vurulub / Test idi (Stoka qayıtsın)",
                        "Zay məhsul (Stoka qayıtmasın)"
                    ])
                    
                    if st.button("Təsdiqlə və Sil", type="primary"):
                        for sid in st.session_state.sales_to_delete:
                            s_row = run_query(
                                "SELECT items, is_test, total, payment_method, created_at FROM sales WHERE id=:id",
                                {"id": sid}
                            )
                            if not s_row.empty:
                                row_data = s_row.iloc[0]
                                actions = []

                                # Stoka qaytar
                                if "qayıtsın" in reason and not row_data['is_test']:
                                    try:
                                        parsed = json.loads(row_data['items'])
                                        for item in parsed:
                                            recs = run_query(
                                                "SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m",
                                                {"m": item.get('item_name')}
                                            )
                                            for _, rc in recs.iterrows():
                                                qty_return = Decimal(str(rc['quantity_required'])) * Decimal(str(item.get('qty', 1)))
                                                actions.append((
                                                    "UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:ing",
                                                    {"q": str(qty_return), "ing": rc['ingredient_name']}
                                                ))
                                    except Exception as e:
                                        logger.warning(f"Stock return parse failed: {e}")

                                # Finance qeydlərini sil
                                if not row_data['is_test']:
                                    t_date = row_data['created_at']
                                    actions.append((
                                        """DELETE FROM finance 
                                           WHERE description IN ('POS Satış', 'Masa Satışı', 'Kart Satış Komissiyası', 'Masa Satış Komissiyası', 'Kart Tip', 'Kart Tip (Staffa)') 
                                           AND ABS(EXTRACT(EPOCH FROM (created_at - :td))) < 60""",
                                        {"td": t_date}
                                    ))

                                # Satışı sil
                                actions.append((
                                    "DELETE FROM sales WHERE id=:id",
                                    {"id": sid}
                                ))

                                try:
                                    if actions:
                                        run_transaction(actions)
                                    log_system(st.session_state.user, f"SALE_DELETE: id={sid}, total={row_data['total']}, reason={reason}")
                                except Exception as e:
                                    st.error(f"Silmə xətası: {e}")
                                    logger.error(f"Sale delete failed: {e}", exc_info=True)

                        st.session_state.sales_to_delete = None
                        st.success("Silindi!")
                        time.sleep(1)
                        st.rerun()

                del_dialog()

        # ============================================================
        # MƏHSULLAR TAB (Orijinal)
        # ============================================================
        with tab2:
            item_counts = {}
            for items_str in real_sales['items']:
                if isinstance(items_str, str) and items_str != "Table Order":
                    try:
                        parsed_items = json.loads(items_str)
                        for item in parsed_items:
                            n = item.get('item_name')
                            item_counts[n] = item_counts.get(n, 0) + item.get('qty', 0)
                    except:
                        pass
            if item_counts:
                st.bar_chart(pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).set_index('Məhsul'))
    else:
        st.info("Məlumat tapılmadı.")


# ============================================================
# Z-HESABAT SƏHİFƏSİ
# ============================================================
def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)

    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    # Finance üçün is_deleted filter
    q_cond_finance = q_cond + " AND (is_deleted IS NULL OR is_deleted = FALSE)"
    params = {"d": sh_start_z, "e": sh_end_z}

    # Decimal hesablamalar
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

    # ============================================================
    # STAFF VİEW (Orijinal)
    # ============================================================
    if st.session_state.role == 'staff':
        my_sales = run_query(
            f"SELECT * FROM sales WHERE cashier=:u {q_cond} ORDER BY created_at DESC",
            {"u": st.session_state.user, "d": sh_start_z, "e": sh_end_z}
        )
        if not my_sales.empty:
            my_sales['items'] = my_sales['items'].apply(parse_items_for_display)
            my_total = safe_decimal(my_sales['total'].sum())
            my_cash = safe_decimal(my_sales[my_sales['payment_method'].isin(['Nəğd', 'Cash'])]['total'].sum())
            my_card = safe_decimal(my_sales[my_sales['payment_method'].isin(['Kart', 'Card'])]['total'].sum())
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Mənim Növbə Satışım", f"{my_total:.2f} ₼")
            m2.metric("Nağd", f"{my_cash:.2f} ₼")
            m3.metric("Kart", f"{my_card:.2f} ₼")
            
            disp_cols = ['id', 'created_at', 'items', 'total', 'payment_method']
            if 'cogs' in my_sales.columns:
                disp_cols.append('cogs')
            st.dataframe(my_sales[disp_cols], hide_index=True, use_container_width=True)
        else:
            st.warning("Bu növbədə hələ satışınız yoxdur.")

    # ============================================================
    # MANAGER/ADMIN VİEW (Orijinal)
    # ============================================================
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Kassa Açılış Balansı", f"{opening_limit:.2f} ₼")
        c2.metric("Nağd Satış", f"{s_cash:.2f} ₼")
        c3.metric("Kart Satış", f"{s_card:.2f} ₼")

        st.markdown("---")
        c4, c5, c6 = st.columns(3)
        c4.metric("Kassaya Mədaxil (Satışsız)", f"{f_in:.2f} ₼")
        c5.metric("Kassadan Məxaric (Xərc)", f"{f_out:.2f} ₼")
        c6.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")

        if st.session_state.role in ['admin', 'manager']:
            gross_profit = s_cash + s_card - s_cogs
            st.markdown(f"**Günlük Maya Dəyəri (COGS):** {s_cogs:.2f} ₼ | **Günlük Brutto Mənfəət:** {gross_profit:.2f} ₼")

        # ============================================================
        # MAAŞ ÖDƏMƏ (Orijinal)
        # ============================================================
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
                    log_system(st.session_state.user, f"SALARY_PAID: {emp}, amount={amt}")
                    st.success("Ödənildi!")
                    time.sleep(1)
                    st.rerun()

    # ============================================================
    # X-HESABAT (Orijinal + Transaction)
    # ============================================================
    cx, cz = st.columns(2)
    if cx.button("🤝 Növbəni Təhvil Ver (X)", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_dialog_fix():
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
                    actions.append((
                        "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                        "VALUES (:t, :c, :a, 'Kassa', 'X-Hesabat zamanı yaranan fərq', :u, :time, FALSE)",
                        {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}
                    ))

                actions.append((
                    "INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:hb, :ec, :ac, :t)",
                    {"hb": u, "ec": str(expected_cash), "ac": str(actual_d), "t": now}
                ))

                try:
                    run_transaction(actions)
                    set_setting("cash_limit", str(actual_d))
                    log_system(u, f"X_REPORT: expected={expected_cash}, actual={actual_d}")
                    st.success("Təhvil verildi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

        x_dialog_fix()

    # ============================================================
    # Z-HESABAT (Orijinal + Transaction)
    # ============================================================
    if cz.button("🔴 Günü Bitir (Z)", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat və Maaş")
        def z_dialog_updated():
            st.write(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual_z = st.number_input("Sabahkı açılış balansı (Kassada qalan):", value=float(expected_cash))

            default_wage = Decimal("25.0") if st.session_state.role in ['manager', 'admin'] else Decimal("20.0")
            wage_amt = st.number_input("Götürülən Maaş (AZN):", value=float(default_wage), min_value=0.0)

            if st.button("✅ Günü Bağla və Maaşı Çıxar", type="primary"):
                actual_z_d = Decimal(str(actual_z))
                wage_d = Decimal(str(wage_amt))
                u = st.session_state.user
                now = get_baku_now()
                is_t = st.session_state.get('test_mode', False)

                diff = actual_z_d - (expected_cash - wage_d)
                actions = []

                if abs(diff) > Decimal("0.01"):
                    c_type = 'in' if diff > 0 else 'out'
                    cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
                    actions.append((
                        "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                        "VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat zamanı yaranan fərq', :u, :time, FALSE)",
                        {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}
                    ))

                actions.append((
                    "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) "
                    "VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)",
                    {"a": str(wage_d), "u": u, "subj": u, "time": now, "tst": is_t}
                ))

                # Z-Report record
                actions.append((
                    "INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) "
                    "VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)",
                    {
                        "ts": str(s_cash + s_card),
                        "cs": str(s_cash),
                        "crs": str(s_card),
                        "cogs": str(s_cogs),
                        "ac": str(actual_z_d),
                        "gb": u,
                        "t": now
                    }
                ))

                try:
                    run_transaction(actions)
                    set_setting("cash_limit", str(actual_z_d))
                    log_system(u, f"Z_REPORT: cash={s_cash}, card={s_card}, wage={wage_d}, next_open={actual_z_d}")
                    st.success("GÜN BAĞLANDI!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")
                    logger.error(f"Z-Report failed: {e}", exc_info=True)

        z_dialog_updated()
