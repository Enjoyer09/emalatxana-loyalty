import streamlit as st
import pandas as pd
import random
import datetime
import time
import os

from database import ensure_schema, run_query, run_action, get_setting, set_setting
from auth import check_url_token_login, validate_session, logout_user, create_session, get_cached_users, verify_password
from utils import BRAND_NAME, VERSION, CARTOON_QUOTES, DEFAULT_TERMS, clean_qr_code, get_baku_now

from modules.pos import render_pos_page
from modules.tables import render_tables_page
from modules.inventory import render_inventory_page
from modules.finance import render_finance_page
from modules.analytics import render_analytics_page, render_z_report_page
from modules.management import render_menu_page, render_recipe_page, render_crm_page, render_qr_page
from modules.admin import render_settings_page, render_database_page, render_logs_page, render_notes_page

st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'session_token' not in st.session_state: st.session_state.session_token = None
if 'multi_carts' not in st.session_state: st.session_state.multi_carts = {1: {'cart': [], 'customer': None}, 2: {'cart': [], 'customer': None}, 3: {'cart': [], 'customer': None}}
if 'active_cart_id' not in st.session_state: st.session_state.active_cart_id = 1
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'pos_key_counter' not in st.session_state: st.session_state.pos_key_counter = 0
if 'search_key_counter' not in st.session_state: st.session_state.search_key_counter = 0
if 'calc_received' not in st.session_state: st.session_state.calc_received = 0.0
if 'tip_input_val' not in st.session_state: st.session_state.tip_input_val = 0.0
if 'edit_recipe_id' not in st.session_state: st.session_state.edit_recipe_id = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'show_receipt_popup' not in st.session_state: st.session_state.show_receipt_popup = False
if 'last_receipt_data' not in st.session_state: st.session_state.last_receipt_data = None
if 'anbar_page' not in st.session_state: st.session_state.anbar_page = 0
if 'z_report_active' not in st.session_state: st.session_state.z_report_active = False
if 'z_calculated' not in st.session_state: st.session_state.z_calculated = False 

