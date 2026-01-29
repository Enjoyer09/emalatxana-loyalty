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
# === EMALATKHANA POS - V5.23 (PRINT FIX) ===
# ==========================================

VERSION = "v5.23 (Print JS + Restore Visible)"
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
if 'selected_recipe_product' not in st.session_state: st.session_state.selected_recipe_product = None

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

    /* RECEIPT STYLE - FIXED FOR PRINT */
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
        .col-qty { width: 10%; text-align: left; }
        .col-name { width: 65%; text-align: left; }
        .col-amt { width: 25%; text-align: right; }
        .rec-total { display: flex; justify-content: space-between; font-size: 16px; font-weight: bold; margin-top: 10px; padding-top: 5px; border-top: 1px dashed black; }
        .rec-footer { margin-top: 20px; font-size: 12px; font-weight: bold; text-transform: uppercase; }
        
        /* HIDE BUTTONS IN PRINT */
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
# === RECEIPT GENERATOR HTML (FIXED) ===
# ==========================================
def get_receipt_html(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME)
    addr = get_setting("receipt_address", "Bakı, Azərbaycan")
    phone = get_setting("receipt_phone", "+994 50 000 00 00")
    foot = get_setting("receipt_footer", "THANK YOU!")
    logo = get_setting("receipt_logo_base64")
    time_str = get_baku_now().strftime('%d/%m/%Y   %I:%M:%S %p')
    
    img_tag = f'<img src="data:image/png;base64,{logo}" class="rec-logo"><br>' if logo else ""
    
    html = f"""
    <div id='receipt-area'>
        {img_tag}
        <div class='rec-title'>RECEIPT OF SALE<br>{store}</div>
        <div class='rec-text'>{addr}<br>Tel: {phone}</div>
        <div class='rec-dash'></div>
        <div class='rec-text'>{time_str}</div>
        <div class='rec-dash'></div>
        <table class='rec-table'>
            <tr><th class='col-qty'>QTY</th><th class='col-name'>NAME</th><th class='col-amt'>AMT</th></tr>
    """
    for i in cart:
        html += f"<tr><td class='col-qty'>{int(i['qty'])}</td><td class='col-name'>{i['item_name']}</td><td class='col-amt'>${i['qty']*i['price']:.2f}</td></tr>"
    
    html += f"""
        </table>
        <div class='rec-dash'></div>
        <div class='rec-total'><span>Total</span><span>${total:.2f}</span></div>
        <div class='rec-dash'></div>
        <div class='rec-footer'>{foot}</div>
    </div>
    """
    return html

