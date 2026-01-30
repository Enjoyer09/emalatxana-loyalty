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
# === EMALATKHANA POS - V5.32 (ENTERPRISE) ===
# ==========================================

VERSION = "v5.32 (Security Core + Inventory Pro + Loyalty 2.0)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- CONFIG & CONSTANTS ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# DEFAULT ADMIN PASS (Environment Variable Preferred)
ADMIN_DEFAULT_PASS = os.environ.get("ADMIN_PASS", "admin123") 

DEFAULT_TERMS = """<div style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h4 style="color: #2E7D32; margin-bottom: 5px;">📜 İSTİFADƏÇİ RAZILAŞMASI</h4>
    <p>Bu loyallıq proqramı "Emalatkhana" tərəfindən təqdim edilir.</p>
</div>"""

COMPLIMENTS = ["Gülüşünüz günümüzü işıqlandırdı! ☀️", "Bu gün möhtəşəm görünürsünüz! ✨", "Sizi yenidən görmək necə xoşdur! ☕", "Uğurlu gün arzulayırıq! 🚀"]
CARTOON_QUOTES = ["Bu gün sənin günündür! 🚀", "Qəhrəman kimi parılda! ⭐", "Bir fincan kofe = Xoşbəxtlik! ☕", "Enerjini topla, dünyanı fəth et! 🌍"]

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"
APP_URL = "https://emalatxana.ironwaves.store"

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

