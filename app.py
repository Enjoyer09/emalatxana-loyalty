import streamlit as st
import pandas as pd
import random
import datetime
import time
import os
from sqlalchemy import text

from database import ensure_schema, run_query, run_action, get_setting, set_setting, conn
from auth import check_url_token_login, validate_session, logout_user, create_session, get_cached_users, verify_password
from utils import BRAND_NAME, VERSION, CARTOON_QUOTES, DEFAULT_TERMS, clean_qr_code, get_baku_now

from modules.pos import render_pos_page
from modules.tables import render_tables_page
from modules.inventory import render_inventory_page
from modules.finance import render_finance_page
from modules.analytics import render_analytics_page, render_z_report_page
from modules.management import render_menu_page, render_recipe_page, render_crm_page, render_qr_page
from modules.admin import render_settings_page, render_database_page, render_logs_page, render_notes_page
from modules.ai_manager import render_ai_page

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
if 'restock_item_id' not in st.session_state: st.session_state.restock_item_id = None
if 'edit_item_id' not in st.session_state: st.session_state.edit_item_id = None
if 'menu_edit_id' not in st.session_state: st.session_state.menu_edit_id = None
if 'low_stock_shown' not in st.session_state: st.session_state.low_stock_shown = False # ANBAR XƏBƏRDARLIĞI ÜÇÜN

ensure_schema()

