import streamlit as st
import pandas as pd
import bcrypt
import time
import json
import datetime
from database import run_query, run_action, get_setting, set_setting
from utils import log_system, get_baku_now

def render_settings_page():
    st.subheader("⚙️ Ayarlar və İdarəetmə")
    
    tab_settings, tab_users, tab_app = st.tabs(["🍽️ Restoran Ayarları", "👥 İstifadəçilər", "📱 Müştəri Tətbiqi (App)"])
    
    with tab_settings:
        st.markdown("### 🍽️ Servis Haqqı Tənzimləməsi")
        current_fee = float(get_setting("service_fee_percent", "0.0"))
        new_fee = st.number_input("Servis Haqqı (%)", min_value=0.0, max_value=100.0, step=1.0, value=current_fee)
        
        st.markdown("### 🕒 Növbə və Vaxt Ayarları (Baku Time)")
        
        # Saat siyahısını yaradırıq (00:00 - 23:30 arası)
        time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        
        c1, c2, c3 = st.columns(3)
        
        # Mövcud ayarları bazadan çəkirik
        current_start = get_setting("shift_start_time", "08:00")
        current_end = get_setting("shift_end_time", "23:59")
        current_offset = get_setting("utc_offset", "4")

        # Dropdown (Selectbox) vasitəsilə saat seçimi
        s_start = c1.selectbox("Növbə Başlanğıcı", time_options, index=time_options.index(current_start) if current_start in time_options else 16)
        s_end = c2.selectbox("Növbə Bitməsi", time_options + ["23:59"], index=(time_options + ["23:59"]).index(current_end) if current_end in (time_options + ["23:59"]) else len(time_options))
        u_offset = c3.selectbox("Bakı Saatı Offset (UTC+)", ["3", "4", "5"], index=1)
        
        if st.button("💾 Ayarları Yadda Saxla", type="primary"):
            set_setting("service_fee_percent", str(new_fee))
            set_setting("shift_start_time", s_start)
            set_setting("shift_end_time", s_end)
            set_setting("utc_offset", u_offset)
            log_system(st.session_state.user, f"AYARLAR DƏYİŞDİRİLDİ | Servis: {new_fee}%, Növbə: {s_start}-{s_end}")
            st.success("✅ Ayarlar uğurla yadda saxlanıldı!")
            time.sleep(1.5)
            st.rerun()
            
    with tab_users:
        st.markdown("### 👥 İstifadəçi İdarəetməsi")
        users_df = run_query("SELECT username, role, last_seen FROM users")
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
        st.divider()
        st.markdown("#### ➕ Yeni İstifadəçi Yarat")
        with st.form("new_user_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            new_user = c1.text_input("İstifadəçi Adı (Login)")
            new_pass = c2.text_input("Şifrə", type="password")
            new_role = c3.selectbox("Rol", ["staff", "manager", "admin"])
            if st.form_submit_button("Yarat", type="primary"):
                if new_user and new_pass:
                    hashed_pass = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    try:
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", 
                                   {"u": new_user.lower(), "p": hashed_pass, "r": new_role})
                        st.success(f"İstifadəçi {new_user} yaradıldı!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error("Bu ad artıq mövcuddur.")

        st.divider()
        st.markdown("#### ✏️ İstifadəçi Redaktəsi və Silmə")
        if not users_df.empty:
            sel_user = st.selectbox("İstifadəçi seçin", users_df['username'].tolist(), key="sel_user_edit")
            col_pwd, col_del = st.columns(2)
            
            new_pwd_edit = col_pwd.text_input("Yeni Şifrə (Dəyişmək üçün)", type="password")
            if col_pwd.button("🔐 Şifrəni Yenilə", use_container_width=True):
                if new_pwd_edit:
                    hashed_new = bcrypt.hashpw(new_pwd_edit.encode(), bcrypt.gensalt()).decode()
                    run_action("UPDATE users SET password=:p WHERE username=:u", {"p": hashed_new, "u": sel_user})
                    log_system(st.session_state.user, f"İSTİFADƏÇİ ŞİFRƏSİ DƏYİŞDİ: {sel_user}")
                    st.success(f"✅ {sel_user} üçün şifrə yeniləndi!")
                else:
                    st.warning("Yeni şifrəni daxil edin!")

            if col_del.button("🗑️ İstifadəçini Sil", type="primary", use_container_width=True):
                if sel_user == "admin" or sel_user == st.session_state.user:
                    st.error("Admini və ya özünüzü silə bilməzsiniz!")
                else:
                    run_action("DELETE FROM users WHERE username=:u", {"u": sel_user})
                    log_system(st.session_state.user, f"İSTİFADƏÇİ SİLİNDİ: {sel_user}")
                    st.success(f"❌ {sel_user} sistemdən silindi!")
                    time.sleep(1)
                    st.rerun()

    with tab_app:
        st.markdown("### 📱 Müştəri Ekranı (Kampaniyalar)")
        with st.form("new_campaign_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            c_title = c1.text_input("Başlıq (Məs: Səhər Kombosu)")
            c_badge = c2.text_input("Etiket (Məs: Yeni!, -50%)")
            c_desc = st.text_input("Açıqlama")
            c_img = st.text_input("Şəkil URL-i")
            c3, c4 = st.columns(2)
            c_promo = c3.text_input("Promo Kod")
            c_disc = c4.number_input("Endirim Faizi %", 0, 100, 0)
            if st.form_submit_button("📢 Kampaniyanı Yayımla", type="primary"):
                if c_title:
                    run_action("INSERT INTO campaigns (title, description, img_url, badge, promo_code, discount_pct) VALUES (:t, :d, :i, :b, :p, :dp)", 
                               {"t":c_title, "d":c_desc, "i":c_img, "b":c_badge, "p":c_promo, "dp":c_disc})
                    st.success("Kampaniya əlavə edildi!")
                    time.sleep(1.5); st.rerun()
        
        st.markdown("#### 🗑️ Aktiv Kampaniyalar")
        camp_df = run_query("SELECT * FROM campaigns ORDER BY id DESC")
        if not camp_df.empty:
            for _, row in camp_df.iterrows():
                cc1, cc2 = st.columns([4, 1])
                cc1.markdown(f"**{row['title']}** (-{row['discount_pct']}%)")
                if cc2.button("Sil", key=f"del_camp_{row['id']}"):
                    run_action("DELETE FROM campaigns WHERE id=:id", {"id": int(row['id'])})
                    st.rerun()

def render_database_page():
    st.subheader("🗄️ Baza İdarəetməsi")
    
    col_clean, col_db = st.columns(2)
    with col_clean:
        st.info("🕒 30 Günlük Loq Sistemi: Bazanın dolmaması üçün köhnə hərəkət tarixçəsini təmizləyir.")
        if st.button("⚠️ 30 gündən köhnə loqları təmizlə", use_container_width=True):
            run_action("DELETE FROM logs WHERE created_at < NOW() - INTERVAL '30 days'")
            st.success("Köhnə loqlar təmizləndi!")

    st.divider()
    st.markdown("### 💾 JSON Backup & Restore")
    c_back, c_rest = st.columns(2)
    
    with c_back:
        st.markdown("#### 📥 Backup")
        if st.button("Bazanı JSON kimi çıxar", use_container_width=True):
            tables = ["users", "menu", "ingredients", "recipes", "campaigns", "settings", "customers"]
            backup_data = {}
            for t in tables:
                try: backup_data[t] = run_query(f"SELECT * FROM {t}").to_dict(orient="records")
                except: pass
            json_str = json.dumps(backup_data, default=str)
            st.download_button(label="📄 JSON Faylını Endir", data=json_str, file_name=f"emalatxana_backup_{datetime.date.today()}.json", mime="application/json", use_container_width=True)

    with c_rest:
        st.markdown("#### 📤 Restore")
        uploaded_json = st.file_uploader("Restore üçün JSON faylı seçin", type="json")
        if st.button("Bazanı Fayldan Bərpa Et", type="primary", use_container_width=True) and uploaded_json:
            data = json.load(uploaded_json)
            for tbl, recs in data.items():
                if recs:
                    run_action(f"TRUNCATE TABLE {tbl} CASCADE")
                    for r in recs:
                        cols = ", ".join(r.keys())
                        vals = ":" + ", :".join(r.keys())
                        run_action(f"INSERT INTO {tbl} ({cols}) VALUES ({vals})", r)
            st.success("✅ Baza uğurla bərpa edildi!")
            time.sleep(2); st.rerun()

def render_logs_page():
    st.subheader("🕵️‍♂️ Sistem Loqları")
    logs = run_query("SELECT * FROM logs ORDER BY created_at DESC LIMIT 500")
    if not logs.empty:
        st.dataframe(logs, use_container_width=True, hide_index=True)

def render_notes_page():
    st.subheader("📝 Admin Qeydləri")
    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Başlıq"); note = st.text_area("Qeyd")
        if st.form_submit_button("Yadda Saxla"):
            if title and note: 
                run_action("INSERT INTO admin_notes (title, note) VALUES (:t, :n)", {"t": title, "n": note})
                st.rerun()
    notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
    if not notes.empty:
        for _, r in notes.iterrows():
            with st.expander(f"📅 {r['created_at'].strftime('%d.%m.%Y %H:%M')} - {r['title']}"): 
                st.write(r['note'])
