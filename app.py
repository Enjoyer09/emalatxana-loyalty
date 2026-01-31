import streamlit as st
import pandas as pd
import random
import time
from sqlalchemy import text
import os
import bcrypt
import secrets
import datetime
import math
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from io import BytesIO
import zipfile
import requests
import json
import base64
import streamlit.components.v1 as components

# ==========================================
# === EMALATKHANA POS - V5.54 (SMART ACTIONS) ===
# ==========================================

VERSION = "v5.54 (Smart Action Bar: Batch Delete & Edit Logic)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- CONFIG ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")
ADMIN_DEFAULT_PASS = os.environ.get("ADMIN_PASS", "admin123") 

DEFAULT_TERMS = """<div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
    <h4 style="color: #2E7D32; margin-bottom: 5px;">📜 İSTİFADƏÇİ RAZILAŞMASI</h4>
    <p>Bu loyallıq proqramı "Emalatkhana" tərəfindən təqdim edilir.</p>
</div>"""

COMPLIMENTS = ["Gülüşünüz günümüzü işıqlandırdı! ☀️", "Bu gün möhtəşəm görünürsünüz! ✨", "Sizi yenidən görmək necə xoşdur! ☕", "Uğurlu gün arzulayırıq! 🚀"]
CARTOON_QUOTES = ["Bu gün sənin günündür! 🚀", "Qəhrəman kimi parılda! ⭐", "Bir fincan kofe = Xoşbəxtlik! ☕", "Enerjini topla, dünyanı fəth et! 🌍"]
SPENDERS = ["Abbas", "Nicat", "Elvin", "Sabina", "Samir", "Admin"]

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"
APP_URL = "https://emalatxana.ironwaves.store"

