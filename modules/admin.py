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

    with tab_app:
        st.markdown("### 📱 Müştəri Ekranı (Kampaniyalar)")
        st.info("Buradan əlavə etdiyiniz kampaniyalar həm müştərinin tətbiqində görünəcək, həm də ofisiantın (POS) ekranında avtomatik tətbiq olunacaq düymə yaradacaq.")
        
        with st.form("new_campaign_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            c_title = c1.text_input("Başlıq (Məs: Səhər Kombosu)")
            c_badge = c2.text_input("Etiket (Məs: Yeni!, -50%)")
            c_desc = st.text_input("Açıqlama (Məs: İstənilən kofe və kruasan...)")
            c_img = st.text_input("Şəkil URL-i (İnternetdən link)")
            
            c3, c4 = st.columns(2)
            c_promo = c3.text_input("Promo Kod (Məs: ENDIRIM20)")
            c_disc = c4.number_input("Endirim Faizi % (POS-da avtomatik kəsiləcək)", 0, 100, 0)
            
            if st.form_submit_button("📢 Kampaniyanı Yayımla", type="primary"):
                if c_title:
                    run_action("INSERT INTO campaigns (title, description, img_url, badge, promo_code, discount_pct) VALUES (:t, :d, :i, :b, :p, :dp)", 
                               {"t":c_title, "d":c_desc, "i":c_img, "b":c_badge, "p":c_promo, "dp":c_disc})
                    st.success("Kampaniya tətbiqə və POS-a əlavə edildi!")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.warning("Başlıq mütləqdir!")
                    
        st.markdown("#### 🗑️ Aktiv Kampaniyalar")
        camp_df = run_query("SELECT * FROM campaigns ORDER BY id DESC")
        if not camp_df.empty:
            for _, row in camp_df.iterrows():
                cc1, cc2 = st.columns([4, 1])
                disc_info = f"(-{row['discount_pct']}%)" if row['discount_pct'] > 0 else ""
                cc1.markdown(f"**{row['title']}** {disc_info} - {row['promo_code']}")
                if cc2.button("Sil", key=f"del_camp_{row['id']}"):
                    run_action("DELETE FROM campaigns WHERE id=:id", {"id": int(row['id'])})
                    st.rerun()
        else:
            st.write("Aktiv kampaniya yoxdur.")

def render_database_page():
    st.subheader("🗄️ Baza İdarəetməsi")
    if st.button("⚠️ Köhnə Loqları Təmizlə (30 gündən əvvəlki)"):
        run_action("DELETE FROM logs WHERE created_at < NOW() - INTERVAL '30 days'")
        st.success("Təmizləndi!")

def render_logs_page():
    st.subheader("🕵️‍♂️ Sistem Loqları (Real-Time Sensor)")
    logs = run_query("SELECT * FROM logs ORDER BY created_at DESC LIMIT 200")
    if not logs.empty: st.dataframe(logs, use_container_width=True, hide_index=True)

def render_notes_page():
    st.subheader("📝 Admin Qeydləri")
    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Başlıq"); note = st.text_area("Qeyd")
        if st.form_submit_button("Yadda Saxla"):
            if title and note: run_action("INSERT INTO admin_notes (title, note) VALUES (:t, :n)", {"t": title, "n": note}); st.rerun()
    notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
    if not notes.empty:
        for _, r in notes.iterrows():
            with st.expander(f"📅 {r['created_at'].strftime('%d.%m.%Y %H:%M')} - {r['title']}"): st.write(r['note'])
