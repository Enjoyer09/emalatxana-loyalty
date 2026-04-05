# app.py — FINAL PATCHED v3.3
import streamlit as st
import pandas as pd
import random
import datetime
import time
import os
from decimal import Decimal
from sqlalchemy import text

from database import ensure_schema, run_query, run_action, run_transaction, get_setting, set_setting, conn
from auth import check_url_token_login, validate_session, attempt_login
from utils import (
    BRAND_NAME, VERSION, CARTOON_QUOTES, DEFAULT_TERMS, clean_qr_code,
    get_baku_now, get_shift_status, open_shift, close_shift, verify_password,
    get_logical_date, get_shift_range, safe_decimal, log_system
)

from modules.pos import render_pos_page
from modules.tables import render_tables_page
from modules.inventory import render_inventory_page
from modules.finance import render_finance_page
from modules.analytics import render_analytics_page, render_z_report_page
from modules.management import render_menu_page, render_recipe_page, render_crm_page, render_qr_page
from modules.admin import render_settings_page, render_database_page, render_logs_page, render_notes_page
from modules.ai_manager import render_ai_page
from modules.customer_menu import render_customer_app
from modules.combos import render_combos_page
from modules.kitchen import render_kitchen_page
from modules.finance import get_shift_finance_snapshot, process_shift_handover

st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

@st.dialog("🕒 Növbə İdarəetməsi")
def shift_modal(mode):
    if mode == "open":
        st.markdown(f"### 🌅 Sabahınız xeyir, {st.session_state.user}!")
        st.warning("Hazırda sistemdə aktiv növbə (Shift) yoxdur.")
        st.info(f"Bakı vaxtı: **{get_baku_now().strftime('%H:%M')}**")
        st.write("Günün ilk növbəsini indi başlatmaq istəyirsiniz?")
        if st.button("✅ BƏLİ, Növbəni Aç", use_container_width=True, type="primary"):
            open_shift(st.session_state.user)
            st.rerun()

    elif mode == "close":
        st.error("Diqqət! Çıxış etməzdən əvvəl hesabatları vurduğunuzdan əmin olun.")

        if not st.session_state.get('handover_mode'):
            st.write("Növbədən necə çıxmaq istəyirsiniz?")
            c1, c2 = st.columns(2)

            if c1.button("🤝 Smeni Təhvil Ver", use_container_width=True):
                st.session_state.handover_expected = float(get_shift_finance_snapshot()["expected_cash"])
                st.session_state.handover_mode = True
                st.rerun()

            if c2.button("🚪 Növbəni Bağla və Çıx", type="primary", use_container_width=True):
                close_shift(st.session_state.user)
                st.session_state.clear()
                st.session_state.logged_in = False
                st.rerun()

        else:
            st.info(f"Sistemə görə kassada olmalıdır: **{st.session_state.handover_expected:.2f} ₼**")
            actual = st.number_input(
                "Kassadakı real nağd (Təhvil verilən):",
                value=float(st.session_state.handover_expected),
                min_value=0.0,
                step=1.0
            )

            c_conf1, c_conf2 = st.columns(2)
            if c_conf1.button("✅ Təsdiqlə və Çıxış Et", type="primary", use_container_width=True):
                try:
                    process_shift_handover(actual, st.session_state.user, "Smen Təhvili (Çıxış) zamanı fərq", "SHIFT_HANDOVER")
                except Exception as e:
                    st.error(f"Xəta: {e}")
                    st.stop()

                st.session_state.clear()
                st.session_state.logged_in = False
                st.rerun()

            if c_conf2.button("Ləğv Et", use_container_width=True):
                st.session_state.handover_mode = False
                st.rerun()

params = st.query_params
if "id" in params:
    render_customer_app(params.get("id"))
    st.stop()

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
if 'low_stock_shown' not in st.session_state: st.session_state.low_stock_shown = False

