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
# === EMALATKHANA POS - V5.9 (FINAL NEON FIX) ===
# ==========================================

VERSION = "v5.9 (Neon Speed & Full Menu)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- DEFAULT TERMS ---
DEFAULT_TERMS = """<div style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h4 style="color: #2E7D32; margin-bottom: 5px;">📜 İSTİFADƏÇİ RAZILAŞMASI</h4>
    <p><b>1. Ümumi:</b> Bu loyallıq proqramı "Emalatkhana" tərəfindən təqdim edilir.</p>
    <p><b>2. Ulduzlar:</b> Yalnız Kofe məhsullarına şamil olunur (9 ulduz = 1 Hədiyyə).</p>
</div>"""

# --- INFRA ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

# --- CONFIG ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# --- INIT STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'active_tab' not in st.session_state: st.session_state.active_tab = "Al-Apar"
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'current_customer_tb' not in st.session_state: st.session_state.current_customer_tb = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'selected_recipe_product' not in st.session_state: st.session_state.selected_recipe_product = None

# --- CSS (NEON GREEN #5ef265 FIX) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    
    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F4F6F9 !important; color: #333333 !important; font-family: 'Oswald', sans-serif !important; }
    p, h1, h2, h3, h4, h5, h6, li, span, label, div[data-testid="stMarkdownContainer"] p { color: #333333 !important; }
    div[data-baseweb="input"] { background-color: #FFFFFF !important; border: 1px solid #ced4da !important; color: #333 !important; }
    input, textarea { color: #333 !important; }
    div[data-baseweb="select"] > div { background-color: #FFFFFF !important; color: #333 !important; }
    header, #MainMenu, footer, [data-testid="stSidebar"] { display: none !important; }
    .block-container { padding-top: 0.5rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    
    /* --- NAVIGATION BUTTONS (Secondary - White) --- */
    div.stButton > button[kind="secondary"] {
        background-color: white !important; 
        color: #333 !important; 
        border: 1px solid #ccc !important;
        border-radius: 8px !important;
        height: 50px !important;
        font-weight: bold !important;
        box-shadow: 0 2px 2px rgba(0,0,0,0.1) !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: #2E7D32 !important; color: #2E7D32 !important;
    }

    /* --- POS & TABLE BUTTONS (Primary - NEON GREEN) --- */
    div.stButton > button[kind="primary"] {
        background-color: #5ef265 !important; /* NEON GREEN */
        color: white !important;
        border: 2px solid #2E7D32 !important;
        border-radius: 15px !important;
        height: 100px !important; /* BIGGER */
        font-weight: 900 !important; /* EXTRA BOLD */
        font-size: 24px !important; /* LARGE TEXT */
        text-shadow: 2px 2px 4px #000000 !important; /* SHADOW FOR READABILITY */
        box-shadow: 0 5px 0 #2E7D32 !important; /* 3D EFFECT */
        transition: all 0.1s !important;
        white-space: pre-wrap !important;
        line-height: 1.1 !important;
    }
    div.stButton > button[kind="primary"]:active {
        transform: translateY(4px);
        box-shadow: none !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #4ce053 !important; /* Slightly darker on hover */
    }

    /* --- ORANGE CATEGORY TABS --- */
    div[role="radiogroup"] { flex-direction: row; gap: 8px; width: 100%; display: flex; flex-wrap: wrap; }
    div[role="radiogroup"] label { 
        background-color: #FF6B35 !important; 
        border: 1px solid #E65100 !important; 
        padding: 12px 5px !important; 
        border-radius: 8px !important; 
        flex: 1; min-width: 80px; 
        text-align: center; justify-content: center; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    div[role="radiogroup"] label p { 
        color: white !important; font-weight: bold !important; font-size: 16px !important; white-space: nowrap !important;
    }
    div[role="radiogroup"] label[data-checked="true"] { background-color: #BF360C !important; transform: translateY(1px); }

    /* CUSTOMER CARDS */
    .digital-card { background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center; margin-bottom: 20px; border: 1px solid #eee; }
    .status-badge { font-size: 20px; font-weight: bold; padding: 5px 15px; border-radius: 50px; display: inline-block; margin-bottom: 10px; color: white; }
    .badge-gold { background: linear-gradient(135deg, #FFC107, #FF9800); }
    .badge-plat { background: linear-gradient(135deg, #90A4AE, #546E7A); }
    .badge-elite { background: linear-gradient(135deg, #212121, #000000); border: 1px solid gold; }
    .badge-eco { background: linear-gradient(135deg, #66BB6A, #2E7D32); }
    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; justify-items: center; margin-top: 20px; }
    .coffee-icon-img { width: 50px; height: 50px; }
    .gift-box-anim { width: 60px; height: 60px; animation: bounce 2s infinite; }
    @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-10px);} }
    
    /* ALERTS & MSG */
    .birthday-alert { animation: pulse-gold 2s infinite; border: 2px solid gold !important; background-color: #FFF8E1 !important; color: #333 !important; }
    @keyframes pulse-gold { 0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.7); } 70% { box-shadow: 0 0 0 20px rgba(255, 215, 0, 0); } }
    .public-msg-box { background-color: #FFF3CD; color: #856404; padding: 15px; border-radius: 10px; border: 1px solid #FFEEBA; text-align: center; font-weight: bold; margin-bottom: 15px; font-size: 18px; }

    @media print {
        body * { visibility: hidden; } .paper-receipt, .paper-receipt * { visibility: visible; } .paper-receipt { position: fixed; left: 0; top: 0; width: 100%; }
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
    with c2:
        if logo_b64: st.markdown(f'<div style="text-align:center; margin-bottom:10px;"><img src="data:image/png;base64,{logo_b64}" width="160"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{BRAND_NAME}</h1>", unsafe_allow_html=True)
    try: df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    except: st.stop()
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token: st.warning("⚠️ QR kod köhnəlib.")
        
        # --- GLOBAL MESSAGE ---
        public_msg = get_setting("public_msg", "")
        if public_msg: st.markdown(f"<div class='public-msg-box'>📢 {public_msg}</div>", unsafe_allow_html=True)

        # --- MANUAL NOTIFICATION ---
        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        if not notifs.empty:
            for _, row in notifs.iterrows():
                with st.container(border=True):
                    st.info(f"💌 {row['message']}")
                    if row['attached_coupon']: st.success(f"🎁 SİZƏ ÖZƏL KUPON: **{row['attached_coupon']}**")
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

        ctype = user['type']; badge_html = ""; warm_msg = ""
        if ctype == 'golden': badge_html = "<div class='status-badge badge-gold'>🌟 GOLDEN</div>"; warm_msg = "Siz bizim 🌟 Qızıl Müştərimizsiniz!"
        elif ctype == 'platinum': badge_html = "<div class='status-badge badge-plat'>💎 PLATINUM</div>"; warm_msg = "Siz bizim 💎 Platinum Müştərimizsiniz!"
        elif ctype == 'elite': badge_html = "<div class='status-badge badge-elite'>👑 ELITE</div>"; warm_msg = "Siz bizim 👑 Ən Özəl VIP Qonağımızsınız!"
        elif ctype == 'thermos': badge_html = "<div class='status-badge badge-eco'>🌿 EKO-TERM</div>"; warm_msg = "Siz əsl Təbiət Dostusunuz! 🌿"
        else: badge_html = "<div class='status-badge' style='background:#ddd; color:#333'>MEMBER</div>"; warm_msg = "Xoş Gəldiniz, Dəyərli Qonağımız! ☕"

        st.markdown(f"""<div class="digital-card">{badge_html}<p style="font-size:18px; margin:5px 0;">{warm_msg}</p><h1 style="color:#2E7D32; font-size: 48px; margin:10px 0;">{user['stars']} / 10</h1><p style="color:#777;">Balansınız</p></div>""", unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png" if i==9 else "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            style = "opacity: 1;" if i < user['stars'] or (i==9 and user['stars']>=9) else "opacity: 0.2; filter: grayscale(100%);"
            html += f'<img src="{icon}" class="coffee-icon-img" style="{style}">'
        st.markdown(html + '</div>', unsafe_allow_html=True)
        
        cps = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": card_id})
        for _, cp in cps.iterrows(): st.success(f"🎁 {cp['coupon_type']}")

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

def render_menu_grid(cart_ref, key_prefix):
    # ORANGE CATEGORY TABS
    cats = run_query("SELECT DISTINCT category FROM menu WHERE is_active=TRUE")
    cat_list = ["Hamısı"] + sorted(cats['category'].tolist()) if not cats.empty else ["Hamısı"]
    sc = st.radio("Kataloq", cat_list, horizontal=True, label_visibility="collapsed", key=f"cat_{key_prefix}")
    sql = "SELECT id, item_name, price, is_coffee FROM menu WHERE is_active=TRUE"
    p = {}; 
    if sc != "Hamısı": sql += " AND category=:c"; p["c"] = sc
    sql += " ORDER BY price ASC"; prods = run_query(sql, p)

    if not prods.empty:
        gr = {}
        for _, r in prods.iterrows():
            n = r['item_name']; pts = n.split(); base = n
            if len(pts) > 1 and pts[-1] in ['S','M','L','XL','Single','Double']: base = " ".join(pts[:-1]); gr.setdefault(base, []).append(r)
            else: gr[n] = [r]

        cols = st.columns(3); i = 0
        @st.dialog("Seçim Edin")
        def show_variant_popup(bn, its):
            st.markdown(f"<h2 style='text-align:center; color:#2E7D32'>{bn}</h2>", unsafe_allow_html=True)
            for it in its:
                label = it['item_name'].replace(bn, "").strip() or "Standard"
                if st.button(f"{label} - {it['price']} ₼", key=f"v_{it['id']}_{key_prefix}", use_container_width=True):
                    add_to_cart(cart_ref, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'status':'new'}); st.rerun()

        for bn, its in gr.items():
            with cols[i % 3]:
                if len(its) > 1: # Grouped -> Popup
                    # NEON GREEN BUTTON (Primary)
                    if st.button(f"{bn}", key=f"g_{bn}_{key_prefix}", use_container_width=True, type="primary"): show_variant_popup(bn, its)
                else: # Simple -> Direct Add
                    it = its[0]
                    # NEON GREEN BUTTON (Primary)
                    if st.button(f"{it['item_name']}\n{it['price']} ₼", key=f"s_{it['id']}_{key_prefix}", use_container_width=True, type="primary"):
                        add_to_cart(cart_ref, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'status':'new'}); st.rerun()
            i += 1

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
                    if not r.empty: 
                        st.session_state.current_customer_ta = r.iloc[0].to_dict()
                        nts = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":cid})
                        if not nts.empty: st.toast("🔔 MÜŞTƏRİYƏ MESAJ/KUPON VAR!", icon="🎁")
                        st.rerun()
                    else: st.error("Tapılmadı")
                except: pass
        if st.session_state.current_customer_ta:
            c = st.session_state.current_customer_ta; bd_alert_cls = ""
            if calculate_smart_total([], c)[6]: bd_alert_cls = "birthday-alert"; st.toast("🎂 AD GÜNÜDÜR!", icon="🎉")
            
            notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":c['card_id']})
            if not notifs.empty:
                for _, n in notifs.iterrows():
                    st.warning(f"📢 **MESAJ:** {n['message']}")
                    if n['attached_coupon']:
                        c_cp1, c_cp2 = st.columns([3, 1]); c_cp1.info(f"🏷️ **KUPON:** {n['attached_coupon']}")
                        if c_cp2.button("Tətbiq Et ✅", key=f"apply_{n['id']}"):
                            run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.success("Kupon tətbiq edildi!"); time.sleep(1); st.rerun()

            st.markdown(f"<div class='{bd_alert_cls}' style='padding:10px; border-radius:10px; margin-bottom:10px; border:1px solid #ddd;'>👤 <b>{c['card_id']}</b><br>⭐ {c['stars']} | 🏷️ {c.get('type','standard').upper()} { '🎂' if bd_alert_cls else ''}</div>", unsafe_allow_html=True)
            if st.button("Ləğv Et", key="ta_cl"): st.session_state.current_customer_ta=None; st.rerun()
        
        raw_total, final_total, _, free_count, _, _, is_bd = calculate_smart_total(st.session_state.cart_takeaway, st.session_state.current_customer_ta, is_table=False)
        
        if st.session_state.cart_takeaway:
            for i, it in enumerate(st.session_state.cart_takeaway):
                st.markdown(f"<div style='background:white;padding:10px;margin-bottom:5px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;border:1px solid #ddd;'><div style='flex:2'><b>{it['item_name']}</b></div><div style='flex:1'>{it['price']}</div><div style='flex:1;color:#E65100'>x{it['qty']}</div><div style='flex:1;text-align:right'>{it['qty']*it['price']:.1f}</div></div>", unsafe_allow_html=True)
                b1,b2,b3=st.columns([1,1,4])
                with b1: 
                    if st.button("➖", key=f"m_ta_{i}"): 
                        if it['qty']>1: it['qty']-=1 
                        else: st.session_state.cart_takeaway.pop(i)
                        st.rerun()
                with b2:
                    if st.button("➕", key=f"p_ta_{i}"): it['qty']+=1; st.rerun()
        
        st.markdown(f"<h3 style='text-align:right; color:#777; text-decoration: line-through;'>{raw_total:.2f} ₼</h3>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:right; color:#E65100'>{final_total:.2f} ₼</h2>", unsafe_allow_html=True)
        if free_count > 0: st.success(f"🎁 {free_count} ədəd Kofe HƏDİYYƏ!")
        
        pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True, key="pm_ta")
        if st.button("✅ ÖDƏNİŞ ET", type="primary", use_container_width=True, key="pay_ta"): # THIS WILL BE ORANGE (Custom CSS)
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
        if c_back.button("⬅️ Masalara Qayıt", key="back_tbl", use_container_width=True): st.session_state.selected_table = None; st.session_state.cart_table = []; st.rerun()
        
        st.markdown(f"### 📝 Sifariş: {tbl['label']}")
        c1, c2 = st.columns([1.5, 3])
        with c1:
            st.info("Masa Sifarişi"); db_cust_id = tbl.get('active_customer_id')
            if db_cust_id and not st.session_state.current_customer_tb:
                 r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":db_cust_id})
                 if not r.empty: st.session_state.current_customer_tb = r.iloc[0].to_dict()

            with st.form("sc_tb", clear_on_submit=True):
                ci, cb = st.columns([3,1]); qv = ci.text_input("Müştəri", label_visibility="collapsed", placeholder="Skan...", key="tb_inp"); 
                if cb.form_submit_button("🔍") or qv:
                    try: 
                        cid = qv.strip().split("id=")[1].split("&")[0] if "id=" in qv else qv.strip()
                        r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                        if not r.empty: st.session_state.current_customer_tb = r.iloc[0].to_dict(); st.rerun()
                        else: st.error("Tapılmadı")
                    except: pass
            if st.session_state.current_customer_tb:
                c = st.session_state.current_customer_tb; st.success(f"👤 {c['card_id']} | ⭐ {c['stars']}")
                notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":c['card_id']})
                if not notifs.empty:
                    for _, n in notifs.iterrows():
                        if n['attached_coupon'] and st.button(f"🎁 KUPONU QƏBUL ET ({n['attached_coupon']})", key=f"tbl_apply_{n['id']}"):
                            run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.success("Tətbiq olundu!"); st.rerun()
                if st.button("Ləğv Et", key="tb_cl"): st.session_state.current_customer_tb=None; st.rerun()
            
            raw_total, final_total, _, free_count, _, serv_chg, _ = calculate_smart_total(st.session_state.cart_table, st.session_state.current_customer_tb, is_table=True)

            if st.session_state.cart_table:
                for i, it in enumerate(st.session_state.cart_table):
                    status = it.get('status', 'new'); bg_col = "#e3f2fd" if status == 'sent' else "white"
                    st.markdown(f"<div style='background:{bg_col};padding:10px;margin-bottom:5px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;border:1px solid #ddd;'><div style='flex:2'><b>{it['item_name']}</b></div><div style='flex:1'>{it['price']}</div><div style='flex:1;color:#E65100'>x{it['qty']}</div><div style='flex:1;text-align:right'>{it['qty']*it['price']:.1f}</div></div>", unsafe_allow_html=True)
                    b1,b2,b3=st.columns([1,1,1])
                    with b1:
                        if st.button("➖", key=f"m_tb_{i}"): 
                            if status == 'sent': st.warning("Silinmə üçün Admin lazımdır")
                            else: 
                                if it['qty']>1: it['qty']-=1 
                                else: st.session_state.cart_table.pop(i)
                                st.rerun()
                    with b2:
                        if st.button("➕", key=f"p_tb_{i}"): it['qty']+=1; st.rerun()
            
            st.markdown(f"<h3 style='text-align:right; color:#777; text-decoration: line-through;'>{raw_total:.2f} ₼</h3>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='text-align:right; color:#E65100'>{final_total:.2f} ₼</h2>", unsafe_allow_html=True)
            if serv_chg > 0: st.caption(f"ℹ️ Servis Haqqı (7%): {serv_chg:.2f} ₼ daxildir")
            
            col_s, col_p = st.columns(2)
            if col_s.button("🔥 MƏTBƏXƏ GÖNDƏR", key="save_tbl", use_container_width=True):
                for x in st.session_state.cart_table: x['status'] = 'sent'
                act_cust_id = st.session_state.current_customer_tb['card_id'] if st.session_state.current_customer_tb else None
                run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t, active_customer_id=:c WHERE id=:id", 
                           {"i":json.dumps(st.session_state.cart_table), "t":final_total, "c":act_cust_id, "id":tbl['id']})
                st.success("Göndərildi!"); time.sleep(1); st.rerun()

            if col_p.button("✅ ÖDƏNİŞ ET", key="pay_tbl", type="primary", use_container_width=True):
                if not st.session_state.cart_table: st.error("Boşdur!"); st.stop()
                st.info("Ödəniş qəbul edildi. Masa təmizlənir..."); time.sleep(1)
                run_action("UPDATE tables SET is_occupied=FALSE, items='[]', total=0, active_customer_id=NULL WHERE id=:id", {"id":tbl['id']})
                st.session_state.selected_table = None; st.session_state.cart_table = []; st.rerun()

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
                # NEON TABLE BUTTONS
                kind = "primary" if row['is_occupied'] else "primary" # Use Primary for color, logic can change border/text if needed in CSS but requested NEON GREEN
                if st.button(f"{row['label']}\n{row['total']} ₼", key=f"tbl_btn_{row['id']}", use_container_width=True, type="primary"):
                    items = json.loads(row['items']) if row['items'] else []
                    st.session_state.selected_table = row.to_dict(); st.session_state.cart_table = items; st.rerun()

def render_crm():
    st.subheader("👥 CRM & Marketinq")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("### 🎯 Hədəfli Mesajlaşma")
        msg_text = st.text_area("Mesaj Mətni", placeholder="Məsələn: Sizi çoxdandır görmürük, gəlin qonağımız olun!")
        target_type = st.radio("Kimə Göndərilsin?", ["🌍 Hamıya (Vitrin Elanı)", "👤 Fərdi (Seçilmiş Müştərilərə)"], horizontal=True)
        selected_ids = []
        if "Fərdi" in target_type:
            all_cust = run_query("SELECT card_id, email, type, stars FROM customers")
            all_cust.insert(0, "Seç", False)
            edited_df = st.data_editor(all_cust, hide_index=True, use_container_width=True)
            selected_ids = edited_df[edited_df["Seç"] == True]['card_id'].tolist()
        
        coupon_ops = ["(Kuponsuz)"] + run_query("SELECT name FROM coupon_templates")['name'].tolist()
        sel_coupon = st.selectbox("Kupon Şablonu", coupon_ops)
        
        col_app, col_mail = st.columns(2)
        if col_app.button("📱 TƏTBİQƏ GÖNDƏR", type="primary", use_container_width=True):
            final_coupon = None if sel_coupon == "(Kuponsuz)" else sel_coupon
            if "Hamıya" in target_type: set_setting("public_msg", msg_text); st.success("Vitrin elanı yeniləndi!")
            else:
                if selected_ids:
                    for cid in selected_ids: run_action("INSERT INTO notifications (card_id, message, attached_coupon, created_at) VALUES (:c, :m, :cp, :t)", {"c":cid, "m":msg_text, "cp":final_coupon, "t":get_baku_now()})
                    st.success(f"{len(selected_ids)} nəfərə bildiriş getdi!")
                else: st.error("Müştəri seçin!")
        
        if col_mail.button("📧 EMAILƏ GÖNDƏR", use_container_width=True):
             if selected_ids:
                 emails = run_query(f"SELECT email FROM customers WHERE card_id IN ({','.join([repr(x) for x in selected_ids])})")['email'].tolist()
                 for e in emails: send_email(e, "Emalatkhana Xəbər", msg_text)
                 st.success("Emaillər göndərildi!")

    with c2:
        with st.form("custom_coupon"):
            cc_name = st.text_input("Kupon Kodu"); cc_perc = st.number_input("Endirim (%)", 1, 100, 10); cc_days = st.number_input("Müddət (Gün)", 1, 365, 7)
            if st.form_submit_button("Şablonu Yadda Saxla"):
                run_action("INSERT INTO coupon_templates (name, percent, days_valid) VALUES (:n, :p, :d)", {"n":cc_name, "p":cc_perc, "d":cc_days}); st.success("OK")
        st.write("Şablonlar:"); st.dataframe(run_query("SELECT name, percent, days_valid FROM coupon_templates"), use_container_width=True)

# --- MAIN ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center; color:#777;'>{VERSION}</h5>", unsafe_allow_html=True)
        login_tabs = st.tabs(["İŞÇİ (STAFF)", "İDARƏETMƏ (ADMIN)"])
        with login_tabs[0]:
            with st.form("staff_login"):
                pin = st.text_input("PIN", type="password"); 
                if st.form_submit_button("Giriş", use_container_width=True):
                    is_blocked, mins = check_login_block(pin) 
                    if is_blocked: st.error(f"Gözləyin: {mins} dəq"); st.stop()
                    udf = run_query("SELECT * FROM users WHERE role='staff'")
                    found = False
                    for _, row in udf.iterrows():
                        if verify_password(pin, row['password']):
                            clear_failed_login(row['username']); st.session_state.logged_in=True; st.session_state.user=row['username']; st.session_state.role='staff'; st.rerun(); found=True; break
                    if not found: st.error("Yanlış PIN!")
        with login_tabs[1]:
            with st.form("admin_login"):
                u = st.text_input("İstifadəçi"); p = st.text_input("Şifrə", type="password")
                if st.form_submit_button("Daxil Ol", use_container_width=True):
                    is_blocked, mins = check_login_block(u)
                    if is_blocked: st.error(f"Gözləyin: {mins} dəq"); st.stop()
                    udf = run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(:u) AND role IN ('admin', 'manager')", {"u":u})
                    if not udf.empty and verify_password(p, udf.iloc[0]['password']):
                        clear_failed_login(u); st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=udf.iloc[0]['role']; st.rerun()
                    else: register_failed_login(u); st.error("Səhv!")
else:
    # --- BLOCK NAVIGATION (2 ROWS) ---
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    r1 = st.columns(5)
    if r1[0].button("🏃‍♂️ AL-APAR", key="nav_pos", help="Takeaway", use_container_width=True, type="secondary"): st.session_state.active_tab = "Al-Apar"; st.rerun()
    if r1[1].button("🍽️ MASALAR", key="nav_table", help="Tables", use_container_width=True, type="secondary"): st.session_state.active_tab = "Masalar"; st.rerun()
    if r1[2].button("📦 Anbar", key="nav_inv", use_container_width=True, type="secondary"): st.session_state.active_tab = "Anbar"; st.rerun()
    if r1[3].button("📜 Resept", key="nav_rec", use_container_width=True, type="secondary"): st.session_state.active_tab = "Resept"; st.rerun()
    if r1[4].button("Analitika", key="nav_ana", use_container_width=True, type="secondary"): st.session_state.active_tab = "Analitika"; st.rerun()
    
    r2 = st.columns(5)
    if r2[0].button("👥 CRM", key="nav_crm", use_container_width=True, type="secondary"): st.session_state.active_tab = "CRM"; st.rerun()
    if r2[1].button("📋 Menyu", key="nav_menu", use_container_width=True, type="secondary"): st.session_state.active_tab = "Menyu"; st.rerun()
    if r2[2].button("⚙️ Ayarlar", key="nav_set", use_container_width=True, type="secondary"): st.session_state.active_tab = "Ayarlar"; st.rerun()
    if r2[3].button("🛡️ Admin", key="nav_adm", use_container_width=True, type="secondary"): st.session_state.active_tab = "Admin"; st.rerun()
    if r2[4].button("📷 QR", key="nav_qr", use_container_width=True, type="secondary"): st.session_state.active_tab = "QR"; st.rerun()
    
    st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)
    if st.button("ÇIXIŞ", key="nav_out", type="secondary"): st.session_state.logged_in=False; st.rerun()
    st.divider()
    
    tab = st.session_state.active_tab
    if tab == "Al-Apar": render_takeaway()
    elif tab == "Masalar": render_tables_main()
    elif tab == "CRM": render_crm()
    elif tab == "Anbar":
        st.subheader("📦 Anbar")
        cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist(); cat_list = ["Bütün"] + cats
        sel_inv_cat = st.selectbox("Filtr", cat_list)
        sql = "SELECT * FROM ingredients"; p={}
        if sel_inv_cat != "Bütün": sql += " WHERE category=:c"; p['c']=sel_inv_cat
        st.dataframe(run_query(sql, p), use_container_width=True)
        with st.expander("➕ Yeni Mal"):
            with st.form("new_inv"):
                n=st.text_input("Ad"); q=st.number_input("Say"); u=st.selectbox("Vahid",["gr","ml","ədəd","litr","kq"]); 
                exist_cats = run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist(); cat_ops = exist_cats + ["➕ Yeni Kateqoriya..."]
                sel_cat = st.selectbox("Kateqoriya", cat_ops); final_cat = st.text_input("Yeni Kateqoriya Adı") if sel_cat == "➕ Yeni Kateqoriya..." else sel_cat
                if st.form_submit_button("Yarat"): run_action("INSERT INTO ingredients (name,stock_qty,unit,category) VALUES (:n,:q,:u,:c)", {"n":n,"q":q,"u":u,"c":final_cat}); st.rerun()
    elif tab == "Analitika": 
        df = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
        st.dataframe(df, use_container_width=True)
    elif tab == "Menyu": # Basic Menu Editor for quick access
        st.subheader("📋 Menyu")
        with st.form("nm"):
                c1, c2, c3 = st.columns(3)
                with c1: n=st.text_input("Ad"); p=st.number_input("Qiymət", min_value=0.0, key="menu_p")
                with c2: c=st.text_input("Kat"); ic=st.checkbox("Kofe?"); pt=st.selectbox("Printer", ["kitchen", "bar"])
                with c3: ph=st.number_input("Yarım Qiymət (Seçimli)", min_value=0.0, value=0.0)
                if st.form_submit_button("Əlavə"): 
                    ph_val = ph if ph > 0 else None
                    run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee,printer_target,price_half) VALUES (:n,:p,:c,TRUE,:ic,:pt,:ph)", 
                               {"n":n,"p":p,"c":c,"ic":ic,"pt":pt,"ph":ph_val}); st.rerun()
        ml = run_query("SELECT * FROM menu"); st.dataframe(ml, use_container_width=True)
    elif tab == "QR": # Quick QR
        cnt = st.number_input("Say", 1, 100, 1)
        if st.button("Yarat"):
             for _ in range(cnt):
                 i = str(random.randint(10000000, 99999999)); tok = secrets.token_hex(8)
                 run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, 'standard', :st)", {"i":i, "st":tok})
             st.success("Yaradil di!")

    st.markdown(f"<div class='footer'>Ironwaves POS {VERSION} | © 2026</div>", unsafe_allow_html=True)
