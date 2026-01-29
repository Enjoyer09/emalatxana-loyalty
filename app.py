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

# ==========================================
# === EMALATKHANA POS - V5.25 (FORTRESS) ===
# ==========================================

VERSION = "v5.25 (Secure Tables + Pro Receipt)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- CONSTANTS ---
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
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'current_customer_tb' not in st.session_state: st.session_state.current_customer_tb = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'last_receipt' not in st.session_state: st.session_state.last_receipt = None # For Popup

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
    }
    .stamp-card:hover { transform: rotate(0deg) scale(1.05); }
    .stamp-gold { border: 4px solid #D4AF37; color: #D4AF37; box-shadow: 0 0 0 4px white, 0 0 0 7px #D4AF37; }
    .stamp-plat { border: 4px solid #78909C; color: #546E7A; box-shadow: 0 0 0 4px white, 0 0 0 7px #78909C; }
    .stamp-elite { border: 4px solid #800020; color: #800020; box-shadow: 0 0 0 4px white, 0 0 0 7px #800020; }
    .stamp-eco  { border: 4px solid #2E7D32; color: #2E7D32; box-shadow: 0 0 0 4px white, 0 0 0 7px #2E7D32; }
    .stamp-std  { border: 4px solid #333; color: #333; box-shadow: 0 0 0 4px white, 0 0 0 7px #333; }
    .stamp-title { font-size: 28px; letter-spacing: 2px; border-bottom: 2px solid; padding-bottom: 5px; margin-bottom: 10px; display: inline-block; }
    .stamp-stars { font-size: 64px; margin: 10px 0; font-family: 'Oswald', sans-serif; }
    .stamp-footer { font-size: 12px; letter-spacing: 1px; }

    .compliment-text { font-family: 'Dancing Script', cursive; color: #E65100; font-size: 26px; font-weight: 900; text-align: center; margin-bottom: 15px; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; justify-items: center; margin-top: 20px; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.3s ease; }
    .gift-box-anim { width: 60px; height: 60px; animation: bounce 2s infinite; }
    @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-10px);} }

    /* RECEIPT STYLE */
    @media print {
        body * { visibility: hidden; }
        #receipt-area, #receipt-area * { visibility: visible; }
        #receipt-area { 
            position: fixed; left: 0; top: 0; width: 100%; 
            margin: 0; padding: 10px; 
            font-family: 'Courier Prime', monospace; color: black; 
            text-align: center; background: white;
        }
        .rec-logo { width: 80px; margin-bottom: 10px; filter: grayscale(100%); }
        .rec-title { font-size: 16px; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; line-height: 1.2; }
        .rec-text { font-size: 12px; margin-bottom: 2px; }
        .rec-dash { margin: 8px 0; border-bottom: 1px dashed black; width: 100%; }
        .rec-table { width: 100%; text-align: left; font-size: 12px; border-collapse: collapse; margin-top: 5px; }
        .rec-table th { text-transform: uppercase; padding-bottom: 5px; border-bottom: 1px dashed black; }
        .rec-table td { padding: 5px 0; vertical-align: top; }
        .col-qty { width: 15%; text-align: left; }
        .col-name { width: 60%; text-align: left; }
        .col-amt { width: 25%; text-align: right; }
        .rec-total { display: flex; justify-content: space-between; font-size: 16px; font-weight: bold; margin-top: 10px; padding-top: 5px; border-top: 1px dashed black; }
        .rec-footer { margin-top: 20px; font-size: 12px; font-weight: bold; text-transform: uppercase; }
        
        button { display: none !important; }
        div[role="dialog"] { box-shadow: none !important; border: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- DB CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL") or os.environ.get("DATABASE_URL")
    if not db_url: st.error("DB URL Not Found"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA ---
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
            p_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin') ON CONFLICT (username) DO UPDATE SET password = :p"), {"p": p_hash})
            s.commit()
        except: s.rollback()
    return True
ensure_schema()

# --- HELPERS ---
def get_baku_now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=4))).replace(tzinfo=None)
def run_query(q, p=None): 
    if p:
        for k, v in p.items():
            if hasattr(v, 'item'): p[k] = int(v.item())
    return conn.query(q, params=p, ttl=0)
def run_action(q, p=None): 
    if p:
        new_p = {}
        for k, v in p.items():
            if hasattr(v, 'item'): new_p[k] = int(v.item()) 
            elif isinstance(v, (int, float)): new_p[k] = v 
            else: new_p[k] = v
        p = new_p
    with conn.session as s: s.execute(text(q), p); s.commit()
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
@st.cache_data
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
            if new_count >= 5: 
                blocked_until = now + datetime.timedelta(minutes=5)
            run_action("UPDATE failed_logins SET attempt_count=:c, last_attempt=:t, blocked_until=:b WHERE username=:u", 
                       {"c":new_count, "t":now, "b":blocked_until, "u":username})
    except: pass

def clear_failed_login(username):
    try: run_action("DELETE FROM failed_logins WHERE username=:u", {"u":username})
    except: pass

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
    total_star_pool = current_stars + cart_coffee_count; potential_free = int(total_star_pool // 10); free_coffees_to_apply = min(potential_free, cart_coffee_count)
    final_items_total = 0.0
    for item in cart:
        line_total = item['qty'] * item['price']; total += line_total
        if item.get('is_coffee'):
            applicable_rate = max(status_discount_rate, thermos_discount_rate); discount_amt = line_total * applicable_rate; final_items_total += (line_total - discount_amt)
        else: final_items_total += line_total
    discounted_total = final_items_total
    if is_table: discounted_total += discounted_total * 0.07
    return total, discounted_total, max(status_discount_rate, thermos_discount_rate), free_coffees_to_apply, total_star_pool, 0, False

# ==========================================
# === RECEIPT GENERATOR (AZ + PRO HTML) ===
# ==========================================
def get_receipt_html(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME)
    addr = get_setting("receipt_address", "Bakı, Azərbaycan")
    phone = get_setting("receipt_phone", "+994 50 000 00 00")
    foot = get_setting("receipt_footer", "TƏŞƏKKÜRLƏR!")
    logo = get_setting("receipt_logo_base64")
    time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    
    img_tag = f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" class="rec-logo" style="width:80px;filter:grayscale(100%);"></div>' if logo else ""
    
    # INLINE CSS FOR EMAIL COMPATIBILITY
    html = f"""
    <div id='receipt-area' style="font-family:'Courier Prime', monospace; color:black; background:white; padding:15px; border:1px solid #eee; width:300px; margin:0 auto;">
        {img_tag}
        <div style="text-align:center; font-weight:bold; font-size:16px; margin-bottom:5px; text-transform:uppercase;">SATIŞ ÇEKİ<br>{store}</div>
        <div style="text-align:center; font-size:12px; margin-bottom:10px;">{addr}<br>Tel: {phone}</div>
        <div style="border-bottom:1px dashed black; margin:10px 0;"></div>
        <div style="text-align:center; font-size:12px;">{time_str}</div>
        <div style="border-bottom:1px dashed black; margin:10px 0;"></div>
        
        <table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">
            <tr>
                <th style="padding-bottom:5px; border-bottom:1px dashed black; width:15%;">SAY</th>
                <th style="padding-bottom:5px; border-bottom:1px dashed black; width:55%;">MƏHSUL</th>
                <th style="padding-bottom:5px; border-bottom:1px dashed black; width:30%; text-align:right;">MƏBLƏĞ</th>
            </tr>
    """
    for i in cart:
        html += f"""
            <tr>
                <td style="padding:5px 0;">{int(i['qty'])}</td>
                <td style="padding:5px 0;">{i['item_name']}</td>
                <td style="padding:5px 0; text-align:right;">{i['qty']*i['price']:.2f} ₼</td>
            </tr>
        """
    
    html += f"""
        </table>
        <div style="border-bottom:1px dashed black; margin:10px 0;"></div>
        <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:16px;">
            <span>YEKUN</span>
            <span>{total:.2f} ₼</span>
        </div>
        <div style="border-bottom:1px dashed black; margin:10px 0;"></div>
        <div style="text-align:center; margin-top:20px; font-size:12px; font-weight:bold;">{foot}</div>
    </div>
    """
    return html

@st.dialog("Ödəniş & Çek")
def show_receipt_dialog(cart, total, customer_email):
    rec_html = get_receipt_html(cart, total)
    st.markdown(rec_html, unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        # PURE JS PRINT
        st.markdown("""<div style="text-align:center;margin-top:10px;"><button onclick="window.print()" style="background:#2E7D32;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-weight:bold;">🖨️ ÇAP ET</button></div>""", unsafe_allow_html=True)
    with c2:
        if customer_email:
            if st.button("📧 Email Göndər", use_container_width=True):
                send_email(customer_email, "Sizin Çekiniz", rec_html)
                st.success("Göndərildi!")
        else: st.caption("⛔ Email yoxdur")

# ==========================================
# === CUSTOMER VIEW INTERFACE ===
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
        
        comp = random.choice(COMPLIMENTS)
        st.markdown(f"<div class='compliment-text'>{comp}</div>", unsafe_allow_html=True)

        public_msg = get_setting("public_msg", "")
        if public_msg: st
