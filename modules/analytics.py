import streamlit as st
import pandas as pd
import datetime, time
import json
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system
from auth import admin_confirm_dialog

def render_analytics_page():
    st.subheader("📊 Analitika va Savdolar")
    
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Boshlanish", get_logical_date())
    d2 = c_d2.date_input("Tugash", get_logical_date())
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    query = """
        SELECT s.*, c.stars as current_stars, c.type as cust_type 
        FROM sales s 
        LEFT JOIN customers c ON s.customer_card_id = c.card_id 
        WHERE s.created_at BETWEEN :s AND :e AND (s.is_test IS NULL OR s.is_test = FALSE)
    """
    params = {"s":ts_start, "e":ts_end}
    
    if st.session_state.role == 'staff':
        query += " AND s.cashier = :u"
        params["u"] = st.session_state.user
    query += " ORDER BY s.created_at DESC"
    
    sales = run_query(query, params)
    
    if not sales.empty:
        total_revenue = sales['total'].sum()
        total_cogs = sales['cogs'].sum() if 'cogs' in sales.columns else 0.0
        gross_profit = total_revenue - total_cogs
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Umumiy Savdo", f"{total_revenue:.2f} ₼")
        c2.metric("Umumiy Chegirma", f"{sales['discount_amount'].sum():.2f} ₼")
        c3.metric("Tannarx (COGS)", f"{total_cogs:.2f} ₼")
        c4.metric("Brutto Foyda", f"{gross_profit:.2f} ₼")
        
        st.divider()
        st.dataframe(sales[['id', 'created_at', 'cashier', 'total', 'cogs', 'payment_method']], hide_index=True, use_container_width=True)
    else:
        st.info("Ma'lumot topilmadi.")

def render_z_report_page():
    st.subheader("📊 Z-Hesobot (Kunlik Yakun)")
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)
    
    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    params = {"d":sh_start_z, "e":sh_end_z}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Nəğd' {q_cond}", params).iloc[0]['s'] or 0.0
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Kart' {q_cond}", params).iloc[0]['s'] or 0.0
    s_cogs = run_query(f"SELECT SUM(cogs) as s FROM sales WHERE 1=1 {q_cond}", params).iloc[0]['s'] or 0.0
    
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond}", params).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' {q_cond}", params).iloc[0]['s'] or 0.0
    
    opening_limit = float(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)

    c1, c2, c3 = st.columns(3)
    c1.metric("Kassa Ochilish Balansi", f"{opening_limit:.2f} ₼")
    c2.metric("Naqd Savdo", f"{float(s_cash):.2f} ₼")
    c3.metric("Kart Savdo", f"{float(s_card):.2f} ₼")

    st.markdown("---")
    c4, c5, c6 = st.columns(3)
    c4.metric("Kassaga Kirimlar (Savdosiz)", f"{float(f_in):.2f} ₼")
    c5.metric("Kassadan Chiqimlar (Xarajat)", f"{float(f_out):.2f} ₼")
    c6.metric("KASSADA BO'LISHI KERAK", f"{expected_cash:.2f} ₼")

    if st.session_state.role in ['admin', 'manager']:
        st.markdown(f"**Tannarx (COGS):** {float(s_cogs):.2f} ₼ | **Kunlik Brutto Foyda:** {(float(s_cash)+float(s_card)) - float(s_cogs):.2f} ₼")

    st.divider()

    if st.button("🔴 Kunni Yopish (Z-Report)", type="primary", use_container_width=True):
        @st.dialog("🔴 Kunni Yakunlash")
        def z_dialog_updated():
            st.write(f"Kassada bo'lishi kerak bo'lgan summa: **{expected_cash:.2f} ₼**")
            actual_z = st.number_input("Kassadagi haqiqiy naqd pul (Ertaga o'tadigan):", value=float(expected_cash))
            
            default_wage = 25.0 if st.session_state.role in ['manager', 'admin'] else 20.0
            wage_amt = st.number_input("Olinayotgan Oylik/Maosh (AZN):", value=default_wage, min_value=0.0)
            
            if st.button("✅ Kunni Yopish va Maoshni Chiqarish"):
                u = st.session_state.user
                now = get_baku_now()
                
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, FALSE)", 
                           {"a": wage_amt, "u": u, "subj": u, "time": now})
                
                final_cash = actual_z - wage_amt
                
                run_action("INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)",
                           {"ts":float(s_cash)+float(s_card), "cs":float(s_cash), "crs":float(s_card), "cogs":float(s_cogs), "ac":final_cash, "gb":u, "t":now})
                
                set_setting("cash_limit", str(final_cash))
                st.success(f"KUN YOPILDI! Ertangi kassa balansi: {final_cash:.2f} ₼")
                time.sleep(1.5)
                st.rerun()
        z_dialog_updated()
