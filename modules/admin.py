import streamlit as st
import pandas as pd
import time
import base64
from io import BytesIO
from database import run_query, run_action, get_setting, set_setting, conn
from auth import admin_confirm_dialog
from utils import hash_password, image_to_base64, BONUS_RECIPIENTS, DEFAULT_TERMS, ALLOWED_TABLES

def render_settings_page():
    st.subheader("⚙️ Ayarlar")
    with st.expander("🧾 Çek Dizaynı və Logo", expanded=True):
        c1, c2 = st.columns([1, 2])
        with c1:
            lg = st.file_uploader("Logo Yüklə", key="logo_uploader")
            if lg:
                b64 = image_to_base64(lg); curr = get_setting("receipt_logo_base64")
                if b64 != curr: set_setting("receipt_logo_base64", b64); st.success("Yükləndi!"); time.sleep(1); st.rerun()
            curr_logo = get_setting("receipt_logo_base64")
            if curr_logo: 
                try: st.image(BytesIO(base64.b64decode(curr_logo)), width=100, caption="Cari Logo")
                except: pass
        with c2:
            rn = st.text_input("Mağaza", value=get_setting("receipt_store_name", "Emalatkhana"))
            ra = st.text_input("Ünvan", value=get_setting("receipt_address", "Baku"))
            rh = st.text_input("Başlıq", value=get_setting("receipt_header", "Xoş Gəlmisiniz!"))
            rf = st.text_input("Son", value=get_setting("receipt_footer", "Təşəkkürlər!"))
            if st.button("💾 Yadda Saxla"): 
                set_setting("receipt_store_name", rn); set_setting("receipt_address", ra); set_setting("receipt_header", rh); set_setting("receipt_footer", rf); st.success("OK")

    st.divider(); st.markdown("### 🛠️ Menecer Səlahiyyətləri")
    col_mp1, col_mp2, col_mp3, col_mp4 = st.columns(4)
    perm_menu = col_mp1.checkbox("✅ Menyu", value=(get_setting("manager_perm_menu", "FALSE") == "TRUE"))
    if col_mp1.button("Yadda Saxla (Menu)", key="save_mgr_menu"): set_setting("manager_perm_menu", "TRUE" if perm_menu else "FALSE"); st.success("OK"); st.rerun()
    perm_tables = col_mp2.checkbox("✅ Masalar", value=(get_setting("manager_show_tables", "TRUE") == "TRUE"))
    if col_mp2.button("Yadda Saxla (Tables)", key="save_mgr_tables"): set_setting("manager_show_tables", "TRUE" if perm_tables else "FALSE"); st.success("OK"); st.rerun()
    perm_crm = col_mp3.checkbox("✅ CRM", value=(get_setting("manager_perm_crm", "TRUE") == "TRUE")) 
    if col_mp3.button("Yadda Saxla (CRM)", key="save_mgr_crm"): set_setting("manager_perm_crm", "TRUE" if perm_crm else "FALSE"); st.success("OK"); st.rerun()
    perm_recipes = col_mp4.checkbox("✅ Reseptlər", value=(get_setting("manager_perm_recipes", "FALSE") == "TRUE"))
    if col_mp4.button("Yadda Saxla (Resept)", key="save_mgr_recipes"): set_setting("manager_perm_recipes", "TRUE" if perm_recipes else "FALSE"); st.success("OK"); st.rerun()
    
    st.divider()
    with st.expander("👤 Rolu Dəyişdir"):
        with st.form("change_role_form"):
            all_users = run_query("SELECT username, role FROM users")
            target_user = st.selectbox("İşçi Seç", all_users['username'].tolist())
            new_role = st.selectbox("Yeni Rol", ["staff", "manager", "admin"])
            if st.form_submit_button("Rolu Dəyiş"): run_action("UPDATE users SET role=:r WHERE username=:u", {"r":new_role, "u":target_user}); st.success("Dəyişdirildi!"); st.rerun()

    with st.expander("💰 Maliyyə Alətləri"):
        b_emp = st.selectbox("İşçi", BONUS_RECIPIENTS); b_amt = st.number_input("Məbləğ (AZN)", 0.0, 100.0, step=0.1)
        if st.button("➕ Bonusu Əl İlə Yaz"): run_action("INSERT INTO bonuses (employee, amount, is_paid) VALUES (:e, :a, FALSE)", {"e":b_emp, "a":b_amt}); st.success("Yazıldı!"); st.rerun()

    with st.expander("🔑 Şifrə Dəyişmə"):
        users = run_query("SELECT username FROM users"); sel_u_pass = st.selectbox("İşçi Seç", users['username'].tolist(), key="pass_change_sel"); new_pass = st.text_input("Yeni Şifrə", type="password")
        if st.button("Şifrəni Yenilə", key="pass_btn"): run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_pass), "u":sel_u_pass}); st.success("Yeniləndi!")
    
    with st.expander("👥 İşçi İdarə"):
        with st.form("nu"):
            u = st.text_input("İstifadəçi"); p = st.text_input("Şifrə"); r = st.selectbox("Rol", ["staff","manager","admin"])
            if st.form_submit_button("Yarat"): run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r) ON CONFLICT (username) DO NOTHING", {"u":u, "p":hash_password(p), "r":r}); st.success("OK"); st.rerun()
        du = st.selectbox("Silinəcək", users['username'].tolist(), key="del_user_sel")
        if st.button("İşçini Sil", key="del_u_btn"): admin_confirm_dialog(f"Sil: {du}?", lambda: run_action("DELETE FROM users WHERE username=:u", {"u":du}))

    with st.expander("🔧 Sistem"):
        st_tbl = st.checkbox("Staff Masaları Görsün?", value=(get_setting("staff_show_tables","TRUE")=="TRUE"))
        if st.button("Yadda Saxla (Tables 2)", key="save_staff_tables"): set_setting("staff_show_tables", "TRUE" if st_tbl else "FALSE"); st.rerun()
        test_mode = st.checkbox("Z-Hesabat [TEST MODE]?", value=(get_setting("z_report_test_mode") == "TRUE"))
        if st.button("Yadda Saxla (Test Mode)", key="save_test_mode"): set_setting("z_report_test_mode", "TRUE" if test_mode else "FALSE"); st.success("Dəyişdirildi!"); st.rerun()
        c_lim = st.number_input("Standart Kassa Limiti", value=float(get_setting("cash_limit", "100.0")))
        if st.button("Limiti Yenilə", key="save_limit"): set_setting("cash_limit", str(c_lim)); st.success("Yeniləndi!")
        rules = st.text_area("Qaydalar", value=get_setting("customer_rules", DEFAULT_TERMS))
        if st.button("Qaydaları Yenilə", key="save_rules"): set_setting("customer_rules", rules); st.success("Yeniləndi")

