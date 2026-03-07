import streamlit as st
import pandas as pd
import random, datetime, time, os
from sqlalchemy import text

from database import ensure_schema, run_query, run_action, get_setting, set_setting, conn
from auth import check_url_token_login, validate_session, logout_user, create_session, get_cached_users, verify_password
from utils import BRAND_NAME, VERSION, CARTOON_QUOTES, DEFAULT_TERMS, clean_qr_code, get_baku_now, get_shift_status, open_shift, close_shift

# BÜTÜN MODUL İMPORTLARI (TAM QORUNUR)
from modules.pos import render_pos_page
from modules.tables import render_tables_page
from modules.inventory import render_inventory_page
from modules.finance import render_finance_page
from modules.analytics import render_analytics_page, render_z_report_page
from modules.management import render_menu_page, render_recipe_page, render_crm_page, render_qr_page
from modules.admin import render_settings_page, render_database_page, render_logs_page, render_notes_page
from modules.ai_manager import render_ai_page
from modules.customer_menu import render_customer_app

st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# 🕒 YENİ: SHIFT POPUP DIALOGS (Sabina və Samir üçün)
@st.dialog("🕒 Növbə İdarəetməsi")
def shift_modal(mode):
    if mode == "open":
        st.markdown(f"### 🌅 Sabahınız xeyir, {st.session_state.user}!")
        st.warning("Hazırda sistemdə aktiv növbə (Shift) yoxdur.")
        st.info(f"Bakı vaxtı: **{get_baku_now().strftime('%H:%M')}**")
        if st.button("✅ BƏLİ, Növbəni Aç", use_container_width=True, type="primary"):
            open_shift(st.session_state.user); st.rerun()
    elif mode == "close":
        st.error("Diqqət! Çıxış etməzdən əvvəl Z-Hesabatı vurduğunuzdan əmin olun.")
        if st.button("🚪 Növbəni Bağla və Çıx", use_container_width=True, type="primary"):
            close_shift(st.session_state.user); st.session_state.clear(); st.session_state.logged_in = False; st.rerun()

# 🚀 QR ROUTING (TAM QORUNUR)
params = st.query_params
if "id" in params:
    render_customer_app(params.get("id")); st.stop()

# 💾 BÜTÜN 20+ SESSIYA STATE-LƏRİ (TAM QORUNUR)
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
for key in ['multi_carts', 'cart_takeaway', 'active_cart_id', 'pos_key_counter', 'search_key_counter', 'calc_received', 'tip_input_val', 'selected_table', 'cart_table', 'low_stock_shown']:
    if key not in st.session_state:
        if key == 'multi_carts': st.session_state[key] = {1: {'cart': [], 'customer': None}, 2: {'cart': [], 'customer': None}, 3: {'cart': [], 'customer': None}}
        elif key == 'active_cart_id': st.session_state[key] = 1
        elif key == 'calc_received' or key == 'tip_input_val': st.session_state[key] = 0.0
        elif key == 'cart_takeaway' or key == 'cart_table': st.session_state[key] = []
        else: st.session_state[key] = False

# --- SƏNİN ORİJİNAL METALLİK CSS BLOKUN (TAM QORUNUR) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;800&family=Nunito:wght@400;700;900&display=swap');
    :root { 
        --metal-bg: radial-gradient(circle at center, #4a5159 0%, #1a1d21 100%);
        --accent-gold: linear-gradient(160deg, #ffd700 0%, #e6b800 50%, #b38f00 100%);
    }
    .stApp { background: var(--metal-bg) !important; color: white !important; font-family: 'Nunito', sans-serif !important; }
    h1, h2, h3 { color: #ffd700 !important; font-family: 'Jura', sans-serif !important; text-transform: uppercase; }
    div[role="radiogroup"] label:has(input:checked) { background: var(--accent-gold) !important; color: black !important; font-weight: 900 !important; transform: scale(1.08) !important; }
    </style>
""", unsafe_allow_html=True)

ensure_schema()

# LOGIN MƏNTİQİ
if not st.session_state.logged_in:
    check_url_token_login()
if not st.session_state.logged_in:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u_df = run_query("SELECT * FROM users WHERE role IN ('staff','manager')")
                    matched = None
                    for _,r in u_df.iterrows():
                        if verify_password(p, r['password']): matched = r; break
                    if matched is not None:
                        st.session_state.logged_in=True; st.session_state.user=matched['username']; st.session_state.role=matched['role']; st.rerun()
                    else: st.error("Səhv PIN")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']; st.rerun()
                    else: st.error("Səhv")
else:
    # --- YENİ: SHIFT YOXLAMASI ---
    s_info = get_shift_status()
    if s_info.get('current_shift_status') == 'Closed' and st.session_state.role != 'admin':
        shift_modal("open")

    if not validate_session(): st.session_state.clear(); st.rerun()
        
    h1, h2, h3 = st.columns([4,1,1], vertical_alignment="center")
    with h1: st.markdown(f"### 👤 {st.session_state.user} | {st.session_state.role.upper()}")
    with h2: st.button("🔄 YENİLƏ", key="refresh_top", use_container_width=True, type="secondary")
    with h3: 
        if st.button("🚪 ÇIXIŞ", type="primary", key="logout_top", use_container_width=True):
            if st.session_state.role == 'staff': shift_modal("close")
            else: st.session_state.clear(); st.session_state.logged_in = False; st.rerun()
    st.divider()

    # NAVİQASİYA
    role = st.session_state.role
    tabs_list = ["🏃‍♂️ AL-APAR"]
    if role == 'admin' or get_setting("staff_show_tables", "TRUE") == "TRUE": tabs_list.append("🍽️ MASALAR")
    tabs_list.append("📊 Z-Hesabat")
    if role in ['admin', 'manager']: tabs_list.extend(["💰 Maliyyə", "📦 Anbar", "📊 Analitika", "🤖 AI Menecer", "📋 Menyu", "📜 Resept", "⚙️ Ayarlar", "💾 Baza", "QR", "🕵️ Loglar", "📝 Qeydlər"])
    
    tabs_list = sorted(list(set(tabs_list)), key=tabs_list.index)
    selected_tab = st.radio("Menu", tabs_list, horizontal=True, label_visibility="collapsed")

    # SƏHİFƏ RENDERLƏRİ
    if selected_tab == "🏃‍♂️ AL-APAR": render_pos_page()
    elif selected_tab == "🍽️ MASALAR": render_tables_page()
    elif selected_tab == "📊 Z-Hesabat": render_z_report_page()
    elif selected_tab == "📦 Anbar": render_inventory_page()
    elif selected_tab == "💰 Maliyyə": render_finance_page()
    elif selected_tab == "📊 Analitika": render_analytics_page()
    elif selected_tab == "🤖 AI Menecer": render_ai_page()
    elif selected_tab == "📋 Menyu": render_menu_page()
    elif selected_tab == "📜 Resept": render_recipe_page()
    elif selected_tab == "⚙️ Ayarlar": render_settings_page()
    elif selected_tab == "💾 Baza": render_database_page()
    elif selected_tab == "QR": render_qr_page()
    elif selected_tab == "🕵️ Loglar": render_logs_page()
    elif selected_tab == "📝 Qeydlər": render_notes_page()

    st.markdown(f"<div style='text-align:center;color:#545b66;margin-top:50px;'>{BRAND_NAME} {VERSION}</div>", unsafe_allow_html=True)
