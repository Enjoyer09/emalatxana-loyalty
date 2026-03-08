import streamlit as st
import pandas as pd
import datetime, time
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system
from auth import admin_confirm_dialog

def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")
    
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    query = "SELECT s.*, c.type as cust_type FROM sales s LEFT JOIN customers c ON s.customer_card_id = c.card_id WHERE s.created_at BETWEEN :s AND :e"
    params = {"s":ts_start, "e":ts_end}
    
    if st.session_state.role == 'staff':
        query += " AND s.cashier = :u"
        params["u"] = st.session_state.user
        
    query += " ORDER BY s.created_at DESC"
    
    sales = run_query(query, params)
    
    if not sales.empty:
        if 'is_test' not in sales.columns: sales['is_test'] = False
        real_sales = sales[sales['is_test'] != True].copy()
        
        bank_fee_rate = 0.02 
        real_sales['bank_fee'] = real_sales.apply(lambda x: x['total'] * bank_fee_rate if x['payment_method'] == 'Card' else 0, axis=1)
        real_sales['net_total'] = real_sales['total'] - real_sales['bank_fee']
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cəmi Brutto", f"{real_sales['total'].sum():.2f} ₼")
        c2.metric("Cəmi Net", f"{real_sales['net_total'].sum():.2f} ₼", delta=f"-{real_sales['bank_fee'].sum():.2f} ₼ Bank")
        c3.metric("Nağd", f"{real_sales[real_sales['payment_method']=='Cash']['total'].sum():.2f} ₼")
        c4.metric("Kart (Net)", f"{real_sales[real_sales['payment_method']=='Card']['net_total'].sum():.2f} ₼")
        
        st.divider()
        tab1, tab2 = st.tabs(["📋 Çeklər", "☕ Məhsullar"])
        
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Net'] = sales_disp.apply(lambda x: x['total'] * 0.98 if x['payment_method'] == 'Card' else x['total'], axis=1)
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            
            display_df = sales_disp[['id', 'created_at', 'cashier', 'items', 'total', 'Net', 'payment_method', 'Test?']].copy()
            display_df.insert(0, "Seç", False)
            
            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_ed_p1",
                column_config={"total": "Brutto", "Net": "Net", "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")}
            )
            
            sel_s_ids = edited_sales[edited_sales["Seç"]]['id'].tolist()
            if st.session_state.role in ['admin', 'manager'] and len(sel_s_ids) > 0:
                col_b1, col_b2 = st.columns(2)
                if len(sel_s_ids) == 1 and col_b1.button("✏️ Düzəliş"):
                    st.session_state.sale_edit_id = int(sel_s_ids[0]); st.rerun()
                if col_b2.button(f"🗑️ {len(sel_s_ids)} Satışı Sil"):
                    st.session_state.sales_to_delete = sel_s_ids; st.rerun()

            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    @st.dialog("✏️ Çek Redaktəsi")
                    def edit_dialog(r):
                        with st.form("ed_f"):
                            e_t = st.number_input("Məbləğ", value=float(r['total']))
                            e_p = st.selectbox("Ödəniş", ["Cash", "Card", "Staff"], index=["Cash", "Card", "Staff"].index(r['payment_method']))
                            if st.form_submit_button("Yadda Saxla"):
                                run_action("UPDATE sales SET total=:t, payment_method=:p WHERE id=:id", {"t":e_t, "p":e_p, "id":r['id']})
                                st.session_state.sale_edit_id = None; st.success("Dəyişdi!"); time.sleep(1); st.rerun()
                    edit_dialog(s_res.iloc[0])

            if st.session_state.get('sales_to_delete'):
                @st.dialog("⚠️ Satışı Sil")
                def del_dialog():
                    if st.button("Təsdiqlə və Sil", type="primary"):
                        for sid in st.session_state.sales_to_delete:
                            run_action("DELETE FROM sales WHERE id=:id", {"id":sid})
                        st.session_state.sales_to_delete = None; st.success("Silindi!"); time.sleep(1); st.rerun()
                del_dialog()

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

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {q_cond}", params).iloc[0]['s'] or 0.0
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Card' {q_cond}", params).iloc[0]['s'] or 0.0
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond}", params).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' {q_cond}", params).iloc[0]['s'] or 0.0
    
    opening_limit = float(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)

    if st.session_state.role == 'staff':
        my_sales = run_query(f"SELECT * FROM sales WHERE cashier=:u {q_cond} ORDER BY created_at DESC", {"u": st.session_state.user, "d": sh_start_z, "e": sh_end_z})
        if not my_sales.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Mənim Növbə Satışım", f"{my_sales['total'].sum():.2f} ₼")
            m2.metric("Nağd", f"{my_sales[my_sales['payment_method']=='Cash']['total'].sum():.2f} ₼")
            m3.metric("Kart", f"{my_sales[my_sales['payment_method']=='Card']['total'].sum():.2f} ₼")
            st.dataframe(my_sales[['id', 'created_at', 'items', 'total', 'payment_method']], hide_index=True, use_container_width=True)
        else: st.warning("Bu növbədə hələ satışınız yoxdur.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Bugünkü Satış", f"{(float(s_cash)+float(s_card)):.2f} ₼")
        c1.write(f"💳 Kart Net (98%): {float(s_card)*0.98:.2f} ₼")
        c2.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")
        
        with st.expander("💸 GÜNLÜK MAAŞ/AVANS ÖDƏ"):
            with st.form("salary_form_fix"):
                emp = st.selectbox("İşçi", run_query("SELECT username FROM users")['username'].tolist())
                amt = st.number_input("Məbləğ", min_value=0.0)
                if st.form_submit_button("💰 Ödə"):
                    run_action("INSERT INTO finance (type, category, amount, source, created_by, description) VALUES ('out', 'Maaş', :a, 'Kassa', :u, :d)", {"a":amt, "u":st.session_state.user, "d":f"{emp} avans"})
                    st.success("Ödənildi!"); time.sleep(1); st.rerun()

    cx, cz = st.columns(2)
    if cx.button("🤝 Növbəni Təhvil Ver (X)", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_dialog_fix():
            actual = st.number_input("Kassadakı nağd:", value=float(expected_cash))
            if st.button("Təsdiqlə"):
                run_action("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash) VALUES (:hb, :ec, :ac)", {"hb":st.session_state.user, "ec":expected_cash, "ac":actual})
                st.success("Təhvil verildi!"); time.sleep(1); st.rerun()
        x_dialog_fix()

    if cz.button("🔴 Günü Bitir (Z)", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat")
        def z_dialog_fix():
            actual_z = st.number_input("Sabahkı açılış balansı:", value=float(expected_cash))
            if st.button("✅ Günü Bağla"):
                run_action("INSERT INTO z_reports (total_sales, cash_sales, card_sales, actual_cash, generated_by) VALUES (:ts, :cs, :crs, :ac, :gb)",
                           {"ts":float(s_cash)+float(s_card), "cs":float(s_cash), "crs":float(s_card), "ac":actual_z, "gb":st.session_state.user})
                set_setting("cash_limit", str(actual_z))
                st.success("GÜN BAĞLANDI!"); time.sleep(1); st.rerun()
        z_dialog_fix()        