def render_database_page():
    st.subheader("💾 Baza")
    if st.button("FULL BACKUP", key="full_backup_btn"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as w:
            for t in ALLOWED_TABLES:
                 try: run_query(f"SELECT * FROM {t}").to_excel(w, sheet_name=t, index=False)
                 except: pass
        st.download_button("Download Backup", out.getvalue(), "backup.xlsx")
    rf = st.file_uploader("Restore (.xlsx)")
    if rf and st.button("Bərpa Et", key="restore_btn"):
        try:
            xls = pd.ExcelFile(rf)
            for t in xls.sheet_names: 
                if t in ALLOWED_TABLES:
                    run_action(f"DELETE FROM {t}")
                    pd.read_excel(xls, t).to_sql(t, conn.engine, if_exists='append', index=False)
            st.success("Bərpa Olundu!"); st.rerun()
        except Exception as e: st.error(f"Xəta: {e}")

def render_logs_page():
    st.subheader("📜 Loglar"); st.dataframe(run_query("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 50"))

def render_notes_page():
    st.subheader("📝 Şəxsi Qeydlər")
    with st.form("add_note_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 2]); n_title = c1.text_input("Nə Aldın? (Ad)"); n_amount = c2.number_input("Nə Qədər? (AZN)", min_value=0.0, step=0.1); n_desc = c3.text_input("Qeyd (Optional)")
        if st.form_submit_button("➕ Əlavə Et"):
            if n_title and n_amount > 0: run_action("INSERT INTO admin_notes (title, amount, note) VALUES (:t, :a, :n)", {"t":n_title, "a":n_amount, "n":n_desc}); st.success("Yazıldı!"); st.rerun()
    notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
    if not notes.empty:
        st.markdown(f"### 💰 CƏM: {notes['amount'].sum():.2f} AZN")
        notes['Seç'] = False; edited_notes = st.data_editor(notes, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True), "amount": st.column_config.NumberColumn(format="%.2f AZN")}, use_container_width=True)
        sel_notes = edited_notes[edited_notes["Seç"]]
        if not sel_notes.empty and st.button(f"🗑️ Seçilən {len(sel_notes)} Qeydi Sil", key="del_notes_btn"):
            for i in sel_notes['id'].tolist(): run_action("DELETE FROM admin_notes WHERE id=:id", {"id":int(i)})
            st.success("Silindi!"); st.rerun()
    else: st.write("📭 Hələ ki qeyd yoxdur.")
