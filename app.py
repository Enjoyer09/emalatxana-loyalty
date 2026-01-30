import streamlit as st
import pandas as pd
import random
import time
from sqlalchemy import text
import os
import bcrypt
import secrets
import datetime
import qrcode
from io import BytesIO
import zipfile
import requests
import json
import base64
import streamlit.components.v1 as components

# ==========================================
# === EMALATKHANA POS - V5.30 (FULL SECURE) ===
# ==========================================

VERSION = "v5.30 (All Functions Restored + Audit Fix)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- CONSTANTS ---
ADMIN_DEFAULT_PASS = os.environ.get("ADMIN_PASS", "admin123") 

DEFAULT_TERMS = """<div style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h4 style="color: #2E7D32; margin-bottom: 5px;">📜 İSTİFADƏÇİ RAZILAŞMASI</h4>
    <p>Bu loyallıq proqramı "Emalatkhana" tərəfindən təqdim edilir.</p>
</div>"""

COMPLIMENTS = [
    "Gülüşünüz günümüzü işıqlandırdı! ☀️",
    "Bu gün möhtəşəm görünürsünüz! ✨",
    "Sizi yenidən görmək necə xoşdur! ☕",
    "Uğurlu gün arzulayırıq! 🚀",
    "Enerjinizə heyranıq! ⚡"
]

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store"
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"

