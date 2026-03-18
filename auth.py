# auth.py — PATCHED v2.0
import streamlit as st
import secrets
import datetime
import logging
import time
from database import run_query, run_action, run_transaction
from utils import get_baku_now, verify_password, log_system

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 5
SESSION_LIFETIME_MINUTES = 480  # 8 saat
MAX_SESSIONS_PER_USER = 3

# ============================================================
# USER QUERIES
# ============================================================
def get_cached_users():
    """Users list (UI display only — password hash daxil deyil)"""
    return run_query("SELECT username, role FROM users")

def get_user_for_auth(username):
    """Auth üçün tam user data"""
    return run_query(
        "SELECT username, password, role, failed_attempts, locked_until FROM users WHERE username=:u",
        {"u": username}
    )

# ============================================================
# SESSION MANAGEMENT
# ============================================================
def create_session(username, role):
    now = get_baku_now()
    
    # Köhnə sessiyaları təmizlə (per-user limit)
    active = run_query(
        "SELECT token FROM active_sessions WHERE username=:u ORDER BY last_activity DESC",
        {"u": username}
    )
    if len(active) >= MAX_SESSIONS_PER_USER:
        old_tokens = active.iloc[MAX_SESSIONS_PER_USER - 1:]['token'].tolist()
        for t in old_tokens:
            run_action("DELETE FROM active_sessions WHERE token=:t", {"t": t})
    
    token = secrets.token_urlsafe(32)
    run_action(
        "INSERT INTO active_sessions (token, username, role, created_at, last_activity) VALUES (:t, :u, :r, :c, :c)",
        {"t": token, "u": username, "r": role, "c": now}
    )
    return token

def validate_session():
    tok = st.session_state.get('session_token')
    if not tok:
        return False

    res = run_query(
        "SELECT username, role, created_at, last_activity FROM active_sessions WHERE token=:t",
        {"t": tok}
    )
    if res.empty:
        return False

    row = res.iloc[0]
    now = get_baku_now()

    # Session expiry check
    last_activity = row['last_activity']
    if last_activity:
        if hasattr(last_activity, 'tzinfo') and last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=now.tzinfo)
        if (now - last_activity).total_seconds() > SESSION_LIFETIME_MINUTES * 60:
            run_action("DELETE FROM active_sessions WHERE token=:t", {"t": tok})
            log_system(row['username'], "SESSION_EXPIRED")
            return False

    # Update last activity
    run_action(
        "UPDATE active_sessions SET last_activity=:n WHERE token=:t",
        {"n": now, "t": tok}
    )
    return True

def check_url_token_login():
    """URL-based login disabled by policy"""
    return False

def logout_user():
    tok = st.session_state.get('session_token')
    if tok:
        run_action("DELETE FROM active_sessions WHERE token=:t", {"t": tok})
    st.session_state.logged_in = False
    st.session_state.session_token = None
    st.query_params.clear()
    st.rerun()

# ============================================================
# SECURE LOGIN FUNCTION
# ============================================================
def attempt_login(username, pin):
    """
    Returns: (success: bool, token: str|None, error_msg: str|None)
    """
    now = get_baku_now()

    user_df = get_user_for_auth(username)
    if user_df.empty:
        log_system(username, "FAILED_LOGIN_UNKNOWN_USER")
        return False, None, "Yanlış istifadəçi adı və ya şifrə"

    row = user_df.iloc[0]

    # Lockout check
    locked_until = row.get('locked_until')
    if locked_until and str(locked_until).strip():
        try:
            if isinstance(locked_until, str):
                locked_until = datetime.datetime.fromisoformat(locked_until)
            if hasattr(locked_until, 'tzinfo') and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=now.tzinfo)
            if now < locked_until:
                remaining = int((locked_until - now).total_seconds())
                log_system(username, f"LOCKED_LOGIN_ATTEMPT remaining={remaining}s")
                return False, None, f"⏳ Hesab kilidlənib. {remaining // 60} dəq {remaining % 60} san gözləyin."
        except Exception as e:
            logger.warning(f"Lockout parse error: {e}")

    # Password verify
    if not verify_password(pin, row['password']):
        fail_count = int(row.get('failed_attempts', 0) or 0) + 1
        lock_until = None
        if fail_count >= MAX_LOGIN_ATTEMPTS:
            lock_until = now + datetime.timedelta(minutes=LOCKOUT_MINUTES)

        run_action(
            "UPDATE users SET failed_attempts=:f, locked_until=:l WHERE username=:u",
            {"f": fail_count, "l": lock_until, "u": username}
        )
        log_system(username, f"FAILED_LOGIN_ATTEMPT #{fail_count}")

        remaining_attempts = MAX_LOGIN_ATTEMPTS - fail_count
        if remaining_attempts > 0:
            return False, None, f"Yanlış şifrə! {remaining_attempts} cəhd qalıb."
        else:
            return False, None, f"⏳ Çox cəhd! Hesab {LOCKOUT_MINUTES} dəqiqə kilidləndi."

    # Success — reset counters
    run_action(
        "UPDATE users SET failed_attempts=0, locked_until=NULL, last_seen=:t WHERE username=:u",
        {"t": now, "u": username}
    )

    token = create_session(username, row['role'])
    log_system(username, "SUCCESSFUL_LOGIN")
    return True, token, None

