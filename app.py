import streamlit as st
import pandas as pd
import random
import qrcode
from io import BytesIO
import zipfile
from PIL import Image, ImageDraw, ImageFont
import time
from sqlalchemy import text, exc
import os
import bcrypt
import requests
import datetime
import secrets
import threading
import base64

# --- INFRASTRUKTUR AYARLARI ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

st.set_page_config(page_title="Emalatxana POS", page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# === DİZAYN KODLARI (CSS) ===
# ==========================================
st.markdown("""
    <script>
    function keepAlive() { var xhr = new XMLHttpRequest(); xhr.open("GET", "/", true); xhr.send(); }
    setInterval(keepAlive, 30000); 
    </script>

    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    
    #MainMenu, header, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .stApp { font-family: 'Oswald', sans-serif !important; background-color: #FAFAFA; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 100%; }

    /* --- POS DÜYMƏLƏRİ --- */
    div.stButton > button[kind="secondary"] {
        background-color: #FFFFFF !important;
        color: #2E7D32 !important;
        border: 3px solid #2E7D32 !important; 
        border-radius: 12px !important;
        height: 60px !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 0 rgba(46, 125, 50, 0.2) !important;
        transition: all 0.1s !important;
    }
    div.stButton > button[kind="secondary"]:active {
        transform: translateY(4px) !important;
        box-shadow: none !important;
        background-color: #E8F5E9 !important;
    }

    div.stButton > button {
        background-color: #FFFFFF !important;
        color: #E65100 !important;
        border: 3px solid #E65100 !important;
        border-radius: 15px !important;
        font-family: 'Oswald', sans-serif !important;
        font-weight: 900 !important;
        font-size: 22px !important;
        min-height: 90px !important;
        width: 100% !important;
        box-shadow: 0 5px 0 rgba(230, 81, 0, 0.2) !important;
        transition: transform 0.1s !important;
    }
    div.stButton > button:active {
        transform: translateY(5px) !important;
        box-shadow: none !important;
        background-color: #FFF3E0 !important;
    }
    
    div.stButton > button[kind="primary"] {
        background-color: #E65100 !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(230, 81, 0, 0.4) !important;
    }

    /* --- MÜŞTƏRİ EKRANI --- */
    .digital-card {
        background: white; border-radius: 20px; padding: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #eee;
        text-align: center; margin-bottom: 20px;
    }
    
    .coffee-grid-container {
        display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; 
        justify-items: center; margin-top: 25px;
    }
    .coffee-icon { width: 50px; height: 50px; transition: all 0.3s ease; }
    
    .gift-box-anim {
        width: 65px; height: 65px;
        animation: bounce 2s infinite;
        filter: drop-shadow(0 0 8px gold);
    }
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
        40% {transform: translateY(-15px);}
        60% {transform: translateY(-7px);}
    }

    .progress-text {
        font-size: 24px; color: #D84315; font-weight: bold; margin-top: 15px;
        background: #FBE9E7; padding: 10px; border-radius: 10px; border: 1px dashed #D84315;
    }

    .inner-motivation {
        font-size: 20px; color: #2E7D32; font-family: 'Oswald', sans-serif;
        font-weight: 700; margin-bottom: 10px; text-align: center;
    }

    .insta-link {
        display: inline-block;
        margin-top: 10px;
        transition: transform 0.2s;
        animation: pulse-insta 2s infinite;
    }
    .insta-link img { width: 40px; height: 40px; }
    .insta-link:hover { transform: scale(1.1); }
    @keyframes pulse-insta {
        0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); }
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("DB URL not found!"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA ---
def ensure_schema():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT);"))
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_feedback_star INTEGER DEFAULT -1;"))
        except: pass
        try: s.execute(text("ALTER TABLE customer_coupons ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;")) 
        except: pass
        
        # IPHONE FIX (OLD TOKENS UPDATE)
        try: s.execute(text("UPDATE customers SET secret_token = md5(random()::text) WHERE secret_token LIKE '%-%' OR secret_token LIKE '%_%';"))
        except: pass
        s.commit()
ensure_schema()

# --- CONFIG ---
def get_config(key, default=""):
    try:
        df = conn.query("SELECT value FROM settings WHERE key = :k", params={"k": key})
        return df.iloc[0]['value'] if not df.empty else default
    except: return default

def set_config(key, value):
    with conn.session as s:
        s.execute(text("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = :v"), {"k": key, "v": value})
        s.commit()
    st.cache_data.clear() 

SHOP_NAME = get_config("shop_name", "Emalatxana Coffee")
SHOP_ADDRESS = get_config("shop_address", "Bakı şəhəri")
SHOP_PHONE = get_config("shop_phone", "+994 50 000 00 00")
INSTAGRAM_LINK = get_config("instagram_link", "https://instagram.com")
FACEBOOK_LINK = get_config("facebook_link", "")
YOUTUBE_LINK = get_config("youtube_link", "")
LOGO_BASE64 = get_config("shop_logo_base64", "")

# --- HELPERS ---
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
def run_query(q, p=None): return conn.query(q, params=p, ttl=0)

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

def process_logo_upload(uploaded_file):
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except: return None
    return None

def clean_df_for_excel(df):
    for col in df.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]']).columns:
        df[col] = df[col].astype(str)
    return df

def render_header():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{SHOP_NAME}</h1>", unsafe_allow_html=True)
        if INSTAGRAM_LINK:
            st.markdown(f"""<div style="text-align:center;"><a href="{INSTAGRAM_LINK}" target="_blank" class="insta-link"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Instagram_logo_2016.svg/2048px-Instagram_logo_2016.svg.png" alt="Instagram"></a></div>""", unsafe_allow_html=True)

# --- EMAIL SYSTEM ---
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return False
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "from": f"{SHOP_NAME} <{DEFAULT_SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "reply_to": "taliyev.abbas84@gmail.com",
        "html": f"<div style='font-family:Arial; padding:20px; color:#333; border:1px solid #eee; border-radius:10px;'><h2>{SHOP_NAME}</h2><hr><p>{body.replace(chr(10), '<br>')}</p></div>"
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        return r.status_code == 200
    except: return False

@st.cache_data
def generate_custom_qr(data, center_text):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype("arial.ttf", 20)
    except: font = ImageFont.load_default()
    bbox = draw.textbbox((0,0), center_text, font=font)
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.rectangle([(img.size[0]-w)/2-5, (img.size[1]-h)/2-5, (img.size[0]+w)/2+5, (img.size[1]+h)/2+5], fill="white")
    draw.text(((img.size[0]-w)/2, (img.size[1]-h)/2), center_text, fill="black", font=font)
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

def get_random_quote():
    quotes = ["Bu gün əla görünürsən! 🧡", "Enerjini bərpa etmək vaxtıdır! ⚡", "Sən ən yaxşısına layiqsən! ✨", "Kofe ilə gün daha gözəldir! ☀️", "Gülüşün dünyanı dəyişə bilər! 😊"]
    return random.choice(quotes)

# --- BIRTHDAY CHECKER ---
def check_and_send_birthday_emails():
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        with conn.session as s:
            res = s.execute(text("SELECT value FROM settings WHERE key = 'last_birthday_check'")).fetchone()
            if res and res[0] == today_str: return 
            today_mm_dd = datetime.date.today().strftime("%m-%d")
            birthdays = s.execute(text("SELECT card_id, email FROM customers WHERE RIGHT(birth_date, 5) = :td AND email IS NOT NULL AND is_active = TRUE"), {"td": today_mm_dd}).fetchall()
            for user in birthdays:
                if send_email(user[1], f"🎉 {SHOP_NAME}: Ad Günün Mübarək!", "Sənə 1 pulsuz kofe hədiyyə!"):
                    s.execute(text("INSERT INTO notifications (card_id, message) VALUES (:cid, '🎂 Ad Günün Mübarək!')"), {"cid": user[0]})
                    s.execute(text("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:cid, 'disc_100_coffee', NOW() + INTERVAL '1 day')"), {"cid": user[0]})
            s.execute(text("INSERT INTO settings (key, value) VALUES ('last_birthday_check', :val) ON CONFLICT (key) DO UPDATE SET value = :val"), {"val": today_str})
            s.commit()
    except: pass

if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = True
    threading.Thread(target=check_and_send_birthday_emails, daemon=True).start()

# --- SESSION ---
if 'cart' not in st.session_state: st.session_state.cart = []
if 'current_customer' not in st.session_state: st.session_state.current_customer = None
if 'pos_category' not in st.session_state: st.session_state.pos_category = "Qəhvə"
if 'active_coupon' not in st.session_state: st.session_state.active_coupon = None

# ===========================
# === 1. MÜŞTƏRİ EKRANI ===
# ===========================
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]
    token = query_params.get("t")
    render_header()
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        # TOKEN CHECK (FIXED)
        if user['secret_token'] and token and user['secret_token'] != token:
            st.error("⛔ İcazəsiz Giriş! Zəhmət olmasa QR kodu yenidən skan edin.")
            st.stop()

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"📩 {row['message']}"); run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        if not user['is_active']:
            st.warning(f"🎉 {SHOP_NAME}-a Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email"); dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                
                with st.expander("📜 Qaydalar və İstifadəçi Razılaşması"):
                    st.markdown("""
                    <div style="font-size:14px; color:#333;">
                        <b>1. Şəxsi Məlumatlar:</b> E-mail və Doğum tarixi yalnız kampaniyalar üçün istifadə olunur.<br>
                        <b>2. Sadiqlik Proqramı:</b> 9 ulduz toplayana 10-cu kofe HƏDİYYƏDİR.<br>
                        <b>3. VIP Termos:</b> Öz termosu ilə gələnlərə endirim edilir.<br>
                        <b>4. Ad Günü:</b> Hədiyyə üçün şəxsiyyət vəsiqəsi tələb oluna bilər.<br>
                        <b>5. Endirimlər:</b> Eyni anda birdən çox endirim varsa, SİZİN ÜÇÜN ƏN SƏRFƏLİ OLAN tətbiq edilir.<br>
                        <b>6. İmtina və Silinmə:</b> İstədiyiniz vaxt məlumatlarınızın bazadan silinməsini personaldan xahiş edə bilərsiniz.<br>
                        <b>7. Dəyişikliklər:</b> {SHOP_NAME} qaydaları dəyişmək hüququnu saxlayır.
                    </div>
                    """.replace("{SHOP_NAME}", SHOP_NAME), unsafe_allow_html=True)
                
                agree = st.checkbox("Qaydalarla tanış oldum və razıyam")
                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    if agree and em:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons(); st.rerun()
            st.stop()

        st.markdown(f"<div class='inner-motivation'>{get_random_quote()}</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="digital-card"><h3 style="margin-top:0">{SHOP_NAME} BONUS</h3><h1 style="color:#2E7D32; font-size: 48px; margin:0;">{user['stars']} / 10</h1><p style="color:#777">Balansınız</p></div>""", unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            if i == 9: 
                icon = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png" 
                if user['stars'] >= 9: cls = "gift-box-anim"; style = "opacity: 1;"
                else: cls = "coffee-icon"; style = "opacity: 0.3; filter: grayscale(100%);"
            else: 
                icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
                cls = "coffee-icon"
                if i < user['stars']: style = "opacity: 1;"
                else: style = "opacity: 0.2; filter: grayscale(100%);"
            html += f'<img src="{icon}" class="{cls}" style="{style}">'
        html += '</div>'; st.markdown(html, unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.markdown("<div class='progress-text'>🎉 TƏBRİKLƏR! Növbəti Kofe Bizdən!</div>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='progress-text'>🎁 Hədiyyəyə {rem} kofe qaldı!</div>", unsafe_allow_html=True)
        
        # ACTIVE COUPONS
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": card_id})
        for _, cp in my_coupons.iterrows():
            name = "🎁 Xüsusi Kupon"
            if cp['coupon_type'] == 'disc_20': name = "🏷️ 20% Endirim!"
            elif cp['coupon_type'] == 'disc_30': name = "🏷️ 30% Endirim!"
            elif cp['coupon_type'] == 'disc_50': name = "🏷️ 50% Endirim!"
            elif cp['coupon_type'] == 'disc_100_coffee': name = "🎂 Ad Günü: 1 Pulsuz Kofe!"
            st.markdown(f"""<div style="background:linear-gradient(135deg, #FFD700 0%, #FF8C00 100%); border-radius:15px; padding:15px; margin:15px 0; color:white; text-align:center; box-shadow:0 5px 15px rgba(255, 215, 0, 0.4); animation: pulse 2s infinite;"><div style="font-size:22px; font-weight:bold; font-family:'Oswald';">TƏBRİKLƏR!</div><div style="font-size:18px;">{name}</div></div>""", unsafe_allow_html=True)

        st.markdown("<div class='feedback-box'>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align:center; margin:0; color:#2E7D32'>💌 Rəy Bildir</h4>", unsafe_allow_html=True)
        with st.form("feed"):
            s = st.feedback("stars"); m = st.text_input("Fikriniz", placeholder="Necə idi?")
            if st.form_submit_button("Göndər"):
                if s is not None:
                    run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                    st.success("Təşəkkürlər!")
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}" if user['secret_token'] else f"{APP_URL}/?id={card_id}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS & ADMIN ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if st.session_state.logged_in:
        with st.sidebar:
            st.markdown(f"### 👤 {st.session_state.user}")
            if st.button("🔄 Məlumatları Yenilə"):
                st.rerun()
            st.divider()
            if st.button("🔴 Çıxış Et"):
                st.session_state.logged_in = False
                st.rerun()

    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1]); 
        with c2: 
            if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
            else: st.markdown(f"<h2 style='text-align:center'>{SHOP_NAME}</h2>", unsafe_allow_html=True)
            with st.form("login"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("GİRİŞ", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(:u)", {"u":u})
                    if not udf.empty and verify_password(p, udf.iloc[0]['password']):
                        st.session_state.logged_in = True; st.session_state.role = udf.iloc[0]['role']; st.session_state.user = u
                        st.rerun()
                    else: st.error("Səhvdir!")
    else:
        role = st.session_state.role
        
        def render_pos():
            layout_col1, layout_col2 = st.columns([1.2, 3]) 
            with layout_col1:
                st.markdown("<h3 style='text-align:center; background:#4CAF50; color:white; padding:10px; border-radius:5px;'>SATIŞ</h3>", unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1])
                scan_val = c1.text_input("QR", label_visibility="collapsed", placeholder="Müştəri Kartı...")
                if c2.button("🔍"):
                    if scan_val:
                        c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                        if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                        else: st.error("Yoxdur")
                curr = st.session_state.current_customer
                if curr:
                    st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                    cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": curr['card_id']})
                    if not cps.empty:
                        cp_map = {"disc_20": "20% Endirim", "disc_30": "30% Endirim", "disc_50": "50% Endirim", "disc_100_coffee": "Ad Günü (Pulsuz Kofe)"}
                        cp_ops = {f"{cp_map.get(r['coupon_type'], r['coupon_type'])}": r['id'] for _, r in cps.iterrows()}
                        sel_cp = st.selectbox("Kupon:", ["Yox"] + list(cp_ops.keys()))
                        if sel_cp != "Yox": 
                            raw_type = next((k for k, v in cp_map.items() if v == sel_cp), sel_cp)
                            st.session_state.active_coupon = {"id": cp_ops[sel_cp], "type": raw_type}
                        else: st.session_state.active_coupon = None
                    if st.button("Ləğv Et", key="pcl"): st.session_state.current_customer = None; st.rerun()
                st.markdown("<div style='background:white; height:60vh; overflow-y:scroll; border:1px solid #ddd; padding:10px;'>", unsafe_allow_html=True)
                total = 0; coffs = 0
                if st.session_state.cart:
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([4, 2, 1])
                        c1.write(f"**{item['item_name']}**"); c2.write(f"{item['price']}")
                        if c3.button("x", key=f"d_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price'])
                        if item.get('is_coffee', False): coffs += 1
                else: st.info("Səbət boşdur")
                st.markdown("</div>", unsafe_allow_html=True)
                final_discount = 0; candidate_discounts = [] 
                if curr:
                    coffee_total = sum([float(x['price']) for x in st.session_state.cart if x.get('is_coffee')])
                    if curr['type'] == 'thermos' and coffee_total > 0: candidate_discounts.append(coffee_total * 0.2)
                    if curr['stars'] >= 9:
                        c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                        if c_items: candidate_discounts.append(float(min(c_items, key=lambda x: float(x['price']))['price']))
                    if st.session_state.active_coupon:
                        cp = st.session_state.active_coupon['type']
                        if cp == 'disc_20': candidate_discounts.append(total * 0.2)
                        elif cp == 'disc_30': candidate_discounts.append(total * 0.3)
                        elif cp == 'disc_50': candidate_discounts.append(total * 0.5)
                        elif cp == 'disc_100_coffee': 
                             c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                             if c_items: candidate_discounts.append(float(min(c_items, key=lambda x: float(x['price']))['price']))
                if candidate_discounts: final_discount = max(candidate_discounts)
                final_price = max(0, total - final_discount)
                st.markdown(f"<div style='font-size:24px; font-weight:bold; text-align:right; color:#D32F2F; margin-top:10px;'>YEKUN: {final_price:.2f} ₼</div>", unsafe_allow_html=True)
                if final_discount > 0: st.caption(f"Endirim: -{final_discount:.2f}")
                pay_m = st.radio("Metod:", ["Nəğd", "Kart"], horizontal=True, label_visibility="collapsed")
                if st.button("✅ ÖDƏNİŞ ET", type="primary", use_container_width=True):
                    if not st.session_state.cart: return
                    p_code = "Cash" if pay_m == "Nəğd" else "Card"
                    items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                    try:
                        with conn.session as s:
                            if curr:
                                ns = int(curr['stars'])
                                if coffs > 0:
                                    if ns >= 9 and any(x.get('is_coffee') for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                if st.session_state.active_coupon: s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                            s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final_price, "p":p_code})
                            s.commit()
                        st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; st.session_state.active_coupon = None; time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Xəta: {e}")
            with layout_col2:
                c1, c2, c3 = st.columns(3)
                if c1.button("☕ Qəhvə", key="cat_coff", type="secondary", use_container_width=True): st.session_state.pos_category = "Qəhvə"; st.rerun()
                if c2.button("🥤 İçkilər", key="cat_drk", type="secondary", use_container_width=True): st.session_state.pos_category = "İçkilər"; st.rerun()
                if c3.button("🍰 Desert", key="cat_dst", type="secondary", use_container_width=True): st.session_state.pos_category = "Desert"; st.rerun()
                
                @st.dialog("Ölçü Seçimi")
                def show_variants(base_name, items):
                    st.write(f"**{base_name}**")
                    cols = st.columns(len(items))
                    for i, item in enumerate(items):
                        label = item['item_name'].split()[-1]; 
                        with cols[i]:
                            if st.button(f"{label}\n{item['price']}₼", key=f"v_{item['id']}"): st.session_state.cart.append(item); st.rerun()
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": st.session_state.pos_category})
                groups = {}
                for idx, row in enumerate(menu_df.to_dict('records')):
                    name = row['item_name']; parts = name.split()
                    if parts[-1] in ['S', 'M', 'L', 'XL']: base = " ".join(parts[:-1]); groups.setdefault(base, []).append(row)
                    else: groups[name] = [row]
                cols = st.columns(4)
                for i, (base_name, items) in enumerate(groups.items()):
                    with cols[i % 4]:
                        if len(items) > 1:
                            if st.button(f"{base_name}\n(Seçim)", key=f"grp_{i}"): show_variants(base_name, items)
                        else:
                            if st.button(f"{items[0]['item_name']}\n{items[0]['price']}₼", key=f"itm_{items[0]['id']}"): st.session_state.cart.append(items[0]); st.rerun()

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Satış")
                today = datetime.date.today(); sel_date = st.date_input("Ay", today); sel_month = sel_date.strftime("%Y-%m")
                sales = run_query("SELECT * FROM sales WHERE TO_CHAR(created_at, 'YYYY-MM') = :m ORDER BY created_at DESC", {"m": sel_month})
                if not sales.empty:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Cəm", f"{sales['total'].sum():.2f}")
                    m2.metric("Nağd", f"{sales[sales['payment_method']=='Cash']['total'].sum():.2f}")
                    m3.metric("Kart", f"{sales[sales['payment_method']=='Card']['total'].sum():.2f}")
                    st.dataframe(sales)
            
            # --- CRM TABLE VIEW (VER 12) ---
            with tabs[2]:
                st.markdown("### 📧 CRM - Müştəri Bazası")
                with st.expander("🗑️ Müştəri Sil (Toplu)"):
                    all_cust = run_query("SELECT card_id, email FROM customers")
                    if not all_cust.empty:
                        to_del = st.multiselect("Silinəcək Müştərilər:", all_cust['card_id'].tolist())
                        if st.button("Seçilənləri Sil"):
                            for d_id in to_del: run_action("DELETE FROM customers WHERE card_id=:id", {"id":d_id})
                            st.success("Silindi!"); st.rerun()
                st.divider()
                
                # TABLE VIEW
                cust_db = run_query("SELECT card_id, email, stars, type, last_visit FROM customers ORDER BY last_visit DESC")
                st.dataframe(cust_db, use_container_width=True)
                
                st.markdown("#### 🎁 Kampaniya Göndər (Seçilənlərə)")
                m_df = run_query("SELECT card_id, email FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    m_df['50% Endirim'] = False
                    m_df['Ad Günü'] = False
                    m_df['Peceniya'] = False
                    edited = st.data_editor(m_df, hide_index=True, use_container_width=True)
                    
                    if st.button("🚀 Seçilənləri Göndər"):
                        cnt = 0
                        for i, r in edited.iterrows():
                            if r['50% Endirim']:
                                if send_email(r['email'], "50% Endirim!", "Sizə özəl 50% endirim!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, '50% Endirim!')", {"id":r['card_id']})
                                    run_action("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:id, 'disc_50', NOW() + INTERVAL '7 days')", {"id":r['card_id']})
                                    cnt += 1
                            if r['Ad Günü']:
                                if send_email(r['email'], "Ad Gününüz Mübarək!", "Bir kofe bizdən hədiyyə!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, 'Ad Günü Hədiyyəsi!')", {"id":r['card_id']})
                                    run_action("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:id, 'disc_100_coffee', NOW() + INTERVAL '1 day')", {"id":r['card_id']})
                                    cnt += 1
                            if r['Peceniya']:
                                if send_email(r['email'], "Şirin Hədiyyə!", "Kofe alana Peceniya bizdən!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, 'Pulsuz Peceniya!')", {"id":r['card_id']})
                                    # Use disc_20 as proxy or define new type
                                    run_action("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:id, 'disc_20', NOW() + INTERVAL '7 days')", {"id":r['card_id']})
                                    cnt += 1
                        st.success(f"{cnt} əməliyyat icra olundu!")
                else: st.info("Müştəri yoxdur")

            with tabs[3]:
                with st.form("add"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                st.dataframe(run_query("SELECT * FROM menu"))
            with tabs[4]:
                st.markdown("### ⚙️ Ayarlar")
                with st.expander("📍 Əlaqə"):
                    na = st.text_input("Ünvan", SHOP_ADDRESS); ni = st.text_input("Instagram", INSTAGRAM_LINK)
                    if st.button("Saxla"): set_config("shop_address", na); set_config("instagram_link", ni); st.success("OK")
                with st.expander("👥 İşçilər"):
                    udf = run_query("SELECT username, role FROM users"); st.dataframe(udf)
                    nu = st.text_input("User"); np = st.text_input("Pass", type="password"); nr = st.selectbox("Role", ["staff","admin"])
                    if st.button("Yarat", key="crt_usr"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":nu, "p":hash_password(np), "r":nr}); st.success("OK")
            with tabs[5]:
                if st.button("📥 BÜTÜN BAZANI YÜKLƏ (BACKUP)", type="primary"):
                    try:
                        out = BytesIO()
                        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                            clean_df_for_excel(run_query("SELECT * FROM customers")).to_excel(writer, sheet_name='Customers')
                            clean_df_for_excel(run_query("SELECT * FROM sales")).to_excel(writer, sheet_name='Sales')
                        st.download_button("⬇️ Endir", out.getvalue(), f"Backup.xlsx")
                    except Exception as e: st.error(e)
            with tabs[6]:
                cnt = st.number_input("Say", 1, 50); is_th = st.checkbox("Termos?")
                if st.button("Yarat"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    for i in ids: 
                        token = secrets.token_hex(8)
                        run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":"thermos" if is_th else "standard", "st":token})
                    if cnt == 1:
                        tkn = run_query("SELECT secret_token FROM customers WHERE card_id=:id", {"id":ids[0]}).iloc[0]['secret_token']
                        d = generate_custom_qr(f"{APP_URL}/?id={ids[0]}&t={tkn}", ids[0])
                        st.image(BytesIO(d), width=200); st.download_button("⬇️", d, f"{ids[0]}.png", "image/png")
                    else: st.success("Hazır!")

        elif role == 'staff': render_pos()
