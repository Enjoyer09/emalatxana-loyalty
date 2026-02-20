import streamlit as st
import pandas as pd
import datetime
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now

def render_analytics_page():
    st.subheader("📊 Analitika")
    d1 = st.date_input("Start", get_logical_date())
    d2 = st.date_input("End", get_logical_date())
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
    if not sales.empty:
        total_rev = sales['total'].sum(); cash_rev = sales[sales['payment_method']=='Cash']['total'].sum(); card_rev = sales[sales['payment_method']=='Card']['total'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Cəmi Satış", f"{total_rev:.2f} ₼"); c2.metric("Nağd", f"{cash_rev:.2f} ₼"); c3.metric("Kart", f"{card_rev:.2f} ₼")
        st.bar_chart(sales, x="created_at", y="total"); st.dataframe(sales)
    else: st.info("Satış yoxdur.")

def render_z_report_page():
    st.subheader("Z-Hesabat")
    if st.button("🔴 Günü Bitir (Z-Hesabat)", type="primary"): st.session_state.z_report_active = True; st.rerun()
    if st.session_state.z_report_active:
        @st.dialog("Günlük Hesabat")
        def z_final_d():
            st.write("---")
            if st.button("Hesabla"): st.session_state.z_calculated = True
            if st.session_state.z_calculated:
                log_date_z = get_logical_date(); sh_start_z, _ = get_shift_range(log_date_z)
                sales_val = run_query("SELECT SUM(total) as s FROM sales WHERE created_at>=:d",{"d":sh_start_z}).iloc[0]['s'] or 0.0
                st.metric("Bugünkü Satış", f"{sales_val:.2f} ₼")
                if st.button("Təsdiq və Bitir"):
                    set_setting("last_z_report_time", get_baku_now().isoformat())
                    st.session_state.z_report_active=False; st.session_state.z_calculated=False; st.success("Gün bağlandı!"); st.rerun()
        z_final_d()
