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

# ==========================================
# === EMALATKHANA POS - V5.15 (GRAND FINALE) ===
# ==========================================

VERSION = "v5.15 (Classic UI + Full Artillery)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- DEFAULT TERMS ---
DEFAULT_TERMS = """<div style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h4 style="color: #2E7D32; margin-bottom: 5px;">📜 İSTİFADƏÇİ RAZILAŞMASI</h4>
    <p>Bu loyallıq proqramı "Emalatkhana" tərəfindən təqdim edilir.</p>
</div>"""

# --- COMPLIMENTS ---
COMPLIMENTS = [
    "Gülüşünüz günümüzü işıqlandırdı! ☀️",
    "Bu gün möhtəşəm görünürsünüz! ✨",
    "Sizi yenidən görmək necə xoşdur! ☕",
    "Uğurlu gün arzulayırıq! 🚀",
    "Sizin üçün ən yaxşısını hazırlayırıq! ❤️",
    "Enerjinizə heyranıq! ⚡"
]

# --- INFRA ---
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

# --- CSS (V5.3 CLASSIC UI + ELEGANT CUSTOMER CARD) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap'); /* Elegant Font */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

    /* GLOBAL - V5.3 CLEAN STYLE */
    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F4F6F9 !important; color: #333333 !important; font-family: 'Oswald', sans-serif !important; }
    p, h1, h2, h3, h4, h5, h6, li, span, label, div[data-testid="stMarkdownContainer"] p { color: #333333 !important; }
    div[data-baseweb="input"] { background-color: #FFFFFF !important; border: 1px solid #ced4da !important; color: #333 !important; }
    input, textarea { color: #333 !important; }
    div[data-baseweb="select"] > div { background-color: #FFFFFF !important; color: #333 !important; }
    
    header, #MainMenu, footer, [data-testid="stSidebar"] { display: none !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    
    /* TABS (Classic V5.3) */
    button[data-baseweb="tab"] {
        font-family: 'Oswald', sans-serif !important; font-size: 18px !important; font-weight: 700 !important;
        background-color: white !important; border: 2px solid #FFCCBC !important; border-radius: 12px !important;
        margin: 0 4px !important; color: #555 !important; flex-grow: 1;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #2E7D32, #1B5E20) !important; border-color: #2E7D32 !important; 
        box-shadow: 0 4px 12px rgba(46, 125, 50, 0.4);
    }
    button[data-baseweb="tab"][aria-selected="true"] p { color: white !important; }
    
    /* BUTTONS (Classic V5.3 - Clean White) */
    div.stButton > button { 
        border-radius: 12px !important; height: 60px !important; font-weight: 700 !important; 
        box-shadow: 0 4px 0 rgba(0,0,0,0.1) !important; transition: all 0.1s !important; 
        background: white !important; color: #333 !important; border: 1px solid #ddd !important; 
    }
    div.stButton > button:active { transform: translateY(3px) !important; box-shadow: none !important; }
    div.stButton > button:hover { border-color: #2E7D32 !important; color: #2E7D32 !important; background-color: #F1F8E9 !important; }

    /* PRIMARY ACTIONS (Orange Gradient) */
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    div.stButton > button[kind="primary"] p { color: white !important; }
    
    /* SECONDARY (Green Gradient) */
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #43A047, #2E7D32) !important; color: white !important; border: 2px solid #1B5E20 !important; height: 120px !important; font-size: 24px !important; white-space: pre-wrap !important; }
    div.stButton > button[kind="secondary"] p { color: white !important; }
    
    .small-btn button { height: 35px !important; min-height: 35px !important; font-size: 14px !important; padding: 0 !important; }

    /* --- CUSTOMER SCREEN (ELEGANT LUXURY) --- */
    .digital-card { 
        border-radius: 24px; padding: 30px; box-shadow: 0 20px 50px rgba(0,0,0,0.15); 
        text-align: center; margin-bottom: 25px; position: relative; overflow: hidden; color: #333;
        font-family: 'Montserrat', sans-serif;
    }
    
    /* ELEGANT VARIANTS */
    .elegant-std { background: white; border: 1px solid #eee; }
    .elegant-gold { 
        background: linear-gradient(135deg, #F3E5AB 0%, #D4AF37 100%); 
        border: 2px solid #C5A028; color: #5D4037 !important;
    }
    .elegant-plat { 
        background: linear-gradient(135deg, #E0E0E0 0%, #BDBDBD 100%); 
        border: 2px solid #9E9E9E; color: #424242 !important;
    }
    .elegant-elite { 
        background: #121212; border: 2px solid #D4AF37; color: #D4AF37 !important;
    }
    .elegant-elite h1, .elegant-elite p, .elegant-elite span { color: #D4AF37 !important; }

    .status-label { font-family: 'Playfair Display', serif; font-size: 18px; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; font-weight: bold; }
    .balance-num { font-size: 72px; font-weight: 300; line-height: 1; margin: 15px 0; font-family: 'Oswald', sans-serif; }
    .greeting-text { font-family: 'Playfair Display', serif; font-style: italic; font-size: 20px; color: #D84315; text-align: center; margin-bottom: 20px; }

    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; justify-items: center; margin-top: 20px; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.3s ease; }

    /* ALERTS */
    .birthday-alert { animation: pulse-gold 2s infinite; border: 2px solid gold !important; background-color: #FFF8E1 !important; color: #333 !important; text-align: center; padding: 10px; border-radius: 10px; }
    @keyframes pulse-gold { 0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.7); } 100% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0); } }
    
    .msg-alert { background-color: #E3F2FD; border-left: 5px solid #2196F3; padding: 15px; margin-bottom: 15px; border-radius: 4px; font-weight: bold; }

    @media print {
        body * { visibility: hidden; } .paper-receipt, .paper-receipt * { visibility: visible; } .paper-receipt { position: fixed; left: 0; top: 0; width: 100%; margin: 0; padding: 0; border: none; box-shadow: none; }
        div[data-testid="stDialog"], div[role="dialog"] { box-shadow: none !important; background: none !important; }
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
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT);"))
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

# --- STOCK CHECKER ---
def get_low_stock_map():
    low_stock_items = []
    try:
        q = "SELECT DISTINCT r.menu_item_name FROM recipes r JOIN ingredients i ON r.ingredient_name = i.name WHERE i.stock_qty <= i.min_limit"
        df = run_query(q)
        if not df.empty: low_stock_items = df['menu_item_name'].tolist()
    except: pass
    return low_stock_items

# --- SMART CALC ---
def calculate_smart_total(cart, customer=None, is_table=False):
    total = 0.0; discounted_total = 0.0; status_discount_rate = 0.0; thermos_discount_rate = 0.0; current_stars = 0; is_birthday = False
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'golden': status_discount_rate = 0.05
        elif ctype == 'platinum': status_discount_rate = 0.10
        elif ctype == 'elite': status_discount_rate = 0.20
        elif ctype == 'thermos': thermos_discount_rate = 0.20 
        try:
            if customer.get('birth_date'):
                bd = datetime.datetime.strptime(customer['birth_date'], "%Y-%m-%d"); now = get_baku_now()
                if bd.month == now.month and bd.day == now.day: is_birthday = True
        except: pass
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
    return total, discounted_total, max(status_discount_rate, thermos_discount_rate), free_coffees_to_apply, total_star_pool, 0, is_birthday

# ==========================================
# === CUSTOMER VIEW INTERFACE (PUBLIC) ===
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
        
        # DYNAMIC GREETING
        hour = get_baku_now().hour
        greeting = "Sabahınız xeyir," if 6 <= hour < 12 else "Hər vaxtınız xeyir," if 12 <= hour < 18 else "Axşamınız xeyir,"
        comp = random.choice(COMPLIMENTS)
        st.markdown(f"<div class='greeting-text'>{greeting} {comp}</div>", unsafe_allow_html=True)

        # GLOBAL MSG
        public_msg = get_setting("public_msg", "")
        if public_msg: st.markdown(f"<div class='msg-alert'>📢 {public_msg}</div>", unsafe_allow_html=True)

        # NOTIFICATIONS
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

        # ELEGANT CARD
        ctype = user['type']; card_style = "elegant-std"; st_label = "CLUB MEMBER"
        if ctype == 'golden': card_style = "elegant-gold"; st_label = "GOLDEN MEMBER"
        elif ctype == 'platinum': card_style = "elegant-plat"; st_label = "PLATINUM MEMBER"
        elif ctype == 'elite': card_style = "elegant-elite"; st_label = "ELITE VIP"
        elif ctype == 'thermos': st_label = "EKO-TERM MEMBER"

        st.markdown(f"""
        <div class="digital-card {card_style}">
            <div class="status-label">{st_label}</div>
            <p>Balansınız</p>
            <div class="balance-num">{user['stars']} / 10</div>
        </div>
        """, unsafe_allow_html=True)
        
        # PROGRESS
        my_bar = st.progress(user['stars'] / 9)
        if user['stars'] >= 9: 
            st.markdown("<div class='birthday-alert'>🎉 TƏBRİKLƏR! Növbəti Kofe HƏDİYYƏDİR!</div>", unsafe_allow_html=True)
            st.balloons() # CONFETTI

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
# === STAFF & ADMIN INTERFACE (PRIVATE) ===
# ==========================================

def add_to_cart(cart_ref, item):
    try: r = run_query("SELECT printer_target, price_half FROM menu WHERE item_name=:n", {"n":item['item_name']}).iloc[0]; item['printer_target'] = r['printer_target']; item['price_half'] = float(r['price_half']) if r['price_half'] else None
    except: item['printer_target'] = 'kitchen'; item['price_half'] = None
    for ex in cart_ref:
        if ex['item_name'] == item['item_name'] and ex.get('status') == 'new' and ex.get('qty') % 1 == 0: ex['qty'] += 1; return
    cart_ref.append(item)

def toggle_portion(idx):
    item = st.session_state.cart_table[idx]
    if item['qty'] == 1.0: item['qty'] = 0.5; 
    elif item['qty'] == 0.5: item['qty'] = 1.0

def render_menu_grid(cart_ref, key_prefix):
    # LOW STOCK ALERT (YELLOW DOT)
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
            if cb.form_submit_button("🔍") or qv:
                try: 
                    cid = qv.strip().split("id=")[1].split("&")[0] if "id=" in qv else qv.strip()
                    r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                    if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.toast("✅"); st.rerun()
                    else: st.error("Tapılmadı")
                except: pass
        if st.session_state.current_customer_ta:
            c = st.session_state.current_customer_ta
            # MSG ALERT
            nts = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":c['card_id']})
            if not nts.empty:
                st.warning(f"🔔 BU MÜŞTƏRİYƏ {len(nts)} OXUNMAMIŞ MESAJ VAR!")
                for _, n in nts.iterrows():
                    if n['attached_coupon']: 
                        if st.button(f"🎁 Tətbiq Et: {n['attached_coupon']}", key=f"ap_{n['id']}"):
                            run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.success("OK"); st.rerun()
            
            # STAFF NOTE
            if c.get('staff_note'): st.info(f"📝 QEYD: {c['staff_note']}")

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
                st.session_state.cart_takeaway=[]; st.rerun()
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
                run_action("UPDATE tables SET is_occupied=FALSE, items='[]', total=0, active_customer_id=NULL WHERE id=:id", {"id":tbl['id']}); st.session_state.selected_table = None; st.session_state.cart_table = []; st.rerun()
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
                if st.button(f"{row['label']}\n{row['total']} ₼", key=f"tbl_btn_{row['id']}", use_container_width=True, type="primary" if row['is_occupied'] else "secondary"):
                    items = json.loads(row['items']) if row['items'] else []
                    st.session_state.selected_table = row.to_dict(); st.session_state.cart_table = items; st.rerun()

def render_analytics(is_admin=False):
    st.subheader("📊 Analitika")
    df = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
    st.dataframe(df, use_container_width=True)
    if is_admin:
        st.divider()
        st.markdown("#### 📤 Hesabatı Göndər (Detallı)")
        c1, c2 = st.columns([3,1])
        target = c1.text_input("Kimə (Email)", placeholder="nümuna@mail.com")
        if c2.button("Göndər"):
            if target:
                today = get_baku_now().date()
                sales_today = run_query(f"SELECT * FROM sales WHERE created_at::date = '{today}'")
                if not sales_today.empty:
                    total = sales_today['total'].sum()
                    count = len(sales_today)
                    cashier_stats = sales_today.groupby('cashier')['total'].sum().reset_index()
                    html_table = "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse; width:100%;'><tr><th>Saat</th><th>Kassir</th><th>Məhsullar</th><th>Məbləğ</th></tr>"
                    for _, row in sales_today.iterrows():
                        html_table += f"<tr><td>{row['created_at'].strftime('%H:%M')}</td><td>{row['cashier']}</td><td>{row['items']}</td><td>{row['total']}</td></tr>"
                    html_table += "</table>"
                    body = f"<h2>📅 Hesabat ({today})</h2><p><b>Cəm:</b> {total} AZN | <b>Çek:</b> {count}</p><hr>{cashier_stats.to_html()}<hr>{html_table}"
                    send_email(target, f"Satış Hesabatı - {today}", body)
                    st.success("Göndərildi!")
                else: st.warning("Bu gün satış yoxdur.")
            else: st.error("Email yazın")

def render_crm():
    st.subheader("👥 CRM & Marketinq")
    t1, t2, t3 = st.tabs(["📢 Mesaj & Kampaniya", "🎟️ Şablonlar", "🛡️ Admin Tools"])
    with t1:
        st.markdown("### 🎯 Hədəfli Göndəriş")
        msg = st.text_area("Mesaj Mətni")
        target = st.radio("Kimə?", ["🌍 Hamıya", "👤 Fərdi"], horizontal=True)
        sel_ids = []
        if target == "👤 Fərdi":
            df = run_query("SELECT card_id, email, type, staff_note FROM customers"); df.insert(0, "Seç", False)
            ed = st.data_editor(df, hide_index=True)
            sel_ids = ed[ed["Seç"]]['card_id'].tolist()
            # Staff Note Update
            with st.expander("📝 Gizli Qeyd Əlavə Et (Seçilənlərə)"):
                new_note = st.text_input("Qeyd")
                if st.button("Qeydi Yaz"):
                    for i in sel_ids: run_action("UPDATE customers SET staff_note=:n WHERE card_id=:i", {"n":new_note, "i":i}); st.success("Yazıldı!")
        
        coupons = ["(Yoxdur)"] + run_query("SELECT name FROM coupon_templates")['name'].tolist()
        cp = st.selectbox("Kupon Yapışdır", coupons)
        c_app, c_mail = st.columns(2)
        final_cp = None if cp == "(Yoxdur)" else cp
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
    with t3:
        st.markdown("### 🗑️ Toplu Silmə")
        del_df = run_query("SELECT card_id, email, type FROM customers"); del_df.insert(0, "Seç", False)
        del_ed = st.data_editor(del_df, hide_index=True)
        del_ids = del_ed[del_ed["Seç"]]['card_id'].tolist()
        if del_ids:
            st.warning(f"{len(del_ids)} müştəri seçilib!")
            adm_pass = st.text_input("Admin Şifrəsi", type="password")
            if st.button("SİL (Geri Dönüş Yoxdur)", type="primary"):
                adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                if not adm.empty and verify_password(adm_pass, adm.iloc[0]['password']):
                    for di in del_ids:
                        run_action("DELETE FROM customers WHERE card_id=:id", {"id":di})
                        run_action("DELETE FROM customer_coupons WHERE card_id=:id", {"id":di})
                    st.success("Silindi!")
                else: st.error("Şifrə səhvdir")

# --- MAIN ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center; color:#777;'>{VERSION}</h5>", unsafe_allow_html=True)
        tabs = st.tabs(["İŞÇİ (STAFF)", "İDARƏETMƏ (ADMIN)"])
        with tabs[0]:
            p = st.text_input("PIN", type="password", key="s_pin")
            if st.button("Giriş", key="s_btn", use_container_width=True):
                is_blocked, mins = check_login_block(p)
                if is_blocked: st.error(f"Blok: {mins} dəq"); st.stop()
                udf = run_query("SELECT * FROM users WHERE role='staff'")
                found = False
                for _, row in udf.iterrows():
                    if verify_password(p, row['password']):
                        clear_failed_login(row['username']); st.session_state.logged_in=True; st.session_state.user=row['username']; st.session_state.role='staff'; st.rerun(); found=True; break
                if not found: st.error("Yanlış PIN!")
        with tabs[1]:
            u = st.text_input("İstifadəçi"); passw = st.text_input("Şifrə", type="password")
            if st.button("Daxil Ol", key="a_btn", use_container_width=True):
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
        if st.button("🚪 Çıxış", type="primary", use_container_width=True): st.session_state.logged_in = False; st.rerun()
    st.divider()

    role = st.session_state.role
    if role == 'admin':
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "📜 Resept", "Analitika", "👥 CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
        with tabs[0]: render_takeaway()
        with tabs[1]: render_tables_main()
        with tabs[2]: 
            st.subheader("📦 Anbar")
            cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist(); cat_list = ["Bütün"] + cats
            sel_inv_cat = st.selectbox("Filtr", cat_list)
            sql = "SELECT * FROM ingredients"; p={}
            if sel_inv_cat != "Bütün": sql += " WHERE category=:c"; p['c']=sel_inv_cat
            df_inv = run_query(sql, p)
            
            # Inventory Dialog
            @st.dialog("Mal Əməliyyatı")
            def manage_stock(id, name, qty, unit):
                st.write(f"### {name}")
                c1, c2 = st.columns(2)
                with c1:
                    add = st.number_input("Artır", 0.0)
                    if st.button("➕ Mədaxil"): run_action("UPDATE ingredients SET stock_qty=stock_qty+:q WHERE id=:id",{"q":add,"id":id}); st.rerun()
                with c2:
                    fix = st.number_input("Düzəliş", value=float(qty))
                    if st.button("✏️ Düzəlt"): run_action("UPDATE ingredients SET stock_qty=:q WHERE id=:id",{"q":fix,"id":id}); st.rerun()
                if st.button("🗑️ Sil", type="primary"): run_action("DELETE FROM ingredients WHERE id=:id",{"id":id}); st.rerun()

            cols = st.columns(4)
            for i, r in df_inv.iterrows():
                with cols[i%4]:
                    if st.button(f"{r['name']}\n{format_qty(r['stock_qty'])} {r['unit']}", key=f"inv_{r['id']}"): manage_stock(r['id'], r['name'], r['stock_qty'], r['unit'])

            with st.expander("➕ Yeni Mal"):
                with st.form("ni"):
                    n=st.text_input("Ad"); q=st.number_input("Say"); u=st.selectbox("Vahid",["gr","ml","ədəd","litr","kq"])
                    # Smart Category
                    ex_cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist()
                    cat_sel = st.selectbox("Kateqoriya", ex_cats + ["➕ Yeni..."])
                    fin_cat = st.text_input("Yeni Ad") if cat_sel == "➕ Yeni..." else cat_sel
                    if st.form_submit_button("Yarat"): run_action("INSERT INTO ingredients (name,stock_qty,unit,category) VALUES (:n,:q,:u,:c)", {"n":n,"q":q,"u":u,"c":fin_cat}); st.rerun()
        
        with tabs[3]: # Resept Full Editor
            st.subheader("📜 Resept")
            c1, c2 = st.columns([1,2])
            with c1:
                sch = st.text_input("Axtar"); q="SELECT * FROM menu WHERE is_active=TRUE"
                if sch: q+=f" AND item_name ILIKE '%{sch}%'"
                prods = run_query(q)
                for _,r in prods.iterrows():
                    if st.button(r['item_name'], key=f"r_{r['id']}"): st.session_state.selected_recipe_product = r['item_name']
            with c2:
                if st.session_state.selected_recipe_product:
                    pn = st.session_state.selected_recipe_product
                    st.write(f"### {pn}")
                    recs = run_query("SELECT * FROM recipes WHERE menu_item_name=:n",{"n":pn})
                    st.dataframe(recs)
                    # Add Ingredient
                    ings = run_query("SELECT name FROM ingredients")['name'].tolist()
                    s_i = st.selectbox("Xammal", ings); s_q = st.number_input("Miqdar")
                    if st.button("Əlavə Et"): run_action("INSERT INTO recipes (menu_item_name,ingredient_name,quantity_required) VALUES (:m,:i,:q)",{"m":pn,"i":s_i,"q":s_q}); st.rerun()

        with tabs[4]: render_analytics(is_admin=True)
        with tabs[5]: render_crm()
        with tabs[6]: # Menu Excel
            st.subheader("📋 Menyu")
            up = st.file_uploader("Excel Yüklə")
            if up and st.button("Yüklə"):
                df = pd.read_excel(up); run_action("DELETE FROM menu")
                for _, row in df.iterrows(): 
                    run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee) VALUES (:n,:p,:c,TRUE,:ic)", 
                               {"n":row['item_name'],"p":row['price'],"c":row['category'],"ic":row.get('is_coffee',False)})
                st.success("Yükləndi!")
            st.dataframe(run_query("SELECT * FROM menu"))

        with tabs[7]: 
            st.subheader("⚙️ Ayarlar")
            t = st.text_input("Müştəri Ekranı Başlığı", value=get_setting("customer_ui_title", BRAND_NAME))
            lg = st.file_uploader("Logo Dəyiş")
            if lg: set_setting("receipt_logo_base64", image_to_base64(lg))
            if st.button("Yadda Saxla"): set_setting("customer_ui_title", t); st.success("Oldu!")
        
        with tabs[8]: # Full Backup
            if st.button("📥 FULL BACKUP"):
                out = BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    for t in ["users","menu","sales","ingredients","recipes","customers","customer_coupons","notifications","coupon_templates","settings","expenses"]:
                        try: run_query(f"SELECT * FROM {t}").to_excel(writer, sheet_name=t)
                        except: pass
                st.download_button("⬇️ Endir", out.getvalue(), "Backup_Full.xlsx")
        
        with tabs[9]:
            cnt = st.number_input("Say",1,100)
            if st.button("QR Yarat"): 
                for _ in range(cnt):
                    i = str(random.randint(10000000, 99999999)); tok = secrets.token_hex(8)
                    run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, 'standard', :st)", {"i":i, "st":tok})
                st.success("Hazırdır!")

    elif role == 'staff':
        staff_tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "Satışlar"])
        with staff_tabs[0]: render_takeaway()
        with staff_tabs[1]: render_tables_main()
        with staff_tabs[2]: render_analytics(is_admin=False)

    st.markdown(f"<div class='footer'>Ironwaves POS {VERSION} | © 2026</div>", unsafe_allow_html=True)
