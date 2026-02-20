import streamlit as st
import pandas as pd
import datetime
from database import run_query, run_action, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range
from auth import admin_confirm_dialog

def render_finance_page():
    st.subheader("💰 Maliyyə Mərkəzi")
    with st.expander("🔓 Səhər Kassanı Aç (Opening Balance)"):
        op_bal = st.number_input("Kassada nə qədər pul var? (AZN)", min_value=0.0, step=0.1)
        if st.button("✅ Kassanı Bu Məbləğlə Aç"): 
            set_setting("cash_limit", str(op_bal)); st.success(f"Gün {op_bal} AZN ilə başladı!"); st.rerun()

    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
    log_date = get_logical_date(); shift_start, shift_end = get_shift_range(log_date)
    
    if "Növbə" in view_mode: cond = "AND created_at >= :d AND created_at < :e"; params = {"d":shift_start, "e":shift_end}
    else:
        last_z = get_setting("last_z_report_time"); last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else datetime.datetime.now() - datetime.timedelta(days=365)
        cond = "AND created_at > :d"; params = {"d":last_z_dt}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {cond}", params).iloc[0]['s'] or 0.0
    e_cash = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_cash = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    start_lim = float(get_setting("cash_limit", "0.0" if "Növbə" in view_mode else "100.0"))
    disp_cash = start_lim + float(s_cash) + float(i_cash) - float(e_cash)
    disp_card = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card'").iloc[0]['s'] or 0.0
    
    st.divider(); m1, m2 = st.columns(2)
    m1.metric("🏪 Kassa (Cibdə)", f"{disp_cash:.2f} ₼"); m2.metric("💳 Bank Kartı (Ümumi)", f"{disp_card:.2f} ₼")

    st.markdown("---")
    with st.expander("➕ Yeni Əməliyyat", expanded=True):
        with st.form("new_fin_trx", clear_on_submit=True):
            c1, c2, c3 = st.columns(3); f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"]); f_source = c2.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Investor"]); f_subj = c3.selectbox("Subyekt", SUBJECTS)
            c4, c5 = st.columns(2); f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kommunal", "Kirayə", "Maaş/Avans", "Borc", "Digər"]); f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
            f_desc = st.text_input("Qeyd")
            if st.form_submit_button("Təsdiqlə"):
                db_type = 'out' if "Məxaric" in f_type else 'in'
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject) VALUES (:t, :c, :a, :s, :d, :u, :sb)", {"t":db_type, "c":f_cat, "a":f_amt, "s":f_source, "d":f_desc, "u":st.session_state.user, "sb":f_subj})
                if db_type == 'out': run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, :r, :s, :src)", {"a":f_amt, "r":f"{f_subj} - {f_desc}", "s":st.session_state.user, "src":f_source})
                st.success("Yazıldı!"); st.rerun()
    
    st.write("📜 Son Əməliyyatlar"); fin_df = run_query("SELECT * FROM finance ORDER BY created_at DESC LIMIT 50")
    if st.session_state.role == 'admin':
        fin_df.insert(0, "Seç", False)
        edited_fin = st.data_editor(fin_df, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, key="fin_admin_ed")
        sel_fin = edited_fin[edited_fin["Seç"]]
        if not sel_fin.empty and st.button(f"🗑️ Seçilən {len(sel_fin)} Əməliyyatı Sil"):
             admin_confirm_dialog(f"Silinsin?", lambda ids: [run_action("DELETE FROM finance WHERE id=:id", {"id":int(i)}) for i in ids], sel_fin['id'].tolist())
    else: st.dataframe(fin_df, hide_index=True)