@st.dialog("Ödəniş & Çek")
def show_payment_popup(cart, total, customer):
    rec_html = get_receipt_html(cart, total)
    st.markdown(rec_html, unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        # PURE JS PRINT BUTTON (Fixes "Print not functional")
        st.markdown("""
            <div style="text-align:center; margin-top:20px;">
                <button onclick="window.print()" style="background-color:#FF6B35; color:white; padding:10px 20px; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">
                    🖨️ Çap Et (Print)
                </button>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        if customer and customer.get('email'):
            if st.button("📧 Email Göndər", use_container_width=True):
                send_email(customer['email'], "Sizin Çekiniz", rec_html)
                st.success("Göndərildi!")
        else: st.warning("⛔ Email yoxdur")

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
        if public_msg: st.info(f"📢 {public_msg}")

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            with st.container(border=True):
                st.info(f"💌 {row['message']}")
                if row['attached_coupon']: st.success(f"🎁 HƏDİYYƏ: {row['attached_coupon']}")
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

        # STAMP CARD
        ctype = user['type']; stamp_class = "stamp-std"; st_label = "MEMBER"; disc_txt = ""
        if ctype == 'golden': stamp_class="stamp-gold"; st_label="GOLDEN MEMBER"; disc_txt="✨ 5% ENDİRİM"
        elif ctype == 'platinum': stamp_class="stamp-plat"; st_label="PLATINUM MEMBER"; disc_txt="✨ 10% ENDİRİM"
        elif ctype == 'elite': stamp_class="stamp-elite"; st_label="ELITE VIP"; disc_txt="✨ 20% ENDİRİM"
        elif ctype == 'thermos': stamp_class="stamp-eco"; st_label="EKO-TERM MEMBER"; disc_txt="🌿 20% ENDİRİM"

        st.markdown(f"""
        <div class="stamp-container">
            <div class="stamp-card {stamp_class}">
                <div class="stamp-title">{st_label}</div>
                <div>{disc_txt}</div>
                <div class="stamp-stars">{user['stars']} / 10</div>
                <div class="stamp-footer">ULDUZ BALANSI</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png" if i==9 else "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            style = "opacity: 1;" if i < user['stars'] or (i==9 and user['stars']>=9) else "opacity: 0.2; filter: grayscale(100%);"
            if i==9 and user['stars']>=9: html += f'<img src="{icon}" class="gift-box-anim">'
            else: html += f'<img src="{icon}" class="coffee-icon-img" style="{style}">'
        st.markdown(html + '</div>', unsafe_allow_html=True)
        if user['stars'] >= 9: st.balloons()

        cps = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": card_id})
        for _, cp in cps.iterrows(): st.success(f"🎫 KUPON: {cp['coupon_type']}")

        with st.form("feed"):
            s = st.feedback("stars"); m = st.text_input("Rəyiniz", key="feed_msg")
            if st.form_submit_button("Göndər") and s:
                run_action("INSERT INTO feedbacks (card_id, rating, comment, created_at) VALUES (:i,:r,:m, :t)", {"i":card_id, "r":s+1, "m":m, "t":get_baku_now()}); st.success("Təşəkkürlər!")
        
        st.divider(); qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")
    st.stop() 

# ==========================================
# === STAFF & ADMIN INTERFACE ===
# ==========================================

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

def render_takeaway():
    c1, c2 = st.columns([1.5, 3])
    with c1:
        st.info("🧾 Al-Apar Çek")
        with st.form("sc_ta", clear_on_submit=True):
            ci, cb = st.columns([3,1]); qv = ci.text_input("Müştəri", label_visibility="collapsed", placeholder="Skan...", key="ta_inp"); 
            submitted = cb.form_submit_button("🔍")
            if submitted or qv:
                try: 
                    cid = qv.strip().split("id=")[1].split("&")[0] if "id=" in qv else qv.strip()
                    r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                    if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.toast("✅"); st.rerun()
                    else: st.error("Tapılmadı")
                except: pass
        if st.session_state.current_customer_ta:
            c = st.session_state.current_customer_ta
            nts = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":c['card_id']})
            if not nts.empty:
                st.warning(f"🔔 {len(nts)} OXUNMAMIŞ MESAJ!")
                for _, n in nts.iterrows():
                    if n['attached_coupon'] and st.button(f"🎁 Tətbiq Et: {n['attached_coupon']}", key=f"ap_{n['id']}"):
                        run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.success("OK"); st.rerun()
            if c.get('staff_note'): st.info(f"📝 {c['staff_note']}")
            st.markdown(f"<div style='padding:10px; border:1px solid #ddd; border-radius:10px; margin-bottom:10px;'>👤 <b>{c['card_id']}</b><br>⭐ {c['stars']}</div>", unsafe_allow_html=True)
            if st.button("Ləğv Et", key="ta_cl"): st.session_state.current_customer_ta=None; st.rerun()
        
        raw_total, final_total, _, free_count, _, _, _ = calculate_smart_total(st.session_state.cart_takeaway, st.session_state.current_customer_ta, is_table=False)
        
        if st.session_state.cart_takeaway:
            for i, it in enumerate(st.session_state.cart_takeaway):
                st.markdown(f"<div style='background:white;padding:10px;margin-bottom:5px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;border:1px solid #ddd;'><div style='flex:2'><b>{it['item_name']}</b></div><div style='flex:1'>{it['price']}</div><div style='flex:1;color:#E65100'>x{it['qty']}</div><div style='flex:1;text-align:right'>{it['qty']*it['price']:.1f}</div></div>", unsafe_allow_html=True)
                b1,b2,b3=st.columns([1,1,4])
                with b1: 
                    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                    if st.button("➖", key=f"m_ta_{i}"): 
                        if it['qty']>1: it['qty']-=1 
                        else: st.session_state.cart_takeaway.pop(i)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                with b2:
                    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                    if st.button("➕", key=f"p_ta_{i}"): it['qty']+=1; st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown(f"<h3 style='text-align:right; color:#777; text-decoration: line-through;'>{raw_total:.2f} ₼</h3>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:right; color:#E65100'>{final_total:.2f} ₼</h2>", unsafe_allow_html=True)
        if free_count > 0: st.success(f"🎁 {free_count} Kofe HƏDİYYƏ!")

        pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True, key="pm_ta")
        if st.button("✅ ÖDƏNİŞ ET", type="primary", use_container_width=True, key="pay_ta"):
            if not st.session_state.cart_takeaway: st.error("Boşdur!"); st.stop()
            try:
                istr = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_takeaway])
                cust_id = st.session_state.current_customer_ta['card_id'] if st.session_state.current_customer_ta else None
                run_action("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id) VALUES (:i,:t,:p,:c,:time, :cid)", 
                           {"i":istr,"t":final_total,"p":("Cash" if pm=="Nəğd" else "Card"),"c":st.session_state.user, "time":get_baku_now(), "cid":cust_id})
                with conn.session as s:
                    for it in st.session_state.cart_takeaway:
                        rs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                        for r in rs: s.execute(text("UPDATE ingredients SET stock_qty=stock_qty-:q WHERE name=:n"), {"q":float(r[1])*it['qty'], "n":r[0]})
                    if st.session_state.current_customer_ta:
                        new_stars_balance = (st.session_state.current_customer_ta['stars'] + sum([item['qty'] for item in st.session_state.cart_takeaway if item.get('is_coffee')])) - (free_count * 10)
                        s.execute(text("UPDATE customers SET stars=:s WHERE card_id=:id"), {"s":new_stars_balance, "id":cust_id})
                    s.commit()
                show_payment_popup(st.session_state.cart_takeaway, final_total, st.session_state.current_customer_ta)
                st.session_state.cart_takeaway=[]
            except Exception as e: st.error(str(e))
    with c2: render_menu_grid(st.session_state.cart_takeaway, "ta")

