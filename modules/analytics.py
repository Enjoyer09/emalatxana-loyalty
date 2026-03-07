import streamlit as st
import pandas as pd
import datetime, time
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system
from auth import admin_confirm_dialog

def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")
    
    # 1. TARİX FİLTRİ
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    query = """
        SELECT s.*, c.type as cust_type, c.stars as cust_stars 
        FROM sales s 
        LEFT JOIN customers c ON s.customer_card_id = c.card_id 
        WHERE s.created_at BETWEEN :s AND :e 
        ORDER BY s.created_at DESC
    """
    sales = run_query(query, {"s":ts_start, "e":ts_end})
    
    if not sales.empty:
        if 'is_test' not in sales.columns: sales['is_test'] = False
        real_sales = sales[sales['is_test'] != True].copy()
        
        # --- NET GƏLİR HESABLAMASI ---
        bank_fee_rate = 0.02 # 2% Bank faizi
        real_sales['bank_fee'] = real_sales.apply(lambda x: x['total'] * bank_fee_rate if x['payment_method'] == 'Card' else 0, axis=1)
        real_sales['net_total'] = real_sales['total'] - real_sales['bank_fee']
        
        # Metriklər
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cəmi Brutto", f"{real_sales['total'].sum():.2f} ₼")
        c2.metric("Cəmi Net", f"{real_sales['net_total'].sum():.2f} ₼", delta=f"-{real_sales['bank_fee'].sum():.2f} ₼ Bank")
        c3.metric("Nağd", f"{real_sales[real_sales['payment_method']=='Cash']['total'].sum():.2f} ₼")
        c4.metric("Kart (Net)", f"{real_sales[real_sales['payment_method']=='Card']['net_total'].sum():.2f} ₼")
        
        st.divider()
        tab1, tab2 = st.tabs(["📋 Çeklərin İdarəedilməsi", "☕ Məhsul Analizi"])
        
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Net'] = sales_disp.apply(lambda x: x['total'] * 0.98 if x['payment_method'] == 'Card' else x['total'], axis=1)
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            
            display_df = sales_disp[['id', 'created_at', 'cashier', 'items', 'total', 'Net', 'payment_method', 'Test?']].copy()
            display_df.insert(0, "Seç", False)
            
            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_admin_ed",
                column_config={"total": "Brutto", "Net": "Net (Karta)", "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")}
            )
            
            sel_s_ids = edited_sales[edited_sales["Seç"]]['id'].tolist()
            if st.session_state.role in ['admin', 'manager'] and len(sel_s_ids) > 0:
                col_b1, col_b2 = st.columns(2)
                if len(sel_s_ids) == 1 and col_b1.button("✏️ Düzəliş"):
                    st.session_state.sale_edit_id = int(sel_s_ids[0]); st.rerun()
                if col_b2.button(f"🗑️ {len(sel_s_ids)} Satışı Sil"):
                    st.session_state.sales_to_delete = sel_s_ids; st.rerun()

            # --- DÜZƏLİŞ DİALOQU ---
            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    s_row = s_res.iloc[0]
                    @st.dialog("✏️ Çek Düzəlişi")
                    def edit_sale_dialog(r):
                        with st.form("edit_form"):
                            e_cashier = st.text_input("Kassir", r['cashier'])
                            e_total = st.number_input("Məbləğ", value=float(r['total']))
                            e_pm = st.selectbox("Ödəniş", ["Cash", "Card", "Staff"], index=["Cash", "Card", "Staff"].index(r['payment_method']))
                            if st.form_submit_button("💾 Yadda Saxla"):
                                run_action("UPDATE sales SET cashier=:c, total=:t, payment_method=:p WHERE id=:id", {"c":e_cashier, "t":e_total, "p":e_pm, "id":r['id']})
                                st.session_state.sale_edit_id = None; st.success("Dəyişdi!"); time.sleep(1); st.rerun()
                    edit_sale_dialog(s_row)

            # --- SİLMƏ DİALOQU ---
            if st.session_state.get('sales_to_delete'):
                @st.dialog("⚠️ Satışı Sil")
                def del_sale_dialog():
                    reason = st.selectbox("Səbəb:", ["Test (Xammal qaytarılsın)", "Zay (Qaytarılmasın)"])
                    if st.button("Təsdiqlə və Sil", type="primary"):
                        for sid in st.session_state.sales_to_delete:
                            if "Test" in reason:
                                s_info = run_query("SELECT items FROM sales WHERE id=:id", {"id": sid})
                                if not s_info.empty:
                                    items_str = s_info.iloc[0]['items']
                                    for p in items_str.split(", "):
                                        if " x" in p:
                                            try:
                                                name, qty_part = p.rsplit(" x", 1); qty = int(qty_part.split()[0])
                                                run_action("UPDATE ingredients SET stock_qty = stock_qty + (SELECT quantity_required * :q FROM recipes WHERE menu_item_name=:m) WHERE name IN (SELECT ingredient_name FROM recipes WHERE menu_item_name=:m)", {"q":qty, "m":name})
                                            except: pass
                            run_action("DELETE FROM sales WHERE id=:id", {"id":sid})
                        st.session_state.sales_to_delete = None; st.success("Silindi!"); time.sleep(1); st.rerun()
                del_sale_dialog()

        with tab2:
            item_counts = {}
            for items_str in real_sales['items']:
                if isinstance(items_str, str) and items_str != "Table Order":
                    for p in items_str.split(", "):
                        if " x" in p:
                            try:
                                n, q = p.rsplit(" x", 1); item_counts[n] = item_counts.get(n, 0) + int(q.split()[0])
                            except: pass
            if item_counts:
                st.bar_chart(pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).set_index('Məhsul'))
    else: st.info("Məlumat tapılmadı.")
        def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    log_date_z = get_logical_date(); sh_start_z, sh_end_z = get_shift_range(log_date_z)
    
    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    params = {"d":sh_start_z, "e":sh_end_z}

    # Satışlar
    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {q_cond}", params).iloc[0]['s'] or 0.0
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Card' {q_cond}", params).iloc[0]['s'] or 0.0
    
    # Maliyyə hərəkətləri
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond}", params).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' {q_cond}", params).iloc[0]['s'] or 0.0
    
    opening_limit = float(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)

    if st.session_state.role != 'staff':
        c1, c2 = st.columns(2)
        c1.metric("Cəmi Satış", f"{(float(s_cash)+float(s_card)):.2f} ₼")
        c1.write(f"💵 Nağd: {float(s_cash):.2f} ₼")
        c1.write(f"💳 Kart (Net 98%): {float(s_card)*0.98:.2f} ₼")
        
        c2.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")
        c2.write(f"Səhər Balansı: {opening_limit:.2f} ₼")
        
        with st.expander("💸 GÜNLÜK MAAŞ/AVANS"):
            with st.form("quick_sal"):
                emp = st.selectbox("Staff", run_query("SELECT username FROM users")['username'].tolist())
                amt = st.number_input("Məbləğ", min_value=0.0)
                if st.form_submit_button("💰 Ödə"):
                    run_action("INSERT INTO finance (type, category, amount, source, created_by, description) VALUES ('out', 'Maaş', :a, 'Kassa', :u, :d)", {"a":amt, "u":st.session_state.user, "d":f"{emp} üçün avans"})
                    st.success("Ödənildi!"); time.sleep(1); st.rerun()

    # X/Z Hesabat Düymələri
    cx, cz = st.columns(2)
    if cx.button("🤝 Növbəni Təhvil Ver (X)", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_rep():
            actual = st.number_input("Kassadakı nağd pul:", value=float(expected_cash))
            if st.button("Təsdiqlə"):
                run_action("INSERT INTO shift_handovers (shift_start, shift_end, handed_by, expected_cash, actual_cash, difference) VALUES (:ss, :se, :hb, :ec, :ac, :df)",
                           {"ss":sh_start_z, "se":get_baku_now(), "hb":st.session_state.user, "ec":expected_cash, "ac":actual, "df":actual-expected_cash})
                st.success("Təhvil verildi!"); time.sleep(1); st.rerun()
        x_rep()

    if cz.button("🔴 Günü Bağla (Z)", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat")
        def z_rep():
            st.warning("Günü bağlayırsınız!")
            actual_z = st.number_input("Sabahkı açılış üçün qalan nağd:", value=float(expected_cash))
            if st.button("✅ Günü Bitir"):
                run_action("INSERT INTO z_reports (shift_start, shift_end, total_sales, cash_sales, card_sales, expected_cash, actual_cash, difference, generated_by) VALUES (:ss, :se, :ts, :cs, :crs, :ec, :ac, :df, :gb)",
                           {"ss":sh_start_z, "se":get_baku_now(), "ts":float(s_cash)+float(s_card), "cs":float(s_cash), "crs":float(s_card), "ec":expected_cash, "ac":actual_z, "df":actual_z-expected_cash, "gb":st.session_state.user})
                set_setting("cash_limit", str(actual_z)); set_setting("last_z_report_time", get_baku_now().isoformat())
                st.success("BAĞLANDI!"); time.sleep(1); st.rerun()
        z_rep()