# --- CONFIG ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# --- INIT STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'session_token' not in st.session_state: st.session_state.session_token = None
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'current_customer_tb' not in st.session_state: st.session_state.current_customer_tb = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'show_receipt_popup' not in st.session_state: st.session_state.show_receipt_popup = False
if 'last_receipt_data' not in st.session_state: st.session_state.last_receipt_data = None

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&display=swap');

    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F4F6F9 !important; color: #333333 !important; font-family: 'Oswald', sans-serif !important; }
    p, h1, h2, h3, h4, h5, h6, li, span, label, div[data-testid="stMarkdownContainer"] p { color: #333333 !important; }
    div[data-baseweb="input"] { background-color: #FFFFFF !important; border: 1px solid #ced4da !important; color: #333 !important; }
    input, textarea { color: #333 !important; }
    header, #MainMenu, footer, [data-testid="stSidebar"] { display: none !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    
    /* BUTTONS */
    div.stButton > button { border-radius: 12px !important; height: 60px !important; font-weight: 700 !important; box-shadow: 0 4px 0 rgba(0,0,0,0.1) !important; background: white !important; color: #333 !important; border: 1px solid #ddd !important; }
    div.stButton > button:hover { border-color: #2E7D32 !important; color: #2E7D32 !important; background-color: #F1F8E9 !important; }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    div.stButton > button[kind="primary"] p { color: white !important; }
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #43A047, #2E7D32) !important; color: white !important; border: 2px solid #1B5E20 !important; height: 100px !important; font-size: 20px !important; white-space: pre-wrap !important; }
    div.stButton > button[kind="secondary"] p { color: white !important; }
    .small-btn button { height: 35px !important; min-height: 35px !important; font-size: 14px !important; padding: 0 !important; }

    /* STAMP CARD */
    .stamp-container { padding: 20px; display: flex; justify-content: center; align-items: center; margin-bottom: 30px; }
    .stamp-card {
        background: white; padding: 20px 40px; text-align: center;
        font-family: 'Courier Prime', monospace; text-transform: uppercase; font-weight: bold;
        transform: rotate(-3deg); border-radius: 15px; transition: transform 0.3s ease; position: relative;
        border: 4px solid #B71C1C; color: #B71C1C; box-shadow: 0 0 0 4px white, 0 0 0 7px #B71C1C; 
    }
    .stamp-card:hover { transform: rotate(0deg) scale(1.05); }
    .stamp-title { font-size: 28px; letter-spacing: 2px; border-bottom: 2px solid; padding-bottom: 5px; margin-bottom: 10px; display: inline-block; }
    .stamp-stars { font-size: 64px; margin: 10px 0; font-family: 'Oswald', sans-serif; }
    .stamp-footer { font-size: 12px; letter-spacing: 1px; }

    /* COFFEE CUPS */
    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; justify-items: center; margin-top: 20px; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.3s ease; }
    .cup-earned { filter: invert(33%) sepia(94%) saturate(403%) hue-rotate(93deg) brightness(92%) contrast(88%); opacity: 1; transform: scale(1.1); }
    .cup-empty { filter: grayscale(100%); opacity: 0.2; }
    .gift-box-anim { width: 60px; height: 60px; animation: bounce 2s infinite; }
    @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-10px);} }

    /* FEEDBACK */
    .feedback-container { text-align: center; margin-top: 30px; background: white; padding: 25px; border-radius: 15px; border: 2px solid #FFCDD2; }
    .feedback-title { font-size: 26px; font-weight: 900; color: #D32F2F; margin-bottom: 15px; font-family: 'Oswald', sans-serif; text-transform: uppercase; }
    div[data-testid="stRating"] { justify-content: center !important; transform: scale(2.5); margin: 20px 0; }
    div[data-testid="stRating"] svg { fill: #FF0000 !important; color: #FF0000 !important; }
    div[data-baseweb="input"] { background-color: white !important; border: 1px solid #333 !important; }
    div[data-baseweb="input"] input { color: black !important; -webkit-text-fill-color: black !important; }

    /* PRINT RECEIPT */
    @media screen { #hidden-print-area { display: none; } }
    @media print {
        body * { visibility: hidden; }
        #hidden-print-area, #hidden-print-area * { visibility: visible; }
        #hidden-print-area { 
            position: fixed; left: 0; top: 0; width: 100%; 
            margin: 0; padding: 10px; 
            font-family: 'Courier Prime', monospace; color: black; 
            text-align: center; background: white;
        }
        .rec-logo { width: 80px; margin-bottom: 10px; filter: grayscale(100%); }
        .rec-table { width: 100%; text-align: left; font-size: 12px; border-collapse: collapse; }
        .rec-table th, .rec-table td { border-bottom: 1px dashed black; padding: 5px; }
        button, .stButton { display: none !important; }
        div[role="dialog"] { box-shadow: none !important; border: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- DB CONNECTION & SCHEMA ---
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
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS ingredients (id SERIAL PRIMARY KEY, name TEXT UNIQUE, stock_qty DECIMAL(10,2) DEFAULT 0, unit TEXT, category TEXT, min_limit DECIMAL(10,2) DEFAULT 10);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS recipes (id SERIAL PRIMARY KEY, menu_item_name TEXT, ingredient_name TEXT, quantity_required DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT, staff_note TEXT);"))
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_at TIMESTAMP")); s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP"))
        except: pass
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS staff_note TEXT"))
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, attached_coupon TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS system_logs (id SERIAL PRIMARY KEY, username TEXT, action TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, title TEXT, amount DECIMAL(10,2), category TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS coupon_templates (id SERIAL PRIMARY KEY, name TEXT, percent INTEGER, days_valid INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS void_logs (id SERIAL PRIMARY KEY, item_name TEXT, qty INTEGER, reason TEXT, deleted_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
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
def log_system(user, action):
    try: run_action("INSERT INTO system_logs (username, action, created_at) VALUES (:u, :a, :t)", {"u":user, "a":action, "t":get_baku_now()})
    except: pass
def get_setting(key, default=""):
    try:
        r = run_query("SELECT value FROM settings WHERE key=:k", {"k":key})
        return r.iloc[0]['value'] if not r.empty else default
    except: return default
def set_setting(key, value):
    run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v", {"k":key, "v":value})
def image_to_base64(image_file): return base64.b64encode(image_file.getvalue()).decode()
@st.cache_data(ttl=60)
def generate_custom_qr(data, center_text):
    qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGBA'); buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return "API_KEY_MISSING"
    url = "https://api.resend.com/emails"; headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    payload = {"from": f"{BRAND_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}
    try: 
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200: return "OK"
        else: return f"API Error {r.status_code}"
    except: return "Connection Error"
def format_qty(val): return int(val) if val % 1 == 0 else val

def check_login_block(username):
    try:
        row = run_query("SELECT attempt_count, blocked_until FROM failed_logins WHERE username=:u", {"u":username})
        if not row.empty:
            data = row.iloc[0]
            if data['blocked_until'] and data['blocked_until'] > get_baku_now():
                delta = data['blocked_until'] - get_baku_now()
                return True, int(delta.total_seconds() // 60) + 1
    except: pass
    return False, 0
def register_failed_login(username):
    now = get_baku_now()
    try:
        row = run_query("SELECT attempt_count FROM failed_logins WHERE username=:u", {"u":username})
        if row.empty:
            run_action("INSERT INTO failed_logins (username, attempt_count, last_attempt) VALUES (:u, 1, :t)", {"u":username, "t":now})
        else:
            new_count = row.iloc[0]['attempt_count'] + 1
            blocked_until = None
            if new_count >= 5: blocked_until = now + datetime.timedelta(minutes=5)
            run_action("UPDATE failed_logins SET attempt_count=:c, last_attempt=:t, blocked_until=:b WHERE username=:u", {"c":new_count, "t":now, "b":blocked_until, "u":username})
    except: pass
def clear_failed_login(username):
    try: run_action("DELETE FROM failed_logins WHERE username=:u", {"u":username})
    except: pass
def create_session(username, role):
    token = secrets.token_urlsafe(32)
    run_action("INSERT INTO active_sessions (token, username, role, created_at) VALUES (:t, :u, :r, :c)", {"t":token, "u":username, "r":role, "c":get_baku_now()})
    return token
def validate_session():
    if not st.session_state.session_token: return False
    res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token})
    if res.empty: return False
    return True

def get_low_stock_map():
    low_stock_items = []
    try:
        q = "SELECT DISTINCT r.menu_item_name FROM recipes r JOIN ingredients i ON r.ingredient_name = i.name WHERE i.stock_qty <= i.min_limit"
        df = run_query(q)
        if not df.empty: low_stock_items = df['menu_item_name'].tolist()
    except: pass
    return low_stock_items

def calculate_smart_total(cart, customer=None, is_table=False):
    total = 0.0; discounted_total = 0.0; status_discount_rate = 0.0; thermos_discount_rate = 0.0; current_stars = 0
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'golden': status_discount_rate = 0.05
        elif ctype == 'platinum': status_discount_rate = 0.10
        elif ctype == 'elite': status_discount_rate = 0.20
        elif ctype == 'thermos': thermos_discount_rate = 0.20 
    cart_coffee_count = sum([item['qty'] for item in cart if item.get('is_coffee')])
    potential_free = int((current_stars + cart_coffee_count) // 10)
    free_coffees_to_apply = min(potential_free, cart_coffee_count)
    final_items_total = 0.0
    for item in cart:
        line_total = item['qty'] * item['price']; total += line_total
        if item.get('is_coffee'):
            applicable_rate = max(status_discount_rate, thermos_discount_rate)
            discount_amt = line_total * applicable_rate
            final_items_total += (line_total - discount_amt)
        else: final_items_total += line_total
    discounted_total = final_items_total
    if is_table: discounted_total += discounted_total * 0.07 
    return total, discounted_total, max(status_discount_rate, thermos_discount_rate), free_coffees_to_apply, 0, 0, False

def get_receipt_html_string(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME)
    addr = get_setting("receipt_address", "Bakı, Azərbaycan")
    phone = get_setting("receipt_phone", "+994 50 000 00 00")
    foot = get_setting("receipt_footer", "TƏŞƏKKÜRLƏR!")
    logo = get_setting("receipt_logo_base64")
    time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" class="rec-logo" style="width:80px;filter:grayscale(100%);"></div>' if logo else ""
    rows = ""
    for i in cart: rows += f"""<tr><td style="padding:5px 0;">{int(i['qty'])}</td><td style="padding:5px 0;">{i['item_name']}</td><td style="padding:5px 0; text-align:right;">{i['qty']*i['price']:.2f} ₼</td></tr>"""
    html = f"""<div id='receipt-area' style="font-family:'Courier New', monospace; color:black; background:white; padding:15px; border:1px solid #eee; width:300px; margin:0 auto;">{img_tag}<div style="text-align:center; font-weight:bold; font-size:16px; margin-bottom:5px; text-transform:uppercase;">SATIŞ ÇEKİ<br>{store}</div><div style="text-align:center; font-size:12px; margin-bottom:10px;">{addr}<br>Tel: {phone}</div><div style="border-bottom:1px dashed black; margin:10px 0;"></div><div style="text-align:center; font-size:12px;">{time_str}</div><div style="border-bottom:1px dashed black; margin:10px 0;"></div><table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;"><tr><th style="padding-bottom:5px; border-bottom:1px dashed black; width:15%;">SAY</th><th style="padding-bottom:5px; border-bottom:1px dashed black; width:55%;">MƏHSUL</th><th style="padding-bottom:5px; border-bottom:1px dashed black; width:30%; text-align:right;">MƏBLƏĞ</th></tr>{rows}</table><div style="border-bottom:1px dashed black; margin:10px 0;"></div><div style="display:flex; justify-content:space-between; font-weight:bold; font-size:16px;"><span>YEKUN</span><span>{total:.2f} ₼</span></div><div style="border-bottom:1px dashed black; margin:10px 0;"></div><div style="text-align:center; margin-top:20px; font-size:12px; font-weight:bold;">{foot}</div></div>"""
    return html

@st.dialog("Ödəniş & Çek")
def show_receipt_dialog(cart_data, total_amt, cust_email):
    html_content = get_receipt_html_string(cart_data, total_amt)
    components.html(html_content, height=500, scrolling=True)
    st.markdown(f'<div id="hidden-print-area">{html_content}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: components.html(f"""<button onclick="window.print()" style="background-color:#2E7D32; color:white; padding:12px 24px; border:none; border-radius:8px; font-weight:bold; font-size:16px; cursor:pointer; width:100%;">🖨️ ÇAP ET</button>""", height=60)
    with c2:
        if cust_email:
            if st.button("📧 Email Göndər", use_container_width=True):
                res = send_email(cust_email, "Sizin Çekiniz", html_content)
                if res == "OK": st.success("Göndərildi!")
                else: st.error(f"Xəta: {res}")
        else: st.caption("⛔ Email yoxdur")
    if st.button("❌ Bağla", use_container_width=True):
        st.session_state.show_receipt_popup = False; st.session_state.last_receipt_data = None; st.rerun()

# ==========================================
# === MAIN APP ===
# ==========================================
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]; token = query_params.get("t")
    c1, c2, c3 = st.columns([1,2,1]); logo_b64 = get_setting("receipt_logo_base64")
    cust_title = get_setting("customer_ui_title", BRAND_NAME)
    with c2:
        if logo_b64: st.markdown(f'<div style="text-align:center; margin-bottom:10px;"><img src="data:image/png;base64,{logo_b64}" width="160"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{cust_title}</h1>", unsafe_allow_html=True)
    try: df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    except: st.stop()
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token: st.warning("⚠️ QR kod köhnəlib.")
        comp = random.choice(COMPLIMENTS); st.markdown(f"<div class='compliment-text'>{comp}</div>", unsafe_allow_html=True)
        public_msg = get_setting("public_msg", ""); 
        if public_msg: st.info(f"📢 {public_msg}")
        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"💌 {row['message']}")
            if st.button("OXUDUM ✅", key=f"read_{row['id']}"):
                run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']}); st.rerun()
        if not user['is_active']:
            st.warning(f"🎉 Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email", key="reg_email"); dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1))
                with st.expander("📜 Qaydalar"): st.markdown(get_setting("customer_terms", DEFAULT_TERMS), unsafe_allow_html=True)
                if st.form_submit_button("Təsdiqlə"):
                    run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE, activated_at=:t WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id, "t":get_baku_now()}); st.rerun()
            st.stop()
        
        ctype = user['type']; st_label = "MEMBER"; disc_txt = ""; border_col = "#B71C1C"
        if ctype == 'golden': st_label="GOLDEN MEMBER"; disc_txt="✨ 5% ENDİRİM"; border_col="#D4AF37"
        elif ctype == 'platinum': st_label="PLATINUM MEMBER"; disc_txt="✨ 10% ENDİRİM"; border_col="#78909C"
        elif ctype == 'elite': st_label="ELITE VIP"; disc_txt="✨ 20% ENDİRİM"; border_col="#B71C1C"
        elif ctype == 'thermos': st_label="EKO-TERM MEMBER"; disc_txt="🌿 20% ENDİRİM"; border_col="#2E7D32"
        st.markdown(f"""<div class="stamp-container"><div class="stamp-card" style="border-color: {border_col}; color: {border_col}; box-shadow: 0 0 0 4px white, 0 0 0 7px {border_col};"><div class="stamp-title">{st_label}</div><div>{disc_txt}</div><div class="stamp-stars">{user['stars']} / 10</div><div class="stamp-footer">ULDUZ BALANSI</div></div></div>""", unsafe_allow_html=True)
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            if i < user['stars']:
                if i == 9: html += f'<img src="{icon}" class="cup-earned gift-box-anim">'
                else: html += f'<img src="{icon}" class="cup-earned coffee-icon-img">'
            else: html += f'<img src="{icon}" class="cup-empty coffee-icon-img">'
        st.markdown(html + '</div>', unsafe_allow_html=True)
        st.markdown('<div class="feedback-container"><div class="feedback-title">RƏYİNİZ BİZİM ÜÇÜN ÖNƏMLİDİR</div>', unsafe_allow_html=True)
        with st.form("feed"):
            s = st.feedback("stars"); m = st.text_input("Şərhiniz", key="feed_msg", placeholder="Fikirlərinizi yazın...")
            if st.form_submit_button("Göndər") and s:
                run_action("INSERT INTO feedbacks (card_id, rating, comment, created_at) VALUES (:i,:r,:m, :t)", {"i":card_id, "r":s+1, "m":m, "t":get_baku_now()}); st.success("Təşəkkürlər!")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

if st.session_state.logged_in:
    if not validate_session():
        st.session_state.logged_in = False; st.session_state.session_token = None; st.error("Sessiya bitib."); st.rerun()

if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center; color:#777;'>{VERSION}</h5>", unsafe_allow_html=True)
        tabs = st.tabs(["İŞÇİ (STAFF)", "İDARƏETMƏ (ADMIN)"])
        with tabs[0]:
            with st.form("staff_login"):
                p = st.text_input("PIN", type="password", key="s_pin")
                if st.form_submit_button("Giriş", use_container_width=True):
                    is_blocked, mins = check_login_block(p)
                    if is_blocked: st.error(f"Blok: {mins} dəq"); st.stop()
                    udf = run_query("SELECT * FROM users WHERE role='staff'")
                    found = False
                    for _, row in udf.iterrows():
                        if verify_password(p, row['password']):
                            clear_failed_login(row['username']); st.session_state.logged_in = True; st.session_state.user = row['username']; st.session_state.role = 'staff'; st.session_state.session_token = create_session(row['username'], 'staff'); st.rerun(); found=True; break
                    if not found: register_failed_login(p); st.error("Yanlış PIN!")
        with tabs[1]:
            with st.form("admin_login"):
                u = st.text_input("İstifadəçi"); passw = st.text_input("Şifrə", type="password")
                if st.form_submit_button("Daxil Ol", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not udf.empty and verify_password(passw, udf.iloc[0]['password']):
                        st.session_state.logged_in = True; st.session_state.user = u; st.session_state.role = udf.iloc[0]['role']; st.session_state.session_token = create_session(u, udf.iloc[0]['role']); st.rerun()
                    else: register_failed_login(u); st.error("Səhv!")
else:
    if st.session_state.show_receipt_popup and st.session_state.last_receipt_data:
        show_receipt_dialog(st.session_state.last_receipt_data['cart'], st.session_state.last_receipt_data['total'], st.session_state.last_receipt_data['email'])

    h1, h2, h3 = st.columns([4, 1, 1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄 Yenilə", use_container_width=True): st.rerun()
    with h3: 
        if st.button("🚪 Çıxış", type="primary", use_container_width=True): 
            log_system(st.session_state.user, "Logout"); run_action("DELETE FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token}); st.session_state.logged_in = False; st.rerun()
    st.divider()

    role = st.session_state.role
    
    def add_to_cart(cart_ref, item):
        try: r = run_query("SELECT printer_target, price_half FROM menu WHERE item_name=:n", {"n":item['item_name']}).iloc[0]; item['printer_target'] = r['printer_target']; item['price_half'] = float(r['price_half']) if r['price_half'] else None
        except: item['printer_target'] = 'kitchen'; item['price_half'] = None
        for ex in cart_ref:
            if ex['item_name'] == item['item_name'] and ex.get('status') == 'new' and ex.get('qty') % 1 == 0: ex['qty'] += 1; return
        cart_ref.append(item)

    def render_menu_grid(cart_ref, key_prefix):
        low_stock = get_low_stock_map()
        cats = run_query("SELECT DISTINCT category FROM menu WHERE is_active=TRUE")
        cat_list = ["Hamısı"] + sorted(cats['category'].tolist()) if not cats.empty else ["Hamısı"]
        sc = st.radio("Kataloq", cat_list, horizontal=True, label_visibility="collapsed", key=f"cat_{key_prefix}")
        sql = "SELECT id, item_name, price, is_coffee FROM menu WHERE is_active=TRUE"; p = {}
        if sc != "Hamısı": sql += " AND category=:c"; p["c"] = sc
        sql += " ORDER BY price ASC"; prods = run_query(sql, p)
        if not prods.empty:
            gr = {}
            for _, r in prods.iterrows():
                n = r['item_name']; pts = n.split(); base = n
                if len(pts)>1 and pts[-1] in ['S','M','L','XL','Single','Double']: base = " ".join(pts[:-1]); gr.setdefault(base, []).append(r)
                else: gr[n] = [r]
            cols = st.columns(4); i=0
            @st.dialog("Seçim")
            def show_v(bn, its):
                for it in its:
                    marker = " 🟡" if it['item_name'] in low_stock else ""
                    if st.button(f"{it['item_name'].replace(bn,'').strip()}{marker}\n{it['price']} ₼", key=f"v_{it['id']}_{key_prefix}", use_container_width=True):
                        add_to_cart(cart_ref, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'status':'new'}); st.rerun()
            for bn, its in gr.items():
                with cols[i%4]:
                    marker = " 🟡" if any(x['item_name'] in low_stock for x in its) else ""
                    if len(its)>1:
                        if st.button(f"{bn}{marker}\n(Seçim)", key=f"g_{bn}_{key_prefix}", use_container_width=True): show_v(bn, its)
                    else:
                        it = its[0]
                        if st.button(f"{it['item_name']}{marker}\n{it['price']} ₼", key=f"s_{it['id']}_{key_prefix}", use_container_width=True):
                            add_to_cart(cart_ref, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'status':'new'}); st.rerun()
                i+=1

    if role == 'admin':
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "📜 Resept", "Analitika", "📜 Loglar", "👥 CRM", "Menyu", "⚙️ Ayarlar", "💾 BAZA", "QR"])
    elif role == 'manager':
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar (Mədaxil)", "📊 Analitika", "📜 Loglar", "👥 CRM"])
    elif role == 'staff':
        show_tbl = (get_setting("staff_show_tables", "TRUE") == "TRUE")
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "Satışlar"] if show_tbl else ["🏃‍♂️ AL-APAR", "Satışlar"])

    with tabs[0]: # TAKEAWAY
        c1, c2 = st.columns([1.5, 3])
        with c1:
            st.info("🧾 Al-Apar Çek")
            with st.form("sc_ta", clear_on_submit=True):
                ci, cb = st.columns([3,1]); qv = ci.text_input("Müştəri", label_visibility="collapsed", placeholder="Skan...", key="ta_inp"); 
                if cb.form_submit_button("🔍") or qv:
                    try: 
                        cid = qv.strip().split("id=")[1].split("&")[0] if "id=" in qv else qv.strip()
                        r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                        if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.toast(f"✅ Müştəri Tanındı: {cid}"); st.rerun()
                        else: st.error("Tapılmadı")
                    except: pass
            if st.session_state.current_customer_ta:
                c = st.session_state.current_customer_ta
                st.markdown(f"<div style='padding:10px; border:1px solid #ddd; border-radius:10px;'>👤 <b>{c['card_id']}</b> | ⭐ {c['stars']}</div>", unsafe_allow_html=True)
                if st.button("Ləğv Et", key="ta_cl"): st.session_state.current_customer_ta=None; st.rerun()
            raw_total, final_total, _, free_count, _, _, _ = calculate_smart_total(st.session_state.cart_takeaway, st.session_state.current_customer_ta, is_table=False)
            if st.session_state.cart_takeaway:
                for i, it in enumerate(st.session_state.cart_takeaway):
                    st.markdown(f"<div style='background:white;padding:10px;margin-bottom:5px;border:1px solid #ddd;display:flex;justify-content:space-between;'><div>{it['item_name']}</div><div>x{it['qty']}</div><div>{it['qty']*it['price']:.1f}</div></div>", unsafe_allow_html=True)
                    b1,b2 = st.columns(2)
                    if b1.button("➖", key=f"m_ta_{i}"): 
                        if it['qty']>1: it['qty']-=1 
                        else: st.session_state.cart_takeaway.pop(i)
                        st.rerun()
                    if b2.button("➕", key=f"p_ta_{i}"): it['qty']+=1; st.rerun()
            st.markdown(f"<h2 style='text-align:right; color:#E65100'>{final_total:.2f} ₼</h2>", unsafe_allow_html=True)
            if free_count > 0: st.success(f"🎁 {free_count} Kofe HƏDİYYƏ!")
            pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True, key="pm_ta")
            if st.button("✅ ÖDƏNİŞ ET", type="primary", use_container_width=True, key="pay_ta"):
                if not st.session_state.cart_takeaway: st.error("Boşdur!"); st.stop()
                try:
                    with conn.session as s:
                        for it in st.session_state.cart_takeaway:
                            rs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                            for r in rs:
                                req_qty = float(r[1]) * it['qty']
                                res = s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n AND stock_qty >= :q"), {"q":req_qty, "n":r[0]})
                                if res.rowcount == 0: raise Exception(f"Stok Çatmır: {r[0]}")
                        istr = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_takeaway])
                        cust_id = st.session_state.current_customer_ta['card_id'] if st.session_state.current_customer_ta else None
                        s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id) VALUES (:i,:t,:p,:c,:time, :cid)"), {"i":istr,"t":final_total,"p":("Cash" if pm=="Nəğd" else "Card"),"c":st.session_state.user, "time":get_baku_now(), "cid":cust_id})
                        if st.session_state.current_customer_ta:
                            new_stars = (st.session_state.current_customer_ta['stars'] + sum([item['qty'] for item in st.session_state.cart_takeaway if item.get('is_coffee')])) - (free_count * 10)
                            s.execute(text("UPDATE customers SET stars=:s WHERE card_id=:id"), {"s":new_stars, "id":cust_id})
                        s.commit()
                    cust_email = st.session_state.current_customer_ta['email'] if st.session_state.current_customer_ta else None
                    st.session_state.last_receipt_data = {'cart': st.session_state.cart_takeaway.copy(), 'total': final_total, 'email': cust_email}
                    st.session_state.show_receipt_popup = True; st.session_state.cart_takeaway = []; st.rerun()
                except Exception as e: st.error(f"Xəta: {str(e)}")
        with c2: render_menu_grid(st.session_state.cart_takeaway, "ta")

    if show_tbl or role != 'staff':
        with tabs[1]: # TABLES
            if st.session_state.selected_table: 
                tbl = st.session_state.selected_table
                if st.button("⬅️ Qayıt", key="back_tbl"): st.session_state.selected_table = None; st.session_state.cart_table = []; st.rerun()
                st.markdown(f"### 📝 {tbl['label']}"); c1, c2 = st.columns([1.5, 3])
                with c1:
                    db_cust_id = tbl.get('active_customer_id')
                    if db_cust_id and not st.session_state.current_customer_tb:
                         r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":db_cust_id})
                         if not r.empty: st.session_state.current_customer_tb = r.iloc[0].to_dict()
                    if st.session_state.current_customer_tb: st.success(f"👤 {st.session_state.current_customer_tb['card_id']}")
                    raw_total, final_total, _, _, _, serv_chg, _ = calculate_smart_total(st.session_state.cart_table, st.session_state.current_customer_tb, is_table=True)
                    for i, it in enumerate(st.session_state.cart_table):
                        st.markdown(f"<div style='background:{'#e3f2fd' if it.get('status')=='sent' else 'white'};padding:10px;margin:5px 0;border:1px solid #ddd;'>{it['item_name']} x{it['qty']} - {it['qty']*it['price']:.1f}</div>", unsafe_allow_html=True)
                        b1,b2 = st.columns(2)
                        if b1.button("➖", key=f"m_tb_{i}") and it.get('status')!='sent': st.session_state.cart_table.pop(i); st.rerun()
                        if b2.button("➕", key=f"p_tb_{i}"): it['qty']+=1; st.rerun()
                    st.markdown(f"### Yekun: {final_total:.2f} ₼"); st.caption(f"Servis: {serv_chg:.2f} ₼")
                    if st.button("🔥 Mətbəxə Göndər", use_container_width=True):
                        for x in st.session_state.cart_table: x['status'] = 'sent'
                        run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id", {"i":json.dumps(st.session_state.cart_table), "t":final_total, "id":tbl['id']}); st.success("Göndərildi!"); time.sleep(1); st.rerun()
                    if st.button("✅ Ödəniş Et", type="primary", use_container_width=True):
                        try:
                            with conn.session as s:
                                for it in st.session_state.cart_table:
                                    if it.get('status') != 'paid': # Avoid double deduction logic if tracked
                                        rs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                                        for r in rs:
                                            req_qty = float(r[1]) * it['qty']
                                            res = s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n AND stock_qty >= :q"), {"q":req_qty, "n":r[0]})
                                            if res.rowcount == 0: raise Exception(f"Stok Çatmır: {r[0]}")
                                istr = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_table])
                                s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at) VALUES (:i,:t,'Cash',:c,:time)"), {"i":istr,"t":final_total,"c":st.session_state.user, "time":get_baku_now()})
                                s.execute(text("UPDATE tables SET is_occupied=FALSE, items='[]', total=0, active_customer_id=NULL WHERE id=:id"), {"id":tbl['id']})
                                s.commit()
                            cust_email = st.session_state.current_customer_tb['email'] if st.session_state.current_customer_tb else None
                            st.session_state.last_receipt_data = {'cart': st.session_state.cart_table.copy(), 'total': final_total, 'email': cust_email}
                            st.session_state.show_receipt_popup = True; st.session_state.selected_table = None; st.session_state.cart_table = []; st.rerun()
                        except Exception as e: st.error(f"Xəta: {e}")
                with c2: render_menu_grid(st.session_state.cart_table, "tb")
            else: 
                if st.session_state.role in ['admin', 'manager']:
                    with st.expander("🛠️ Masa"):
                        n_l = st.text_input("Ad"); 
                        if st.button("➕"): run_action("INSERT INTO tables (label) VALUES (:l)", {"l":n_l}); st.rerun()
                tables = run_query("SELECT * FROM tables ORDER BY id"); cols = st.columns(3)
                for idx, row in tables.iterrows():
                    with cols[idx % 3]:
                        if st.button(f"{row['label']}\n{row['total']} ₼", key=f"tbl_{row['id']}", type="primary" if row['is_occupied'] else "secondary", use_container_width=True):
                            st.session_state.selected_table = row.to_dict(); st.session_state.cart_table = json.loads(row['items']) if row['items'] else []; st.rerun()

    if role == 'admin' or role == 'manager':
        with tabs[2]: # INVENTORY
            st.subheader("📦 Anbar")
            cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist(); cat_list = ["Bütün"] + cats
            sel_inv_cat = st.selectbox("Filtr", cat_list)
            sql = "SELECT * FROM ingredients"; p={}
            if sel_inv_cat != "Bütün": sql += " WHERE category=:c"; p['c']=sel_inv_cat
            df_inv = run_query(sql, p); df_inv.insert(0, "Seç", False)
            ed_inv = st.data_editor(df_inv, hide_index=True, disabled=["id","name","stock_qty","unit","category","min_limit"])
            if role == 'admin':
                to_del_inv = ed_inv[ed_inv["Seç"]]['id'].tolist()
                if to_del_inv:
                    if st.button("Seçilənləri Sil"):
                        for d in to_del_inv: run_action("DELETE FROM ingredients WHERE id=:id", {"id":d}); log_system(st.session_state.user, f"Deleted Inv: {d}")
                        st.success("Silindi!"); st.rerun()
                with st.expander("➕ Yeni Mal"):
                    with st.form("ni", clear_on_submit=True):
                        n=st.text_input("Ad"); q=st.number_input("Say"); u=st.selectbox("Vahid",["gr","ml","ədəd"]); c=st.text_input("Kat")
                        if st.form_submit_button("Yarat"): 
                            run_action("INSERT INTO ingredients (name,stock_qty,unit,category) VALUES (:n,:q,:u,:c)", {"n":n,"q":q,"u":u,"c":c}); st.rerun()
            if role == 'manager': # Manager Add Stock
                cols = st.columns(4)
                for i, r in df_inv.iterrows():
                    with cols[i%4]:
                        @st.dialog(f"Mədaxil: {r['name']}")
                        def add_stock(id, name):
                            add = st.number_input("Artır", 0.0)
                            if st.button("Təsdiq"): run_action("UPDATE ingredients SET stock_qty=stock_qty+:q WHERE id=:id",{"q":add,"id":id}); st.rerun()
                        if st.button(f"{r['name']}\n{format_qty(r['stock_qty'])}", key=f"mi_{r['id']}"): add_stock(r['id'], r['name'])

    if role == 'admin':
        with tabs[3]: # RECIPE
            st.subheader("📜 Resept")
            sel_prod = st.selectbox("Məhsul", ["(Seçin)"] + run_query("SELECT item_name FROM menu WHERE is_active=TRUE")['item_name'].tolist())
            if sel_prod != "(Seçin)":
                recs = run_query("SELECT id, ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:n", {"n":sel_prod})
                ed_rec = st.data_editor(recs, hide_index=True, disabled=["id","ingredient_name","quantity_required"])
                with st.form("add_rec", clear_on_submit=True):
                    s_i = st.selectbox("Xammal", run_query("SELECT name FROM ingredients")['name'].tolist()); s_q = st.number_input("Miqdar")
                    if st.form_submit_button("Əlavə Et"): run_action("INSERT INTO recipes (menu_item_name,ingredient_name,quantity_required) VALUES (:m,:i,:q)",{"m":sel_prod,"i":s_i,"q":s_q}); st.rerun()

    if role != 'staff': # ANALYTICS
        idx = 4 if role=='admin' else 3
        with tabs[idx]:
            st.subheader("📊 Analitika")
            c1, c2 = st.columns([1, 2]); f_type = c1.selectbox("Filtr", ["Bu Gün", "Bu Ay", "Tarix Aralığı"])
            d1 = get_baku_now().date(); d2 = get_baku_now().date()
            if f_type == "Bu Ay": d1 = d1.replace(day=1)
            elif f_type == "Tarix Aralığı": d1 = c2.date_input("Start"); d2 = c2.date_input("End")
            
            # SECURE PARAMETERIZED QUERY
            df_sales = run_query("SELECT * FROM sales WHERE created_at::date BETWEEN :d1 AND :d2 ORDER BY created_at DESC", {"d1":d1, "d2":d2})
            st.metric("Toplam Satış", f"{df_sales['total'].sum():.2f} ₼")
            st.dataframe(df_sales)

    if role != 'staff': # LOGS
        idx = 5 if role=='admin' else 4
        with tabs[idx]:
            st.dataframe(run_query("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 100"))

    if role != 'staff': # CRM
        idx = 6 if role=='admin' else 5
        with tabs[idx]:
            st.subheader("👥 CRM")
            msg = st.text_area("Mesaj"); 
            if st.button("Hamıya Göndər"): set_setting("public_msg", msg); st.success("Vitrin Yeniləndi")
            if role == 'admin':
                df = run_query("SELECT card_id, email, type FROM customers"); df.insert(0, "Seç", False)
                ed = st.data_editor(df, hide_index=True, disabled=["card_id","email","type"])
                del_ids = ed[ed["Seç"]]['card_id'].tolist()
                if del_ids and st.button("Seçilənləri Sil"):
                    for di in del_ids: 
                        run_action("DELETE FROM customers WHERE card_id=:id", {"id":di}); run_action("DELETE FROM customer_coupons WHERE card_id=:id", {"id":di})
                        log_system(st.session_state.user, f"Deleted Customer: {di}")
                    st.success("Silindi!"); st.rerun()

    if role == 'admin':
        with tabs[7]: # MENU
            st.subheader("📋 Menyu")
            with st.form("nm", clear_on_submit=True):
                n=st.text_input("Ad"); p=st.number_input("Qiymət"); c=st.text_input("Kat"); ic=st.checkbox("Kofe?")
                if st.form_submit_button("Yarat"): 
                    run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee) VALUES (:n,:p,:c,TRUE,:ic)", {"n":n,"p":p,"c":c,"ic":ic}); st.rerun()
            ml = run_query("SELECT * FROM menu"); ml.insert(0, "Seç", False)
            ed_m = st.data_editor(ml, hide_index=True, disabled=["id","item_name","price","category","is_active","is_coffee","printer_target","price_half"])
            del_m = ed_m[ed_m["Seç"]]['id'].tolist()
            if del_m and st.button("Menyudan Sil"):
                for d in del_m: run_action("DELETE FROM menu WHERE id=:id", {"id":d}); log_system(st.session_state.user, f"Deleted Menu ID: {d}")
                st.success("Silindi!"); st.rerun()

        with tabs[8]: # SETTINGS
            st.subheader("⚙️ Ayarlar")
            with st.form("add_u", clear_on_submit=True):
                u=st.text_input("Ad"); pin=st.text_input("PIN"); r=st.selectbox("Rol", ["staff","manager"])
                if st.form_submit_button("İşçi Yarat"):
                    run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":u, "p":hash_password(pin), "r":r}); st.success("OK")
            lg = st.file_uploader("Logo"); 
            if lg: set_setting("receipt_logo_base64", image_to_base64(lg)); st.success("Yükləndi")

        with tabs[9]: # BAZA
            st.subheader("💾 Baza")
            if st.button("FULL BACKUP"):
                out = BytesIO(); 
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    for t in ["users","menu","sales","ingredients","recipes","customers","customer_coupons","notifications","settings","system_logs"]:
                        try: run_query(f"SELECT * FROM {t}").to_excel(writer, sheet_name=t, index=False)
                        except: pass
                st.download_button("⬇️ Endir", out.getvalue(), "Backup.xlsx")
            rf = st.file_uploader("Restore (.xlsx)")
            if rf and st.button("⚠️ Bərpa Et"):
                try:
                    xls = pd.ExcelFile(rf)
                    for t in ["menu","ingredients","recipes","coupon_templates"]:
                        if t in xls.sheet_names: run_action(f"DELETE FROM {t}"); pd.read_excel(xls, t).to_sql(t, conn.engine, if_exists='append', index=False)
                    log_system(st.session_state.user, "Restored Backup"); st.success("Bərpa Olundu!")
                except: st.error("Xəta")

        with tabs[10]: # QR
            cnt = st.number_input("Say",1,100); k = st.selectbox("Növ", ["Golden","Platinum","Elite","Thermos"])
            if st.button("QR Yarat"): 
                for _ in range(cnt):
                    kt = k.lower().split()[0]; i = str(random.randint(10000000, 99999999)); tok = secrets.token_hex(8)
                    run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":kt, "st":tok})
                st.success("Hazırdır!")

    st.markdown(f"<div class='footer'>Ironwaves POS {VERSION} | © 2026</div>", unsafe_allow_html=True)