# ============================================================
# ADMIN CONFIRM DIALOG (Kiosk Numpad)
# ============================================================
@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")

    st.markdown("""
        <style>
        .admin-pin-box { font-size: 35px; text-align: center; letter-spacing: 15px; height: 60px;
            margin-bottom: 15px; background: white; border-radius: 12px; border: 2px solid #E65100;
            display: flex; align-items: center; justify-content: center; color: #E65100; }
        </style>
    """, unsafe_allow_html=True)

    if 'admin_pin_in' not in st.session_state:
        st.session_state.admin_pin_in = ""

    def admin_pad_cb(val):
        if val == 'C':
            st.session_state.admin_pin_in = ""
        elif val == '⌫':
            st.session_state.admin_pin_in = st.session_state.admin_pin_in[:-1]
        else:
            if len(st.session_state.admin_pin_in) < 15:
                st.session_state.admin_pin_in += str(val)

    disp = "• " * len(st.session_state.admin_pin_in) if st.session_state.admin_pin_in else \
        "<span style='color:#ccc; font-size:16px;'>PİN DAXİL EDİN</span>"
    st.markdown(f"<div class='admin-pin-box'>{disp}</div>", unsafe_allow_html=True)

    for row in [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['C', '0', '⌫']]:
        c1, c2, c3 = st.columns(3)
        c1.button(row[0], key=f"ad_{row[0]}", on_click=admin_pad_cb, args=(row[0],), use_container_width=True)
        c2.button(row[1], key=f"ad_{row[1]}", on_click=admin_pad_cb, args=(row[1],), use_container_width=True)
        c3.button(row[2], key=f"ad_{row[2]}", on_click=admin_pad_cb, args=(row[2],), use_container_width=True)

    st.write("")
    if st.button("Təsdiqlə", type="primary", use_container_width=True):
        adm = run_query("SELECT username, password FROM users WHERE role='admin' LIMIT 1")
        if not adm.empty and verify_password(st.session_state.admin_pin_in, adm.iloc[0]['password']):
            admin_user = adm.iloc[0]['username']
            log_system(admin_user, f"ADMIN_APPROVAL: {action_name}")
            st.session_state.admin_pin_in = ""
            callback(*args)
            st.success("İcra olundu!")
            time.sleep(1)
            st.rerun()
        else:
            log_system("unknown", f"FAILED_ADMIN_APPROVAL: {action_name}")
            st.error("Yanlış Şifrə!")
            st.session_state.admin_pin_in = ""
            time.sleep(1)
            st.rerun()

# ============================================================
# LOGIN PAGE (Kiosk Numpad)
# ============================================================
def render_login_page():
    st.markdown("""
        <style>
        .login-pin-display { font-size: 60px; text-align: center; letter-spacing: 25px; height: 100px;
            margin-bottom: 30px; background: #F9F6F0; border-radius: 20px; border: 2px solid #E65100;
            display: flex; align-items: center; justify-content: center; color: #E65100; }
        </style>
    """, unsafe_allow_html=True)

    if 'login_step' not in st.session_state:
        st.session_state.login_step = 'select_user'
        st.session_state.selected_user = None
        st.session_state.pin_code = ""

    if st.session_state.login_step == 'select_user':
        st.markdown("<h1 style='text-align:center;'>Sistemə Giriş</h1>", unsafe_allow_html=True)

        users_df = get_cached_users()
        if not users_df.empty:
            cols = st.columns(3)
            for i, row in enumerate(users_df.itertuples()):
                with cols[i % 3]:
                    if st.button(f"👤 {row.username}", use_container_width=True, key=f"u_{row.username}"):
                        st.session_state.selected_user = row.username
                        st.session_state.login_step = 'enter_pin'
                        st.rerun()
        else:
            st.warning("Sistemdə heç bir istifadəçi tapılmadı.")

    elif st.session_state.login_step == 'enter_pin':
        st.markdown(f"<h2 style='text-align:center;'>👤 {st.session_state.selected_user}</h2>", unsafe_allow_html=True)

        disp = "• " * len(st.session_state.pin_code) if st.session_state.pin_code else \
            "<span style='color:#ccc;'>ŞİFRƏ</span>"

        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            st.markdown(f"<div class='login-pin-display'>{disp}</div>", unsafe_allow_html=True)

            def pin_press(val):
                if val == 'C':
                    st.session_state.pin_code = ""
                elif val == '⌫':
                    st.session_state.pin_code = st.session_state.pin_code[:-1]
                else:
                    if len(st.session_state.pin_code) < 15:
                        st.session_state.pin_code += str(val)

            for row in [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['C', '0', '⌫']]:
                c1, c2, c3 = st.columns(3)
                c1.button(row[0], key=f"lp_{row[0]}", on_click=pin_press, args=(row[0],), use_container_width=True)
                c2.button(row[1], key=f"lp_{row[1]}", on_click=pin_press, args=(row[1],), use_container_width=True)
                c3.button(row[2], key=f"lp_{row[2]}", on_click=pin_press, args=(row[2],), use_container_width=True)

            st.write("")
            c_b1, c_b2 = st.columns(2)
            if c_b1.button("⬅️ Başqa İstifadəçi", use_container_width=True):
                st.session_state.login_step = 'select_user'
                st.session_state.pin_code = ""
                st.rerun()

            if c_b2.button("Daxil Ol ✅", type="primary", use_container_width=True):
                success, token, error_msg = attempt_login(
                    st.session_state.selected_user,
                    st.session_state.pin_code
                )

                if success:
                    user_df = get_user_for_auth(st.session_state.selected_user)
                    st.session_state.session_token = token
                    st.session_state.logged_in = True
                    st.session_state.user = st.session_state.selected_user
                    st.session_state.role = user_df.iloc[0]['role']
                    st.session_state.pin_code = ""
                    st.session_state.login_step = 'select_user'
                    st.rerun()
                else:
                    st.error(error_msg)
                    st.session_state.pin_code = ""
                    time.sleep(1)
                    st.rerun()
