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

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana POS", page_icon="☕", layout="wide", initial_sidebar_state="expanded")

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
        background-color: #D32F2F !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(211, 47, 47, 0.4) !important;
    }

    /* --- MÜŞTƏRİ EKRANI --- */
    .digital-card {
        background: white; border-radius: 20px; padding: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #eee;
        text-align: center; margin-bottom: 20px;
    }
    
    .thermos-vip {
        background: linear-gradient(135deg, #2E7D32, #66BB6A);
        color: white;
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 15px;
        box-shadow: 0 5px 15px rgba(46, 125, 50, 0.4);
        border: 2px dashed #A5D6A7;
    }
    .thermos-title { font-size: 24px; font-weight: bold; font-family: 'Oswald'; }
    .thermos-sub { font-size: 14px; font-style: italic; opacity: 0.9; }
    
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
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        
        # MIGRATIONS
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_feedback_star INTEGER DEFAULT -1;"))
        except: pass
        try: s.execute(text("ALTER TABLE customer_coupons ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;")) 
        except: pass
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender TEXT;"))
        except: pass
        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS cashier TEXT;"))
        except: pass
        
        # ***FIX: QR KOD YENİLƏNMƏSİ LƏĞV EDİLDİ (SABİT TOKEN)***
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

# --- CRM MOTIVATION LIST ---
CRM_QUOTES = [
    "Səni görmək çox xoşdur! ☕", "Həftəsonun əla keçsin! 🎉", "Yeni həftəyə enerji ilə başla! 🚀", "Günün aydın olsun! ☀️",
    "Sənin üçün darıxdıq! ❤️", "Bu gün özünə bir yaxşılıq et! 🍰", "Kofe ətri səni çağırır! ☕", "Dostlarınla gözəl vaxt keçir! 👯",
    "Emalatxana səni sevir! 🧡", "Hava soyuqdur, kofe istidir! ❄️", "Gülüşünlə ətrafı işıqlandır! ✨", "Uğurlu bir gün olsun! 💼",
    "Sən bizim üçün dəyərlisən! 💎", "Kiçik xoşbəxtliklər böyükdür! 🎈", "Özünə vaxt ayır! ⏳", "Dadlı bir fasilə ver! 🥐",
    "Hər qurtumda ləzzət! 😋", "Bu gün möcüzəvidir! 🌟", "Sən özəl birisən! 🎁", "Həyat gözəldir, dadını çıxar! 🌈",
    "Bizimlə olduğun üçün təşəkkürlər! 🙏", "Kofe sənin haqqındır! ☕", "Ulduzun parlasın! ⭐", "Xoşbəxtlik bir fincan uzaqlıqdadır! 💖",
    "Enerjini bizimlə bərpa et! 🔋", "Həmişə belə gülümsə! 😊", "Sənə uğurlar arzulayırıq! 👍", "Kofe bəhanə, söhbət şahanə! 🗣️"
]

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

# --- SESSION & REFRESH LOGIC ---
def check_session_token():
    query_params = st.query_params
    token = query_params.get("token")
    if token:
        try:
            res = run_query("SELECT username, role FROM active_sessions WHERE token=:t", {"t":token})
            if not res.empty:
                st.session_state.logged_in = True
                st.session_state.user = res.iloc[0]['username']
                st.session_state.role = res.iloc[0]['role']
        except: pass

check_session_token()

if 'cart' not in st.session_state: st.session_state.cart = []
if 'current_customer' not in st.session_state: st.session_state.current_customer = None
if 'pos_category' not in st.session_state: st.session_state.pos_category = "Qəhvə"
if 'active_coupon' not in st.session_state: st.session_state.active_coupon = None
if 'scan_input' not in st.session_state: st.session_state.scan_input = ""

# ===========================
# === 1. MÜŞTƏRİ EKRANI ===
# ===========================
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]
    token = query_params.get("t")
    render_header()
    
    try: df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    except: st.stop()

    if not df.empty:
        user = df.iloc[0]
        # TOKEN CHECK (CRITICAL: ALLOWING OLD TOKENS TO WORK)
        if user['secret_token'] and token and user['secret_token'] != token:
            st.warning("⚠️ QR kod köhnəlib, amma girişə icazə verildi. Xahiş olunur kassadan yeni QR istəyin.")
            # st.stop() # REMOVED TO PREVENT LOCKOUT

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"📩 {row['message']}"); run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        if not user['is_active']:
            st.warning(f"🎉 {SHOP_NAME}-a Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email"); dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                gender = st.radio("Cinsiyyət:", ["Kişi", "Qadın", "Qeyd etmirəm"], horizontal=True)
                
                with st.expander("📜 Qaydalar və İstifadəçi Razılaşması"):
                    st.markdown("""
                    <div style="font-size:14px; color:#333;">
                        <b>1. Sadiqlik Proqramı:</b> Bu rəqəmsal kartla hər kofe alışında ulduz toplayır və hədiyyələr qazanırsınız.<br>
                        <b>2. Bonus Sistemi:</b> Hər <b>tam qiymətli</b> (endurimsiz) kofe alışı = 1 Ulduz. Endirimli və ya hədiyyə kofelərdə ulduz hesablanmır.<br>
                        <b>3. Hədiyyə Kofe:</b> 9 ulduz toplandıqda, növbəti kofe bizdən HƏDİYYƏDİR! ☕<br>
                        <b>4. EKO-TERM Klubu:</b> Emalatxana termosu alanlara ilk kofe hədiyyədir. Növbəti gəlişlərdə öz termosu ilə gələnlərə daimi ekoloji endirim tətbiq olunur.<br>
                        <b>5. Ağıllı Endirim:</b> Eyni anda bir neçə endirim şansı varsa, sistem avtomatik olaraq <b>Sizə ən sərfəli olanını</b> seçir.<br>
                        <b>6. Məxfilik:</b> Məlumatlarınız yalnız sizə özəl kampaniyalar üçün istifadə olunur.
                    </div>
                    """.replace("{SHOP_NAME}", SHOP_NAME), unsafe_allow_html=True)
                agree = st.checkbox("Qaydalarla tanış oldum və razıyam")
                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    if agree and em:
                        g_code = "M" if gender=="Kişi" else "F" if gender=="Qadın" else "U"
                        run_action("UPDATE customers SET email=:e, birth_date=:b, gender=:g, is_active=TRUE WHERE card_id=:i", 
                                   {"e":em, "b":dob.strftime("%Y-%m-%d"), "g":g_code, "i":card_id})
                        st.balloons(); st.rerun()
            st.stop()

        st.markdown(f"<div class='inner-motivation'>{get_random_quote()}</div>", unsafe_allow_html=True)
        if user['type'] == 'thermos':
            st.markdown("""<div class="thermos-vip"><div class="thermos-title">♻️ EKO-TERM KLUBU (VIP) ♻️</div><div class="thermos-sub">Təbiəti Qoruduğun Üçün Təşəkkürlər!</div></div>""", unsafe_allow_html=True)

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
        
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": card_id})
        for _, cp in my_coupons.iterrows():
            name = "🎁 Xüsusi Kupon"
            if cp['coupon_type'] == 'disc_20': name = "🏷️ 20% Endirim!"
            elif cp['coupon_type'] == 'disc_30': name = "🏷️ 30% Endirim!"
            elif cp['coupon_type'] == 'disc_50': name = "🏷️ 50% Endirim!"
            elif cp['coupon_type'] == 'disc_100_coffee': name = "🎂 Ad Günü: 1 Pulsuz Kofe!"
            elif cp['coupon_type'] == 'thermos_welcome': name = "♻️ Xoşgəldin: İLK KOFE BİZDƏN!"
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
        qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
        
        if st.button("🔴 Hesabdan Çıx", type="primary"):
            st.query_params.clear()
            st.rerun()

    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS & ADMIN ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if st.session_state.logged_in:
        c_head1, c_head2 = st.columns([4, 1])
        with c_head1:
            st.markdown(f"### 👤 {st.session_state.user} | {st.session_state.role.upper()}")
        with c_head2:
            if st.button("🚪 ÇIXIŞ", type="primary", key="top_logout"):
                token = st.query_params.get("token")
                if token: run_action("DELETE FROM active_sessions WHERE token=:t", {"t":token})
                st.session_state.logged_in = False
                st.query_params.clear()
                st.rerun()
        st.divider()
        
        with st.sidebar:
            st.button("🔄 Yenilə", on_click=st.rerun)

    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1]); 
        with c2: 
            if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
            else: st.markdown(f"<h2 style='text-align:center'>{SHOP_NAME}</h2>", unsafe_allow_html=True)
            
            tabs = st.tabs(["STAFF GİRİŞİ (PIN)", "ADMIN GİRİŞİ"])
            
            with tabs[0]:
                with st.form("staff_login"):
                    pin = st.text_input("PIN Kodu Daxil Edin", type="password", placeholder="****")
                    if st.form_submit_button("GİRİŞ", use_container_width=True):
                        udf = run_query("SELECT * FROM users WHERE role='staff'") 
                        found = False
                        for _, u_row in udf.iterrows():
                            if verify_password(pin, u_row['password']):
                                st.session_state.logged_in = True; st.session_state.role = 'staff'; st.session_state.user = u_row['username']
                                s_token = secrets.token_urlsafe(16)
                                run_action("INSERT INTO active_sessions (token, username, role) VALUES (:t, :u, :r)", {"t":s_token, "u":u_row['username'], "r":'staff'})
                                st.query_params["token"] = s_token
                                st.rerun()
                                found = True; break
                        if not found: st.error("Yanlış PIN!")

            with tabs[1]:
                with st.form("admin_login"):
                    u = st.text_input("Username"); p = st.text_input("Password", type="password")
                    if st.form_submit_button("ADMIN GİRİŞ", use_container_width=True):
                        udf = run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(:u) AND role='admin'", {"u":u})
                        if not udf.empty and verify_password(p, udf.iloc[0]['password']):
                            st.session_state.logged_in = True; st.session_state.role = 'admin'; st.session_state.user = u
                            s_token = secrets.token_urlsafe(16)
                            run_action("INSERT INTO active_sessions (token, username, role) VALUES (:t, :u, :r)", {"t":s_token, "u":u, "r":'admin'})
                            st.query_params["token"] = s_token
                            st.rerun()
                        else: st.error("Səhvdir!")
    else:
        role = st.session_state.role
        
        def render_pos():
            layout_col1, layout_col2 = st.columns([1.2, 3]) 
            with layout_col1:
                st.markdown("<h3 style='text-align:center; background:#4CAF50; color:white; padding:10px; border-radius:5px;'>SATIŞ</h3>", unsafe_allow_html=True)
                with st.form("scan_form", clear_on_submit=True):
                    val = st.text_input("QR Skan (Enter)", key="pos_qr", placeholder="Skan et...")
                    if st.form_submit_button("Axtar", use_container_width=True) and val:
                        clean_id = val.strip()
                        if "id=" in val:
                            try: clean_id = val.split("id=")[1].split("&")[0]
                            except: pass
                        try:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":clean_id})
                            if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict()
                            else: st.error("Tapılmadı")
                        except: st.error("Xəta")

                curr = st.session_state.current_customer
                if curr:
                    st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                    cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": curr['card_id']})
                    if not cps.empty:
                        cp_map = {"disc_20": "20% Endirim", "disc_30": "30% Endirim", "disc_50": "50% Endirim", "disc_100_coffee": "Ad Günü (Pulsuz Kofe)", "thermos_welcome": "♻️ Termos Xoşgəldin (Pulsuz)"}
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
                        elif cp == 'thermos_welcome':
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
                                used_welcome = False
                                if st.session_state.active_coupon:
                                    cp_type = st.session_state.active_coupon['type']
                                    if 'thermos_welcome' in cp_type or 'Xoşgəldin' in cp_type: 
                                        used_welcome = True

                                if coffs > 0:
                                    if st.session_state.active_coupon: pass # Coupon used -> No star
                                    elif ns >= 9 and any(x.get('is_coffee') for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                
                                s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                if st.session_state.active_coupon: 
                                    s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                            
                            s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at) VALUES (:i, :t, :p, :c, NOW())"), 
                                      {"i":items_str, "t":final_price, "p":p_code, "c":st.session_state.user})
                            s.commit()
                        st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; st.session_state.active_coupon = None; time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Xəta: {e}")
            
            with layout_col2:
                with st.expander("📊 Mənim Satışlarım (Analitika)"):
                    sf_mode = st.radio("Rejim:", ["Günlük", "Aylıq", "Aralıq"], horizontal=True, key="s_mode")
                    sql = "SELECT * FROM sales WHERE cashier = :u"
                    p = {'u': st.session_state.user}
                    
                    if sf_mode == "Günlük":
                        d = st.date_input("Gün", datetime.date.today(), key="s_d")
                        sql += " AND DATE(created_at AT TIME ZONE 'Asia/Baku') = :d"
                        p['d'] = d
                    elif sf_mode == "Aylıq":
                        d = st.date_input("Ay", datetime.date.today(), key="s_m")
                        sql += " AND TO_CHAR(created_at AT TIME ZONE 'Asia/Baku', 'YYYY-MM') = :m"
                        p['m'] = d.strftime("%Y-%m")
                    else:
                        d1 = st.date_input("Başlanğıc", datetime.date.today(), key="s_d1")
                        d2 = st.date_input("Bitmə", datetime.date.today(), key="s_d2")
                        sql += " AND DATE(created_at AT TIME ZONE 'Asia/Baku') BETWEEN :d1 AND :d2"
                        p['d1'] = d1; p['d2'] = d2
                    
                    sql += " ORDER BY created_at DESC"
                    my_sales = run_query(sql, p)
                    
                    if not my_sales.empty:
                        my_sales['created_at'] = pd.to_datetime(my_sales['created_at']) + pd.Timedelta(hours=4)
                        tot = my_sales['total'].sum()
                        cash = my_sales[my_sales['payment_method']=='Cash']['total'].sum()
                        card = my_sales[my_sales['payment_method']=='Card']['total'].sum()
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Cəm", f"{tot:.2f}")
                        c2.metric("Nağd", f"{cash:.2f}")
                        c3.metric("Kart", f"{card:.2f}")
                        
                        disp_df = my_sales[['id', 'created_at', 'items', 'total', 'payment_method']]
                        disp_df.columns = ['Çek №', 'Tarix', 'Məhsullar', 'Məbləğ', 'Ödəniş']
                        st.dataframe(disp_df, hide_index=True)
                    else: st.info("Seçilən tarixdə satış yoxdur.")

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
                
                def fmt_name(row): return f"☕ {row['item_name']}" if row['is_coffee'] else row['item_name']

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
                            if st.button(f"{fmt_name(items[0])}\n{items[0]['price']}₼", key=f"itm_{items[0]['id']}"): st.session_state.cart.append(items[0]); st.rerun()

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Satış Analitikası (Bakı Vaxtı)")
                f_mode = st.radio("Rejim:", ["Günlük", "Aylıq", "Aralıq"], horizontal=True)
                sql = "SELECT * FROM sales"
                p = {}
                if f_mode == "Günlük":
                    d = st.date_input("Gün", datetime.date.today())
                    sql += " WHERE DATE(created_at AT TIME ZONE 'Asia/Baku') = :d"
                    p['d'] = d
                elif f_mode == "Aylıq":
                    d = st.date_input("Ay (Hər hansı gününü seç)", datetime.date.today())
                    sql += " WHERE TO_CHAR(created_at AT TIME ZONE 'Asia/Baku', 'YYYY-MM') = :m"
                    p['m'] = d.strftime("%Y-%m")
                else:
                    d1 = st.date_input("Başlanğıc", datetime.date.today())
                    d2 = st.date_input("Bitmə", datetime.date.today())
                    sql += " WHERE DATE(created_at AT TIME ZONE 'Asia/Baku') BETWEEN :d1 AND :d2"
                    p['d1'] = d1; p['d2'] = d2
                
                sql += " ORDER BY created_at DESC"
                sales = run_query(sql, p)
                
                if not sales.empty:
                    sales['created_at'] = pd.to_datetime(sales['created_at']) + pd.Timedelta(hours=4)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Cəm", f"{sales['total'].sum():.2f}")
                    m2.metric("Nağd", f"{sales[sales['payment_method']=='Cash']['total'].sum():.2f}")
                    m3.metric("Kart", f"{sales[sales['payment_method']=='Card']['total'].sum():.2f}")
                    
                    disp_df = sales[['id', 'created_at', 'items', 'total', 'payment_method', 'cashier']]
                    disp_df.columns = ['Çek №', 'Tarix', 'Məhsullar', 'Məbləğ', 'Ödəniş', 'Kassir']
                    st.dataframe(disp_df, hide_index=True)
                    
                    st.divider()
                    st.markdown("#### 🗑️ Satış Ləğvi")
                    with st.form("del_sale"):
                        c1, c2 = st.columns(2)
                        sid = c1.number_input("Satış ID (Çek №)", min_value=1, step=1)
                        apass = c2.text_input("Admin Şifrəsi", type="password")
                        if st.form_submit_button("Sil"):
                            adm = run_query("SELECT password FROM users WHERE LOWER(username)=LOWER(:u) AND role='admin'", {"u":st.session_state.user})
                            if not adm.empty and verify_password(apass, adm.iloc[0]['password']):
                                run_action("DELETE FROM sales WHERE id=:id", {"id":sid})
                                st.success(f"Satış #{sid} silindi!")
                                time.sleep(1); st.rerun()
                            else: st.error("Şifrə yanlışdır!")
                else: st.info("Satış yoxdur")
            
            with tabs[2]:
                st.markdown("### 📧 CRM")
                with st.expander("🗑️ Müştəri Sil (Toplu)"):
                    all_cust = run_query("SELECT card_id, email FROM customers")
                    if not all_cust.empty:
                        to_del = st.multiselect("Silinəcək Müştərilər:", all_cust['card_id'].tolist())
                        if st.button("Seçilənləri Sil"):
                            for d_id in to_del: run_action("DELETE FROM customers WHERE card_id=:id", {"id":d_id})
                            st.success("Silindi!"); st.rerun()
                st.divider()
                
                f_gen = st.radio("Filtr:", ["Hamısı", "Kişi", "Qadın"], horizontal=True)
                sql_q = "SELECT card_id, email, stars, type, gender, last_visit FROM customers WHERE email IS NOT NULL"
                params = {}
                if f_gen == "Kişi": sql_q += " AND gender='M'"
                elif f_gen == "Qadın": sql_q += " AND gender='F'"
                
                m_df = run_query(sql_q, params)
                if not m_df.empty:
                    if 'select_all' not in st.session_state: st.session_state.select_all = False
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("✅ Hamısını Seç"): st.session_state.select_all = True
                    if c_btn2.button("❌ Sıfırla"): st.session_state.select_all = False
                    
                    m_df.insert(0, "Seç", st.session_state.select_all)
                    edited = st.data_editor(m_df, hide_index=True, use_container_width=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)})
                    
                    st.divider()
                    st.markdown("#### 📢 Kampaniya Göndər")
                    coupon_type = st.selectbox("Kupon Seç:", ["Yoxdur", "20% Endirim", "30% Endirim", "50% Endirim", "Ad Günü (1 Pulsuz Kofe)"])
                    sel_quote = st.selectbox("Motivasiya Seç:", ["(Özün Yaz)"] + CRM_QUOTES)
                    custom_msg_val = sel_quote if sel_quote != "(Özün Yaz)" else ""
                    
                    with st.form("custom_crm"):
                        txt = st.text_area("Mesaj Mətni", value=custom_msg_val)
                        if st.form_submit_button("Seçilənlərə Göndər"):
                            selected_rows = edited[edited["Seç"] == True]
                            if not selected_rows.empty:
                                cnt = 0
                                db_code = None
                                if "20%" in coupon_type: db_code = "disc_20"
                                elif "30%" in coupon_type: db_code = "disc_30"
                                elif "50%" in coupon_type: db_code = "disc_50"
                                elif "Ad Günü" in coupon_type: db_code = "disc_100_coffee"

                                for idx, row in selected_rows.iterrows():
                                    email = row['email']
                                    cid = row['card_id']
                                    final_msg = txt if txt else custom_msg_val
                                    send_email(email, "Emalatxana Coffee: Xüsusi Təklif!", final_msg)
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :m)", {"id":cid, "m":final_msg})
                                    if db_code:
                                        run_action("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:id, :ct, NOW() + INTERVAL '7 days')", {"id":cid, "ct":db_code})
                                    cnt+=1
                                st.success(f"{cnt} müştəriyə göndərildi!")
                            else: st.warning("Heç kim seçilməyib!")
                else: st.info("Müştəri yoxdur")

            with tabs[3]:
                with st.form("add"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                
                m_list = run_query("SELECT * FROM menu ORDER BY category")
                m_list['is_coffee'] = m_list['is_coffee'].apply(lambda x: "☕" if x else "")
                st.dataframe(m_list)

            with tabs[4]:
                st.markdown("### ⚙️ Ayarlar")
                with st.expander("🔐 Şifrə Dəyişmə (Admin/Staff)"):
                    all_users = run_query("SELECT username FROM users")
                    sel_user = st.selectbox("İstifadəçi Seç", all_users['username'].tolist())
                    new_pass = st.text_input("Yeni Şifrə / PIN", type="password")
                    if st.button("Şifrəni Yenilə"):
                        run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_pass), "u":sel_user})
                        st.success("Yeniləndi!")

                with st.expander("👥 Yeni İşçi Yarat"):
                    nu = st.text_input("Ad (Username)"); np = st.text_input("PIN / Şifrə", type="password"); nr = st.selectbox("Role", ["staff","admin"])
                    if st.button("Yarat", key="crt_usr"):
                        try:
                            run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":nu, "p":hash_password(np), "r":nr})
                            st.success("OK")
                        except: st.error("Bu ad artıq var")

                with st.expander("📍 Əlaqə"):
                    na = st.text_input("Ünvan", SHOP_ADDRESS); ni = st.text_input("Instagram", INSTAGRAM_LINK)
                    if st.button("Saxla"): set_config("shop_address", na); set_config("instagram_link", ni); st.success("OK")

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
                    zip_buffer = BytesIO()
                    has_multiple = cnt > 1
                    
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for i in ids: 
                            token = secrets.token_hex(8)
                            run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":"thermos" if is_th else "standard", "st":token})
                            if is_th:
                                run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:i, 'thermos_welcome')", {"i":i})
                            
                            img_data = generate_custom_qr(f"{APP_URL}/?id={i}&t={token}", i)
                            zf.writestr(f"{i}.png", img_data)
                            
                            if not has_multiple:
                                st.image(BytesIO(img_data), width=250)
                                single_data = img_data

                    if has_multiple:
                        st.success(f"{cnt} ədəd QR yaradıldı!")
                        st.download_button("📥 ZIP Yüklə", zip_buffer.getvalue(), "qrcodes.zip", "application/zip")
                    else:
                        st.download_button("⬇️ Yüklə", single_data, f"{ids[0]}.png", "image/png")

        elif role == 'staff': render_pos()