# --- STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'session_token' not in st.session_state: st.session_state.session_token = None
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'show_receipt_popup' not in st.session_state: st.session_state.show_receipt_popup = False
if 'last_receipt_data' not in st.session_state: st.session_state.last_receipt_data = None
if 'anbar_page' not in st.session_state: st.session_state.anbar_page = 0
if 'anbar_rows_per_page' not in st.session_state: st.session_state.anbar_rows_per_page = 20
if 'edit_item_id' not in st.session_state: st.session_state.edit_item_id = None
if 'restock_item_id' not in st.session_state: st.session_state.restock_item_id = None

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;700&display=swap');

    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F8F9FA !important; color: #333 !important; font-family: 'Arial', sans-serif !important; }
    
    div[data-testid="stStatusWidget"] { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }

    div.stButton > button { 
        border-radius: 12px !important; min-height: 80px !important; 
        font-weight: bold !important; font-size: 18px !important; 
        border: 1px solid #ccc !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important; 
    }
    div.stButton > button:active { transform: scale(0.98); }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #43A047, #2E7D32) !important; color: white !important; }

    .cartoon-quote { font-family: 'Comfortaa', cursive; color: #E65100; font-size: 22px; font-weight: 700; text-align: center; margin-bottom: 20px; animation: float 3s infinite; }
    @keyframes float { 0% {transform: translateY(0px);} 50% {transform: translateY(-8px);} 100% {transform: translateY(0px);} }
    .msg-box { background: linear-gradient(45deg, #FF9800, #FFC107); padding: 15px; border-radius: 15px; color: white; font-weight: bold; text-align: center; margin-bottom: 20px; font-family: 'Comfortaa', cursive !important; animation: pulse 2s infinite; }
    @keyframes pulse { 0% {transform: scale(1);} 50% {transform: scale(1.02);} 100% {transform: scale(1);} }

    .stamp-container { display: flex; justify-content: center; margin-bottom: 20px; }
    .stamp-card { background: white; padding: 15px 30px; text-align: center; font-family: 'Courier Prime', monospace; font-weight: bold; transform: rotate(-3deg); border-radius: 12px; border: 4px solid #B71C1C; color: #B71C1C; box-shadow: 0 0 0 4px white, 0 0 0 7px #B71C1C; }

    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; justify-items: center; margin-top: 20px; max-width: 400px; margin-left: auto; margin-right: auto; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.5s ease; }
    .cup-earned { filter: invert(24%) sepia(96%) saturate(1720%) hue-rotate(94deg) brightness(92%) contrast(102%); opacity: 1; transform: scale(1.1); }
    .cup-red-base { filter: invert(18%) sepia(90%) saturate(6329%) hue-rotate(356deg) brightness(96%) contrast(116%); }
    .cup-anim { animation: bounce 1s infinite; }
    .cup-empty { filter: grayscale(100%); opacity: 0.2; }
    @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-5px);} }

    div[data-testid="stRating"] { justify-content: center !important; transform: scale(1.5); }
    div[data-testid="stRating"] svg { fill: #FF0000 !important; color: #FF0000 !important; }
    @media print { body * { visibility: hidden; } #hidden-print-area, #hidden-print-area * { visibility: visible; } #hidden-print-area { position: fixed; left: 0; top: 0; width: 100%; } }
    </style>
""", unsafe_allow_html=True)

# --- DB ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL") or os.environ.get("DATABASE_URL")
    if not db_url: st.error("DB URL Not Found"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

@st.cache_resource
def ensure_schema():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS tables (id SERIAL PRIMARY KEY, label TEXT, is_occupied BOOLEAN DEFAULT FALSE, items TEXT, total DECIMAL(10,2) DEFAULT 0, opened_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_active BOOLEAN DEFAULT FALSE, is_coffee BOOLEAN DEFAULT FALSE, printer_target TEXT DEFAULT 'kitchen', price_half DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, customer_card_id TEXT);"))
        try:
            s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS original_total DECIMAL(10,2) DEFAULT 0"))
            s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS discount_amount DECIMAL(10,2) DEFAULT 0"))
            s.commit()
        except: pass

        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS ingredients (id SERIAL PRIMARY KEY, name TEXT UNIQUE, stock_qty DECIMAL(10,2) DEFAULT 0, unit TEXT, category TEXT, min_limit DECIMAL(10,2) DEFAULT 10, type TEXT DEFAULT 'ingredient', unit_cost DECIMAL(18,5) DEFAULT 0, approx_count INTEGER DEFAULT 0);"))
        try: 
            s.execute(text("ALTER TABLE ingredients ALTER COLUMN unit_cost TYPE DECIMAL(18,5)"))
            s.commit()
        except: pass

        try: s.execute(text("ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'ingredient'")); s.execute(text("ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS unit_cost DECIMAL(18,5) DEFAULT 0")); s.execute(text("ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS approx_count INTEGER DEFAULT 0"))
        except: pass
        
        s.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, amount DECIMAL(10,2), reason TEXT, spender TEXT, source TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS recipes (id SERIAL PRIMARY KEY, menu_item_name TEXT, ingredient_name TEXT, quantity_required DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT, staff_note TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS promo_codes (id SERIAL PRIMARY KEY, code TEXT UNIQUE, discount_percent INTEGER, valid_until DATE, assigned_user_id TEXT, is_used BOOLEAN DEFAULT FALSE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, attached_coupon TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS system_logs (id SERIAL PRIMARY KEY, username TEXT, action TEXT, customer_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedbacks (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS failed_logins (username TEXT PRIMARY KEY, attempt_count INTEGER DEFAULT 0, last_attempt TIMESTAMP, blocked_until TIMESTAMP);"))
        try:
            p_hash = bcrypt.hashpw(ADMIN_DEFAULT_PASS.encode(), bcrypt.gensalt()).decode()
            s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin') ON CONFLICT (username) DO NOTHING"), {"p": p_hash})
            s.commit()
        except: s.rollback()
    return True
ensure_schema()

# --- HELPERS ---
def get_baku_now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=4))).replace(tzinfo=None)
def run_query(q, p=None): return conn.query(q, params=p if p else {}, ttl=0)
def run_action(q, p=None): 
    with conn.session as s: s.execute(text(q), p if p else {}); s.commit()
    return True
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): 
    try: return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
    except: return False
def log_system(user, action, cid=None):
    try: run_action("INSERT INTO system_logs (username, action, customer_id, created_at) VALUES (:u, :a, :c, :t)", {"u":user, "a":action, "c":cid, "t":get_baku_now()})
    except: pass
def get_setting(key, default=""):
    try: return run_query("SELECT value FROM settings WHERE key=:k", {"k":key}).iloc[0]['value']
    except: return default
def set_setting(key, value): run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v", {"k":key, "v":value})
def image_to_base64(image_file): return base64.b64encode(image_file.getvalue()).decode()

def generate_styled_qr(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(image_factory=StyledPilImage, module_drawer=SquareModuleDrawer(), 
                        color_mask=SolidFillColorMask(front_color=(0, 128, 0, 255), back_color=(255, 255, 255, 0)))
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
def generate_custom_qr(data, center_text): return generate_styled_qr(data)

def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return "API_KEY_MISSING"
    try: requests.post("https://api.resend.com/emails", json={"from": f"{BRAND_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}, headers={"Authorization": f"Bearer {RESEND_API_KEY}"}); return "OK"
    except: return "Error"
def format_qty(val): return int(val) if val % 1 == 0 else val

# --- CALLBACKS ---
def clear_customer_data():
    st.session_state.current_customer_ta = None
    if "search_input_ta" in st.session_state:
        st.session_state.search_input_ta = "" 

# --- SECURITY ---
def create_session(username, role):
    token = secrets.token_urlsafe(32)
    run_action("INSERT INTO active_sessions (token, username, role, created_at) VALUES (:t, :u, :r, :c)", {"t":token, "u":username, "r":role, "c":get_baku_now()})
    return token
def validate_session():
    if not st.session_state.session_token: return False
    res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token})
    return not res.empty

@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")
    with st.form("admin_conf_form"):
        pwd = st.text_input("Admin Şifrəsi", type="password")
        if st.form_submit_button("Təsdiqlə"):
            adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
            if not adm.empty and verify_password(pwd, adm.iloc[0]['password']):
                callback(*args); st.success("İcra olundu!"); time.sleep(1); st.rerun()
            else: st.error("Yanlış Şifrə!")

def calculate_smart_total(cart, customer=None, is_table=False):
    total = 0.0; disc_rate = 0.0; current_stars = 0
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'ikram': return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20}
        disc_rate = rates.get(ctype, 0.0)
    
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
    final_total = 0.0
    for i in cart:
        line = i['qty'] * i['price']; total += line
        if i.get('is_coffee'): final_total += (line - (line * disc_rate))
        else: final_total += line
    if is_table: final_total += final_total * 0.07
    return total, final_total, disc_rate, free_cof, 0, 0, False

def get_receipt_html_string(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME); addr = get_setting("receipt_address", "Baku"); phone = get_setting("receipt_phone", "")
    logo = get_setting("receipt_logo_base64"); time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<img src="data:image/png;base64,{logo}" style="width:80px; filter:grayscale(100%);">' if logo else ""
    rows = "".join([f"<tr><td style='border-bottom:1px dashed #000; padding:5px;'>{int(i['qty'])}</td><td style='border-bottom:1px dashed #000; padding:5px;'>{i['item_name']}</td><td style='border-bottom:1px dashed #000; padding:5px; text-align:right;'>{i['qty']*i['price']:.2f}</td></tr>" for i in cart])
    return f"""<div id='receipt-area' style="font-family:'Courier New'; width:300px; margin:0 auto; text-align:center;">{img_tag}<h3>{store}</h3><p>{addr}<br>{phone}</p><p>{time_str}</p><table style="width:100%; text-align:left; border-collapse:collapse;"><tr><th style='border-bottom:1px dashed #000;'>Say</th><th style='border-bottom:1px dashed #000;'>Mal</th><th style='border-bottom:1px dashed #000; text-align:right;'>Məb</th></tr>{rows}</table><h3>YEKUN: {total:.2f} ₼</h3><p>Təşəkkürlər!</p></div>"""

@st.dialog("🧾 Çek")
def show_receipt_dialog(cart_data, total_amt, cust_email):
    html = get_receipt_html_string(cart_data, total_amt)
    components.html(html, height=450, scrolling=True)
    st.markdown(f'<div id="hidden-print-area">{html}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: components.html(f"""<button onclick="window.print()" style="background:#2E7D32;color:white;padding:10px;border-radius:5px;width:100%;">🖨️ ÇAP ET</button>""", height=50)
    with c2: 
        if cust_email and st.button("📧 Email"): send_email(cust_email, "Çekiniz", html); st.success("Getdi!")
    if st.button("❌ Bağla"): st.session_state.show_receipt_popup=False; st.session_state.last_receipt_data=None; st.rerun()

# ==========================================
# === MAIN APP ===
# ==========================================
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]; token = query_params.get("t")
    c1, c2, c3 = st.columns([1,2,1]); logo = get_setting("receipt_logo_base64")
    with c2: 
        if logo: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" width="120"></div>', unsafe_allow_html=True)
    try: df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":card_id})
    except: st.stop()
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token: st.warning("⚠️ QR kod köhnəlib.")
        st.markdown(f"<div class='cartoon-quote'>{random.choice(CARTOON_QUOTES)}</div>", unsafe_allow_html=True)
        notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":card_id})
        for _, n in notifs.iterrows():
            st.markdown(f"<div class='msg-box'>📩 {n['message']}</div>", unsafe_allow_html=True)
            if st.button("Oxudum ✅", key=f"n_{n['id']}"): run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.rerun()
        if not user['is_active']:
            st.info("Xoş Gəldiniz!"); terms = get_setting("customer_rules", DEFAULT_TERMS)
            with st.form("act"):
                em = st.text_input("Email"); dob = st.date_input("Doğum Tarixi", min_value=datetime.date(1950,1,1))
                with st.expander("Qaydalar"): st.markdown(terms, unsafe_allow_html=True)
                if st.form_submit_button("Təsdiqlə"): run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob, "i":card_id}); st.rerun()
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
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            style = ""
            if i == 9: 
                if user['stars'] >= 10: cls = "cup-red-base cup-anim"; style = "opacity: 1;"
                else: op = 0.1 + (user['stars'] * 0.09); cls = "cup-red-base"; style = f"opacity: {op};"
            elif i < user['stars']: cls = "cup-earned"
            else: cls = "cup-empty"
            html += f'<img src="{icon}" class="{cls} coffee-icon-img" style="{style}">'
        st.markdown(html + "</div>", unsafe_allow_html=True)
        if user['stars'] >= 10: st.success("🎉 Təbriklər! Bu kofeniz bizdəndir!")
        st.markdown("<div style='text-align:center; margin-top:20px; font-family:Comfortaa;'><b>Xidmətimizi bəyəndinizmi?</b></div>", unsafe_allow_html=True)
        with st.form("fd"):
            s = st.feedback("stars"); m = st.text_input("Fikriniz...")
            if st.form_submit_button("Göndər") and s: run_action("INSERT INTO feedbacks (card_id,rating,comment,created_at) VALUES (:c,:r,:m,:t)", {"c":card_id,"r":s+1,"m":m,"t":get_baku_now()}); st.success("Təşəkkürlər!")
        st.stop()

if st.session_state.logged_in:
    if not validate_session():
        st.session_state.logged_in=False; st.session_state.session_token=None; st.error("Sessiya bitib."); st.rerun()

if not st.session_state.logged_in:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u = run_query("SELECT * FROM users WHERE role IN ('staff','manager')")
                    for _,r in u.iterrows():
                        if verify_password(p, r['password']):
                            st.session_state.logged_in=True; st.session_state.user=r['username']; st.session_state.role=r['role']; st.session_state.session_token=create_session(r['username'],r['role']); st.rerun()
                    st.error("Səhv PIN")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']; st.session_state.session_token=create_session(u,ud.iloc[0]['role']); st.rerun()
                    else: st.error("Səhv")
else:
    if st.session_state.show_receipt_popup and st.session_state.last_receipt_data:
        show_receipt_dialog(st.session_state.last_receipt_data['cart'], st.session_state.last_receipt_data['total'], st.session_state.last_receipt_data['email'])

    h1, h2, h3 = st.columns([4,1,1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄"): st.rerun()
    with h3: 
        if st.button("🚪", type="primary"): 
            run_action("DELETE FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token}); st.session_state.logged_in=False; st.rerun()
    st.divider()

    role = st.session_state.role
    show_tbl = True
    if role == 'staff': show_tbl = (get_setting("staff_show_tables", "TRUE") == "TRUE")

    tabs_list = []
    if role == 'admin': tabs_list = ["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "💸 Xərclər", "📜 Resept", "📊 Analitika", "📜 Loglar", "👥 CRM", "📋 Menyu", "⚙️ Ayarlar", "💾 Baza", "QR"]
    elif role == 'manager': tabs_list = ["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "💸 Xərclər", "📊 Analitika", "📜 Loglar", "👥 CRM"]
    elif role == 'staff': tabs_list = ["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "Satışlar"] if show_tbl else ["🏃‍♂️ AL-APAR", "Satışlar"]
    tabs = st.tabs(tabs_list)

    def add_to_cart(cart, item):
        for i in cart: 
            if i['item_name'] == item['item_name'] and i.get('status')=='new': i['qty']+=1; return
        cart.append(item)

    def render_menu(cart, key):
        cats = ["Hamısı"] + run_query("SELECT DISTINCT category FROM menu WHERE is_active=TRUE")['category'].tolist()
        sc = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_{key}")
        sql = "SELECT * FROM menu WHERE is_active=TRUE" + (" AND category=:c" if sc!="Hamısı" else "")
        prods = run_query(sql + " ORDER BY price ASC", {"c":sc})
        if not prods.empty:
            groups = {}
            for _, r in prods.iterrows():
                n = r['item_name']; base = n
                for s in [" S", " M", " L", " XL", " Single", " Double"]:
                    if n.endswith(s): base = n[:-len(s)]; break
                if base not in groups: groups[base] = []
                groups[base].append(r)
            cols = st.columns(4); i=0
            for base, items in groups.items():
                with cols[i%4]:
                    if len(items) > 1:
                        @st.dialog(f"{base}")
                        def show_variants(its):
                            for it in its:
                                if st.button(f"{it['item_name']} - {it['price']}₼", key=f"v_{it['id']}_{key}", use_container_width=True):
                                    add_to_cart(cart, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'status':'new'}); st.rerun()
                        if st.button(f"{base} ▾", key=f"grp_{base}_{key}", use_container_width=True): show_variants(items)
                    else:
                        r = items[0]
                        if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}", use_container_width=True):
                            add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'status':'new'}); st.rerun()
                i+=1

    with tabs[0]: # AL-APAR
        c1, c2 = st.columns([1.5, 3])
        with c1:
            st.info("🧾 Al-Apar")
            with st.form("scta", clear_on_submit=True):
                code = st.text_input("Müştəri", label_visibility="collapsed", placeholder="Skan...", key="search_input_ta")
                if st.form_submit_button("🔍") or code:
                    try: 
                        cid = code.split("id=")[1].split("&")[0] if "id=" in code else code
                        r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                        if not r.empty: 
                            st.session_state.current_customer_ta = r.iloc[0].to_dict()
                            cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id":cid})
                            if not cps.empty: st.toast(f"🎁 Aktiv Promo Var: {cps.iloc[0]['coupon_type']}")
                            else: st.toast(f"✅ Müştəri: {cid}")
                            st.rerun()
                        else: st.error("Tapılmadı")
                    except: pass
            
            cust = st.session_state.current_customer_ta
            if cust: 
                c_head, c_del = st.columns([4,1])
                c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                c_del.button("❌", key="clear_cust", on_click=clear_customer_data)

            raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust)
            if st.session_state.cart_takeaway:
                for i, item in enumerate(st.session_state.cart_takeaway):
                    c_n, c_d, c_q, c_u = st.columns([3, 1, 1, 1])
                    with c_n: st.write(f"{item['item_name']}")
                    with c_d: 
                        if st.button("➖", key=f"dec_{i}"): 
                            if item['qty'] > 1: item['qty'] -= 1
                            else: st.session_state.cart_takeaway.pop(i)
                            st.rerun()
                    with c_q: st.write(f"x{item['qty']}")
                    with c_u:
                        if st.button("➕", key=f"inc_{i}"): item['qty'] += 1; st.rerun()

            st.markdown(f"<h2 style='text-align:right;color:#E65100'>{final:.2f} ₼</h2>", unsafe_allow_html=True)
            if is_ikram: st.success("🎁 İKRAM")
            elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
            pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True)
            if st.button("✅ ÖDƏNİŞ", type="primary", use_container_width=True):
                if not st.session_state.cart_takeaway: st.error("Boşdur"); st.stop()
                try:
                    with conn.session as s:
                        for it in st.session_state.cart_takeaway:
                            recs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                            for r in recs:
                                res = s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n AND stock_qty >= :q"), {"q":float(r[1])*it['qty'], "n":r[0]})
                                if res.rowcount == 0: raise Exception(f"Stok yoxdur: {r[0]}")
                        items_str = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_takeaway])
                        
                        discount_amt = raw - final
                        s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount) VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da)"), 
                                  {"i":items_str,"t":final,"p":("Cash" if pm=="Nəğd" else "Card"),"c":st.session_state.user,"time":get_baku_now(),"cid":cust['card_id'] if cust else None, "ot":raw, "da":discount_amt})
                        
                        if cust and not is_ikram:
                            cf_cnt = sum([x['qty'] for x in st.session_state.cart_takeaway if x.get('is_coffee')])
                            new_s = (cust['stars'] + cf_cnt) - (free * 10)
                            s.execute(text("UPDATE customers SET stars=:s WHERE card_id=:id"), {"s":new_s, "id":cust['card_id']})
                        s.commit()
                    
                    st.session_state.last_receipt_data = {'cart':st.session_state.cart_takeaway.copy(), 'total':final, 'email':cust['email'] if cust else None}
                    
                    # AUTO CLEAR
                    st.session_state.cart_takeaway = []
                    clear_customer_data()
                    
                    st.session_state.show_receipt_popup=True
                    st.rerun()
                except Exception as e: st.error(f"Xəta: {e}")
        with c2: render_menu(st.session_state.cart_takeaway, "ta")

    if show_tbl or role != 'staff':
        with tabs[1]:
            if st.session_state.selected_table:
                tbl = st.session_state.selected_table
                if st.button("⬅️ Qayıt"): st.session_state.selected_table=None; st.session_state.cart_table=[]; st.rerun()
                st.markdown(f"### {tbl['label']}")
                c1, c2 = st.columns([1.5, 3])
                with c1:
                    raw, final, _, _, _, serv, _ = calculate_smart_total(st.session_state.cart_table, is_table=True)
                    for i, it in enumerate(st.session_state.cart_table): st.write(f"{it['item_name']} x{it['qty']}")
                    st.metric("Yekun", f"{final:.2f} ₼"); st.button("🔥 Mətbəxə", on_click=lambda: (run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id", {"i":json.dumps(st.session_state.cart_table), "t":final, "id":tbl['id']}), st.success("OK")))
                    if st.button("✅ Ödəniş (Masa)", type="primary"):
                        try:
                            with conn.session as s:
                                s.execute(text("UPDATE tables SET is_occupied=FALSE, items='[]', total=0 WHERE id=:id"), {"id":tbl['id']})
                                s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, original_total, discount_amount) VALUES (:i,:t,'Table',:c,:tm, :ot, 0)"), 
                                          {"i":"Table Order", "t":final, "c":st.session_state.user, "tm":get_baku_now(), "ot":final})
                                s.commit()
                            st.session_state.selected_table=None; st.session_state.cart_table=[]; st.rerun()
                        except: st.error("Xəta")
                with c2: render_menu(st.session_state.cart_table, "tb")
            else:
                if role in ['admin','manager']:
                    with st.expander("🛠️ Masa İdarə"):
                        nl = st.text_input("Ad"); 
                        if st.button("Yarat"): run_action("INSERT INTO tables (label) VALUES (:l)", {"l":nl}); st.rerun()
                        dl = st.selectbox("Sil", run_query("SELECT label FROM tables")['label'].tolist() if not run_query("SELECT label FROM tables").empty else [])
                        if st.button("Sil"): admin_confirm_dialog("Silinsin?", lambda: run_action("DELETE FROM tables WHERE label=:l", {"l":dl}))
                df_t = run_query("SELECT * FROM tables ORDER BY id"); cols = st.columns(3)
                for i, r in df_t.iterrows():
                    with cols[i%3]:
                        if st.button(f"{r['label']}\n{r['total']} ₼", key=f"t_{r['id']}", type="primary" if r['is_occupied'] else "secondary", use_container_width=True):
                            st.session_state.selected_table = r.to_dict(); st.session_state.cart_table = json.loads(r['items']) if r['items'] else []; st.rerun()

    # --- ANBAR (CHECKBOX LOGIC + ACTION BAR) ---
    if role in ['admin','manager']:
        with tabs[2]:
            c1, c2 = st.columns([3,1])
            search_query = st.text_input("🔍 Axtarış (Bütün Anbar)...", placeholder="Malın adı...")
            
            # 1. GET DATA
            if search_query:
                df_i = run_query("SELECT id, name, stock_qty, unit, unit_cost, approx_count, category, type FROM ingredients WHERE name ILIKE :s ORDER BY name", {"s":f"%{search_query}%"})
                asset_val = (df_i['stock_qty'] * df_i['unit_cost']).sum()
            else:
                itype = st.radio("Növ", ["Hamısı", "Ərzaq", "Sərfiyyat"], horizontal=True)
                if itype == "Hamısı":
                    df_i = run_query("SELECT id, name, stock_qty, unit, unit_cost, approx_count, category, type FROM ingredients ORDER BY name")
                else:
                    db_type = 'ingredient' if itype == "Ərzaq" else 'consumable'
                    df_i = run_query("SELECT id, name, stock_qty, unit, unit_cost, approx_count, category, type FROM ingredients WHERE type=:t ORDER BY name", {"t":db_type})
                asset_val = (df_i['stock_qty'] * df_i['unit_cost']).sum()

            st.markdown(f"### 📦 Anbar (Cəmi: {asset_val:.2f} ₼)")

            # 2. PAGINATION
            rows_per_page = st.selectbox("Səhifədə neçə mal olsun?", [20, 40, 60], index=0)
            if rows_per_page != st.session_state.anbar_rows_per_page:
                st.session_state.anbar_rows_per_page = rows_per_page
                st.session_state.anbar_page = 0
            
            total_rows = len(df_i)
            total_pages = math.ceil(total_rows / rows_per_page)
            start_idx = st.session_state.anbar_page * rows_per_page
            end_idx = start_idx + rows_per_page
            
            df_page = df_i.iloc[start_idx:end_idx].copy()
            df_page['Total Value'] = df_page['stock_qty'] * df_page['unit_cost']
            
            # 3. PREPARE EDITOR
            df_page.insert(0, "Seç", False)
            locked_cols = ["id", "name", "stock_qty", "unit", "unit_cost", "approx_count", "category", "Total Value", "type"]
            
            # 4. SHOW EDITOR
            edited_df = st.data_editor(
                df_page, 
                hide_index=True, 
                column_config={
                    "Seç": st.column_config.CheckboxColumn(required=True),
                    "unit_cost": st.column_config.NumberColumn(format="%.5f"),
                    "Total Value": st.column_config.NumberColumn(format="%.2f")
                },
                disabled=locked_cols,
                use_container_width=True,
                key="anbar_editor"
            )

            # 5. GET SELECTION
            sel_rows = edited_df[edited_df["Seç"]]
            sel_ids = sel_rows['id'].tolist()
            sel_count = len(sel_ids)

            # 6. ACTION BAR
            st.divider()
            ab1, ab2, ab3 = st.columns(3)
            
            # BUTTON: Mədaxil (Active only if 1 selected)
            with ab1:
                if sel_count == 1:
                    if st.button("➕ Seçilənə Mədaxil", use_container_width=True, type="secondary"):
                        st.session_state.restock_item_id = int(sel_ids[0])
                        st.rerun()
                else:
                    st.button("➕ Seçilənə Mədaxil", disabled=True, use_container_width=True)

            # BUTTON: Düzəliş (Active only if 1 selected)
            with ab2:
                if sel_count == 1 and role == 'admin':
                    if st.button("✏️ Seçilənə Düzəliş", use_container_width=True, type="secondary"):
                        st.session_state.edit_item_id = int(sel_ids[0])
                        st.rerun()
                else:
                    st.button("✏️ Seçilənə Düzəliş", disabled=True, use_container_width=True)

            # BUTTON: Sil (Active if >= 1 selected)
            with ab3:
                if sel_count > 0 and role == 'admin':
                    @st.dialog("⚠️ Silinmə Təsdiqi")
                    def confirm_batch_delete(ids):
                        st.warning(f"{len(ids)} ədəd mal silinəcək! Bu əməliyyat geri qaytarılmır.")
                        if st.button("Təsdiq Edirəm", type="primary"):
                            for i in ids:
                                run_action("DELETE FROM ingredients WHERE id=:id", {"id":int(i)})
                            st.success("Silindi!")
                            time.sleep(1)
                            st.rerun()
                    
                    if st.button(f"🗑️ Sil ({sel_count})", use_container_width=True, type="primary"):
                        confirm_batch_delete(sel_ids)
                else:
                    st.button("🗑️ Sil", disabled=True, use_container_width=True)

            # 7. DIALOGS (TRIGGERED BY STATE)
            if st.session_state.restock_item_id:
                # Fetch fresh data for the item
                r_item = run_query("SELECT * FROM ingredients WHERE id=:id", {"id":st.session_state.restock_item_id})
                if not r_item.empty:
                    row = r_item.iloc[0]
                    @st.dialog("➕ Mədaxil")
                    def show_restock(r):
                        st.write(f"**{r['name']}**")
                        with st.form("rs_form", clear_on_submit=True):
                            c1, c2 = st.columns(2)
                            packs = c1.number_input("Neçə ədəd/qutu?", 1)
                            per_pack = c2.number_input(f"Birinin Çəkisi ({r['unit']})", min_value=0.001, step=0.001, value=1.0, format="%.3f")
                            tot_price = st.number_input("Yekun Məbləğ (AZN)", 0.0)
                            if st.form_submit_button("Təsdiq"):
                                total_new_qty = packs * per_pack
                                new_cost = tot_price / total_new_qty if total_new_qty > 0 else r['unit_cost']
                                run_action("UPDATE ingredients SET stock_qty=stock_qty+:q, unit_cost=:uc, approx_count=:ac WHERE id=:id", 
                                           {"q":total_new_qty,"id":int(r['id']), "uc":new_cost, "ac":packs})
                                st.session_state.restock_item_id = None
                                st.rerun()
                    show_restock(row)
                else:
                    st.session_state.restock_item_id = None # Item gone

            if st.session_state.edit_item_id:
                r_item = run_query("SELECT * FROM ingredients WHERE id=:id", {"id":st.session_state.edit_item_id})
                if not r_item.empty:
                    row = r_item.iloc[0]
                    @st.dialog("✏️ Düzəliş")
                    def show_edit(r):
                        with st.form("ed_form"):
                            en = st.text_input("Ad", r['name'])
                            ec = st.text_input("Kateqoriya", r['category'])
                            eu = st.selectbox("Vahid", ["KQ", "L", "ƏDƏD"], index=["KQ", "L", "ƏDƏD"].index(r['unit']) if r['unit'] in ["KQ", "L", "ƏDƏD"] else 0)
                            et = st.selectbox("Növ", ["ingredient","consumable"], index=0 if r['type']=='ingredient' else 1)
                            ecost = st.number_input("Maya Dəyəri", value=float(r['unit_cost']), format="%.5f")
                            if st.form_submit_button("Yadda Saxla"):
                                run_action("UPDATE ingredients SET name=:n, category=:c, unit=:u, unit_cost=:uc, type=:t WHERE id=:id", 
                                           {"n":en, "c":ec, "u":eu, "uc":ecost, "t":et, "id":int(r['id'])})
                                st.session_state.edit_item_id = None
                                st.rerun()
                    show_edit(row)
                else:
                    st.session_state.edit_item_id = None

            # PAGINATION CONTROLS (Moved to bottom)
            pc1, pc2, pc3 = st.columns([1,2,1])
            with pc1:
                if st.button("⬅️ Əvvəlki", disabled=(st.session_state.anbar_page == 0)):
                    st.session_state.anbar_page -= 1
                    st.rerun()
            with pc2:
                st.markdown(f"<div style='text-align:center; padding-top:10px;'>Səhifə {st.session_state.anbar_page + 1} / {max(1, total_pages)}</div>", unsafe_allow_html=True)
            with pc3:
                if st.button("Növbəti ➡️", disabled=(st.session_state.anbar_page >= total_pages - 1)):
                    st.session_state.anbar_page += 1
                    st.rerun()

            with st.expander("📤 İmport / Export"):
                if st.button("📤 Export"): out = BytesIO(); run_query("SELECT * FROM ingredients").to_excel(out, index=False); st.download_button("⬇️ Endir", out.getvalue(), "anbar.xlsx")
                upl = st.file_uploader("📥 Import", type="xlsx")
                if upl and st.button("Yüklə"):
                    try:
                        df_imp = pd.read_excel(upl); df_imp['type'] = 'ingredient'
                        for _, r in df_imp.iterrows(): run_action("INSERT INTO ingredients (name, stock_qty, unit, category, type, unit_cost) VALUES (:n, :s, :u, :c, :t, :uc) ON CONFLICT (name) DO UPDATE SET stock_qty=ingredients.stock_qty+:s, unit_cost=:uc", r.to_dict())
                        st.success("Yükləndi!"); st.rerun()
                    except: st.error("Format Xətası")
            
            if role == 'admin':
                with st.expander("📂 Kateqoriya İdarəetməsi"):
                    all_cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist()
                    t1, t2 = st.tabs(["Düzəliş Et", "Sil"])
                    with t1:
                        old_c = st.selectbox("Köhnə Ad", all_cats, key="ren_old")
                        new_c = st.text_input("Yeni Ad", key="ren_new")
                        if st.button("Dəyişdir"):
                            run_action("UPDATE ingredients SET category=:n WHERE category=:o", {"n":new_c, "o":old_c}); st.success("Hazır!"); st.rerun()
                    with t2:
                        del_c = st.selectbox("Silinəcək", all_cats, key="del_cat")
                        if st.button("Kateqoriyanı Sil (Mallar Qalsın)"):
                            run_action("UPDATE ingredients SET category='Təyinsiz' WHERE category=:o", {"o":del_c}); st.success("Silindi!"); st.rerun()

                with st.expander("➕ Yeni Mal (Qutu ilə)"):
                    with st.form("ninv", clear_on_submit=True):
                        n = st.text_input("Ad (Məs: Tac Şəkər Tozu)")
                        c1, c2, c3 = st.columns(3)
                        packs = c1.number_input("Qutu/Paçka Sayı", 1)
                        per_pack = c2.number_input("Birinin Çəkisi", min_value=0.001, step=0.001, format="%.3f")
                        u = c3.selectbox("Vahid", ["KQ", "L", "ƏDƏD"])
                        tot_price = st.number_input("Yekun Ödənilən Məbləğ (AZN)", 0.0)
                        typ = st.selectbox("Növ", ["Ərzaq","Sərfiyyat"])
                        cats = ["Yeni..."] + run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist()
                        c_sel = st.selectbox("Kateqoriya", cats); c_new = st.text_input("Yeni Kateqoriya") if c_sel == "Yeni..." else c_sel
                        
                        if st.form_submit_button("Yarat"): 
                            check = run_query("SELECT id FROM ingredients WHERE name ILIKE :n", {"n":n.strip()})
                            if not check.empty:
                                st.error("⚠️ Bu adda mal artıq mövcuddur! Axtarışdan istifadə edin.")
                            else:
                                total_qty = packs * per_pack
                                unit_cost = tot_price / total_qty if total_qty > 0 else 0
                                f_type = 'ingredient' if typ=="Ərzaq" else 'consumable'
                                run_action("INSERT INTO ingredients (name, stock_qty, unit, category, type, unit_cost, approx_count) VALUES (:n,:q,:u,:c,:t,:uc,:ac)", 
                                           {"n":n.strip(),"q":total_qty,"u":u,"c":c_new,"t":f_type,"uc":unit_cost,"ac":packs})
                                st.rerun()

    # --- EXPENSES ---
    if role in ['admin','manager']:
        with tabs[3]:
            st.subheader("💸 Xərclər")
            with st.form("new_exp", clear_on_submit=True):
                c1,c2 = st.columns(2)
                amt = c1.number_input("Məbləğ (AZN)", 0.0); rsn = c2.text_input("Təyinat (Səbəb)")
                who = c1.selectbox("Xərcləyən", SPENDERS); src = c2.radio("Növ", ["Kassadan (Cash)", "Cibdən (Pocket)"])
                if st.form_submit_button("Əlavə Et"):
                    run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, :r, :s, :src)", {"a":amt,"r":rsn,"s":who,"src":src}); st.success("Yazıldı!"); st.rerun()
            exp_df = run_query("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50")
            if role == 'admin':
                exp_df.insert(0, "Seç", False)
                ed_ex = st.data_editor(exp_df, hide_index=True)
                del_ex = ed_ex[ed_ex["Seç"]]['id'].tolist()
                if del_ex and st.button("Seçilən Xərcləri Sil"):
                    admin_confirm_dialog("Silinsin?", lambda: [run_action("DELETE FROM expenses WHERE id=:id", {"id":i}) for i in del_ex])
            else: st.dataframe(exp_df, hide_index=True)

    if role == 'admin':
        with tabs[4]: # RESEPT
            st.subheader("📜 Resept")
            sel_prod = st.selectbox("Məhsul", ["(Seçin)"] + run_query("SELECT item_name FROM menu WHERE is_active=TRUE")['item_name'].tolist())
            if sel_prod != "(Seçin)":
                recs = run_query("SELECT id, ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:n", {"n":sel_prod})
                st.data_editor(recs, hide_index=True, disabled=True, num_rows="fixed")
                with st.form("add_rec", clear_on_submit=True):
                    s_i = st.selectbox("Xammal", run_query("SELECT name FROM ingredients")['name'].tolist()); s_q = st.number_input("Miqdar")
                    if st.form_submit_button("Əlavə Et"): run_action("INSERT INTO recipes (menu_item_name,ingredient_name,quantity_required) VALUES (:m,:i,:q)",{"m":sel_prod,"i":s_i,"q":s_q}); st.rerun()

    # --- ANALITIKA (SMART EMAIL + PRO REPORT) ---
    if role != 'staff':
        idx = 5 if role == 'admin' else 4
        with tabs[idx]:
            st.subheader("📊 Analitika & Mənfəəti")
            
            with st.container():
                c_mail, c_btn = st.columns([3,1])
                target_email = c_mail.text_input("Hesabat Emaili", value=get_setting("admin_email", DEFAULT_SENDER_EMAIL))
                if c_btn.button("📩 Gündəlik Hesabatı Göndər (08:00-01:00)"):
                    now = get_baku_now()
                    start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
                    end_time = (now + datetime.timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0) if now.hour >= 8 else now.replace(hour=1, minute=0, second=0, microsecond=0)
                    if now.hour < 8: start_time -= datetime.timedelta(days=1)
                    
                    # Month Start
                    month_start = now.replace(day=1, hour=0, minute=0, second=0)

                    # Query for Daily Report
                    q_rep = """
                        SELECT s.created_at, s.cashier, s.items, s.original_total, s.discount_amount, s.total,
                               COALESCE(c.type, 'Standart') as status
                        FROM sales s 
                        LEFT JOIN customers c ON s.customer_card_id = c.card_id 
                        WHERE s.created_at BETWEEN :s AND :e
                        ORDER BY s.created_at DESC
                    """
                    rep_data = run_query(q_rep, {"s":start_time, "e":end_time})
                    
                    # Query for Monthly Total
                    q_month = "SELECT SUM(total) as m_total FROM sales WHERE created_at >= :ms"
                    m_total = run_query(q_month, {"ms":month_start}).iloc[0]['m_total'] or 0.0

                    if not rep_data.empty:
                        d_total = rep_data['total'].sum()
                        
                        html_table = """
                        <table border='1' style='border-collapse:collapse; width:100%; font-family:Arial, sans-serif;'>
                            <tr style='background-color:#f2f2f2;'>
                                <th>SAAT</th><th>KASSIR</th><th>MALLAR</th><th>MEBLEG</th><th>ENDIRIM</th><th>CEMI</th><th>STATUS</th>
                            </tr>
                        """
                        for _, r in rep_data.iterrows():
                            # Fallback if original_total is 0 (old data)
                            orig = r['original_total'] if r['original_total'] > 0 else r['total']
                            disc = r['discount_amount']
                            
                            html_table += f"<tr><td>{r['created_at'].strftime('%H:%M')}</td><td>{r['cashier']}</td><td>{r['items']}</td><td>{orig:.2f}</td><td>{disc:.2f}</td><td>{r['total']:.2f}</td><td>{r['status']}</td></tr>"
                        
                        html_table += "</table>"
                        html_table += f"<h3 style='text-align:right;'>📅 Bu Günün Cəmi: {d_total:.2f} AZN</h3>"
                        html_table += f"<h3 style='text-align:right; color:#2E7D32;'>📅 Bu Ayın Cəmi: {m_total:.2f} AZN</h3>"

                        send_email(target_email, f"Günlük Hesabat ({start_time.date()})", html_table)
                        st.success("Hesabat göndərildi!")
                    else:
                        st.warning("Bu aralıqda satış yoxdur.")

            st.divider()
            c1, c2 = st.columns(2); d1 = c1.date_input("Start"); d2 = c2.date_input("End")
            t1 = c1.time_input("Saat Başla", datetime.time(8,0)); t2 = c2.time_input("Saat Bit (01:00 = Ertəsi)", datetime.time(1,0))
            ts_start = datetime.datetime.combine(d1, t1)
            ts_end = datetime.datetime.combine(d2 + datetime.timedelta(days=1 if t2 < t1 else 0), t2)
            sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
            exps = run_query("SELECT * FROM expenses WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
            rev = sales['total'].sum()
            cost = exps['amount'].sum()
            profit = rev - cost
            c1,c2,c3 = st.columns(3)
            c1.metric("Toplam Satış", f"{rev:.2f} ₼")
            c2.metric("Toplam Xərc", f"{cost:.2f} ₼")
            c3.metric("Xalis (Cash Flow)", f"{profit:.2f} ₼", delta_color="normal")
            st.caption("Satışlar")
            st.dataframe(sales, hide_index=True)

    if role == 'staff':
        with tabs[-1]:
            now = get_baku_now(); today_start = now.replace(hour=0,minute=0,second=0)
            daily_sales = run_query("SELECT total FROM sales WHERE cashier=:u AND created_at >= :d", {"u":st.session_state.user, "d":today_start})
            total_today = daily_sales['total'].sum() if not daily_sales.empty else 0.0
            st.metric("BUGÜN", f"{total_today:.2f} ₼")
            q = """SELECT s.id, s.created_at, s.items, s.total, s.payment_method, COALESCE(c.email, c.type, 'Qonaq') as Customer FROM sales s LEFT JOIN customers c ON s.customer_card_id = c.card_id WHERE s.cashier = :u ORDER BY s.created_at DESC LIMIT 50"""
            mys = run_query(q, {"u":st.session_state.user})
            display_df = mys[['created_at', 'items', 'total', 'payment_method', 'customer']].copy()
            display_df.columns = ['Saat', 'Mallar', 'Məbləğ', 'Ödəniş', 'Müştəri']
            st.dataframe(display_df, hide_index=True, use_container_width=True)

    if role in ['admin','manager']:
        with tabs[idx+1]: st.dataframe(run_query("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 100"), hide_index=True)

    if role != 'staff':
        idx_crm = 7 if role == 'admin' else 6
        with tabs[idx_crm]:
            st.subheader("👥 CRM")
            cust_df = run_query("SELECT card_id, type, stars, email FROM customers"); cust_df.insert(0, "Seç", False)
            ed_cust = st.data_editor(cust_df, hide_index=True)
            sel_cust_ids = ed_cust[ed_cust["Seç"]]['card_id'].tolist()
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                msg = st.text_area("Ekran Mesajı")
                promo_list = ["(Kuponsuz)"] + run_query("SELECT code FROM promo_codes")['code'].tolist()
                sel_promo = st.selectbox("Promo Yapışdır", promo_list)
                if st.button("📢 Seçilənlərə Göndər / Tətbiq Et"):
                    if sel_cust_ids:
                        for cid in sel_cust_ids:
                            if msg: run_action("INSERT INTO notifications (card_id, message) VALUES (:c, :m)", {"c":cid, "m":msg})
                            if sel_promo != "(Kuponsuz)": run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:c, :t)", {"c":cid, "t":sel_promo})
                        st.success("OK!")
                    else: st.warning("Seçin!")
            with c2:
                em_sub = st.text_input("Email Başlıq"); em_body = st.text_area("Email Mətn")
                if st.button("📧 Email Göndər"):
                    if sel_cust_ids:
                        emails = run_query(f"SELECT email FROM customers WHERE card_id IN ({','.join([repr(x) for x in sel_cust_ids])})")['email'].tolist()
                        for e in emails: 
                            if e: send_email(e, em_sub, em_body)
                        st.success("OK!")
            if role == 'admin':
                with st.expander("🎫 Yeni Promo Kod"):
                    with st.form("pc"):
                        code = st.text_input("Kod"); perc = st.number_input("Faiz", 1, 100)
                        if st.form_submit_button("Yarat"): run_action("INSERT INTO promo_codes (code, discount_percent) VALUES (:c, :p)", {"c":code, "p":perc}); st.success("Hazır!")
                st.dataframe(run_query("SELECT * FROM promo_codes"), hide_index=True)

    if role == 'admin':
        with tabs[8]: # MENU
            st.subheader("📋 Menyu")
            with st.form("nm", clear_on_submit=True):
                n=st.text_input("Ad (Məs: Americano S)"); p=st.number_input("Qiymət"); c=st.text_input("Kat"); ic=st.checkbox("Kofe?")
                if st.form_submit_button("Yarat"): 
                    run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee) VALUES (:n,:p,:c,TRUE,:ic)", {"n":n,"p":p,"c":c,"ic":ic}); st.rerun()
            
            # MENU DELETE LOGIC
            ml = run_query("SELECT * FROM menu")
            ml.insert(0, "Seç", False)
            ed_m = st.data_editor(ml, hide_index=True, num_rows="fixed")
            to_del_m = ed_m[ed_m["Seç"]]['id'].tolist()
            if to_del_m and st.button("🚨 Seçilənləri Menyudan Sil"): 
                admin_confirm_dialog("Menyudan Sil?", lambda: [run_action("DELETE FROM menu WHERE id=:id", {"id":i}) for i in to_del_m])

        with tabs[9]: # SETTINGS
            st.subheader("⚙️ Ayarlar")
            with st.expander("🔑 Şifrə Dəyişmə"):
                users = run_query("SELECT username FROM users")
                sel_u_pass = st.selectbox("İşçi Seç", users['username'].tolist())
                new_pass = st.text_input("Yeni Şifrə", type="password")
                if st.button("Şifrəni Yenilə"):
                    run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_pass), "u":sel_u_pass}); st.success("Yeniləndi!")
            with st.expander("👥 İşçi İdarə"):
                with st.form("nu"):
                    u = st.text_input("İstifadəçi"); p = st.text_input("Şifrə"); r = st.selectbox("Rol", ["staff","manager","admin"])
                    if st.form_submit_button("Yarat"): run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r) ON CONFLICT (username) DO NOTHING", {"u":u, "p":hash_password(p), "r":r}); st.success("OK"); st.rerun()
                du = st.selectbox("Silinəcək", users['username'].tolist()); 
                if st.button("İşçini Sil"): admin_confirm_dialog(f"Sil: {du}?", lambda: run_action("DELETE FROM users WHERE username=:u", {"u":du}))
            with st.expander("🔧 Sistem"):
                st_tbl = st.checkbox("Staff Masaları Görsün?", value=(get_setting("staff_show_tables","TRUE")=="TRUE"))
                if st.button("Yadda Saxla"): set_setting("staff_show_tables", "TRUE" if st_tbl else "FALSE"); st.rerun()
                # --- ID REPAIR BUTTON ---
                if st.button("🛠️ Bazanı Düzəlt (Reset IDs)"):
                    try: 
                        run_action("SELECT setval('ingredients_id_seq', (SELECT MAX(id) FROM ingredients))")
                        st.success("Baza düzəldildi! İndi 'Yeni Mal' əlavə edə bilərsiniz.")
                    except Exception as e: st.error(f"Xəta: {e}")
                
                rules = st.text_area("Qaydalar", value=get_setting("customer_rules", DEFAULT_TERMS))
                if st.button("Qaydaları Yenilə"): set_setting("customer_rules", rules); st.success("Yeniləndi")
            lg = st.file_uploader("Logo"); 
            if lg: set_setting("receipt_logo_base64", image_to_base64(lg)); st.success("Yükləndi")

        with tabs[10]: # BAZA
             c1, c2 = st.columns(2)
             with c1:
                 if st.button("FULL BACKUP"):
                    out = BytesIO(); 
                    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                        for t in ["users","menu","sales","ingredients","recipes","customers","notifications","settings","system_logs","tables","promo_codes","customer_coupons","expenses"]: 
                            try: run_query(f"SELECT * FROM {t}").to_excel(writer, sheet_name=t, index=False)
                            except: pass
                    st.download_button("Endir", out.getvalue(), "backup.xlsx")
             with c2:
                 rf = st.file_uploader("Restore (.xlsx)")
                 if rf and st.button("Bərpa Et"):
                     try:
                         xls = pd.ExcelFile(rf)
                         for t in xls.sheet_names: 
                             run_action(f"DELETE FROM {t}"); pd.read_excel(xls, t).to_sql(t, conn.engine, if_exists='append', index=False)
                         st.success("Bərpa Olundu!"); st.rerun()
                     except: st.error("Xəta")
        
        with tabs[11]: # QR
            st.subheader("QR Kodlar")
            cnt = st.number_input("Say",1,50); kt = st.selectbox("Növ", ["Golden (5%)","Platinum (10%)","Elite (20%)","Thermos (20%)","Ikram (100%)"])
            if st.button("QR Yarat"):
                type_map = {"Golden (5%)":"golden", "Platinum (10%)":"platinum", "Elite (20%)":"elite", "Thermos (20%)":"thermos", "Ikram (100%)":"ikram"}
                generated_qrs = []
                for _ in range(cnt):
                    cid = str(random.randint(10000000,99999999)); tok = secrets.token_hex(8)
                    run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :s)", {"i":cid, "t":type_map[kt], "s":tok})
                    url = f"{APP_URL}/?id={cid}&t={tok}"
                    img_bytes = generate_styled_qr(url)
                    generated_qrs.append((cid, img_bytes))
                
                if cnt <= 3:
                    cols = st.columns(cnt)
                    for idx, (cid, img) in enumerate(generated_qrs):
                        with cols[idx]:
                            st.image(img, caption=f"{cid} ({kt})")
                            st.download_button(f"⬇️ {cid}", img, f"{cid}.png", "image/png")
                else:
                    zip_buf = BytesIO()
                    with zipfile.ZipFile(zip_buf, "w") as zf:
                        for cid, img in generated_qrs:
                            zf.writestr(f"{cid}_{type_map[kt]}.png", img)
                    st.success(f"{cnt} QR Kod yaradıldı!")
                    st.download_button("📦 Hamsını Endir (ZIP)", zip_buf.getvalue(), "qrcodes.zip", "application/zip")

    st.markdown(f"<div style='text-align:center;color:#aaa;margin-top:50px;'>Ironwaves POS {VERSION}</div>", unsafe_allow_html=True)