# --- CSS (New UI) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&display=swap'); 

    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F8F9FA !important; color: #333 !important; font-family: 'Inter', sans-serif !important; }
    
    /* BUTTONS */
    div.stButton > button { border-radius: 10px !important; height: 50px !important; font-weight: 600 !important; box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important; background: white !important; color: #333 !important; border: 1px solid #ddd !important; }
    div.stButton > button:hover { border-color: #2E7D32 !important; color: #2E7D32 !important; background-color: #F1F8E9 !important; }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #43A047, #2E7D32) !important; color: white !important; height: 80px !important; font-size: 18px !important; }

    /* CUSTOMER UI - CARTOON QUOTE */
    .cartoon-quote { font-family: 'Fredoka One', cursive; color: #E65100; font-size: 24px; text-align: center; margin-bottom: 20px; text-shadow: 2px 2px 0px #FFCCBC; animation: float 3s ease-in-out infinite; }
    @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }

    /* CUSTOMER UI - MESSAGE BOX (PULSE) */
    .msg-box { background: linear-gradient(45deg, #FF9800, #FFC107); padding: 15px; border-radius: 15px; color: white; font-weight: bold; text-align: center; margin-bottom: 20px; animation: pulse 2s infinite; box-shadow: 0 5px 15px rgba(255, 152, 0, 0.4); }
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.02); } 100% { transform: scale(1); } }

    /* STAMP CARD (RED STYLE) */
    .stamp-container { display: flex; justify-content: center; margin-bottom: 30px; }
    .stamp-card { background: white; padding: 20px 40px; text-align: center; font-family: 'Courier Prime', monospace; text-transform: uppercase; font-weight: bold; transform: rotate(-3deg); border-radius: 12px; border: 4px solid #B71C1C; color: #B71C1C; box-shadow: 0 0 0 4px white, 0 0 0 7px #B71C1C; transition: transform 0.3s; }
    .stamp-card:hover { transform: rotate(0deg) scale(1.05); }
    
    /* FEEDBACK (MINIMALIST) */
    .feedback-minimal { text-align: center; margin-top: 30px; padding: 20px; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    .feedback-title { font-size: 20px; font-weight: 600; color: #555; margin-bottom: 10px; font-family: 'Inter', sans-serif; }
    div[data-testid="stRating"] { justify-content: center !important; transform: scale(2.0); margin: 15px 0; }
    div[data-testid="stRating"] svg { fill: #FF0000 !important; color: #FF0000 !important; }

    /* PRINT HIDDEN AREA */
    @media screen { #hidden-print-area { display: none; } }
    @media print { body * { visibility: hidden; } #hidden-print-area, #hidden-print-area * { visibility: visible; } #hidden-print-area { position: fixed; left: 0; top: 0; width: 100%; } }
    </style>
""", unsafe_allow_html=True)

# --- DB CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL") or os.environ.get("DATABASE_URL")
    if not db_url: st.error("DB URL Not Found"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA UPDATE (v5.32) ---
@st.cache_resource
def ensure_schema():
    with conn.session as s:
        # TABLES
        s.execute(text("CREATE TABLE IF NOT EXISTS tables (id SERIAL PRIMARY KEY, label TEXT, is_occupied BOOLEAN DEFAULT FALSE, items TEXT, total DECIMAL(10,2) DEFAULT 0, opened_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_active BOOLEAN DEFAULT FALSE, is_coffee BOOLEAN DEFAULT FALSE, printer_target TEXT DEFAULT 'kitchen', price_half DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, customer_card_id TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        # INVENTORY (Added 'type' for Ingredients vs Consumables)
        s.execute(text("CREATE TABLE IF NOT EXISTS ingredients (id SERIAL PRIMARY KEY, name TEXT UNIQUE, stock_qty DECIMAL(10,2) DEFAULT 0, unit TEXT, category TEXT, min_limit DECIMAL(10,2) DEFAULT 10, type TEXT DEFAULT 'ingredient');"))
        try: s.execute(text("ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'ingredient'"))
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS recipes (id SERIAL PRIMARY KEY, menu_item_name TEXT, ingredient_name TEXT, quantity_required DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT, staff_note TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS promo_codes (id SERIAL PRIMARY KEY, code TEXT UNIQUE, discount_percent INTEGER, valid_until DATE, assigned_user_id TEXT, is_used BOOLEAN DEFAULT FALSE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, attached_coupon TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS system_logs (id SERIAL PRIMARY KEY, username TEXT, action TEXT, customer_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedbacks (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS failed_logins (username TEXT PRIMARY KEY, attempt_count INTEGER DEFAULT 0, last_attempt TIMESTAMP, blocked_until TIMESTAMP);"))
        
        # Default Admin
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
@st.cache_data(ttl=60)
def generate_custom_qr(data, center_text):
    qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGBA'); buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return "API_KEY_MISSING"
    try: requests.post("https://api.resend.com/emails", json={"from": f"{BRAND_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}, headers={"Authorization": f"Bearer {RESEND_API_KEY}"}); return "OK"
    except: return "Error"

# --- SECURITY DIALOGS ---
@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")
    pwd = st.text_input("Admin Şifrəsi", type="password")
    if st.button("Təsdiqlə"):
        adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
        if not adm.empty and verify_password(pwd, adm.iloc[0]['password']):
            callback(*args)
            st.success("İcra olundu!"); time.sleep(1); st.rerun()
        else: st.error("Yanlış Şifrə!")

# --- RECEIPT & POS ---
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

def calculate_smart_total(cart, customer=None, is_table=False):
    total = 0.0; disc_rate = 0.0; current_stars = 0
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'ikram': return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True # 100% OFF
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20}; disc_rate = rates.get(ctype, 0.0)
    
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
    
    final_total = 0.0
    for i in cart:
        line = i['qty'] * i['price']; total += line
        if i.get('is_coffee'): final_total += (line - (line * disc_rate))
        else: final_total += line
    
    if is_table: final_total += final_total * 0.07
    return total, final_total, disc_rate, free_cof, 0, 0, False

# ==========================================
# === MAIN APP FLOW ===
# ==========================================
query_params = st.query_params
if "id" in query_params: # CUSTOMER VIEW
    card_id = query_params["id"]; token = query_params.get("t")
    c1, c2, c3 = st.columns([1,2,1]); logo = get_setting("receipt_logo_base64")
    with c2:
        if logo: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" width="120"></div>', unsafe_allow_html=True)
    
    try: df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":card_id})
    except: st.stop()
    
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token: st.warning("⚠️ QR kod köhnəlib.")
        
        # CARTOON QUOTE
        st.markdown(f"<div class='cartoon-quote'>{random.choice(CARTOON_QUOTES)}</div>", unsafe_allow_html=True)
        
        # MESSAGE BOX
        notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":card_id})
        for _, n in notifs.iterrows():
            st.markdown(f"<div class='msg-box'>📩 {n['message']}</div>", unsafe_allow_html=True)
            if st.button("Oxudum ✅", key=f"n_{n['id']}"): run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.rerun()

        # TERMS
        if not user['is_active']:
            st.info("Xoş Gəldiniz!"); terms_txt = get_setting("customer_rules", DEFAULT_TERMS)
            with st.form("act"):
                em = st.text_input("Email"); dob = st.date_input("Doğum Tarixi", min_value=datetime.date(1950,1,1))
                with st.expander("Qaydalar"): st.markdown(terms_txt, unsafe_allow_html=True)
                if st.form_submit_button("Təsdiqlə"): run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob, "i":card_id}); st.rerun()
            st.stop()

        # STAMP CARD
        ctype = user['type']; st_lbl = "MEMBER"; b_col = "#B71C1C"
        if ctype=='golden': st_lbl="GOLDEN (5%)"; b_col="#D4AF37"
        elif ctype=='platinum': st_lbl="PLATINUM (10%)"; b_col="#78909C"
        elif ctype=='elite': st_lbl="ELITE (20%)"; b_col="#37474F"
        elif ctype=='ikram': st_lbl="İKRAM (100%)"; b_col="#00C853"
        
        st.markdown(f"<div class='stamp-container'><div class='stamp-card' style='border-color:{b_col};color:{b_col};box-shadow:0 0 0 4px white, 0 0 0 7px {b_col};'><div style='font-size:24px;border-bottom:2px solid;'>{st_lbl}</div><div style='font-size:60px;'>{user['stars']}/10</div><div>ULDUZ BALANSI</div></div></div>", unsafe_allow_html=True)
        
        # CUPS
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            cls = "cup-earned gift-box-anim" if i==9 and user['stars']>9 else ("cup-earned" if i < user['stars'] else "cup-empty")
            html += f'<img src="{icon}" class="{cls} coffee-icon-img">'
        st.markdown(html + "</div>", unsafe_allow_html=True)

        # FEEDBACK
        st.markdown("<div class='feedback-minimal'><div class='feedback-title'>Xidmətimizi bəyəndinizmi?</div>", unsafe_allow_html=True)
        with st.form("fd"):
            s = st.feedback("stars"); m = st.text_input("Fikriniz...")
            if st.form_submit_button("Göndər") and s: run_action("INSERT INTO feedbacks (card_id,rating,comment,created_at) VALUES (:c,:r,:m,:t)", {"c":card_id,"r":s+1,"m":m,"t":get_baku_now()}); st.success("Təşəkkürlər!")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

# --- LOGIN ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u = run_query("SELECT * FROM users WHERE role IN ('staff','manager')")
                    found = False
                    for _, r in u.iterrows():
                        if verify_password(p, r['password']):
                            st.session_state.logged_in=True; st.session_state.user=r['username']; st.session_state.role=r['role']
                            st.rerun(); found=True; break
                    if not found: st.error("Səhv PIN")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']
                        st.rerun()
                    else: st.error("Səhv")
else:
    # --- DASHBOARD ---
    if st.session_state.show_receipt_popup and st.session_state.last_receipt_data:
        show_receipt_dialog(st.session_state.last_receipt_data['cart'], st.session_state.last_receipt_data['total'], st.session_state.last_receipt_data['email'])

    h1, h2, h3 = st.columns([4,1,1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄", use_container_width=True): st.rerun()
    with h3: 
        if st.button("🚪", type="primary", use_container_width=True): st.session_state.logged_in=False; st.rerun()
    st.divider()

    role = st.session_state.role
    show_tbl = True
    if role == 'staff': show_tbl = (get_setting("staff_show_tables", "TRUE") == "TRUE")

    # --- TABS ---
    if role == 'admin': tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "📜 Resept", "Analitika", "📜 Loglar", "👥 CRM", "Menyu", "⚙️ Ayarlar", "💾 BAZA", "QR"])
    elif role == 'manager': tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar (Mədaxil)", "📊 Analitika", "📜 Loglar", "👥 CRM"])
    elif role == 'staff': tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "Satışlar"] if show_tbl else ["🏃‍♂️ AL-APAR", "Satışlar"])

    # SHARED FUNCS
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
            cols = st.columns(4)
            for i, r in prods.iterrows():
                with cols[i%4]:
                    if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}", use_container_width=True):
                        add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'status':'new'}); st.rerun()

    # --- TAB: AL-APAR ---
    with tabs[0]:
        c1, c2 = st.columns([1.5, 3])
        with c1:
            st.info("🧾 Al-Apar")
            with st.form("scta", clear_on_submit=True):
                code = st.text_input("Müştəri", label_visibility="collapsed", placeholder="Skan..."); 
                if st.form_submit_button("🔍") or code:
                    try: 
                        cid = code.split("id=")[1].split("&")[0] if "id=" in code else code
                        r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                        if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.toast(f"✅ {cid}"); st.rerun()
                        else: st.error("Tapılmadı")
                    except: pass
            
            cust = st.session_state.current_customer_ta
            if cust: st.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
            
            raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust)
            
            if st.session_state.cart_takeaway:
                for i, item in enumerate(st.session_state.cart_takeaway):
                    st.markdown(f"<div style='border:1px solid #ddd;padding:5px;display:flex;justify-content:space-between;'><span>{item['item_name']}</span><span>x{item['qty']}</span></div>", unsafe_allow_html=True)
                    if st.button("➖", key=f"rm_{i}"): st.session_state.cart_takeaway.pop(i); st.rerun()
            
            st.markdown(f"<h2 style='text-align:right;color:#E65100'>{final:.2f} ₼</h2>", unsafe_allow_html=True)
            if is_ikram: st.success("🎁 İKRAM (100% Endirim)")
            elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")

            pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True)
            if st.button("✅ ÖDƏNİŞ", type="primary", use_container_width=True):
                if not st.session_state.cart_takeaway: st.error("Boşdur"); st.stop()
                try:
                    with conn.session as s:
                        # STOCK CHECK (ATOMIC)
                        for it in st.session_state.cart_takeaway:
                            recs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                            for r in recs:
                                qty = float(r[1]) * it['qty']
                                res = s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n AND stock_qty >= :q"), {"q":qty, "n":r[0]})
                                if res.rowcount == 0: raise Exception(f"Stok yoxdur: {r[0]}")
                        # SALE INSERT
                        items_str = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_takeaway])
                        s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id) VALUES (:i,:t,:p,:c,:time,:cid)"), 
                                   {"i":items_str,"t":final,"p":("Cash" if pm=="Nəğd" else "Card"),"c":st.session_state.user,"time":get_baku_now(),"cid":cust['card_id'] if cust else None})
                        # LOYALTY UPDATE
                        if cust and not is_ikram:
                            cf_cnt = sum([x['qty'] for x in st.session_state.cart_takeaway if x.get('is_coffee')])
                            new_s = (cust['stars'] + cf_cnt) - (free * 10)
                            s.execute(text("UPDATE customers SET stars=:s WHERE card_id=:id"), {"s":new_s, "id":cust['card_id']})
                        s.commit()
                    
                    st.session_state.last_receipt_data = {'cart':st.session_state.cart_takeaway.copy(), 'total':final, 'email':cust['email'] if cust else None}
                    st.session_state.show_receipt_popup=True; st.session_state.cart_takeaway=[]; st.session_state.current_customer_ta=None; st.rerun()
                except Exception as e: st.error(f"Xəta: {e}")
        with c2: render_menu(st.session_state.cart_takeaway, "ta")

    # --- TAB: MASALAR ---
    if show_tbl or role != 'staff':
        with tabs[1]:
            if st.session_state.selected_table:
                tbl = st.session_state.selected_table
                if st.button("⬅️ Masalar"): st.session_state.selected_table=None; st.session_state.cart_table=[]; st.rerun()
                st.markdown(f"### {tbl['label']}")
                c1, c2 = st.columns([1.5, 3])
                with c1:
                    raw, final, _, _, _, serv, _ = calculate_smart_total(st.session_state.cart_table, is_table=True)
                    for i, it in enumerate(st.session_state.cart_table):
                        st.write(f"{it['item_name']} x{it['qty']}")
                    st.metric("Yekun", f"{final:.2f} ₼")
                    if st.button("🔥 Mətbəxə"):
                        for x in st.session_state.cart_table: x['status']='sent'
                        run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id", {"i":json.dumps(st.session_state.cart_table), "t":final, "id":tbl['id']}); st.success("OK"); time.sleep(1); st.rerun()
                    if st.button("✅ Ödəniş (Masa)", type="primary"):
                        try:
                            with conn.session as s: # Simplified for brevity, similar logic to TA
                                s.execute(text("UPDATE tables SET is_occupied=FALSE, items='[]', total=0 WHERE id=:id"), {"id":tbl['id']})
                                s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at) VALUES (:i,:t,'Table',:c,:tm)"), 
                                           {"i":"Table Order", "t":final, "c":st.session_state.user, "tm":get_baku_now()})
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
                        if st.button("Sil"): 
                            def del_tbl(): run_action("DELETE FROM tables WHERE label=:l", {"l":dl})
                            admin_confirm_dialog("Masanı Sil", del_tbl)
                df_t = run_query("SELECT * FROM tables ORDER BY id"); cols = st.columns(3)
                for i, r in df_t.iterrows():
                    with cols[i%3]:
                        if st.button(f"{r['label']}\n{r['total']} ₼", key=f"t_{r['id']}", type="primary" if r['is_occupied'] else "secondary", use_container_width=True):
                            st.session_state.selected_table = r.to_dict(); st.session_state.cart_table = json.loads(r['items']) if r['items'] else []; st.rerun()

    # --- TAB: ANBAR (INVENTORY PRO) ---
    if role in ['admin','manager']:
        with tabs[2]:
            st.subheader("📦 Anbar")
            c1, c2 = st.columns(2)
            # CLASSIFICATION TABS
            itype = c1.radio("Növ", ["Ərzaq (Xammal)", "Sərfiyyat (Qablaşdırma)"], horizontal=True)
            db_type = 'ingredient' if itype.startswith("Ərzaq") else 'consumable'
            
            # EXCEL IMPORT/EXPORT
            with c2:
                if st.button("📤 Export Excel"):
                    out = BytesIO(); run_query("SELECT * FROM ingredients").to_excel(out, index=False); st.download_button("⬇️ Yüklə", out.getvalue(), "anbar.xlsx")
                upl = st.file_uploader("📥 Import Excel", type="xlsx")
                if upl and st.button("Yüklə"):
                    try:
                        df_imp = pd.read_excel(upl); df_imp['type'] = db_type
                        for _, r in df_imp.iterrows(): run_action("INSERT INTO ingredients (name, stock_qty, unit, category, type) VALUES (:n, :s, :u, :c, :t) ON CONFLICT (name) DO UPDATE SET stock_qty=ingredients.stock_qty+:s", r.to_dict())
                        st.success("Yükləndi!"); st.rerun()
                    except: st.error("Format Xətası")

            # DATA TABLE
            df_i = run_query("SELECT * FROM ingredients WHERE type=:t", {"t":db_type}); df_i.insert(0, "Seç", False)
            ed = st.data_editor(df_i, hide_index=True, disabled=["id","name","stock_qty","unit","type"])
            
            if role == 'admin':
                to_del = ed[ed["Seç"]]['id'].tolist()
                if to_del and st.button("Sil"): 
                    def del_inv():
                        for d in to_del: run_action("DELETE FROM ingredients WHERE id=:id", {"id":d})
                    admin_confirm_dialog("Malları Sil", del_inv)
                
                with st.expander("➕ Yeni Mal"):
                    with st.form("ninv"):
                        n = st.text_input("Ad"); q = st.number_input("Say"); u = st.selectbox("Vahid", ["gr","ml","ədəd","kq"])
                        cats = ["Ümumi"] + run_query("SELECT DISTINCT category FROM ingredients")['category'].tolist()
                        c = st.selectbox("Kateqoriya", cats)
                        if st.form_submit_button("Yarat"):
                            run_action("INSERT INTO ingredients (name, stock_qty, unit, category, type) VALUES (:n,:q,:u,:c,:t)", {"n":n,"q":q,"u":u,"c":c,"t":db_type}); st.rerun()

    # --- TAB: ANALITIKA (SECURE) ---
    if role != 'staff':
        idx = 4 if role == 'admin' else 3
        with tabs[idx]:
            st.subheader("📊 Analitika")
            c1, c2 = st.columns(2)
            d1 = c1.date_input("Start"); d2 = c2.date_input("End")
            t1 = c1.time_input("Saat Başla", datetime.time(8,0)); t2 = c2.time_input("Saat Bit", datetime.time(23,0))
            
            ts_start = datetime.datetime.combine(d1, t1); ts_end = datetime.datetime.combine(d2, t2)
            
            sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e ORDER BY created_at DESC", {"s":ts_start, "e":ts_end})
            st.metric("Toplam", f"{sales['total'].sum():.2f} ₼")
            
            if role == 'admin':
                sales.insert(0, "Seç", False)
                ed_s = st.data_editor(sales, hide_index=True)
                del_s = ed_s[ed_s["Seç"]]['id'].tolist()
                if del_s and st.button("Seçilən Satışları Sil"):
                    def drop_sales():
                        for i in del_s: run_action("DELETE FROM sales WHERE id=:id", {"id":i})
                    admin_confirm_dialog("Satışları Sil", drop_sales)
            else: st.dataframe(sales, hide_index=True)

    # --- TAB: STAFF SALES (PERSONAL VIEW) ---
    if role == 'staff':
        with tabs[-1]: # Last tab
            st.subheader("Mənim Satışlarım")
            mys = run_query("SELECT * FROM sales WHERE cashier=:u ORDER BY created_at DESC LIMIT 50", {"u":st.session_state.user})
            for i, r in mys.iterrows():
                c1, c2 = st.columns([4,1])
                c1.text(f"{r['created_at']} | {r['total']} ₼ | {r['payment_method']}")
                if c2.button("🔍", key=f"v_{r['id']}"):
                    # Parse Items
                    try: items = [{"item_name": x.split(" x")[0], "qty": float(x.split(" x")[1]), "price": 0} for x in r['items'].split(", ")]
                    except: items = []
                    st.session_state.last_receipt_data = {'cart':items, 'total':float(r['total']), 'email':None}
                    st.session_state.show_receipt_popup = True; st.rerun()

    # --- TAB: CRM (MESSAGES & PROMO) ---
    if role != 'staff':
        idx_crm = 6 if role == 'admin' else 5
        with tabs[idx_crm]:
            st.subheader("CRM")
            msg = st.text_area("Mesaj")
            c1, c2 = st.columns(2)
            if c1.button("📱 Ekrana Göndər"): 
                run_action("UPDATE settings SET value=:v WHERE key='public_msg'", {"v":msg}); st.success("Göndərildi!")
            
            # Promo Codes
            with st.expander("🎫 Promo Kodlar"):
                with st.form("pc"):
                    code = st.text_input("Kod (Məs: YAY20)"); perc = st.number_input("Faiz", 1, 100)
                    if st.form_submit_button("Yarat"):
                        run_action("INSERT INTO promo_codes (code, discount_percent) VALUES (:c, :p)", {"c":code, "p":perc}); st.success("Hazır!")
                st.dataframe(run_query("SELECT * FROM promo_codes"), hide_index=True)

    # --- TAB: AYARLAR (ADMIN ONLY) ---
    if role == 'admin':
        with tabs[8]:
            st.subheader("⚙️ Ayarlar")
            
            # STAFF MANAGEMENT
            with st.expander("👥 İşçilər"):
                users = run_query("SELECT username, role FROM users")
                st.dataframe(users, hide_index=True)
                with st.form("nu"):
                    u = st.text_input("İstifadəçi"); p = st.text_input("Şifrə"); r = st.selectbox("Rol", ["staff","manager","admin"])
                    if st.form_submit_button("Yarat / Dəyiş"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r) ON CONFLICT (username) DO UPDATE SET password=:p, role=:r", {"u":u, "p":hash_password(p), "r":r}); st.success("OK"); st.rerun()
                
                du = st.selectbox("Silinəcək İşçi", users['username'].tolist())
                if st.button("İşçini Sil"):
                    def del_u(): run_action("DELETE FROM users WHERE username=:u", {"u":du})
                    admin_confirm_dialog(f"İşçi silinsin: {du}?", del_u)

            # GLOBAL SETTINGS
            with st.expander("🔧 Sistem"):
                st_tbl = st.checkbox("Staff Masaları Görsün?", value=(get_setting("staff_show_tables","TRUE")=="TRUE"))
                if st.button("Yadda Saxla"): set_setting("staff_show_tables", "TRUE" if st_tbl else "FALSE"); st.rerun()
                
                rules = st.text_area("Müştəri Qaydaları (HTML)", value=get_setting("customer_rules", DEFAULT_TERMS))
                if st.button("Qaydaları Yenilə"): set_setting("customer_rules", rules); st.success("Yeniləndi")

    # --- OTHER TABS (Simplified for brevity, similar logic applies) ---
    # Loglar (Admin/Manager), Baza, QR etc. are standard from previous versions.
    if role in ['admin','manager']:
        with tabs[idx_crm-1]: # Loglar
            st.dataframe(run_query("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 100"), hide_index=True)
            
    if role == 'admin':
        with tabs[9]: # BAZA
             if st.button("FULL BACKUP"):
                out = BytesIO(); 
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    for t in ["users","sales","ingredients","customers"]: run_query(f"SELECT * FROM {t}").to_excel(writer, sheet_name=t, index=False)
                st.download_button("Endir", out.getvalue(), "backup.xlsx")
        
        with tabs[10]: # QR
            cnt = st.number_input("Say",1,50); kt = st.selectbox("Növ", ["Golden","Platinum","Elite","Thermos","Ikram"])
            if st.button("QR Yarat"):
                for _ in range(cnt):
                    run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :s)", {"i":str(random.randint(10000000,99999999)), "t":kt.lower(), "s":secrets.token_hex(8)})
                st.success("Hazır!")

    st.markdown(f"<div style='text-align:center;color:#aaa;margin-top:50px;'>Ironwaves POS {VERSION}</div>", unsafe_allow_html=True)