ensure_schema()

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

    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { background-color: #16191d !important; border: 2px solid #3a4149 !important; border-radius: 8px !important; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5) !important; }
    div[data-baseweb="input"] input { color: #ffffff !important; font-weight: 700 !important; -webkit-text-fill-color: #ffffff !important; background: transparent !important; }
    div[data-baseweb="input"] input::placeholder { color: #7b8896 !important; -webkit-text-fill-color: #7b8896 !important; }
    div[data-baseweb="select"] span { color: #ffffff !important; font-weight: 700 !important; }
    ul[role="listbox"] { background-color: #1e2226 !important; border: 1px solid #3a4149 !important; }
    ul[role="listbox"] li { color: #ffffff !important; }
    
    div[role="dialog"] { background: transparent !important; }
    div[role="dialog"] > div { background: var(--metal-bg) !important; border: 2px solid #ffd700 !important; border-radius: 15px !important; box-shadow: 0 10px 40px rgba(0,0,0,0.9) !important; }
    div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 { color: #ffd700 !important; }
    div[role="dialog"] p, div[role="dialog"] span, div[role="dialog"] label { color: #ffffff !important; }
    div[role="dialog"] header { background: transparent !important; }
    
    div[role="radiogroup"] { gap: 10px; border: none; flex-wrap: wrap; }
    div[role="radiogroup"] > label { 
        background: var(--metal-btn) !important; border: 2px solid #3a4149 !important; border-radius: 8px !important; 
        padding: 10px 20px !important; cursor: pointer; box-shadow: 4px 4px 8px rgba(0,0,0,0.6), inset 1px 1px 2px rgba(255,255,255,0.1) !important; transition: all 0.2s;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; width: 0 !important; height: 0 !important; }
    div[role="radiogroup"] > label p { color: #ffffff !important; font-weight: 800 !important; font-size: 15px !important; font-family: 'Jura', sans-serif !important; margin: 0 !important; display: block !important;}
    div[role="radiogroup"] > label:hover { background: var(--metal-btn-hover) !important; transform: translateY(-2px); }
    
    div[role="radiogroup"] label:has(input:checked),
    div[role="radiogroup"] label[data-checked="true"],
    div[role="radiogroup"] label[aria-checked="true"] { 
        background: var(--accent-gold) !important; 
        border: 2px solid #ffffff !important; 
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.8), inset 2px 2px 5px rgba(255,255,255,0.5) !important;
        transform: scale(1.08) translateY(-3px) !important;
        z-index: 10;
    }
    div[role="radiogroup"] label:has(input:checked) p,
    div[role="radiogroup"] label[data-checked="true"] p,
    div[role="radiogroup"] label[aria-checked="true"] p { color: #000000 !important; font-size: 16px !important; font-weight: 900 !important; }
    
    div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="expander"], div[data-testid="stPopoverBody"] {
        background: var(--metal-panel) !important; border: 2px solid #3a4149 !important; border-radius: 12px !important;
        box-shadow: 6px 6px 12px rgba(0,0,0,0.4), inset 1px 1px 2px rgba(255,255,255,0.05) !important; padding: 15px !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] { 
        background: var(--metal-btn) !important; border: 2px solid #3a4149 !important; border-radius: 10px !important; 
        box-shadow: inset 0 1px 0 #6a7179, 0 5px 10px rgba(0,0,0,0.5) !important; min-height: 70px; transition: all 0.15s;
    }
    button[kind="secondary"] p, button[kind="secondaryFormSubmit"] p, button[kind="secondaryFormSubmit"] div { color: #ffffff !important; font-size: 16px !important; font-weight: 800 !important; font-family: 'Nunito' !important; display: block !important; }
    button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover { background: var(--metal-btn-hover) !important; transform: translateY(-3px); border-color: #7b8896 !important; }
    
    button[kind="primary"], button[kind="primaryFormSubmit"] { 
        background: var(--accent-gold) !important; border: 2px solid #ffd700 !important; border-radius: 10px !important; 
        box-shadow: 0 5px 15px rgba(255, 215, 0, 0.4), inset 2px 2px 5px rgba(255,255,255,0.5) !important; min-height: 50px;
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p, button[kind="primaryFormSubmit"] div { color: #000000 !important; font-weight: 900 !important; font-size: 18px !important; font-family: 'Jura' !important; text-shadow: none !important; display: block !important; }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { background: linear-gradient(160deg, #ffed4d 0%, #ffd700 50%, #e6b800 100%) !important; transform: translateY(-2px); }
    
    hr { border-top: 2px solid #3a4149 !important; opacity: 0.5; }
    .stMetric { background: var(--metal-btn); padding: 15px; border-radius: 10px; border: 2px solid #3a4149; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5); }
    .stMetric label { color: #aaa !important; font-weight: 700; } .stMetric div { color: #ffd700 !important; font-family: 'Jura'; font-weight: 900; }
    
    .pin-box { background-color: #16191d !important; border: 2px solid #3a4149 !important; border-radius: 8px !important; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5) !important; height: 50px; display: flex; align-items: center; justify-content: center; color: #ffd700 !important; font-size: 32px !important; letter-spacing: 15px; margin-bottom: 15px; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

def get_receipt_html_string(cart, total):
    return "<div>Çek HTML...</div>"

@st.dialog("🧾 Çek")
def show_receipt_dialog(cart_data, total_amt, cust_email):
    st.write("Sifariş tamamlandı!")
    st.write(f"Məbləğ: {total_amt} ₼")
    if st.button("Bağla"):
        st.session_state.show_receipt_popup = False
        st.rerun()

if not st.session_state.logged_in:
    check_url_token_login()

if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1.1, 1])
    with c2:
        st.markdown(f"<h1 style='text-align:center;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])

        with t1:
            if 'staff_pin' not in st.session_state:
                st.session_state.staff_pin = ""

            def staff_pad_cb(val):
                if val == 'C':
                    st.session_state.staff_pin = ""
                elif val == '⌫':
                    st.session_state.staff_pin = st.session_state.staff_pin[:-1]
                else:
                    if len(st.session_state.staff_pin) < 10:
                        st.session_state.staff_pin += str(val)

            disp = "• " * len(st.session_state.staff_pin) if st.session_state.staff_pin else "<span style='color:#7b8896; font-size:16px; letter-spacing:2px; font-family:Nunito;'>PIN DAXİL EDİN</span>"
            st.markdown(f"<div class='pin-box'>{disp}</div>", unsafe_allow_html=True)

            for row in [['1','2','3'], ['4','5','6'], ['7','8','9'], ['C','0','⌫']]:
                cols = st.columns(3)
                for i, val in enumerate(row):
                    cols[i].button(val, key=f"spad_{val}", on_click=staff_pad_cb, args=(val,), use_container_width=True)

            st.write("")
            if st.button("Giriş", type="primary", use_container_width=True, key="staff_login_btn"):
                pin = st.session_state.staff_pin
                if not pin:
                    st.error("PIN daxil edin!")
                else:
                    all_staff = run_query("SELECT username, password, role FROM users WHERE role IN ('staff', 'manager')")
                    found = False

                    if not all_staff.empty:
                        for _, r in all_staff.iterrows():
                            if verify_password(pin, r['password']):
                                success, token, error_msg = attempt_login(r['username'], pin)
                                if success:
                                    st.session_state.logged_in = True
                                    st.session_state.user = r['username']
                                    st.session_state.role = r['role']
                                    st.session_state.session_token = token
                                    st.session_state.staff_pin = ""
                                    st.query_params.clear()
                                    found = True
                                    st.rerun()
                                else:
                                    st.error(error_msg or "Giriş xətası")
                                    st.session_state.staff_pin = ""
                                    found = True
                                break

                    if not found:
                        st.error("Yanlış PIN")
                        st.session_state.staff_pin = ""

        with t2:
            with st.form("al"):
                u = st.text_input("User")
                p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    if not u or not p:
                        st.error("İstifadəçi adı və şifrə daxil edin!")
                    else:
                        success, token, error_msg = attempt_login(u, p)
                        if success:
                            ud = run_query("SELECT role FROM users WHERE username=:u", {"u": u})
                            st.session_state.logged_in = True
                            st.session_state.user = u
                            st.session_state.role = ud.iloc[0]['role']
                            st.session_state.session_token = token
                            st.query_params.clear()
                            st.rerun()
                        else:
                            st.error(error_msg or "Səhv ad və ya şifrə")
else:
    s_info = get_shift_status()
    if s_info.get('current_shift_status') == 'Closed' and st.session_state.role in ['staff', 'manager']:
        shift_modal("open")

    if not validate_session():
        st.session_state.clear()
        st.rerun()

    h1, h2, h3 = st.columns([4, 1, 1], vertical_alignment="center")
    with h1:
        st.markdown(f"<h3 style='margin:0;'>👤 {st.session_state.user} | <span style='color:#ffffff !important; font-size:16px;'>{st.session_state.role.upper()}</span></h3>", unsafe_allow_html=True)
    with h2:
        st.button("🔄 YENİLƏ", key="refresh_top", use_container_width=True, type="secondary")
    with h3:
        if st.button("🚪 ÇIXIŞ", type="primary", key="logout_top", use_container_width=True):
            if st.session_state.role == 'staff':
                shift_modal("close")
            else:
                st.session_state.clear()
                st.session_state.logged_in = False
                st.rerun()
    st.divider()

    if not st.session_state.low_stock_shown:
        try:
            low_stock_df = run_query("SELECT name as \"Xammal\", stock_qty as \"Qalıq\", unit as \"Vahid\" FROM ingredients WHERE stock_qty <= 5.0")
            if not low_stock_df.empty:
                @st.dialog("⚠️ DİQQƏT: ANBARDA AZALAN MALLAR VAR!")
                def show_low_stock_dialog(df):
                    st.error("Aşağıdakı malların ehtiyatı (5-dən azdır). Zəhmət olmasa təchizatı təmin edin!")
                    st.dataframe(df, hide_index=True, use_container_width=True)
                    if st.button("✅ Anladım, Bağla", type="primary", use_container_width=True):
                        st.session_state.low_stock_shown = True
                        st.rerun()
                show_low_stock_dialog(low_stock_df)
            else:
                st.session_state.low_stock_shown = True
        except Exception:
            st.session_state.low_stock_shown = True

    # Navigation
    role = st.session_state.role
    tabs_list = []

    if role in ['admin', 'manager', 'staff']:
        tabs_list.append("🏃‍♂️ AL-APAR")

    show_tables_staff = get_setting("staff_show_tables", "TRUE") == "TRUE"
    show_tables_mgr = get_setting("manager_show_tables", "TRUE") == "TRUE"
    if role == 'admin' or (role == 'manager' and show_tables_mgr) or (role == 'staff' and show_tables_staff):
        tabs_list.append("🍽️ MASALAR")

    show_kitchen_staff = get_setting("staff_show_kitchen", "TRUE") == "TRUE"
    if role in ['admin', 'manager'] or (role == 'staff' and show_kitchen_staff):
        tabs_list.append("🍳 Mətbəx")

    if role in ['staff', 'manager', 'admin']:
        tabs_list.append("📊 Z-Hesabat")

    if role in ['admin', 'manager']:
        tabs_list.extend(["💰 Maliyyə", "📦 Anbar", "🍔 Kombolar", "📊 Analitika", "📜 Loglar", "👥 CRM", "🤖 AI Menecer"])

    if role == 'manager':
        if get_setting("manager_perm_menu", "FALSE") == "TRUE":
            tabs_list.append("📋 Menyu")
        if get_setting("manager_perm_recipes", "FALSE") == "TRUE":
            tabs_list.append("📜 Resept")

    if role == 'admin':
        tabs_list.extend(["📋 Menyu", "📜 Resept", "📝 Qeydlər", "⚙️ Ayarlar", "💾 Baza", "QR"])

    tabs_list = sorted(list(set(tabs_list)), key=tabs_list.index)

    if "current_tab" not in st.session_state:
        st.session_state.current_tab = tabs_list[0]

    selected_tab = st.radio(
        "Menu",
        tabs_list,
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav_radio",
        index=tabs_list.index(st.session_state.current_tab) if st.session_state.current_tab in tabs_list else 0
    )

    if selected_tab != st.session_state.current_tab:
        st.session_state.current_tab = selected_tab

    # Routes
    if selected_tab == "🏃‍♂️ AL-APAR":
        render_pos_page()
    elif selected_tab == "🍽️ MASALAR":
        render_tables_page()
    elif selected_tab == "🍳 Mətbəx":
        render_kitchen_page()
    elif selected_tab == "📊 Z-Hesabat":
        render_z_report_page()
    elif selected_tab == "📦 Anbar":
        render_inventory_page()
    elif selected_tab == "🍔 Kombolar":
        render_combos_page()
    elif selected_tab == "💰 Maliyyə":
        render_finance_page()
    elif selected_tab == "📊 Analitika":
        render_analytics_page()
    elif selected_tab == "👥 CRM":
        render_crm_page()
    elif selected_tab == "🤖 AI Menecer":
        render_ai_page()
    elif selected_tab == "📋 Menyu":
        render_menu_page()
    elif selected_tab == "📜 Resept":
        render_recipe_page()
    elif selected_tab == "📝 Qeydlər":
        render_notes_page()
    elif selected_tab == "⚙️ Ayarlar":
        render_settings_page()
    elif selected_tab == "💾 Baza":
        render_database_page()
    elif selected_tab == "QR":
        render_qr_page()
    elif selected_tab == "📜 Loglar":
        render_logs_page()

    st.markdown(f"<div style='text-align:center;color:#545b66;margin-top:50px;font-family:Jura;'>{BRAND_NAME} {VERSION}</div>", unsafe_allow_html=True)