def render_tables_main():
    if st.session_state.selected_table: 
        tbl = st.session_state.selected_table
        c_back, c_trans = st.columns([3, 1])
        if c_back.button("⬅️ Masalara Qayıt", key="back_tbl", use_container_width=True, type="secondary"): st.session_state.selected_table = None; st.session_state.cart_table = []; st.rerun()
        st.markdown(f"### 📝 Sifariş: {tbl['label']}")
        c1, c2 = st.columns([1.5, 3])
        with c1:
            st.info("Masa Sifarişi"); db_cust_id = tbl.get('active_customer_id')
            if db_cust_id and not st.session_state.current_customer_tb:
                 r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":db_cust_id})
                 if not r.empty: st.session_state.current_customer_tb = r.iloc[0].to_dict()
            if st.session_state.current_customer_tb:
                c = st.session_state.current_customer_tb; st.success(f"👤 {c['card_id']} | ⭐ {c['stars']}")
                nts = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":c['card_id']})
                if not nts.empty: st.warning("🔔 MÜŞTƏRİYƏ ÖZƏL TƏKLİFLƏR VAR!")
            raw_total, final_total, _, _, _, serv_chg, _ = calculate_smart_total(st.session_state.cart_table, st.session_state.current_customer_tb, is_table=True)
            if st.session_state.cart_table:
                for i, it in enumerate(st.session_state.cart_table):
                    status = it.get('status', 'new'); bg_col = "#e3f2fd" if status == 'sent' else "white"
                    st.markdown(f"<div style='background:{bg_col};padding:10px;margin-bottom:5px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;border:1px solid #ddd;'><div style='flex:2'><b>{it['item_name']}</b></div><div style='flex:1'>{it['price']}</div><div style='flex:1;color:#E65100'>x{it['qty']}</div><div style='flex:1;text-align:right'>{it['qty']*it['price']:.1f}</div></div>", unsafe_allow_html=True)
                    b1,b2,b3=st.columns([1,1,1])
                    with b1:
                        st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                        if st.button("➖", key=f"m_tb_{i}"): 
                            if status != 'sent': st.session_state.cart_table.pop(i); st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    with b2:
                        st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                        if st.button("➕", key=f"p_tb_{i}"): it['qty']+=1; st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
            st.markdown(f"<h3 style='text-align:right; color:#777; text-decoration: line-through;'>{raw_total:.2f} ₼</h3>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='text-align:right; color:#E65100'>{final_total:.2f} ₼</h2>", unsafe_allow_html=True)
            if serv_chg > 0: st.caption(f"ℹ️ Servis Haqqı (7%): {serv_chg:.2f} ₼ daxildir")
            col_s, col_p = st.columns(2)
            if col_s.button("🔥 MƏTBƏXƏ GÖNDƏR", key="save_tbl", use_container_width=True):
                for x in st.session_state.cart_table: x['status'] = 'sent'
                run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id", {"i":json.dumps(st.session_state.cart_table), "t":final_total, "id":tbl['id']}); st.success("Göndərildi!"); time.sleep(1); st.rerun()
            if col_p.button("✅ ÖDƏNİŞ ET", key="pay_tbl", type="primary", use_container_width=True):
                if not st.session_state.cart_table: st.error("Boşdur!"); st.stop()
                run_action("UPDATE tables SET is_occupied=FALSE, items='[]', total=0, active_customer_id=NULL WHERE id=:id", {"id":tbl['id']}); 
                show_payment_popup(st.session_state.cart_table, final_total, st.session_state.current_customer_tb)
                st.session_state.selected_table = None; st.session_state.cart_table = []
        with c2: render_menu_grid(st.session_state.cart_table, "tb")
    else: 
        if st.session_state.role in ['admin', 'manager']:
            with st.expander("🛠️ Masa İdarəetməsi"):
                n_l = st.text_input("Masa Adı"); 
                if st.button("➕ Yarat"): run_action("INSERT INTO tables (label) VALUES (:l)", {"l":n_l}); st.rerun()
                d_l = st.selectbox("Silinəcək", run_query("SELECT label FROM tables")['label'].tolist() if not run_query("SELECT label FROM tables").empty else [])
                if st.button("❌ Sil"): run_action("DELETE FROM tables WHERE label=:l", {"l":d_l}); st.rerun()
        st.markdown("### 🍽️ ZAL PLAN")
        tables = run_query("SELECT * FROM tables ORDER BY id"); cols = st.columns(3)
        for idx, row in tables.iterrows():
            with cols[idx % 3]:
                if st.button(f"{row['label']}\n\n{row['total']} ₼", key=f"tbl_btn_{row['id']}", use_container_width=True, type="primary" if row['is_occupied'] else "secondary"):
                    items = json.loads(row['items']) if row['items'] else []
                    st.session_state.selected_table = row.to_dict(); st.session_state.cart_table = items; st.rerun()

