import streamlit as st
import secrets
import pandas as pd
import time
from database import run_query, run_action
from utils import get_baku_now, verify_password

@st.cache_data(ttl=600)
def get_cached_users(): return run_query("SELECT * FROM users")

def create_session(username, role):
    token = secrets.token_urlsafe(32)
    run_action("INSERT INTO active_sessions (token, username, role, created_at, last_activity) VALUES (:t, :u, :r, :c, :c)", {"t": token, "u": username, "r": role, "c": get_baku_now()})
    return token

def check_url_token_login():
    qp = st.query_params; token_in_url = qp.get("token")
    if token_in_url and not st.session_state.get('logged_in'):
        res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t": token_in_url})
        if not res.empty:
            r = res.iloc[0]; last_act = pd.to_datetime(r['last_activity']) if r['last_activity'] else pd.to_datetime(r['created_at'])
            if (get_baku_now() - last_act).total_seconds() > 28800:
                 run_action("DELETE FROM active_sessions WHERE token=:t", {"t": token_in_url}); st.error("Sessiya bitib."); return False
            st.session_state.logged_in = True; st.session_state.user = r['username']; st.session_state.role = r['role']; st.session_state.session_token = token_in_url
            run_action("UPDATE active_sessions SET last_activity=:n WHERE token=:t", {"n": get_baku_now(), "t": token_in_url}); st.query_params.clear(); return True
    return False

def validate_session():
    if not st.session_state.get('session_token'): return False
    res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t": st.session_state.session_token})
    if res.empty: return False
    run_action("UPDATE active_sessions SET last_activity=:n WHERE token=:t", {"n": get_baku_now(), "t": st.session_state.session_token}); return True

def logout_user():
    if st.session_state.get('session_token'): run_action("DELETE FROM active_sessions WHERE token=:t", {"t": st.session_state.session_token})
    st.session_state.logged_in = False; st.session_state.session_token = None; st.query_params.clear(); st.rerun()

@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")
    with st.form("admin_conf_form_auth"):
        pwd = st.text_input("Admin Şifrəsi", type="password")
        if st.form_submit_button("Təsdiqlə"):
            adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
            if not adm.empty and verify_password(pwd, adm.iloc[0]['password']): callback(*args); st.success("İcra olundu!"); time.sleep(1); st.rerun()
            else: st.error("Yanlış Şifrə!")
