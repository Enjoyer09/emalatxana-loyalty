import streamlit as st
import pandas as pd
import bcrypt
import time
from database import run_query, run_action, get_setting, set_setting
from utils import log_system

def render_admin_page():
    st.subheader("🛠️ İdarəetmə Paneli (Admin)")
    
    tab_settings, tab_users = st.tabs(["⚙️ Ümumi Ayarlar", "👥 İstifadəçilər"])
    
    with tab_settings:
        st.markdown("### 🍽️ Restoran Ayarları")
        
        current_fee = float(get_setting("service_fee_percent", "0.0"))
        st.info("💡 Əgər müştəridən servis haqqı alınırsa (məsələn, 7%), bura qeyd edin. Ləğv etmək və ya gizlətmək üçün 0 yazın.")
        
        new_fee = st.number_input("Servis Haqqı (%)", min_value=0.0, max_value=100.0, step=1.0, value=current_fee)
        
        if st.button("💾 Ayarları Yadda Saxla", type="primary"):
            set_setting("service_fee_percent", str(new_fee))
            log_system(st.session_state.user, f"AYARLAR DƏYİŞDİRİLDİ | Yeni Servis Haqqı: {new_fee}%")
            st.success(f"✅ Servis haqqı {new_fee}% olaraq təyin edildi!")
            time.sleep(1)
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
                        log_system(st.session_state.user, f"YENİ İSTİFADƏÇİ YARADILDI | Adı: {new_user} | Rol: {new_role}")
                        st.success(f"İstifadəçi {new_user} yaradıldı!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Xəta: Bu ad artıq mövcuddur. ({e})")
                else:
                    st.warning("Ad və şifrə mütləqdir!")
