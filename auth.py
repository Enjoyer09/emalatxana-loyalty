# auth.py
import streamlit as st
import secrets
import pandas as pd
import time
from database import run_query, run_action
from utils import get_baku_now, verify_password

def get_cached_users(): 
    return run_query("SELECT * FROM users")

def create_session(username, role):
    token = secrets.token_urlsafe(32)
    run_action("INSERT INTO active_sessions (token, username, role, created_at, last_activity) VALUES (:t, :u, :r, :c, :c)", {"t": token, "u": username, "r": role, "c": get_baku_now()})
    return token

def check_url_token_login():
    return False

def validate_session():
    if not st.session_state.get('session_token'): return False
    res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t": st.session_state.session_token})
    if res.empty: return False
    run_action("UPDATE active_sessions SET last_activity=:n WHERE token=:t", {"n": get_baku_now(), "t": st.session_state.session_token})
    return True

def logout_user():
    if st.session_state.get('session_token'): run_action("DELETE FROM active_sessions WHERE token=:t", {"t": st.session_state.session_token})
    st.session_state.logged_in = False
    st.session_state.session_token = None
    st.query_params.clear()
    st.rerun()

# ==============================================================
# 1. KİOSK REJİMİ - ADMİN TƏSDİQİ ÜÇÜN NUMPAD
# ==============================================================
@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")
    
    st.markdown("""
        <style>
        .admin-numpad button { height: 60px !important; font-size: 22px !important; font-weight: bold !important; border-radius: 12px !important; background: #f0f2f6 !important; color: #333 !important; border: 1px solid #ddd !important; transition: transform 0.1s; }
        .admin-numpad button:active { background: #E65100 !important; color: white !important; transform: scale(0.95); }
        .admin-pin-box { font-size: 35px; text-align: center; letter-spacing: 15px; height: 60px; margin-bottom: 15px; background: white; border-radius: 12px; border: 2px solid #E65100; display: flex; align-items: center; justify-content: center; color: #E65100; }
        </style>
    """, unsafe_allow_html=True)
    
    if 'admin_pin_in' not in st.session_state: st.session_state.admin_pin_in = ""
        
    def admin_pad_cb(val):
        if val == 'C': st.session_state.admin_pin_in = ""
        elif val == '⌫': st.session_state.admin_pin_in = st.session_state.admin_pin_in[:-1]
        else: st.session_state.admin_pin_in += str(val)
        
    disp = "• " * len(st.session_state.admin_pin_in) if st.session_state.admin_pin_in else "<span style='color:#ccc; font-size:16px; letter-spacing:1px;'>PİN DAXİL EDİN</span>"
    st.markdown(f"<div class='admin-pin-box'>{disp}</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='admin-numpad'>", unsafe_allow_html=True)
    for row in [['1','2','3'], ['4','5','6'], ['7','8','9'], ['C','0','⌫']]:
        c1, c2, c3 = st.columns(3)
        c1.button(row[0], key=f"ad_{row[0]}", on_click=admin_pad_cb, args=(row[0],), use_container_width=True)
        c2.button(row[1], key=f"ad_{row[1]}", on_click=admin_pad_cb, args=(row[1],), use_container_width=True)
        c3.button(row[2], key=f"ad_{row[2]}", on_click=admin_pad_cb, args=(row[2],), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
        
    st.write("")
    if st.button("Təsdiqlə", type="primary", use_container_width=True):
        adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
        if not adm.empty and verify_password(st.session_state.admin_pin_in, adm.iloc[0]['password']): 
            st.session_state.admin_pin_in = "" 
            callback(*args)
            st.success("İcra olundu!")
            time.sleep(1)
            st.rerun()
        else: 
            st.error("Yanlış Şifrə!")
            st.session_state.admin_pin_in = ""
            time.sleep(1)
            st.rerun()

# ==============================================================
# 2. KİOSK REJİMİ - GİRİŞ (LOGİN) EKRANI ÜÇÜN XÜSUSİ NUMPAD
# ==============================================================
def render_login_page():
    st.markdown("""
        <style>
        .login-numpad button { height: 85px !important; font-size: 32px !important; font-weight: 900 !important; border-radius: 20px !important; background: #FFFFFF !important; color: #1A1A1A !important; border: 1px solid #EBEBEB !important; box-shadow: 0 8px 15px rgba(0,0,0,0.03) !important; transition: transform 0.1s ease, background 0.1s ease !important; }
        .login-numpad button:active { background: #E65100 !important; color: white !important; transform: scale(0.95) !important; }
        .login-pin-display { font-size: 60px; text-align: center; letter-spacing: 25px; height: 100px; margin-bottom: 30px; background: #F9F6F0; border-radius: 20px; border: 2px solid #E65100; display: flex; align-items: center; justify-content: center; color: #E65100; box-shadow: inset 0 5px 10px rgba(0,0,0,0.05); }
        .user-btn button { height: 80px !important; font-size: 20px !important; font-weight: 800 !important; border-radius: 20px !important; border: 2px solid #F0F0F0 !important; background: white !important; color: #333 !important; box-shadow: 0 5px 15px rgba(0,0,0,0.03) !important; }
        .user-btn button:hover { border-color: #E65100 !important; color: #E65100 !important; }
        </style>
    """, unsafe_allow_html=True)

    if 'login_step' not in st.session_state:
        st.session_state.login_step = 'select_user'
        st.session_state.selected_user = None
        st.session_state.pin_code = ""

    if st.session_state.login_step == 'select_user':
        st.markdown("<h1 style='text-align:center; color:#1A1A1A; font-weight:900; margin-bottom:40px; font-size:40px;'>Sistemə Giriş</h1>", unsafe_allow_html=True)
        
        users_df = get_cached_users()
        if not users_df.empty:
            st.markdown("<div class='user-btn'>", unsafe_allow_html=True)
            cols = st.columns(3)
            for i, row in enumerate(users_df.itertuples()):
                with cols[i % 3]:
                    if st.button(f"👤 {row.username}", use_container_width=True, key=f"u_{row.username}"):
                        st.session_state.selected_user = row.username
                        st.session_state.login_step = 'enter_pin'
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Sistemdə heç bir istifadəçi tapılmadı.")
            
    elif st.session_state.login_step == 'enter_pin':
        st.markdown(f"<h2 style='text-align:center; color:#1A1A1A; font-weight:900; margin-bottom:5px;'>👤 {st.session_state.selected_user}</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#888; font-size:18px; margin-bottom:30px;'>PİN Kodunuzu daxil edin</p>", unsafe_allow_html=True)
        
        disp = "• " * len(st.session_state.pin_code) if st.session_state.pin_code else "<span style='color:#ccc; font-size:24px; letter-spacing:2px; font-weight:700;'>ŞİFRƏ</span>"
        
        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            st.markdown(f"<div class='login-pin-display'>{disp}</div>", unsafe_allow_html=True)
            
            def pin_press(val):
                if val == 'C': st.session_state.pin_code = ""
                elif val == '⌫': st.session_state.pin_code = st.session_state.pin_code[:-1]
                else:
                    if len(st.session_state.pin_code) < 15:
                        st.session_state.pin_code += str(val)

            st.markdown("<div class='login-numpad'>", unsafe_allow_html=True)
            for row in [['1','2','3'], ['4','5','6'], ['7','8','9'], ['C','0','⌫']]:
                c1, c2, c3 = st.columns(3)
                c1.button(row[0], key=f"lp_{row[0]}", on_click=pin_press, args=(row[0],), use_container_width=True)
                c2.button(row[1], key=f"lp_{row[1]}", on_click=pin_press, args=(row[1],), use_container_width=True)
                c3.button(row[2], key=f"lp_{row[2]}", on_click=pin_press, args=(row[2],), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.write("")
            c_b1, c_b2 = st.columns(2)
            if c_b1.button("⬅️ Başqa İstifadəçi", use_container_width=True):
                st.session_state.login_step = 'select_user'
                st.session_state.pin_code = ""
                st.rerun()
                
            if c_b2.button("Daxil Ol ✅", type="primary", use_container_width=True):
                users_df = get_cached_users()
                user_row = users_df[users_df['username'] == st.session_state.selected_user]
                if not user_row.empty:
                    hashed_pw = user_row.iloc[0]['password']
                    role = user_row.iloc[0]['role']
                    
                    if verify_password(st.session_state.pin_code, hashed_pw):
                        token = create_session(st.session_state.selected_user, role)
                        st.session_state.session_token = token
                        st.session_state.logged_in = True
                        st.session_state.user = st.session_state.selected_user
                        st.session_state.role = role
                        st.session_state.pin_code = ""
                        st.session_state.login_step = 'select_user'
                        st.rerun()
                    else:
                        st.error("Yanlış Şifrə!")
                        st.session_state.pin_code = ""
                        time.sleep(1)
                        st.rerun()