# --- YENİ TƏMİZ VƏ SƏHVSİZ METALLİK CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;800&family=Nunito:wght@400;700;900&display=swap');
    
    :root { 
        --metal-bg: radial-gradient(circle at center, #4a5159 0%, #1a1d21 100%);
        --metal-panel: linear-gradient(145deg, #323841, #252a30);
        --metal-btn: linear-gradient(160deg, #4a5159 0%, #2a2f35 50%, #1e2226 100%);
        --metal-btn-hover: linear-gradient(160deg, #5c6570 0%, #383f47 50%, #2a2f35 100%);
        --accent-gold: linear-gradient(160deg, #ffd700 0%, #e6b800 50%, #b38f00 100%);
        --text-light: #ffffff;
        --border-color: #545b66;
    }
    
    html, body { font-family: 'Nunito', sans-serif !important; font-size: 16px !important; }
    .stApp { background: var(--metal-bg) !important; color: var(--text-light) !important; }
    div[data-testid="stStatusWidget"], #MainMenu, header, footer { display: none !important; }
    
    h1, h2, h3 { color: #ffd700 !important; font-family: 'Jura', sans-serif !important; font-weight: 800 !important; text-transform: uppercase; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
    h4, p, span, label { color: var(--text-light) !important; }

    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { 
        background-color: #16191d !important; border: 2px solid #3a4149 !important; border-radius: 8px !important; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5) !important;
    }
    div[data-baseweb="input"] input { 
        color: #ffffff !important; font-weight: 700 !important; -webkit-text-fill-color: #ffffff !important; background: transparent !important;
    }
    div[data-baseweb="input"] input::placeholder { color: #7b8896 !important; -webkit-text-fill-color: #7b8896 !important; }
    div[data-baseweb="select"] span { color: #ffffff !important; font-weight: 700 !important; }
    ul[role="listbox"] { background-color: #1e2226 !important; border: 1px solid #3a4149 !important; }
    ul[role="listbox"] li { color: #ffffff !important; }
    
    div[role="dialog"] { background: transparent !important; }
    div[role="dialog"] > div { background: var(--metal-bg) !important; border: 2px solid #ffd700 !important; border-radius: 15px !important; box-shadow: 0 10px 40px rgba(0,0,0,0.9) !important; }
    div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 { color: #ffd700 !important; }
    div[role="dialog"] p, div[role="dialog"] span, div[role="dialog"] label { color: #ffffff !important; }
    div[role="dialog"] header { background: transparent !important; }
    
    /* NAVİQASİYA DÜYMƏLƏRİ VƏ "HARADAYAM" EFEKTİ */
    div[role="radiogroup"] { gap: 10px; border: none; flex-wrap: wrap; }
    div[role="radiogroup"] > label { 
        background: var(--metal-btn) !important; border: 2px solid #3a4149 !important; border-radius: 8px !important; 
        padding: 10px 20px !important; cursor: pointer; box-shadow: 4px 4px 8px rgba(0,0,0,0.6), inset 1px 1px 2px rgba(255,255,255,0.1) !important; transition: all 0.2s;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; width: 0 !important; height: 0 !important; }
    div[role="radiogroup"] > label p { color: #ffffff !important; font-weight: 800 !important; font-size: 15px !important; font-family: 'Jura', sans-serif !important; margin: 0 !important; display: block !important;}
    div[role="radiogroup"] > label:hover { background: var(--metal-btn-hover) !important; transform: translateY(-2px); }
    
    /* AKTİV SƏHİFƏNİN VİZUAL QABARDILMASI (HARADAYAM?) */
    div[role="radiogroup"] > label[data-checked="true"] { 
        background: var(--accent-gold) !important; 
        border: 2px solid #ffffff !important; 
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.8), inset 2px 2px 5px rgba(255,255,255,0.5) !important;
        transform: scale(1.08) translateY(-3px) !important;
        z-index: 10;
    }
    div[role="radiogroup"] > label[data-checked="true"] p { color: #000000 !important; font-size: 16px !important; font-weight: 900 !important; }
    
    div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="expander"], div[data-testid="stPopoverBody"] {
        background: var(--metal-panel) !important; border: 2px solid #3a4149 !important; border-radius: 12px !important;
        box-shadow: 6px 6px 12px rgba(0,0,0,0.4), inset 1px 1px 2px rgba(255,255,255,0.05) !important; padding: 15px !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] { 
        background: var(--metal-btn) !important; border: 2px solid #3a4149 !important; border-radius: 10px !important; 
        box-shadow: inset 0 1px 0 #6a7179, 0 5px 10px rgba(0,0,0,0.5) !important; min-height: 70px; transition: all 0.15s;
    }
    button[kind="secondary"] p, button[kind="secondaryFormSubmit"] p, button[kind="secondaryFormSubmit"] div { 
        color: #ffffff !important; font-size: 16px !important; font-weight: 800 !important; font-family: 'Nunito' !important; display: block !important;
    }
    button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover { 
        background: var(--metal-btn-hover) !important; transform: translateY(-3px); border-color: #7b8896 !important; 
    }
    
    button[kind="primary"], button[kind="primaryFormSubmit"] { 
        background: var(--accent-gold) !important; border: 2px solid #ffd700 !important; border-radius: 10px !important; 
        box-shadow: 0 5px 15px rgba(255, 215, 0, 0.4), inset 2px 2px 5px rgba(255,255,255,0.5) !important; min-height: 50px;
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p, button[kind="primaryFormSubmit"] div { 
        color: #000000 !important; font-weight: 900 !important; font-size: 18px !important; font-family: 'Jura' !important; text-shadow: none !important; display: block !important;
    }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { 
        background: linear-gradient(160deg, #ffed4d 0%, #ffd700 50%, #e6b800 100%) !important; transform: translateY(-2px); 
    }
    
    hr { border-top: 2px solid #3a4149 !important; opacity: 0.5; }
    .stMetric { background: var(--metal-btn); padding: 15px; border-radius: 10px; border: 2px solid #3a4149; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5); }
    .stMetric label { color: #aaa !important; font-weight: 700; } .stMetric div { color: #ffd700 !important; font-family: 'Jura'; font-weight: 900; }
    </style>
""", unsafe_allow_html=True)

def get_receipt_html_string(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME); addr = get_setting("receipt_address", "Baku"); phone = get_setting("receipt_phone", "")
    header = get_setting("receipt_header", ""); footer = get_setting("receipt_footer", "Təşəkkürlər!")
    logo = get_setting("receipt_logo_base64"); time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<img src="data:image/png;base64,{logo}" style="width:80px; margin-bottom: 10px; filter:grayscale(100%);">' if logo else ""
    rows = "".join([f"<tr><td style='border-bottom:1px dashed #000; padding:5px;'>{int(i['qty'])}</td><td style='border-bottom:1px dashed #000; padding:5px;'>{i['item_name']}</td><td style='border-bottom:1px dashed #000; padding:5px; text-align:right;'>{i['qty']*i['price']:.2f}</td></tr>" for i in cart])
    return f"""<html><head><style>body{{font-family:'Courier New',monospace;text-align:center;margin:0;padding:0;background:white;color:black;}}.receipt-container{{width:300px;margin:0 auto;padding:10px;background:white;color:black;}}table{{width:100%;text-align:left;border-collapse:collapse;color:black;}}th,td{{border-bottom:1px dashed #000;padding:5px;color:black;}}h3,p{{color:black;}}@media print{{body,html{{width:100%;height:100%;margin:0;padding:0}}body *{{visibility:hidden}}.receipt-container,.receipt-container *{{visibility:visible}}.receipt-container{{position:absolute;left:0;top:0;width:100%;margin:0;padding:0}}#print-btn{{display:none}}}}</style></head><body><div class="receipt-container">{img_tag}<h3 style="margin:5px 0;">{store}</h3><p style="margin:0;font-size:12px;">{addr}<br>{phone}</p><p style="margin:5px 0;font-weight:bold;">{header}</p><p style="font-size:12px;">{time_str}</p><br><table><tr><th>Say</th><th>Mal</th><th style='text-align:right;'>Məb</th></tr>{rows}</table><h3>YEKUN: {total:.2f} ₼</h3><p>{footer}</p><br><button id="print-btn" onclick="window.print()" style="background:#2E7D32;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">🖨️ ÇAP ET</button></div></body></html>"""

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

# --- MÜŞTƏRİ EKRANI ÜÇÜN XÜSUSİ AĞ REJİM VƏ MOBİL OPTİMİZASİYA ---
if "id" in st.query_params and not st.session_state.logged_in:
    st.markdown("""
        <style>
        .stApp { background: #FFFFFF !important; }
        .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp span, .stApp div { color: #000000 !important; text-shadow: none !important; }
        .stApp button { background: #2E7D32 !important; border: none !important; box-shadow: none !important; min-height: 50px !important; }
        .stApp button p { color: #FFFFFF !important; font-family: 'Nunito' !important; display: block !important;}
        .customer-card { background: #f8f9fa; border: 4px solid #2E7D32; border-radius: 15px; padding: 20px; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .msg-box { background: #e3f2fd; border-left: 5px solid #2196f3; padding: 15px; margin-bottom: 15px; border-radius: 8px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)
    
    card_id = st.query_params["id"]; token = st.query_params.get("t")
    c1, c2, c3 = st.columns([1,2,1])
    with c2: 
        logo_db = get_setting("receipt_logo_base64")
        if logo_db: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_db}" width="120"></div>', unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:center; color:#2E7D32 !important; margin:0;'>{BRAND_NAME}</h2>", unsafe_allow_html=True)
        st.divider()

    try: df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":card_id})
    except: st.error("Baza xətası"); st.stop()
    
    if not df.empty:
        user = df.iloc[0]
        notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":card_id})
        for _, n in notifs.iterrows():
            st.markdown(f"<div class='msg-box'>📩 {n['message']}</div>", unsafe_allow_html=True)
            if st.button("Oxudum ✅", key=f"n_{n['id']}", use_container_width=True): 
                run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.rerun()
        
        ctype = user['type']; st_lbl = "MEMBER"; b_col = "#2E7D32"
        if ctype=='golden': st_lbl="GOLDEN (5%)"; b_col="#D4AF37"
        elif ctype=='platinum': st_lbl="PLATINUM (10%)"; b_col="#78909C"
        elif ctype=='elite': st_lbl="ELITE (20%)"; b_col="#37474F"
        
        st.markdown(f"""
        <div class='customer-card' style='border-color:{b_col};'>
            <h3 style='margin:0; color:{b_col} !important;'>{st_lbl}</h3>
            <h1 style='font-size:60px; margin:10px 0; color:{b_col} !important;'>{user['stars']}/10</h1>
            <p style='margin:0; font-weight:bold; color:{b_col} !important;'>ULDUZ BALANSI</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        cups_html = '<div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; margin-top: 10px;">'
        for i in range(10):
            if i < user['stars']:
                cups_html += '<img src="https://cdn-icons-png.flaticon.com/512/751/751621.png" width="45" style="margin-bottom:10px;">'
            else:
                cups_html += '<img src="https://cdn-icons-png.flaticon.com/512/751/751621.png" width="45" style="filter: grayscale(100%); opacity: 0.2; margin-bottom:10px;">'
        cups_html += '</div>'
        st.markdown(cups_html, unsafe_allow_html=True)
        
        if user['stars'] >= 10: st.success("🎉 Təbriklər! 1 ədəd pulsuz kofeniz var!")
        st.divider()
        with st.expander("💬 Bizə Yazın (Rəy Bildir)"):
             with st.form("fd"):
                s = st.feedback("stars"); m = st.text_area("Fikriniz...")
                if st.form_submit_button("Göndər") and s: 
                    run_action("INSERT INTO feedbacks (card_id,rating,comment,created_at) VALUES (:c,:r,:m,:t)", {"c":card_id,"r":s+1,"m":m,"t":get_baku_now()}); st.success("Təşəkkürlər!")
    else: st.error("Kart tapılmadı.")
    st.stop()

# --- LOGIN VƏ NAVIQASİYA ---
if not st.session_state.logged_in: check_url_token_login()
if not st.session_state.logged_in:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        logo_db = get_setting("receipt_logo_base64")
        if logo_db: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_db}" class="round-logo" width="150" style="border-radius:50%;"></div>', unsafe_allow_html=True)
        elif os.path.exists("logo.jpg"): st.image("logo.jpg", width=150)
        st.markdown(f"<h1 style='text-align:center; margin-bottom:0;'>{BRAND_NAME}</h1><h5 style='text-align:center; color:#7b8896 !important;'>{VERSION}</h5>", unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u = get_cached_users(); found = False; matched_user = None
                    for _,r in u.iterrows():
                        if r['role'] in ['staff','manager']:
                            if verify_password(p, r['password']): matched_user = r; found = True; break
                    if matched_user is not None:
                        st.session_state.logged_in=True; st.session_state.user=matched_user['username']; st.session_state.role=matched_user['role']; token = create_session(matched_user['username'],matched_user['role']); st.session_state.session_token = token; st.query_params.clear(); st.rerun()
                    elif not found: st.error("Yanlış PIN")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']; token = create_session(u,ud.iloc[0]['role']); st.session_state.session_token = token; st.query_params.clear(); st.rerun()
                    else: st.error("Səhv")
else:
    if not validate_session(): 
        st.session_state.clear()
        st.rerun()
        
    # LOGOUT XƏTASININ TAM HƏLLİ (Callback olmadan, birbaşa trigger)
    h1, h2, h3 = st.columns([4,1,1], vertical_alignment="center")
    with h1: st.markdown(f"<h3 style='margin:0;'>👤 {st.session_state.user} | <span style='color:#ffffff !important; font-size:16px;'>{st.session_state.role.upper()}</span></h3>", unsafe_allow_html=True)
    with h2: st.button("🔄 YENİLƏ", key="refresh_top", use_container_width=True, type="secondary")
    with h3: 
        if st.button("🚪 ÇIXIŞ", type="primary", key="logout_top", use_container_width=True):
            st.session_state.clear()
            st.session_state.logged_in = False
            st.rerun()
    st.divider()

    # ANBAR POP-UP XƏBƏRDARLIĞI (Yalnız daxil olanda və 1 dəfə görünür)
    if not st.session_state.low_stock_shown:
        try:
            low_stock_df = run_query("SELECT name as \"Xammal\", stock_qty as \"Qalıq\", unit as \"Vahid\" FROM ingredients WHERE stock_qty <= 5.0")
            if not low_stock_df.empty:
                @st.dialog("⚠️ DİQQƏT: ANBARDA AZALAN MALLAR VAR!")
                def show_low_stock_dialog(df):
                    st.error("Aşağıdakı xammalların ehtiyatı kritik səviyyədədir (5-dən azdır). Xahiş edirik anbarı yoxlayın!")
                    st.dataframe(df, hide_index=True, use_container_width=True)
                    if st.button("✅ Anladım, Bağla", type="primary", use_container_width=True):
                        st.session_state.low_stock_shown = True
                        st.rerun()
                show_low_stock_dialog(low_stock_df)
            else:
                st.session_state.low_stock_shown = True
        except:
            st.session_state.low_stock_shown = True

    role = st.session_state.role
    tabs_list = []
    if role in ['admin', 'manager', 'staff']: tabs_list.append("🏃‍♂️ AL-APAR")
    show_tables_staff = get_setting("staff_show_tables", "TRUE") == "TRUE"; show_tables_mgr = get_setting("manager_show_tables", "TRUE") == "TRUE"
    if role == 'admin' or (role == 'manager' and show_tables_mgr) or (role == 'staff' and show_tables_staff): tabs_list.append("🍽️ MASALAR")
    if role in ['staff', 'manager', 'admin']: tabs_list.append("📊 Z-Hesabat")
    if role in ['admin', 'manager']: tabs_list.extend(["💰 Maliyyə", "📦 Anbar", "📊 Analitika", "📜 Loglar", "👥 CRM", "🤖 AI Menecer"])
    if role == 'manager':
         if get_setting("manager_perm_menu", "FALSE") == "TRUE": tabs_list.append("📋 Menyu")
         if get_setting("manager_perm_recipes", "FALSE") == "TRUE": tabs_list.append("📜 Resept")
    if role == 'admin':
        tabs_list.extend(["📋 Menyu", "📜 Resept", "📝 Qeydlər", "⚙️ Ayarlar", "💾 Baza", "QR"])
    
    tabs_list = sorted(list(set(tabs_list)), key=tabs_list.index)

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
    elif selected_tab == "🤖 AI Menecer": render_ai_page()
    elif selected_tab == "📋 Menyu": render_menu_page()
    elif selected_tab == "📜 Resept": render_recipe_page()
    elif selected_tab == "📝 Qeydlər": render_notes_page()
    elif selected_tab == "⚙️ Ayarlar": render_settings_page()
    elif selected_tab == "💾 Baza": render_database_page()
    elif selected_tab == "QR": render_qr_page()
    elif selected_tab == "📜 Loglar": render_logs_page()

    st.markdown(f"<div style='text-align:center;color:#545b66;margin-top:50px;font-family:Jura;'>{BRAND_NAME} {VERSION}</div>", unsafe_allow_html=True)