def render_analytics(role):
    st.subheader("📊 Analitika")
    
    # STAFF LOCK: Staff sees only Sales, filtered by their own username
    tabs_list = ["Satışlar", "Xərclər", "Mənfəət"]
    if role == 'staff': tabs_list = ["Satışlar"]
    
    tabs = st.tabs(tabs_list)
    
    c1, c2 = st.columns([1, 2])
    f_type = c1.selectbox("Filtr", ["Bu Gün", "Bu Ay", "Tarix Aralığı"], label_visibility="collapsed")
    d1 = get_baku_now().date(); d2 = get_baku_now().date()
    if f_type == "Bu Ay": d1 = d1.replace(day=1)
    elif f_type == "Tarix Aralığı":
        cd1, cd2 = c2.columns(2)
        d1 = cd1.date_input("Start"); d2 = cd2.date_input("End")
    
    with tabs[0]: # Sales
        base_sql = f"SELECT * FROM sales WHERE created_at::date >= '{d1}' AND created_at::date <= '{d2}'"
        if role == 'staff': base_sql += f" AND cashier = '{st.session_state.user}'" # STAFF FILTER
        base_sql += " ORDER BY created_at DESC"
        
        df_sales = run_query(base_sql)
        st.metric("Toplam Satış", f"{df_sales['total'].sum():.2f} ₼")
        if role == 'admin':
            df_sales.insert(0, "Seç", False); ed = st.data_editor(df_sales, hide_index=True)
            to_del = ed[ed["Seç"]]['id'].tolist()
            if to_del:
                pas = st.text_input("Admin Şifrə", type="password")
                if st.button("Satışı Sil"):
                    adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                    if verify_password(pas, adm.iloc[0]['password']):
                        for d in to_del: run_action("DELETE FROM sales WHERE id=:id", {"id":d})
                        st.success("Silindi!"); st.rerun()
                    else: st.error("Səhv")
        else: st.dataframe(df_sales)
        
        if role in ['admin', 'manager']:
            st.divider()
            target = st.text_input("Hesabatı Göndər (Email)", placeholder="mudir@mail.com")
            if st.button("Göndər"):
                if target and not df_sales.empty:
                    html = f"<h2>Hesabat ({d1} - {d2})</h2><table border='1'><tr><th>Tarix</th><th>Kassir</th><th>Məbləğ</th></tr>"
                    for _, r in df_sales.iterrows(): html += f"<tr><td>{r['created_at']}</td><td>{r['cashier']}</td><td>{r['total']}</td></tr>"
                    html += "</table>"
                    send_email(target, "Satış Hesabatı", html); st.success("Getdi!")

    if role != 'staff':
        with tabs[1]: # Expenses
            exp_sql = f"SELECT * FROM expenses WHERE created_at::date >= '{d1}' AND created_at::date <= '{d2}'"
            df_exp = run_query(exp_sql)
            st.metric("Toplam Xərc", f"{df_exp['amount'].sum():.2f} ₼")
            if role in ['admin', 'manager']:
                with st.form("new_exp"):
                    t=st.text_input("Təyinat"); a=st.number_input("Məbləğ"); c=st.selectbox("Kat", ["Maaş","İcarə","Kommunal","Təchizat"])
                    if st.form_submit_button("Xərc Əlavə Et"):
                        run_action("INSERT INTO expenses (title,amount,category,created_at) VALUES (:t,:a,:c,:time)", {"t":t,"a":a,"c":c,"time":get_baku_now()}); st.rerun()
            if role == 'admin':
                df_exp.insert(0, "Seç", False); ed_x = st.data_editor(df_exp, hide_index=True)
                del_x = ed_x[ed_x["Seç"]]['id'].tolist()
                if del_x:
                    px = st.text_input("Admin Şifrə", type="password", key="x_del")
                    if st.button("Xərci Sil"):
                        adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                        if verify_password(px, adm.iloc[0]['password']):
                            for d in del_x: run_action("DELETE FROM expenses WHERE id=:id", {"id":d})
                            st.success("Silindi!"); st.rerun()

        with tabs[2]: # Profit
            inc = df_sales['total'].sum(); out = df_exp['amount'].sum()
            st.metric("Xalis Mənfəət", f"{inc - out:.2f} ₼", delta=f"{inc} (Gəlir) - {out} (Xərc)")

