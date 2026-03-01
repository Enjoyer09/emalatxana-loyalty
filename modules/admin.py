import streamlit as st
import pandas as pd
import bcrypt
import time
from database import run_query, run_action, get_setting, set_setting
from utils import log_system

def render_settings_page():
    st.subheader("⚙️ Ayarlar və İdarəetmə")
    
    tab_settings, tab_users, tab_app = st.tabs(["🍽️ Restoran Ayarları", "👥 İstifadəçilər", "📱 Müştəri Tətbiqi (App)"])
    
    with tab_settings:
        st.markdown("### 🍽️ Servis Haqqı Tənzimləməsi")
        current_fee = float(get_setting("service_fee_percent", "0.0"))
        st.info("💡 Əgər müştəridən servis haqqı alınırsa (məsələn, 7%), bura qeyd edin. Ləğv etmək və ya gizlətmək üçün 0 yazın.")
        new_fee = st.number_input("Servis Haqqı (%)", min_value=0.0, max_value=100.0, step=1.0, value=current_fee)
        if st.button("💾 Ayarları Yadda Saxla", type="primary"):
            set_setting("service_fee_percent", str(new_fee))
            log_system(st.session_state.user, f"AYARLAR DƏYİŞDİRİLDİ | Yeni Servis Haqqı: {new_fee}%")
            st.success(f"✅ Servis haqqı {new_fee}% olaraq təyin edildi!")
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
                else:
                    st.warning("Ad və şifrə mütləqdir!")

    with tab_app:
        st.markdown("### 📱 Müştəri Ekranı (Kampaniyalar)")
        st.info("Buradan əlavə etdiyiniz kampaniyalar birbaşa müştərinin telefonundakı tətbiqdə görünəcək.")
        
        with st.form("new_campaign_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            c_title = c1.text_input("Başlıq (Məs: Səhər Kombosu)")
            c_badge = c2.text_input("Etiket (Məs: Yeni!, -20%, 6 ₼)")
            c_desc = st.text_input("Açıqlama (Məs: İstənilən kofe və kruasan...)")
            c_img = st.text_input("Şəkil URL-i (İnternetdən kopyalanmış link)")
            
            if st.form_submit_button("📢 Kampaniyanı Yayımla", type="primary"):
                if c_title:
                    run_action("INSERT INTO campaigns (title, description, img_url, badge) VALUES (:t, :d, :i, :b)", 
                               {"t":c_title, "d":c_desc, "i":c_img, "b":c_badge})
                    st.success("Kampaniya tətbiqə əlavə edildi!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Başlıq mütləqdir!")
                    
        st.markdown("#### 🗑️ Aktiv Kampaniyalar")
        camp_df = run_query("SELECT * FROM campaigns ORDER BY id DESC")
        if not camp_df.empty:
            for _, row in camp_df.iterrows():
                cc1, cc2 = st.columns([4, 1])
                cc1.markdown(f"**{row['title']}** - {row['description']}")
                if cc2.button("Sil", key=f"del_camp_{row['id']}"):
                    run_action("DELETE FROM campaigns WHERE id=:id", {"id": int(row['id'])})
                    st.rerun()
        else:
            st.write("Aktiv kampaniya yoxdur.")

def render_database_page():
    st.subheader("🗄️ Baza İdarəetməsi")
    st.info("Sistem məlumatlarının ehtiyat nüsxəsi və təmizlənməsi.")
    if st.button("⚠️ Köhnə Loqları Təmizlə (30 gündən əvvəlki)"):
        run_action("DELETE FROM logs WHERE created_at < NOW() - INTERVAL '30 days'")
        log_system(st.session_state.user, "Köhnə loqlar təmizləndi.")
        st.success("Təmizləndi!")

def render_logs_page():
    st.subheader("🕵️‍♂️ Sistem Loqları (Real-Time Sensor)")
    logs = run_query("SELECT * FROM logs ORDER BY created_at DESC LIMIT 200")
    if not logs.empty:
        st.dataframe(logs, use_container_width=True, hide_index=True)
    else:
        st.info("Hələ heç bir hərəkət qeydə alınmayıb.")

def render_notes_page():
    st.subheader("📝 Admin Qeydləri")
    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Başlıq")
        note = st.text_area("Qeyd")
        if st.form_submit_button("Yadda Saxla"):
            if title and note:
                run_action("INSERT INTO admin_notes (title, note) VALUES (:t, :n)", {"t": title, "n": note})
                st.success("Qeyd əlavə edildi!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Xanaları doldurun.")
            
    notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
    if not notes.empty:
        for _, r in notes.iterrows():
            with st.expander(f"📅 {r['created_at'].strftime('%d.%m.%Y %H:%M') if pd.notna(r['created_at']) else ''} - {r['title']}"):
                st.write(r['note'])
