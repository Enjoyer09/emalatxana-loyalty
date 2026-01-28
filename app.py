import streamlit as st
import streamlit.components.v1 as components
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
from PIL import Image, ImageDraw, ImageFont
import requests
from urllib.parse import urlparse, parse_qs 
import base64
import json
from collections import Counter

# ==========================================
# === EMALATKHANA POS - V4.6.1 (HOTFIX) ===
# ==========================================

VERSION = "v4.6.1 PRO (Init Fix)"
BRAND_NAME = "Emalatkhana Daily Coffee and Drinks"

# --- INFRA ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

# --- CONFIG ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# --- INIT STATE (MOVED TO TOP FOR SAFETY) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'current_customer_tb' not in st.session_state: st.session_state.current_customer_tb = None
if 'last_sale' not in st.session_state: st.session_state.last_sale = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'selected_recipe_product' not in st.session_state: st.session_state.selected_recipe_product = None

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');

    .stApp { font-family: 'Oswald', sans-serif !important; background-color: #F4F6F9; }
    header, #MainMenu, footer, [data-testid="stSidebar"] { display: none !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    
    button[data-baseweb="tab"] {
        font-family: 'Oswald', sans-serif !important; font-size: 18px !important; font-weight: 700 !important;
        background-color: white !important; border: 2px solid #FFCCBC !important; border-radius: 12px !important;
        margin: 0 4px !important; color: #555 !important; flex-grow: 1;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #2E7D32, #1B5E20) !important; border-color: #2E7D32 !important; color: white !important;
        box-shadow: 0 4px 12px rgba(46, 125, 50, 0.4);
    }
    
    div[data-testid="stRadio"] > label { display: none !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] { flex-direction: row; flex-wrap: wrap; gap: 8px; }
    div[data-testid="stRadio"] label[data-baseweb="radio"] { 
        background: white; border: 1px solid #ddd; padding: 5px 15px; border-radius: 20px; 
        font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s;
    }
    div[data-testid="stRadio"] label[aria-checked="true"] {
        background: #2E7D32; color: white; border-color: #2E7D32;
    }

    div.stButton > button { border-radius: 12px !important; height: 60px !important; font-weight: 700 !important; box-shadow: 0 4px 0 rgba(0,0,0,0.1) !important; transition: all 0.1s !important; }
    div.stButton > button:active { transform: translateY(3px) !important; box-shadow: none !important; }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; }
    
    .small-btn button { height: 35px !important; min-height: 35px !important; font-size: 14px !important; padding: 0 !important; }

    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #43A047, #2E7D32) !important; color: white !important; border: 2px solid #1B5E20 !important; height: 120px !important; font-size: 24px !important; white-space: pre-wrap !important; }
    div.stButton > button[kind="primary"].table-occ { background: linear-gradient(135deg, #E53935, #C62828) !important; color: white !important; border: 2px solid #B71C1C !important; height: 120px !important; font-size: 24px !important; white-space: pre-wrap !important; animation: pulse-red 2s infinite; }

    .paper-receipt { background-color: #fff; width: 100%; max-width: 350px; padding: 20px; margin: 0 auto; box-shadow: 0 0 15px rgba(0,0,0,0.1); font-family: 'Courier Prime', monospace; font-size: 13px; color: #000; border: 1px solid #ddd; }
    .receipt-cut-line { border-bottom: 2px dashed #000; margin: 15px 0; }
    
    .cust-card { background: white; border-radius: 20px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center; margin-bottom: 20px; border: 1px solid #eee; }
    .coffee-grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 20px; }
    .coffee-icon { width: 45px; opacity: 0.2; filter: grayscale(100%); transition: all 0.5s; }
    .coffee-icon.active { opacity: 1; filter: none; transform: scale(1.1); }
    
    .motivation-text { font-size: 18px; color: #555; font-style: italic; text-align: center; margin-bottom: 15px; }

    @media print {
        body * { visibility: hidden; }
        .paper-receipt, .paper-receipt * { visibility: visible; }
        .paper-receipt { position: fixed; left: 0; top: 0; width: 100%; margin: 0; padding: 0; border: none; box-shadow: none; }
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
def ensure_schema():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS tables (id SERIAL PRIMARY KEY, label TEXT, is_occupied BOOLEAN DEFAULT FALSE, items TEXT, total DECIMAL(10,2) DEFAULT 0, opened_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_active BOOLEAN DEFAULT FALSE, is_coffee BOOLEAN DEFAULT FALSE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS ingredients (id SERIAL PRIMARY KEY, name TEXT UNIQUE, stock_qty DECIMAL(10,2) DEFAULT 0, unit TEXT, category TEXT, min_limit DECIMAL(10,2) DEFAULT 10);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS recipes (id SERIAL PRIMARY KEY, menu_item_name TEXT, ingredient_name TEXT, quantity_required DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS system_logs (id SERIAL PRIMARY KEY, username TEXT, action TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, title TEXT, amount DECIMAL(10,2), category TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS coupon_templates (id SERIAL PRIMARY KEY, name TEXT, percent INTEGER, days_valid INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS void_logs (id SERIAL PRIMARY KEY, item_name TEXT, qty INTEGER, reason TEXT, deleted_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedbacks (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))

        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS customer_card_id TEXT;"))
        except: pass
        try: s.execute(text("ALTER TABLE tables ADD COLUMN IF NOT EXISTS active_customer_id TEXT;"))
        except: pass
        try: s.execute(text("ALTER TABLE menu ADD COLUMN IF NOT EXISTS printer_target TEXT DEFAULT 'kitchen';")) 
        except: pass
        try: s.execute(text("ALTER TABLE menu ADD COLUMN IF NOT EXISTS price_half DECIMAL(10,2);"))
        except: pass
        try: s.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS ingredient_name TEXT;"))
        except: pass
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_feedback_star_count INTEGER DEFAULT 0;"))
        except: pass
        
        res = s.execute(text("SELECT count(*) FROM tables")).fetchone()
        if res[0] == 0:
            for i in range(1, 7): s.execute(text("INSERT INTO tables (label, is_occupied) VALUES (:l, FALSE)"), {"l": f"MASA {i}"})
        s.commit()
    with conn.session as s:
        try:
            chk = s.execute(text("SELECT * FROM users WHERE username='admin'")).fetchone()
            if not chk:
                p_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
                s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin')"), {"p": p_hash})
                s.commit()
        except: s.rollback()
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
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
    datas = img.getdata(); newData = []
    for item in datas:
        if item[0] > 200: newData.append((255, 255, 255, 0)) 
        else: newData.append((0, 100, 0, 255)) 
    img.putdata(newData)
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return "API_KEY_MISSING"
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    payload = {"from": f"{BRAND_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}
    try: 
        r = requests.post(url, json=payload, headers=headers, timeout=5)
        if r.status_code == 200: return "OK"
        else: return f"API Error {r.status_code}"
    except: return "Connection Error"
def format_qty(val):
    if val % 1 == 0: return int(val)
    return val

# --- SMART CALCULATION ENGINE ---
def calculate_smart_total(cart, customer=None, is_table=False):
    total = 0.0; discounted_total = 0.0; coffee_discount_rate = 0.0
    current_stars = 0
    if customer:
        current_stars = customer.get('stars', 0)
        if customer.get('type') == 'thermos': coffee_discount_rate = 0.20
        try:
            coupons = run_query("SELECT coupon_type FROM customer_coupons WHERE card_id=:id AND is_used=FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": customer['card_id']})
            for _, c in coupons.iterrows():
                parts = c['coupon_type'].split('_')
                for p in parts:
                    if p.isdigit():
                        rate = int(p) / 100.0
                        if rate > coffee_discount_rate: coffee_discount_rate = rate 
        except: pass

    cart_coffee_count = sum([item['qty'] for item in cart if item.get('is_coffee')])
    total_star_pool = current_stars + cart_coffee_count
    potential_free = int(total_star_pool // 10)
    free_coffees_to_apply = min(potential_free, cart_coffee_count)
    
    for item in cart:
        total += item['qty'] * item['price']
    
    discounted_total = total
    coffee_sum = sum([item['qty'] * item['price'] for item in cart if item.get('is_coffee')])
    discount_amount = coffee_sum * coffee_discount_rate
    discounted_total -= discount_amount
    
    service_charge = 0.0
    if is_table:
        service_charge = discounted_total * 0.07
        discounted_total += service_charge
            
    return total, discounted_total, coffee_discount_rate, free_coffees_to_apply, total_star_pool, service_charge

# --- SMART ADD (AGGREGATION) ---
def add_to_cart(cart_ref, item):
    try:
        r = run_query("SELECT printer_target, price_half FROM menu WHERE item_name=:n", {"n":item['item_name']})
        if not r.empty:
            item['printer_target'] = r.iloc[0]['printer_target']
            item['price_half'] = float(r.iloc[0]['price_half']) if r.iloc[0]['price_half'] else None
        else:
            item['printer_target'] = 'kitchen'
            item['price_half'] = None
    except: 
        item['printer_target'] = 'kitchen'
        item['price_half'] = None
    
    for ex in cart_ref:
        if ex['item_name'] == item['item_name'] and ex.get('status') == 'new' and ex.get('qty') % 1 == 0: 
            ex['qty'] += 1
            return
    cart_ref.append(item)

# --- PORTION TOGGLE ---
def toggle_portion(idx):
    item = st.session_state.cart_table[idx]
    if item['qty'] == 1.0:
        item['qty'] = 0.5
        if item.get('price_half'):
            item['price'] = item['price_half'] * 2 
    elif item['qty'] == 0.5:
        item['qty'] = 1.0
        r = run_query("SELECT price FROM menu WHERE item_name=:n", {"n":item['item_name']})
        if not r.empty: item['price'] = float(r.iloc[0]['price'])

# --- 1. MÜŞTƏRİ PORTALI (V4.6 - UPDATED) ---
qp = st.query_params
if "id" in qp:
    card_id = qp["id"]
    c1, c2, c3 = st.columns([1,2,1])
    with c2: 
        # BRAND HEADER
        st.markdown(f"<h2 style='text-align:center; color:#2E7D32; font-weight:bold;'>{BRAND_NAME}</h2>", unsafe_allow_html=True)
    
    user_df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not user_df.empty:
        user = user_df.iloc[0]
        
        # MOTIVATION
        quotes = [
            "Bu gün əla görünürsən! ☕", "Uğur bir fincan kofe ilə başlayır.", 
            "Gülüşün günümüzü işıqlandırır.", "Kofe bəhanə, söhbət şahanə.", 
            "Enerjini topla, dünyanı fəth et!", "Sənin kofen, sənin qaydaların."
        ]
        st.markdown(f"<div class='motivation-text'>{random.choice(quotes)}</div>", unsafe_allow_html=True)

        if not user['is_active']:
            st.info("🎉 Xoş gəlmisiniz! Qeydiyyatı tamamlayın.")
            with st.form("act_form"):
                em = st.text_input("Email"); dob = st.date_input("Doğum Tarixi", min_value=datetime.date(1950,1,1))
                st.markdown("### 📜 İstifadəçi Razılaşması")
                with st.expander("Qaydaları Oxumaq üçün Toxunun"):
                    st.markdown(f"""
                    **İSTİFADƏÇİ RAZILAŞMASI VƏ MƏXFİLİK SİYASƏTİ**

                    **1. Ümumi Müddəalar**
                    Bu loyallıq proqramı **"{BRAND_NAME}"** sistemi vasitəsilə idarə olunur. Qeydiyyatdan keçməklə siz aşağıdakı şərtləri qəbul etmiş olursunuz.

                    **2. Bonuslar, Hədiyyələr və Endirim Siyasəti**
                    2.1. Toplanılan ulduzlar və bonuslar heç bir halda nağd pula çevrilə, başqa hesaba köçürülə və ya qaytarıla bilməz.
                    2.2. **Şəxsiyyətin Təsdiqi:** Ad günü və ya xüsusi kampaniya hədiyyələrinin təqdim edilməsi zamanı, sui-istifadə hallarınin qarşısını almaq və təvəllüdü dəqiqləşdirmək məqsədilə, şirkət əməkdaşı müştəridən şəxsiyyət vəsiqəsini təqdim etməsini tələb etmək hüququna malikdir. Sənəd təqdim edilmədikdə hədiyyə verilməyə bilər.
                    2.3. **Endirimlərin Tətbiq Sahəsi:** Nəzərinizə çatdırırıq ki, **"{BRAND_NAME}"** loyallıq proqramı çərçivəsində təqdim olunan bütün növ imtiyazlar (o cümlədən "Ekoloji Termos" endirimi, xüsusi promo-kodlar və faizli endirim kartları) **müstəsna olaraq kofe və kofe əsaslı içkilərə şamil edilir.** Şirniyyatlar, qablaşdırılmış qida məhsulları və digər soyuq içkilər endirim siyasətindən xaricdir. Sizin kofe həzzinizi daha əlçatan etmək üçün çalışırıq!

                    **3. Dəyişikliklər və İmtina Hüququ**
                    3.1. Şirkət, bu razılaşmanın şərtlərini dəyişdirmək hüququnu özündə saxlayır.
                    3.2. **Bildiriş:** Şərtlərdə əsaslı dəyişikliklər edildiyi təqdirdə, qeydiyyatlı e-poçt ünvanınıza bildiriş göndəriləcək.
                    3.3. **İmtina:** Əgər yeni şərtlərlə razılaşmırsınızsa, sistemdən qeydiyyatınızın və fərdi məlumatlarınızın silinməsini tələb etmək hüququnuz var.

                    **4. Məxfilik**
                    4.1. Sizin məlumatlarınız (Email, Doğum tarixi) üçüncü tərəflə paylaşılmır və yalnız xidmət keyfiyyətinin artırılması üçün istifadə olunur.
                    """)
                agree = st.checkbox("Şərtləri qəbul edirəm")
                if st.form_submit_button("Tamamla"):
                    if agree:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob, "i":card_id})
                        st.success("Hazırdır!"); st.rerun()
                    else: st.error("Qaydaları qəbul etməlisiniz.")
            st.stop()
        
        # BALANCE CARD
        st.markdown(f"<div class='cust-card'><h4 style='margin:0; color:#888;'>BALANS</h4><h1 style='color:#2E7D32; font-size: 48px; margin:0;'>{user['stars']} / 10</h1><p style='color:#555;'>ID: {card_id}</p></div>", unsafe_allow_html=True)
        html_grid = '<div class="coffee-grid">'
        for i in range(10):
            icon_url = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            cls = "coffee-icon"; style = ""
            if i == 9: 
                icon_url = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png"
                if user['stars'] >= 10: style="opacity:1; filter:none; animation: bounce 1s infinite;"
            elif i < user['stars']: style="opacity:1; filter:none;"
            html_grid += f'<img src="{icon_url}" class="{cls}" style="{style}">'
        html_grid += '</div>'
        st.markdown(html_grid, unsafe_allow_html=True)
        
        # --- FEEDBACK LOGIC ---
        last_fb = user.get('last_feedback_star_count', 0) or 0
        current_stars = user['stars']
        
        if current_stars > 0 and current_stars > last_fb:
            st.divider()
            st.markdown("#### 🌟 Fikriniz önəmlidir!")
            with st.form("fb_form"):
                rating = st.radio("Xidmətimizi qiymətləndirin:", ["⭐️", "⭐️⭐️", "⭐️⭐️⭐️", "⭐️⭐️⭐️⭐️", "⭐️⭐️⭐️⭐️⭐️"], horizontal=True, index=4)
                comment = st.text_area("Rəyiniz (İstəyə bağlı)", placeholder="Kofe necə idi?")
                if st.form_submit_button("Göndər"):
                    r_val = len(rating) // 2 
                    if rating == "⭐️": r_val = 1
                    elif rating == "⭐️⭐️": r_val = 2
                    elif rating == "⭐️⭐️⭐️": r_val = 3
                    elif rating == "⭐️⭐️⭐️⭐️": r_val = 4
                    elif rating == "⭐️⭐️⭐️⭐️⭐️": r_val = 5
                    
                    run_action("INSERT INTO feedbacks (card_id, rating, comment, created_at) VALUES (:c, :r, :m, :t)", 
                               {"c":card_id, "r":r_val, "m":comment, "t":get_baku_now()})
                    run_action("UPDATE customers SET last_feedback_star_count = :s WHERE card_id = :c", {"s":current_stars, "c":card_id})
                    st.success("Təşəkkürlər! Rəyiniz qəbul olundu. 💚")
                    time.sleep(2); st.rerun()
        elif current_stars > 0 and current_stars == last_fb:
             st.markdown("<p style='text-align:center; color:#2E7D32; margin-top:20px;'><i>Dəyərli fikriniz üçün təşəkkürlər! Növbəti kofedə görüşərik 💚</i></p>", unsafe_allow_html=True)

        st.divider()
        if st.button("Çıxış"): st.query_params.clear(); st.rerun()
        st.stop()

# --- SESSION ---
def check_session_token():
    token = st.query_params.get("token")
    if token:
        try:
            res = run_query("SELECT username, role FROM active_sessions WHERE token=:t", {"t":token})
            if not res.empty:
                st.session_state.logged_in=True; st.session_state.user=res.iloc[0]['username']; st.session_state.role=res.iloc[0]['role']; st.query_params.clear()
        except: pass
def cleanup_old_sessions():
    try: run_action("DELETE FROM active_sessions WHERE created_at < NOW() - INTERVAL '24 hours'")
    except: pass

check_session_token()
if st.session_state.get('logged_in'):
    cleanup_old_sessions()
    run_action("UPDATE users SET last_seen = :t WHERE username = :u", {"t":get_baku_now(), "u": st.session_state.user})

if 'last_sale' in st.session_state and st.session_state.last_sale: show_receipt_dialog(); st.session_state.last_sale = None

# --- MAIN ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        # LOGIN HEADER
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center; color:#777;'>{VERSION}</h5>", unsafe_allow_html=True)
        tabs = st.tabs(["İŞÇİ", "ADMİN"])
        with tabs[0]:
            with st.form("staff_login"):
                pin = st.text_input("PIN", type="password"); 
                if st.form_submit_button("Giriş", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE role='staff'")
                    found = False
                    for _, row in udf.iterrows():
                        if verify_password(pin, row['password']):
                            st.session_state.logged_in=True; st.session_state.user=row['username']; st.session_state.role='staff'
                            tok=secrets.token_urlsafe(16); run_action("INSERT INTO active_sessions (token,username,role,created_at) VALUES (:t,:u,:r,:time)", {"t":tok,"u":row['username'],"r":'staff',"time":get_baku_now()})
                            log_system(row['username'], "Login (Staff)"); st.query_params["token"] = tok; st.rerun(); found=True; break
                    if not found: st.error("Yanlış PIN!")
        with tabs[1]:
            with st.form("admin_login"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Admin Giriş", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(:u) AND role='admin'", {"u":u})
                    if not udf.empty and verify_password(p, udf.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role='admin'
                        tok=secrets.token_urlsafe(16); run_action("INSERT INTO active_sessions (token,username,role,created_at) VALUES (:t,:u,:r,:time)", {"t":tok,"u":u,"r":'admin',"time":get_baku_now()})
                        log_system(u, "Login (Admin)"); st.query_params["token"] = tok; st.rerun()
                    else: st.error("Səhv!")
else:
    h1, h2, h3 = st.columns([4, 1, 1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄 Yenilə", use_container_width=True): st.rerun()
    with h3: 
        if st.button("🚪 Çıxış", type="primary", use_container_width=True):
            run_action("DELETE FROM active_sessions WHERE token=:t", {"t":st.query_params.get("token")})
            log_system(st.session_state.user, "Logout"); st.session_state.logged_in = False; st.rerun()
    st.divider()

    role = st.session_state.role
    
    if role == 'admin':
        # DYNAMIC ADMIN TABS
        tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "📦 Anbar", "📜 Resept", "Analitika", "👥 CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
        with tabs[0]: render_takeaway()
        with tabs[1]: render_tables_main()
        with tabs[2]: # Anbar
            st.subheader("📦 Anbar")
            cats = run_query("SELECT DISTINCT category FROM ingredients ORDER BY category")['category'].tolist()
            if not cats: cats = ["Ümumi"]
            all_tabs_list = ["Bütün"] + cats
            inv_tabs = st.tabs(all_tabs_list)
            
            @st.dialog("Anbar Əməliyyatı")
            def manage_stock(id, name, current_qty, unit):
                st.markdown(f"### {name}")
                c1, c2 = st.columns(2)
                with c1:
                    add_q = st.number_input(f"Artır ({unit})", min_value=0.0, key=f"add_{id}")
                    if st.button("➕ Mədaxil", key=f"btn_add_{id}"):
                        run_action("UPDATE ingredients SET stock_qty=stock_qty+:q WHERE id=:id", {"q":add_q, "id":id}); 
                        log_system(st.session_state.user, f"Restock: {name} +{add_q}{unit}")
                        st.success("Oldu!"); st.rerun()
                with c2:
                    fix_q = st.number_input("Dəqiq Say", value=float(current_qty), min_value=0.0, key=f"fix_{id}")
                    if st.button("✏️ Düzəliş", key=f"btn_fix_{id}"):
                        run_action("UPDATE ingredients SET stock_qty=:q WHERE id=:id", {"q":fix_q, "id":id}); 
                        log_system(st.session_state.user, f"Stock Correction: {name} -> {fix_q}{unit}")
                        st.success("Oldu!"); st.rerun()
                st.divider()
                if st.button("🗑️ Malı Sil", key=f"del_{id}", type="primary"):
                    run_action("DELETE FROM ingredients WHERE id=:id", {"id":id}); 
                    log_system(st.session_state.user, f"Deleted Ingredient: {name}")
                    st.rerun()

            def render_inv(cat=None):
                sql = "SELECT * FROM ingredients"
                p={}
                if cat and cat != "Bütün": sql += " WHERE category=:c"; p['c']=cat
                sql += " ORDER BY name"
                df = run_query(sql, p)
                if not df.empty:
                    cols = st.columns(4)
                    for idx, r in df.iterrows():
                        with cols[idx % 4]:
                            key_suffix = cat if cat else "all"
                            label = f"{r['name']}\n{format_qty(r['stock_qty'])} {r['unit']}"
                            if st.button(label, key=f"inv_{r['id']}_{key_suffix}", use_container_width=True):
                                manage_stock(r['id'], r['name'], r['stock_qty'], r['unit'])
                else: st.info("Boşdur")

            for i, t_name in enumerate(all_tabs_list):
                with inv_tabs[i]:
                    render_inv(t_name)
                    if i==0:
                        st.divider()
                        with st.expander("➕ Yeni Mal Yarat"):
                            with st.form("new_inv"):
                                n=st.text_input("Ad"); q=st.number_input("Say", min_value=0.0, key="ni_q"); u=st.selectbox("Vahid",["gr","ml","ədəd","litr","kq"]); c=st.text_input("Kateqoriya (Məs: Bar, Süd)")
                                if st.form_submit_button("Yarat"):
                                    run_action("INSERT INTO ingredients (name,stock_qty,unit,category) VALUES (:n,:q,:u,:c)", {"n":n,"q":q,"u":u,"c":c}); st.rerun()

        with tabs[3]: # Resept
            st.subheader("📜 Reseptlər")
            rc1, rc2 = st.columns([1, 2])
            with rc1: 
                search_menu = st.text_input("🔍 Axtar", key="rec_search")
                sql = "SELECT id, item_name FROM menu WHERE is_active=TRUE"
                if search_menu: sql += f" AND item_name ILIKE '%{search_menu}%'"
                sql += " ORDER BY item_name"
                menu_items = run_query(sql)
                if not menu_items.empty:
                    for _, r in menu_items.iterrows():
                        if st.button(r['item_name'], key=f"rm_{r['id']}", use_container_width=True):
                            st.session_state.selected_recipe_product = r['item_name']
                else: st.caption("Tapılmadı")
            with rc2: 
                if st.session_state.selected_recipe_product:
                    p_name = st.session_state.selected_recipe_product
                    p_price = run_query("SELECT price FROM menu WHERE item_name=:n", {"n":p_name}).iloc[0]['price']
                    with st.container(border=True):
                        st.markdown(f"### 🍹 {p_name}")
                        st.markdown(f"**Satış Qiyməti:** {p_price} ₼")
                        st.divider()
                        recs = run_query("""
                            SELECT r.id, r.ingredient_name, r.quantity_required, i.unit 
                            FROM recipes r 
                            JOIN ingredients i ON r.ingredient_name = i.name 
                            WHERE r.menu_item_name=:n
                        """, {"n":p_name})
                        if not recs.empty:
                            recs['Miqdar'] = recs['quantity_required'].astype(str) + " " + recs['unit']
                            recs.insert(0, "Seç", False)
                            edited_recs = st.data_editor(
                                recs, 
                                column_config={
                                    "Seç": st.column_config.CheckboxColumn(required=True),
                                    "id": None, "quantity_required": None, "unit": None,
                                    "ingredient_name": "İnqrediyent"
                                }, 
                                hide_index=True, use_container_width=True, key="rec_editor"
                            )
                            to_del = edited_recs[edited_recs['Seç']]['id'].tolist()
                            if to_del and st.button(f"Seçilənləri Sil ({len(to_del)})", type="primary"):
                                for d_id in to_del: run_action("DELETE FROM recipes WHERE id=:id", {"id":d_id})
                                st.rerun()
                        else: st.info("Resept boşdur.")
                        st.divider()
                        st.markdown("➕ **İnqrediyent Əlavə Et**")
                        all_ings = run_query("SELECT name, unit FROM ingredients ORDER BY name")
                        if not all_ings.empty:
                            c_sel, c_qty, c_btn = st.columns([2, 1, 1])
                            sel_ing = c_sel.selectbox("Xammal", all_ings['name'].tolist(), label_visibility="collapsed", key="new_r_ing")
                            sel_unit = all_ings[all_ings['name']==sel_ing].iloc[0]['unit']
                            sel_qty = c_qty.number_input(f"Miqdar ({sel_unit})", min_value=0.0, step=1.0, label_visibility="collapsed", key="new_r_qty")
                            if c_btn.button("Əlavə", type="primary", use_container_width=True):
                                run_action("INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m,:i,:q)", {"m":p_name, "i":sel_ing, "q":sel_qty}); st.rerun()
                else: st.info("👈 Soldan məhsul seçin")

        with tabs[4]: render_analytics(is_admin=True)
        with tabs[5]: # CRM
            st.subheader("👥 CRM"); c_cp, c_mail, c_fb = st.columns([1,1,1])
            crm_tabs = st.tabs(["Kupon Yarat", "Şablonlar", "Email", "💬 Rəylər"])
            
            with crm_tabs[0]:
                with st.form("custom_coupon"):
                    cc_name = st.text_input("Kupon Kodu (Məs: YAY2026)")
                    cc_perc = st.number_input("Endirim (%)", 1, 100, 10)
                    cc_days = st.number_input("Müddət (Gün)", 1, 365, 7)
                    if st.form_submit_button("Şablonu Yadda Saxla"):
                        run_action("INSERT INTO coupon_templates (name, percent, days_valid) VALUES (:n, :p, :d)", {"n":cc_name, "p":cc_perc, "d":cc_days})
                        st.success("Yadda saxlandı!")
            
            with crm_tabs[1]:
                templates = run_query("SELECT * FROM coupon_templates ORDER BY created_at DESC")
                if not templates.empty:
                    for _, t in templates.iterrows():
                        c_t1, c_t2 = st.columns([3, 1])
                        c_t1.write(f"🏷️ **{t['name']}** - {t['percent']}% ({t['days_valid']} gün)")
                        if c_t2.button("Payla", key=f"dist_{t['id']}"):
                            ctype = f"custom_{t['percent']}_{t['name']}"
                            for _, r in run_query("SELECT card_id FROM customers").iterrows(): 
                                run_action(f"INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES ('{r['card_id']}', '{ctype}', NOW() + INTERVAL '{t['days_valid']} days')")
                            st.success("Göndərildi!")
                else: st.info("Şablon yoxdur")

            with crm_tabs[2]:
                st.markdown("#### 📧 Email")
                all_customers = run_query("SELECT card_id, email, stars FROM customers")
                all_customers.insert(0, "Seç", False)
                edited_df = st.data_editor(all_customers, hide_index=True, use_container_width=True)
                selected_emails = edited_df[edited_df["Seç"] == True]['email'].tolist()
                with st.form("mail"):
                    sub = st.text_input("Mövzu"); msg = st.text_area("Mesaj"); 
                    if st.form_submit_button("Seçilənlərə Göndər"):
                        c = 0
                        for e in selected_emails: 
                            if e and send_email(e, sub, msg) == "OK": c+=1
                        st.success(f"{c} email getdi!")
            
            # V4.6 NEW TAB: FEEDBACKS
            with crm_tabs[3]:
                st.markdown("### 💬 Müştəri Rəyləri")
                fbs = run_query("SELECT * FROM feedbacks ORDER BY created_at DESC")
                if not fbs.empty:
                    for _, fb in fbs.iterrows():
                        stars = "⭐️" * fb['rating']
                        st.markdown(f"**ID:** {fb['card_id']} | {stars}")
                        st.info(fb['comment'] or "(Rəy yazılmayıb)")
                        st.caption(f"Tarix: {fb['created_at']}")
                        st.divider()
                else: st.info("Hələ rəy yoxdur")

        with tabs[6]: # Menyu (V4.0 - HALF PRICE)
            st.subheader("📋 Menyu (V4.6)")
            with st.expander("📥 Excel"):
                up = st.file_uploader("Fayl", type=['xlsx'])
                if up and st.button("Yüklə", key="xl_load"):
                    df = pd.read_excel(up); run_action("DELETE FROM menu")
                    for _, row in df.iterrows(): 
                        pt = row.get('printer_target', 'kitchen')
                        ph = row.get('price_half', None)
                        run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee,printer_target,price_half) VALUES (:n,:p,:c,TRUE,:ic,:pt,:ph)", 
                                   {"n":row['item_name'],"p":row['price'],"c":row['category'],"ic":row.get('is_coffee',False),"pt":pt,"ph":ph})
                    st.rerun()
            with st.form("nm"):
                c1, c2, c3 = st.columns(3)
                with c1: n=st.text_input("Ad"); p=st.number_input("Qiymət", min_value=0.0, key="menu_p")
                with c2: c=st.text_input("Kat"); ic=st.checkbox("Kofe?"); pt=st.selectbox("Printer", ["kitchen", "bar"])
                with c3: ph=st.number_input("Yarım Qiymət (Seçimli)", min_value=0.0, value=0.0)
                
                if st.form_submit_button("Əlavə"): 
                    ph_val = ph if ph > 0 else None
                    run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee,printer_target,price_half) VALUES (:n,:p,:c,TRUE,:ic,:pt,:ph)", 
                               {"n":n,"p":p,"c":c,"ic":ic,"pt":pt,"ph":ph_val})
                    log_system(st.session_state.user, f"Added Menu Item: {n} ({p} AZN)")
                    st.rerun()
            
            ml = run_query("SELECT * FROM menu")
            if not ml.empty:
                ml.insert(0, "Seç", False)
                edited_menu = st.data_editor(ml, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, hide_index=True, use_container_width=True)
                to_del_menu = edited_menu[edited_menu['Seç']]['item_name'].tolist()
                if to_del_menu and st.button(f"Seçilənləri Sil ({len(to_del_menu)})", type="primary", key="del_menu_bulk"):
                    for i_n in to_del_menu: 
                        run_action("DELETE FROM menu WHERE item_name=:n", {"n":i_n})
                        log_system(st.session_state.user, f"Deleted Menu Item: {i_n}")
                    st.rerun()

        with tabs[7]: # Ayarlar
            st.subheader("⚙️ Ayarlar")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**🧾 Çek Məlumatları**")
                r_name = st.text_input("Mağaza Adı", value=get_setting("receipt_store_name", BRAND_NAME))
                r_addr = st.text_input("Ünvan", value=get_setting("receipt_address", "Bakı"))
                r_phone = st.text_input("Telefon", value=get_setting("receipt_phone", "+994 55 000 00 00"))
                r_web = st.text_input("Vebsayt", value=get_setting("receipt_web", "www.ironwaves.store"))
                r_insta = st.text_input("Instagram", value=get_setting("receipt_insta", "@ironwaves"))
                r_email = st.text_input("Email", value=get_setting("receipt_email", "info@ironwaves.store"))
                r_foot = st.text_input("Footer", value=get_setting("receipt_footer", "Təşəkkürlər!"))
                lf = st.file_uploader("Logo"); 
                if lf and st.button("Logo Saxla", key="sv_lg"): set_setting("receipt_logo_base64", image_to_base64(lf)); st.success("OK")
                if st.button("Məlumatları Saxla", key="sv_txt"): 
                    set_setting("receipt_store_name", r_name); set_setting("receipt_address", r_addr)
                    set_setting("receipt_phone", r_phone); set_setting("receipt_footer", r_foot)
                    set_setting("receipt_web", r_web); set_setting("receipt_insta", r_insta); set_setting("receipt_email", r_email)
                    st.success("Yadda saxlanıldı!")
                
                st.divider()
                st.markdown("**🔧 Sistem Ayarları**")
                show_tbl = st.checkbox("İşçi Panelində 'Masalar' bölməsini göstər", value=(get_setting("staff_show_tables", "TRUE")=="TRUE"))
                if st.button("Yadda Saxla", key="sv_sys"):
                    set_setting("staff_show_tables", "TRUE" if show_tbl else "FALSE")
                    st.success("Yadda saxlanıldı! (Yeniləyin)")

            with c2:
                st.markdown("**🔐 Şifrə Dəyişmə**")
                all_users = run_query("SELECT username FROM users")
                target_user = st.selectbox("İstifadəçi Seç", all_users['username'].tolist(), key="cp_user")
                new_pass = st.text_input("Yeni Şifrə / PIN", type="password", key="cp_pass")
                if st.button("Şifrəni Yenilə"):
                    run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_pass), "u":target_user})
                    log_system(st.session_state.user, f"Changed password for {target_user}")
                    st.success("Yeniləndi!")
                st.divider()
                with st.form("nu"):
                    u=st.text_input("Ad"); p=st.text_input("PIN"); r=st.selectbox("Rol",["staff","admin"])
                    if st.form_submit_button("Yarat"): 
                        run_action("INSERT INTO users (username,password,role) VALUES (:u,:p,:r)", {"u":u,"p":hash_password(p),"r":r})
                        log_system(st.session_state.user, f"Created User: {u}")
                        st.success("OK")
        
        with tabs[8]: # Admin
            st.subheader("🔧 Admin Tools")
            if st.button("📥 FULL BACKUP", key="bkp_btn"):
                log_system(st.session_state.user, "Requested Full Backup")
                out = BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    for t in ["customers", "sales", "menu", "users", "ingredients", "recipes", "system_logs", "tables", "expenses", "void_logs", "feedbacks"]:
                        clean_df_for_excel(run_query(f"SELECT * FROM {t}")).to_excel(writer, sheet_name=t.capitalize())
                st.download_button("⬇️ Endir", out.getvalue(), "Backup.xlsx")
            st.divider()
            with st.form("restore_form"):
                rf = st.file_uploader("Backup (.xlsx)")
                ap = st.text_input("Admin Şifrə", type="password")
                if st.form_submit_button("Bərpa Et"):
                    adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
                    if not adm.empty and verify_password(ap, adm.iloc[0]['password']):
                        if rf:
                            xls = pd.ExcelFile(rf)
                            try:
                                run_action("DELETE FROM menu"); run_action("DELETE FROM ingredients"); run_action("DELETE FROM recipes")
                                if "Menu" in xls.sheet_names:
                                    for _, row in pd.read_excel(xls, "Menu").iterrows():
                                        run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee) VALUES (:n,:p,:c,TRUE,:ic)", 
                                                   {"n":row['item_name'],"p":row['price'],"c":row['category'],"ic":row.get('is_coffee',False)})
                                log_system(st.session_state.user, "Restored Database from Backup")
                                st.success("Bərpa olundu!")
                            except Exception as e: st.error(f"Xəta: {e}")
                    else: st.error("Şifrə səhvdir")

        with tabs[9]: # QR
            cnt = st.number_input("Say", value=1, min_value=1, key="qr_cnt"); k = st.selectbox("Növ", ["Standard", "Termos", "10%", "20%", "50%"])
            if st.button("Yarat", key="gen_qr"):
                zb = BytesIO()
                with zipfile.ZipFile(zb, "w") as zf:
                    images = []
                    for _ in range(cnt):
                        i = str(random.randint(10000000, 99999999)); tok = secrets.token_hex(8); ct = "thermos" if k=="Termos" else "standard"
                        run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":ct, "st":tok})
                        code = None
                        if "10%" in k: code="disc_10"
                        elif "20%" in k: code="disc_20"
                        elif "50%" in k: code="disc_50"
                        if code: run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:i, :c)", {"i":i, "c":code})
                        
                        img_bytes = generate_custom_qr(f"{APP_URL}/?id={i}&t={tok}", i)
                        zf.writestr(f"QR_{i}.png", img_bytes)
                        images.append(img_bytes)
                
                if cnt <= 3:
                    cols = st.columns(cnt)
                    for idx, img in enumerate(images):
                        with cols[idx]: st.image(img, width=200)
                
                st.download_button("📥 Bütün QR-ları Endir (ZIP)", zb.getvalue(), "qrcodes.zip", "application/zip", type="primary")

    elif role == 'staff':
        # DYNAMIC STAFF TABS (V4.2)
        show_tables = (get_setting("staff_show_tables", "TRUE") == "TRUE")
        if show_tables:
            staff_tabs = st.tabs(["🏃‍♂️ AL-APAR", "🍽️ MASALAR", "Mənim Satışlarım"])
            with staff_tabs[0]: render_takeaway()
            with staff_tabs[1]: render_tables_main()
            with staff_tabs[2]: render_analytics(is_admin=False)
        else:
            staff_tabs = st.tabs(["🏃‍♂️ AL-APAR", "Mənim Satışlarım"])
            with staff_tabs[0]: render_takeaway()
            with staff_tabs[1]: render_analytics(is_admin=False)

    st.markdown(f"<div class='footer'>Ironwaves POS {VERSION} | © 2026</div>", unsafe_allow_html=True)