def render_logs(role):
    st.subheader("📜 Sistem Logları")
    c1, c2 = st.columns(2)
    d1 = c1.date_input("Başlanğıc", value=get_baku_now().date(), key="l_d1")
    d2 = c2.date_input("Bitmə", value=get_baku_now().date(), key="l_d2")
    logs = run_query(f"SELECT * FROM system_logs WHERE created_at::date >= '{d1}' AND created_at::date <= '{d2}' ORDER BY created_at DESC")
    if role == 'admin':
        logs.insert(0, "Seç", False); ed_l = st.data_editor(logs, hide_index=True)
        del_l = ed_l[ed_l["Seç"]]['id'].tolist()
        if del_l:
            pl = st.text_input("Admin Şifrə", type="password", key="l_del_pass")
            if st.button("Logları Sil"):
                adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                if verify_password(pl, adm.iloc[0]['password']):
                    for d in del_l: run_action("DELETE FROM system_logs WHERE id=:id", {"id":d})
                    st.success("Təmizləndi!"); st.rerun()
    else: st.dataframe(logs)

def render_crm(role):
    st.subheader("👥 CRM & Marketinq")
    t1, t2, t3 = st.tabs(["📢 Mesaj", "🎟️ Şablonlar", "🛡️ Admin Tools"])
    with t1:
        msg = st.text_area("Mesaj Mətni"); target = st.radio("Kimə?", ["🌍 Hamıya", "👤 Fərdi"], horizontal=True)
        sel_ids = []
        if target == "👤 Fərdi":
            df = run_query("SELECT card_id, email, type, staff_note FROM customers"); df.insert(0, "Seç", False)
            ed = st.data_editor(df, hide_index=True); sel_ids = ed[ed["Seç"]]['card_id'].tolist()
            with st.expander("📝 Gizli Qeyd"):
                new_note = st.text_input("Qeyd"); 
                if st.button("Yaz"): 
                    for i in sel_ids: run_action("UPDATE customers SET staff_note=:n WHERE card_id=:i", {"n":new_note, "i":i}); st.success("Yazıldı!")
        
        coupons = ["(Yoxdur)"] + run_query("SELECT name FROM coupon_templates")['name'].tolist()
        cp = st.selectbox("Kupon Yapışdır", coupons); final_cp = None if cp == "(Yoxdur)" else cp
        c_app, c_mail = st.columns(2)
        if c_app.button("📱 TƏTBİQƏ GÖNDƏR", type="primary"):
            if target == "🌍 Hamıya": set_setting("public_msg", msg); st.success("Vitrin elanı yeniləndi!")
            else:
                for cid in sel_ids: run_action("INSERT INTO notifications (card_id, message, attached_coupon, created_at) VALUES (:c,:m,:cp,:t)", {"c":cid, "m":msg, "cp":final_cp, "t":get_baku_now()})
                st.success("Göndərildi!")
        if c_mail.button("📧 EMAILƏ GÖNDƏR"):
            if sel_ids:
                ems = run_query(f"SELECT email FROM customers WHERE card_id IN ({','.join([repr(x) for x in sel_ids])})")['email'].tolist()
                for e in ems: send_email(e, "Emalatkhana Xəbər", msg)
                st.success("Emaillər getdi!")
    with t2:
        with st.form("new_templ"):
            n = st.text_input("Şablon Adı (Məs: YAY20)"); p = st.number_input("Faiz (%)", 1, 100, 10); d = st.number_input("Gün", 1, 365, 7)
            if st.form_submit_button("Yarat"):
                run_action("INSERT INTO coupon_templates (name, percent, days_valid) VALUES (:n,:p,:d)", {"n":n,"p":p,"d":d}); st.success("Yarandı!")
        st.dataframe(run_query("SELECT * FROM coupon_templates"), use_container_width=True)
    if role == 'admin':
        with t3:
            del_df = run_query("SELECT card_id, email, type FROM customers"); del_df.insert(0, "Seç", False)
            del_ed = st.data_editor(del_df, hide_index=True); del_ids = del_ed[del_ed["Seç"]]['card_id'].tolist()
            if del_ids:
                adm_pass = st.text_input("Admin Şifrəsi", type="password")
                if st.button("SİL (Geri Dönüş Yoxdur)", type="primary"):
                    adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                    if verify_password(adm_pass, adm.iloc[0]['password']):
                        for di in del_ids: run_action("DELETE FROM customers WHERE card_id=:id", {"id":di}); run_action("DELETE FROM customer_coupons WHERE card_id=:id", {"id":di})
                        st.success("Silindi!")
                    else: st.error("Şifrə səhvdir")

