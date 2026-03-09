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
        
        # 💳 ENDİRİM VƏ LOYALLIQ METRİKLƏRİ ƏLAVƏ EDİLDİ
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Cəmi Brutto", f"{real_sales['original_total'].sum():.2f} ₼")
        c2.metric("Cəmi Endirim", f"{real_sales['discount_amount'].sum():.2f} ₼")
        c3.metric("Yekun Satış", f"{real_sales['total'].sum():.2f} ₼")
        c4.metric("Nağd", f"{real_sales[real_sales['payment_method']=='Cash']['total'].sum():.2f} ₼")
        c5.metric("Kart (Net)", f"{real_sales[real_sales['payment_method']=='Card']['net_total'].sum():.2f} ₼")
        
        st.divider()
        tab1, tab2 = st.tabs(["📋 Çeklər", "☕ Məhsullar"])
        
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Net'] = sales_disp.apply(lambda x: x['total'] * 0.98 if x['payment_method'] == 'Card' else x['total'], axis=1)
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            
            # Cədvələ Endirim və Original Məbləğ sütunları əlavə edildi
            display_df = sales_disp[['id', 'created_at', 'cashier', 'items', 'original_total', 'discount_amount', 'total', 'Net', 'payment_method', 'Test?']].copy()
            display_df.insert(0, "Seç", False)
            
            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_ed_v2",
                column_config={
                    "original_total": "Brutto", 
                    "discount_amount": "Endirim", 
                    "total": "Yekun", 
                    "Net": "Net", 
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                }
            )
            # Düzəliş və Silmə düymələri eyni qalır...
def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    log_date_z = get_logical_date(); sh_start_z, sh_end_z = get_shift_range(log_date_z)
    
    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    params = {"d":sh_start_z, "e":sh_end_z}

    # Riyazi hesablamalar...
    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {q_cond}", params).iloc[0]['s'] or 0.0
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond}", params).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' {q_cond}", params).iloc[0]['s'] or 0.0
    
    opening_limit = float(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)

    # Günü Bitir (Z) Dialoqunun Samir üçün tənzimlənməsi
    if st.button("🔴 Günü Bitir (Z)", type="primary", use_container_width=True, key="main_z_btn"):
        @st.dialog("🔴 Z-Hesabat və Maaş")
        def z_dialog_updated():
            st.write(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual_z = st.number_input("Sabahkı açılış balansı (Kassada qalan):", value=100.0)
            
            # Samir maaşını bura yazacaq
            default_wage = 25.0 if st.session_state.role in ['manager', 'admin'] else 20.0
            wage_amt = st.number_input("Götürülən Maaş (AZN):", value=default_wage, min_value=0.0)
            
            if st.button("✅ Günü Bağla və Maaşı Çıxar"):
                u = st.session_state.user
                now = get_baku_now()
                is_t = st.session_state.get('test_mode', False)
                
                # 1. Maaşı xərc kimi qeyd et
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)", 
                           {"a": wage_amt, "u": u, "subj": u, "time": now, "tst": is_t})
                
                # 2. Z-Hesabatı yaz
                run_action("INSERT INTO z_reports (total_sales, cash_sales, card_sales, actual_cash, generated_by) VALUES (:ts, :cs, :crs, :ac, :gb)",
                           {"ts":float(s_cash), "cs":float(s_cash), "crs":0.0, "ac":actual_z, "gb":u})
                
                set_setting("cash_limit", str(actual_z))
                st.success("GÜN BAĞLANDI!"); time.sleep(1); st.rerun()
        z_dialog_updated()            