ensure_schema()

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;700&display=swap');
    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F4F5F7 !important; color: #333 !important; font-family: 'Arial', sans-serif !important; }
    div[data-testid="stStatusWidget"] { visibility: hidden; } #MainMenu { visibility: hidden; } header { visibility: hidden; } footer { visibility: hidden; }
    div[data-testid="stImage"] img { border-radius: 50% !important; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    div.stRadio > div[role="radiogroup"] { display: flex; flex-direction: row; justify-content: center; overflow-x: auto; background: white; padding: 10px; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    div.stRadio > div[role="radiogroup"] > label { background: transparent; border: 1px solid #ddd; border-radius: 8px; margin: 0 5px; padding: 5px 15px; cursor: pointer; transition: all 0.2s; }
    div.stRadio > div[role="radiogroup"] > label[data-checked="true"] { background: #2E7D32 !important; color: white !important; border-color: #2E7D32; }
    div.stButton > button { border-radius: 12px !important; font-weight: bold !important; border: 1px solid #999 !important; box-shadow: 2px 2px 5px rgba(0,0,0,0.2) !important; transition: all 0.1s; }
    div.stButton > button:active { transform: scale(0.98); box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3) !important; }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    div.stButton > button[kind="secondary"] { background: linear-gradient(145deg, #f8f9fa, #cfd8dc) !important; color: #263238 !important; min-height: 90px !important; white-space: pre-wrap !important; font-size: 16px !important; line-height: 1.3 !important; padding: 8px !important; }
    @keyframes flash { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.8; transform: scale(1.02); } 100% { opacity: 1; transform: scale(1); } }
    .flash-message { animation: flash 1.5s infinite; border: 3px solid #FFD700 !important; background: linear-gradient(45deg, #FF6B35, #FF8C00) !important; }
    .msg-box { background: linear-gradient(45deg, #FF9800, #FFC107); padding: 15px; border-radius: 15px; color: white; font-weight: bold; text-align: center; margin-bottom: 20px; font-family: 'Comfortaa', cursive !important; animation: pulse 2s infinite; }
    .stamp-container { display: flex; justify-content: center; margin-bottom: 20px; }
    .stamp-card { background: white; padding: 15px 30px; text-align: center; font-family: 'Courier Prime', monospace; font-weight: bold; transform: rotate(-3deg); border-radius: 12px; border: 4px solid #B71C1C; color: #B71C1C; box-shadow: 0 0 0 4px white, 0 0 0 7px #B71C1C; }
    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; justify-items: center; margin-top: 20px; max-width: 400px; margin-left: auto; margin-right: auto; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.5s ease; }
    .cup-earned { filter: invert(24%) sepia(96%) saturate(1720%) hue-rotate(94deg) brightness(92%) contrast(102%); opacity: 1; transform: scale(1.1); }
    .cup-red-base { filter: invert(18%) sepia(90%) saturate(6329%) hue-rotate(356deg) brightness(96%) contrast(116%); }
    .cup-anim { animation: bounce 1s infinite; }
    .cup-empty { filter: grayscale(100%); opacity: 0.2; }
    div[data-testid="stRating"] { justify-content: center !important; transform: scale(1.5); }
    div[data-testid="stRating"] svg { fill: #FF0000 !important; color: #FF0000 !important; }
    .round-logo { display: block; margin-left: auto; margin-right: auto; border-radius: 50%; width: 150px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

def get_receipt_html_string(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME); addr = get_setting("receipt_address", "Baku"); phone = get_setting("receipt_phone", "")
    header = get_setting("receipt_header", ""); footer = get_setting("receipt_footer", "Təşəkkürlər!")
    logo = get_setting("receipt_logo_base64"); time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<img src="data:image/png;base64,{logo}" style="width:80px; margin-bottom: 10px; filter:grayscale(100%);">' if logo else ""
    rows = "".join([f"<tr><td style='border-bottom:1px dashed #000; padding:5px;'>{int(i['qty'])}</td><td style='border-bottom:1px dashed #000; padding:5px;'>{i['item_name']}</td><td style='border-bottom:1px dashed #000; padding:5px; text-align:right;'>{i['qty']*i['price']:.2f}</td></tr>" for i in cart])
    return f"""<html><head><style>body{{font-family:'Courier New',monospace;text-align:center;margin:0;padding:0}}.receipt-container{{width:300px;margin:0 auto;padding:10px;background:white}}table{{width:100%;text-align:left;border-collapse:collapse}}th{{border-bottom:1px dashed #000;padding:5px}}@media print{{body,html{{width:100%;height:100%;margin:0;padding:0}}body *{{visibility:hidden}}.receipt-container,.receipt-container *{{visibility:visible}}.receipt-container{{position:absolute;left:0;top:0;width:100%;margin:0;padding:0}}#print-btn{{display:none}}}}</style></head><body><div class="receipt-container">{img_tag}<h3 style="margin:5px 0;">{store}</h3><p style="margin:0;font-size:12px;">{addr}<br>{phone}</p><p style="margin:5px 0;font-weight:bold;">{header}</p><p style="font-size:12px;">{time_str}</p><br><table><tr><th>Say</th><th>Mal</th><th style='text-align:right;'>Məb</th></tr>{rows}</table><h3>YEKUN: {total:.2f} ₼</h3><p>{footer}</p><br><button id="print-btn" onclick="window.print()" style="background:#2E7D32;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">🖨️ ÇAP ET</button></div></body></html>"""

@st.dialog("🧾 Çek")
def show_receipt_dialog(cart_data, total_amt, cust_email):
    html = get_receipt_html_string(cart_data, total_amt)
    import streamlit.components.v1 as components
    components.html(html, height=500, scrolling=True)
    c1, c2 = st.columns(2)
    with c1: 
        if cust_email and st.button("📧 Email Göndər"): 
            from utils import send_email 
            send_email(cust_email, "Çekiniz", html); st.success("Getdi!")
    if st.button("❌ Bağla"): st.session_state.show_receipt_popup=False; st.session_state.last_receipt_data=None; st.rerun()

if "id" in st.query_params and not st.session_state.logged_in:
    card_id = st.query_params["id"]; token = st.query_params.get("t")
    c1, c2, c3 = st.columns([1,2,1])
    with c2: 
        logo_db = get_setting("receipt_logo_base64")
        if logo_db: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_db}" class="round-logo" width="120"></div>', unsafe_allow_html=True)
        elif os.path.exists("logo.jpg"): st.image("logo.jpg", width=120)
    st.markdown("""<style>.stApp{background-color:#FFFFFF!important;}h1,h2,h3,h4,h5,h6,p,div,span,label,li{color:#000000!important;}</style>""", unsafe_allow_html=True)
    try: df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":card_id})
    except: st.stop()
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token: st.warning("⚠️ QR kod köhnəlib.")
        st.markdown(f"<div class='cartoon-quote'>{random.choice(CARTOON_QUOTES)}</div>", unsafe_allow_html=True)
        notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":card_id})
        for _, n in notifs.iterrows():
            st.markdown(f"<div class='msg-box flash-message'>📩 {n['message']}</div>", unsafe_allow_html=True)
            st.balloons()
            if st.button("Oxudum ✅", key=f"n_{n['id']}"): run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.rerun()
        if not user['is_active']:
            st.info("Xoş Gəldiniz!"); terms = get_setting("customer_rules", DEFAULT_TERMS)
            with st.form("act"):
                st.markdown(terms, unsafe_allow_html=True); agree = st.checkbox("Qaydaları oxudum və qəbul edirəm", value=False); st.divider(); st.write("**Könüllü:**"); em = st.text_input("Email"); dob = st.date_input("Doğum Tarixi", value=None, min_value=datetime.date(1950,1,1))
                if st.form_submit_button("TƏSDİQLƏ VƏ QOŞUL"):
                    if agree: run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":str(dob) if dob else None, "i":card_id}); st.rerun()
                    else: st.error("Qaydaları qəbul edin.")
            st.stop()
        ctype = user['type']; st_lbl = "MEMBER"; b_col = "#B71C1C"
        if ctype=='golden': st_lbl="GOLDEN (5%)"; b_col="#D4AF37"
        elif ctype=='platinum': st_lbl="PLATINUM (10%)"; b_col="#78909C"
        elif ctype=='elite': st_lbl="ELITE (20%)"; b_col="#37474F"
        elif ctype=='ikram': st_lbl="İKRAM (100%)"; b_col="#00C853"
        elif ctype=='thermos': st_lbl="EKO-TERM (20%)"; b_col="#2E7D32"
        st.markdown(f"<div class='stamp-container'><div class='stamp-card' style='border-color:{b_col};color:{b_col};box-shadow:0 0 0 4px white, 0 0 0 7px {b_col};'><div style='font-size:20px;border-bottom:2px solid;'>{st_lbl}</div><div style='font-size:50px;'>{user['stars']}/10</div><div>ULDUZ BALANSI</div></div></div>", unsafe_allow_html=True)
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; style = ""; cls = "cup-empty"
            if i == 9: 
                if user['stars'] >= 10: cls = "cup-red-base cup-anim"; style = "opacity: 1;"
                else: op = 0.1 + (user['stars'] * 0.09); cls = "cup-red-base"; style = f"opacity: {op};"
            elif i < user['stars']: cls = "cup-earned"
            html += f'<img src="{icon}" class="{cls} coffee-icon-img" style="{style}">'
        st.markdown(html + "</div>", unsafe_allow_html=True)
        if user['stars'] >= 10: st.success("🎉 Təbriklər! Bu kofeniz bizdəndir!")
        with st.form("fd"):
            s = st.feedback("stars"); m = st.text_input("Fikriniz...")
            if st.form_submit_button("Göndər") and s: run_action("INSERT INTO feedbacks (card_id,rating,comment,created_at) VALUES (:c,:r,:m,:t)", {"c":card_id,"r":s+1,"m":m,"t":get_baku_now()}); st.success("Təşəkkürlər!")
        st.stop()

if not st.session_state.logged_in: check_url_token_login()
if not st.session_state.logged_in:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        logo_db = get_setting("receipt_logo_base64")
        if logo_db: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_db}" class="round-logo" width="150"></div>', unsafe_allow_html=True)
        elif os.path.exists("logo.jpg"): st.image("logo.jpg", width=150)
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u = get_cached_users(); found = False; matched_user = None
                    for _,r in u.iterrows():
                        if r['role'] in ['staff','manager']:
                            if r['locked_until'] and pd.to_datetime(r['locked_until']) > get_baku_now(): st.error("BLOKLANDI!"); found=True; break
                            if verify_password(p, r['password']): matched_user = r; found = True; break
                            else: fail = (r['failed_attempts'] or 0) + 1
                    if matched_user is not None:
                        st.session_state.logged_in=True; st.session_state.user=matched_user['username']; st.session_state.role=matched_user['role']; token = create_session(matched_user['username'],matched_user['role']); st.session_state.session_token = token; run_action("UPDATE users SET failed_attempts=0 WHERE username=:u", {"u":matched_user['username']}); st.query_params.clear(); st.rerun()
                    elif not found: st.error("Yanlış PIN")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']; token = create_session(u,ud.iloc[0]['role']); st.session_state.session_token = token; st.query_params.clear(); st.rerun()
                    else: st.error("Səhv")
else:
    if not validate_session(): logout_user()
    h1, h2, h3 = st.columns([4,1,1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄 YENİLƏ", key="refresh_top", use_container_width=True, type="secondary"): st.rerun()
    with h3: 
        if st.button("🚪 ÇIXIŞ", type="primary", key="logout_top", use_container_width=True): logout_user()
    st.divider()

    role = st.session_state.role
    tabs_list = []
    if role in ['admin', 'manager', 'staff']: tabs_list.append("🏃‍♂️ AL-APAR")
    show_tables_staff = get_setting("staff_show_tables", "TRUE") == "TRUE"; show_tables_mgr = get_setting("manager_show_tables", "TRUE") == "TRUE"
    if role == 'admin' or (role == 'manager' and show_tables_mgr) or (role == 'staff' and show_tables_staff): tabs_list.append("🍽️ MASALAR")
    if role in ['staff', 'manager', 'admin']: tabs_list.append("📊 Z-Hesabat")
    if role in ['admin', 'manager']: tabs_list.extend(["💰 Maliyyə", "📦 Anbar", "📊 Analitika", "📜 Loglar", "👥 CRM"])
    if role == 'manager':
         if get_setting("manager_perm_menu", "FALSE") == "TRUE": tabs_list.append("📋 Menyu")
         if get_setting("manager_perm_recipes", "FALSE") == "TRUE": tabs_list.append("📜 Resept")
    if role == 'admin':
        if "📋 Menyu" not in tabs_list: tabs_list.append("📋 Menyu")
        if "📜 Resept" not in tabs_list: tabs_list.append("📜 Resept")
        tabs_list.extend(["📝 Qeydlər", "⚙️ Ayarlar", "💾 Baza", "QR"])

    if "current_tab" not in st.session_state: st.session_state.current_tab = tabs_list[0]
    selected_tab = st.radio("Menu", tabs_list, horizontal=True, label_visibility="collapsed", key="main_nav_radio", index=tabs_list.index(st.session_state.current_tab) if st.session_state.current_tab in tabs_list else 0)
    if selected_tab != st.session_state.current_tab: st.session_state.current_tab = selected_tab

    if st.session_state.show_receipt_popup and st.session_state.last_receipt_data and selected_tab == "🏃‍♂️ AL-APAR":
        show_receipt_dialog(st.session_state.last_receipt_data['cart'], st.session_state.last_receipt_data['total'], st.session_state.last_receipt_data['email'])

    if selected_tab == "🏃‍♂️ AL-APAR": render_pos_page()
    elif selected_tab == "🍽️ MASALAR": render_tables_page()
    elif selected_tab == "📊 Z-Hesabat": render_z_report_page()
    elif selected_tab == "📦 Anbar": render_inventory_page()
    elif selected_tab == "💰 Maliyyə": render_finance_page()
    elif selected_tab == "📊 Analitika": render_analytics_page()
    elif selected_tab == "👥 CRM": render_crm_page()
    elif selected_tab == "📋 Menyu": render_menu_page()
    elif selected_tab == "📜 Resept": render_recipe_page()
    elif selected_tab == "📝 Qeydlər": render_notes_page()
    elif selected_tab == "⚙️ Ayarlar": render_settings_page()
    elif selected_tab == "💾 Baza": render_database_page()
    elif selected_tab == "QR": render_qr_page()
    elif selected_tab == "📜 Loglar": render_logs_page()

    st.markdown(f"<div style='text-align:center;color:#aaa;margin-top:50px;'>{BRAND_NAME} {VERSION}</div>", unsafe_allow_html=True)