# --- MAIN ---
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
                            clear_failed_login(row['username']); st.session_state.logged_in=True; st.session_state.user=row['username']; st.session_state.role='staff'; st.rerun(); found=True; break
                    if not found: st.error("Yanlış PIN!")
        with tabs[1]:
            with st.form("admin_login"):
                u = st.text_input("İstifadəçi"); passw = st.text_input("Şifrə", type="password")
                if st.form_submit_button("Daxil Ol", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not udf.empty and verify_password(passw, udf.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=udf.iloc[0]['role']; st.rerun()
                    else: st.error("Səhv!")
else:
    h1, h2, h3 = st.columns([4, 1, 1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄 Yenilə", use_container_width=True): st.rerun()
    with h3: 
        if st.button("🚪 Çıxış", type="primary", use_container_width=True): 
            log_system(st.session_state.user, "Logout")
            st.session_state.logged_in = False; st.rerun()
    st.divider()

    role = st.session_state.role
    
    if role == 'admin':
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "📜 Resept", "Analitika", "📜 Loglar", "👥 CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
        with tabs[0]: render_takeaway()
        with tabs[1]: render_tables_main()
        with tabs[2]: # INVENTORY
            st.subheader("📦 Anbar")
            cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist(); cat_list = ["Bütün"] + cats
            sel_inv_cat = st.selectbox("Filtr", cat_list)
            sql = "SELECT * FROM ingredients"; p={}
            if sel_inv_cat != "Bütün": sql += " WHERE category=:c"; p['c']=sel_inv_cat
            df_inv = run_query(sql, p); df_inv.insert(0, "Seç", False)
            ed_inv = st.data_editor(df_inv, hide_index=True)
            to_del_inv = ed_inv[ed_inv["Seç"]]['id'].tolist()
            if to_del_inv:
                pas = st.text_input("Admin Şifrə", type="password", key="inv_del")
                if st.button("Seçilənləri Sil"):
                    adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                    if verify_password(pas, adm.iloc[0]['password']):
                        for d in to_del_inv: run_action("DELETE FROM ingredients WHERE id=:id", {"id":d}); log_system(st.session_state.user, f"Deleted Inventory ID: {d}")
                        st.success("Silindi!"); st.rerun()
            with st.expander("➕ Yeni Mal"):
                with st.form("ni"):
                    n=st.text_input("Ad"); q=st.number_input("Say"); u=st.selectbox("Vahid",["gr","ml","ədəd","litr","kq"])
                    ex_cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist()
                    cat_sel = st.selectbox("Kateqoriya", ex_cats + ["➕ Yeni..."])
                    fin_cat = st.text_input("Yeni Ad") if cat_sel == "➕ Yeni..." else cat_sel
                    if st.form_submit_button("Yarat"): 
                        run_action("INSERT INTO ingredients (name,stock_qty,unit,category) VALUES (:n,:q,:u,:c)", {"n":n,"q":q,"u":u,"c":fin_cat}); 
                        log_system(st.session_state.user, f"Created Item: {n}")
                        st.rerun()
        
        with tabs[3]: # RECIPE
            st.subheader("📜 Resept")
            all_menu = run_query("SELECT item_name FROM menu WHERE is_active=TRUE")['item_name'].tolist()
            sel_prod = st.selectbox("Məhsul Seç", ["(Seçin)"] + all_menu)
            if sel_prod != "(Seçin)":
                st.markdown(f"#### 🍹 {sel_prod}")
                recs = run_query("SELECT id, ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:n", {"n":sel_prod})
                for _, r in recs.iterrows(): st.text(f"🔹 {r['ingredient_name']} - {r['quantity_required']}")
                recs.insert(0, "Seç", False)
                ed_rec = st.data_editor(recs, hide_index=True)
                del_rec = ed_rec[ed_rec["Seç"]]['id'].tolist()
                if del_rec:
                    rp = st.text_input("Şifrə", type="password", key="rp_del")
                    if st.button("Reseptdən Sil"):
                        adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                        if verify_password(rp, adm.iloc[0]['password']):
                            for d in del_rec: run_action("DELETE FROM recipes WHERE id=:id", {"id":d}); log_system(st.session_state.user, f"Deleted Recipe Part ID: {d}")
                            st.success("Silindi!"); st.rerun()
                st.divider()
                with st.form("add_rec"):
                    ings = run_query("SELECT name FROM ingredients")['name'].tolist()
                    s_i = st.selectbox("Xammal", ings); s_q = st.number_input("Miqdar")
                    if st.form_submit_button("Əlavə Et"): run_action("INSERT INTO recipes (menu_item_name,ingredient_name,quantity_required) VALUES (:m,:i,:q)",{"m":sel_prod,"i":s_i,"q":s_q}); st.rerun()

        with tabs[4]: render_analytics(role='admin')
        with tabs[5]: render_logs(role='admin')
        with tabs[6]: render_crm(role='admin')
        with tabs[7]: # MENU
            st.subheader("📋 Menyu")
            with st.form("nm"):
                c1, c2, c3 = st.columns(3)
                with c1: n=st.text_input("Ad"); p=st.number_input("Qiymət", min_value=0.0)
                with c2: c=st.text_input("Kat"); ic=st.checkbox("Kofe?"); pt=st.selectbox("Printer", ["kitchen", "bar"])
                with c3: ph=st.number_input("Yarım Qiymət", 0.0)
                if st.form_submit_button("Yarat"): 
                    ph_val = ph if ph > 0 else None
                    run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee,printer_target,price_half) VALUES (:n,:p,:c,TRUE,:ic,:pt,:ph)", 
                               {"n":n,"p":p,"c":c,"ic":ic,"pt":pt,"ph":ph_val}); log_system(st.session_state.user, f"Created Menu Item: {n}"); st.rerun()
            ml = run_query("SELECT * FROM menu"); ml.insert(0, "Seç", False)
            ed_m = st.data_editor(ml, hide_index=True)
            del_m = ed_m[ed_m["Seç"]]['id'].tolist()
            if del_m:
                mp = st.text_input("Şifrə", type="password", key="mp_del")
                if st.button("Menyudan Sil"):
                    adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                    if verify_password(mp, adm.iloc[0]['password']):
                        for d in del_m: run_action("DELETE FROM menu WHERE id=:id", {"id":d}); log_system(st.session_state.user, f"Deleted Menu ID: {d}")
                        st.success("Silindi!"); st.rerun()

        with tabs[8]: # Settings
            st.subheader("⚙️ Ayarlar")
            
            # --- RESTORE SECTION (MOVED TO TOP VISIBLE) ---
            st.markdown("#### 🔄 DATABASE RESTORE (Bərpa)")
            c_res1, c_res2 = st.columns(2)
            rf = c_res1.file_uploader("Restore (.xlsx)", key="rest_file")
            rp = c_res2.text_input("Restore Password", type="password", key="rest_pass")
            if rf and c_res2.button("Bərpa Et", key="btn_rest"):
                adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                if verify_password(rp, adm.iloc[0]['password']):
                    xls = pd.ExcelFile(rf)
                    try:
                        for t in ["menu","ingredients","recipes","coupon_templates"]:
                            if t in xls.sheet_names: run_action(f"DELETE FROM {t}"); pd.read_excel(xls, t).to_sql(t, conn.engine, if_exists='append', index=False)
                        log_system(st.session_state.user, "Restored Backup"); st.success("Bərpa olundu!")
                    except: st.error("Xəta")
                else: st.error("Şifrə Səhv")
            
            st.divider()

            with st.expander("🧾 Çek Dizaynı"):
                s_name = st.text_input("Mağaza Adı", value=get_setting("receipt_store_name", BRAND_NAME))
                s_addr = st.text_input("Ünvan", value=get_setting("receipt_address", "Bakı"))
                s_phone = st.text_input("Telefon", value=get_setting("receipt_phone", ""))
                s_foot = st.text_input("Footer", value=get_setting("receipt_footer", "Təşəkkürlər!"))
                if st.button("Çek Ayarlarını Saxla"):
                    set_setting("receipt_store_name", s_name); set_setting("receipt_address", s_addr)
                    set_setting("receipt_phone", s_phone); set_setting("receipt_footer", s_foot)
                    st.success("Yadda Saxlanıldı!")

            with st.expander("👤 Personal"):
                with st.form("add_u"):
                    u=st.text_input("Ad"); pin=st.text_input("PIN"); r=st.selectbox("Rol", ["staff","manager"])
                    if st.form_submit_button("Yarat"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":u, "p":hash_password(pin), "r":r}); log_system(st.session_state.user, f"Created User: {u}"); st.success("OK")
                users = run_query("SELECT username, role FROM users"); users.insert(0, "Seç", False)
                ed_u = st.data_editor(users, hide_index=True)
                sel_u = ed_u[ed_u["Seç"]]['username'].tolist()
                if sel_u:
                    up = st.text_input("Şifrə", type="password", key="u_del")
                    if st.button("Sil"):
                        adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                        if verify_password(up, adm.iloc[0]['password']):
                            for d in sel_u: 
                                if d != "admin": run_action("DELETE FROM users WHERE username=:u", {"u":d}); log_system(st.session_state.user, f"Deleted User: {d}")
                            st.success("Silindi!"); st.rerun()
                    new_pin = st.text_input("Yeni PIN", key="np_u")
                    if st.button("Şifrəni Dəyiş"):
                         for d in sel_u: run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_pin), "u":d}); log_system(st.session_state.user, f"Changed Password: {d}"); st.success("Dəyişildi!")

            with st.expander("🔧 Sistem"):
                show = st.checkbox("İşçi Ekranında Masaları Göstər", value=(get_setting("staff_show_tables", "TRUE")=="TRUE"))
                if st.button("Yadda Saxla", key="sv_sh"): set_setting("staff_show_tables", "TRUE" if show else "FALSE"); st.rerun()

            with st.expander("📱 Müştəri Ekranı"):
                lg = st.file_uploader("Logo")
                if lg: set_setting("receipt_logo_base64", image_to_base64(lg)); st.success("Logo!")
                t = st.text_input("Başlıq", value=get_setting("customer_ui_title", BRAND_NAME))
                terms = st.text_area("Qaydalar (HTML)", value=get_setting("customer_terms", DEFAULT_TERMS))
                if st.button("Yadda Saxla", key="save_cust"): 
                    set_setting("customer_ui_title", t); set_setting("customer_terms", terms); st.success("Oldu!")

        with tabs[9]: # Backup
            if st.button("📥 FULL BACKUP"):
                log_system(st.session_state.user, "Downloaded Backup")
                out = BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    for t in ["users","menu","sales","ingredients","recipes","customers","customer_coupons","notifications","coupon_templates","settings","expenses","system_logs"]:
                        try: run_query(f"SELECT * FROM {t}").to_excel(writer, sheet_name=t, index=False)
                        except: pass
                st.download_button("⬇️ Endir", out.getvalue(), "Backup_Full.xlsx")
        
        with tabs[10]: # QR
            cnt = st.number_input("Say",1,100)
            k = st.selectbox("Növ", ["Golden (5%)", "Platinum (10%)", "Elite (20%)", "Termos (20%)"])
            if st.button("QR Yarat"): 
                for _ in range(cnt):
                    kt = k.split(" ")[0].lower() # extract 'golden' from 'Golden (5%)'
                    i = str(random.randint(10000000, 99999999)); tok = secrets.token_hex(8)
                    run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":kt, "st":tok})
                log_system(st.session_state.user, f"Generated {cnt} {k} QRs"); st.success("Hazırdır!")

    elif role == 'manager':
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar (Mədaxil)", "📊 Analitika", "📜 Loglar", "👥 CRM"])
        with tabs[0]: render_takeaway()
        with tabs[1]: render_tables_main()
        with tabs[2]:
            st.subheader("📦 Anbar Mədaxil")
            df_inv = run_query("SELECT * FROM ingredients")
            cols = st.columns(4)
            for i, r in df_inv.iterrows():
                with cols[i%4]:
                    @st.dialog("Mədaxil")
                    def add_stock_dia(id, name):
                        add = st.number_input("Artır", 0.0)
                        if st.button("Təsdiqlə"): 
                            run_action("UPDATE ingredients SET stock_qty=stock_qty+:q WHERE id=:id",{"q":add,"id":id}); 
                            log_system(st.session_state.user, f"Manager Added Stock: {add} to {name}"); st.rerun()
                    if st.button(f"{r['name']}\n{format_qty(r['stock_qty'])} {r['unit']}", key=f"man_inv_{r['id']}"): add_stock_dia(r['id'], r['name'])
        with tabs[3]: render_analytics(role='manager')
        with tabs[4]: render_logs(role='manager')
        with tabs[5]: render_crm(role='manager')

    elif role == 'staff':
        show_tbl = (get_setting("staff_show_tables", "TRUE") == "TRUE")
        tabs_list = ["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "Satışlar"] if show_tbl else ["🏃‍♂️ AL-APAR", "Satışlar"]
        staff_tabs = st.tabs(tabs_list)
        with staff_tabs[0]: render_takeaway()
        if show_tbl:
            with staff_tabs[1]: render_tables_main()
            with staff_tabs[2]: render_analytics(role='staff')
        else:
            with staff_tabs[1]: render_analytics(role='staff')

    st.markdown(f"<div class='footer'>Ironwaves POS {VERSION} | © 2026</div>", unsafe_allow_html=True)
