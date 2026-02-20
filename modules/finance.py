import streamlit as st
import pandas as pd
import datetime
import time
from database import run_query, run_action, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range
from auth import admin_confirm_dialog

def render_finance_page():
    st.subheader("💰 Maliyyə Mərkəzi")
    
    with st.expander("🔓 Səhər Kassanı Aç (Opening Balance)"):
        op_bal = st.number_input("Kassada nə qədər pul var? (AZN)", min_value=0.0, step=0.1)
        if st.button("✅ Kassanı Bu Məbləğlə Aç"): 
            set_setting("cash_limit", str(op_bal)); st.success(f"Gün {op_bal} AZN ilə başladı!"); time.sleep(1); st.rerun()

    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
    log_date = get_logical_date(); shift_start, shift_end = get_shift_range(log_date)
    
    if "Növbə" in view_mode: 
        cond = "AND created_at >= :d AND created_at < :e"; params = {"d":shift_start, "e":shift_end}
    else:
        last_z = get_setting("last_z_report_time")
        last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else datetime.datetime.now() - datetime.timedelta(days=365)
        cond = "AND created_at > :d"; params = {"d":last_z_dt}

    # KASSA HESABI
    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {cond}", params).iloc[0]['s'] or 0.0
    e_cash = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_cash = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    start_lim = float(get_setting("cash_limit", "0.0" if "Növbə" in view_mode else "100.0"))
    disp_cash = start_lim + float(s_cash) + float(i_cash) - float(e_cash)
    
    # KART HESABI (Növbəlik)
    s_card_shift = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Card' {cond}", params).iloc[0]['s'] or 0.0
    e_card_shift = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_card_shift = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    disp_card_view = float(s_card_shift) + float(i_card_shift) - float(e_card_shift)
    
    # KART HESABI (Ümumi - Həmişə görünsün)
    s_card_all = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card'").iloc[0]['s'] or 0.0
    e_card_all = run_query("SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out'").iloc[0]['e'] or 0.0
    i_card_all = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in'").iloc[0]['i'] or 0.0
    disp_card_all = float(s_card_all) + float(i_card_all) - float(e_card_all)
    
    st.divider(); m1, m2 = st.columns(2)
    m1.metric("🏪 Kassa (Cibdə)", f"{disp_cash:.2f} ₼")
    # BURADA HƏM NÖVBƏ, HƏM ÜMUMİ KART BALANSI GÖSTƏRİLİR
    m2.metric(f"💳 Bank Kartı ({'Növbə' if 'Növbə' in view_mode else 'Seçilmiş'})", f"{disp_card_view:.2f} ₼", delta=f"Bazada Ümumi: {disp_card_all:.2f} ₼", delta_color="off")

    st.markdown("---")
    with st.expander("➕ Yeni Əməliyyat", expanded=True):
        with st.form("new_fin_trx", clear_on_submit=True):
            c1, c2, c3 = st.columns(3); f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"]); f_source = c2.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Investor"]); f_subj = c3.selectbox("Subyekt", SUBJECTS)
            c4, c5 = st.columns(2); f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kommunal", "Kirayə", "Maaş/Avans", "Borc", "Digər", "Tips / Çayvoy"]); f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
            f_desc = st.text_input("Qeyd")
            if st.form_submit_button("Təsdiqlə"):
                db_type = 'out' if "Məxaric" in f_type else 'in'
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject) VALUES (:t, :c, :a, :s, :d, :u, :sb)", {"t":db_type, "c":f_cat, "a":f_amt, "s":f_source, "d":f_desc, "u":st.session_state.user, "sb":f_subj})
                if db_type == 'out': run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, :r, :s, :src)", {"a":f_amt, "r":f"{f_subj} - {f_desc}", "s":st.session_state.user, "src":f_source})
                st.success("Yazıldı!"); time.sleep(1); st.rerun()
    
    st.write("📜 Son Əməliyyatlar"); fin_df = run_query("SELECT * FROM finance ORDER BY created_at DESC LIMIT 50")
    
    if st.session_state.role in ['admin', 'manager']:
        fin_df.insert(0, "Seç", False)
        edited_fin = st.data_editor(fin_df, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, key="fin_admin_ed")
        sel_fin = edited_fin[edited_fin["Seç"]]; sel_ids = sel_fin['id'].tolist()
        
        c_btn1, c_btn2 = st.columns(2)
        if len(sel_ids) == 1:
            if c_btn1.button("✏️ Düzəliş", key="edit_fin_btn"): 
                st.session_state.edit_fin_id = int(sel_ids[0])
                st.rerun()
                
        if len(sel_ids) > 0 and st.session_state.role == 'admin':
            if c_btn2.button(f"🗑️ Sil ({len(sel_ids)})", key="del_fin_btn"): 
                for i in sel_ids: run_action("DELETE FROM finance WHERE id=:id", {"id":int(i)})
                st.success("Silindi!"); time.sleep(1); st.rerun()
                
        # --- DÜZƏLİŞ DİALOQU ---
        if st.session_state.get('edit_fin_id'):
            res_fin = run_query("SELECT * FROM finance WHERE id=:id", {"id":st.session_state.edit_fin_id})
            if not res_fin.empty:
                r_fin = res_fin.iloc[0]
                @st.dialog("✏️ Maliyyə Düzəlişi")
                def edit_fin_dialog(r):
                    with st.form("ed_fin_form"):
                        n_t = st.selectbox("Növ", ["out", "in"], index=0 if r['type']=='out' else 1)
                        n_s = st.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Investor"], index=["Kassa", "Bank Kartı", "Seyf", "Investor"].index(r['source']) if r['source'] in ["Kassa", "Bank Kartı", "Seyf", "Investor"] else 0)
                        n_c = st.text_input("Kateqoriya", r['category'])
                        n_a = st.number_input("Məbləğ", value=float(r['amount']), step=0.5)
                        n_d = st.text_input("Qeyd", r['description'] if pd.notna(r['description']) else "")
                        
                        if st.form_submit_button("Yadda Saxla"):
                            run_action("UPDATE finance SET type=:t, source=:s, category=:c, amount=:a, description=:d WHERE id=:id", {"t":n_t,"s":n_s,"c":n_c,"a":n_a,"d":n_d,"id":int(r['id'])})
                            st.session_state.edit_fin_id = None
                            st.success("Düzəldildi!")
                            time.sleep(1)
                            st.rerun()
                edit_fin_dialog(r_fin)
    else:
        st.dataframe(fin_df, hide_index=True)
