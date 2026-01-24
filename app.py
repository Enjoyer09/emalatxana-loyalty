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
st.set_page_config(
    page_title="Emalatxana Coffee", 
    page_icon="☕", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# === DİZAYN KODLARI (CSS & JS) ===
# ==========================================
st.markdown("""
    <script>
    function keepAlive() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/", true);
        xhr.send();
    }
    setInterval(keepAlive, 30000); 
    </script>

    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700&display=swap');
    
    #MainMenu, header, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    
    .stApp { font-family: 'Oswald', sans-serif !important; background-color: #FAFAFA; }
    .block-container { padding-top: 1rem !important; padding-bottom: 4rem !important; max-width: 100%; }

    /* --- POS DÜYMƏLƏRİ (NARINCI KONTUR & BOLD) --- */
    div.stButton > button {
        background-color: #FFFFFF !important;
        color: #E65100 !important; /* Narıncı Yazı */
        border: 3px solid #E65100 !important; /* Narıncı Çərçivə */
        border-radius: 15px !important;
        font-family: 'Oswald', sans-serif !important;
        font-weight: 700 !important; /* BOLD */
        font-size: 20px !important;
        min-height: 90px !important; /* Touch screen üçün hündür */
        width: 100% !important;
        transition: transform 0.1s !important;
        box-shadow: 0 4px 0 rgba(230, 81, 0, 0.1) !important;
    }
    
    div.stButton > button:active {
        transform: translateY(4px) !important;
        box-shadow: none !important;
        background-color: #FFF3E0 !important;
    }

    /* Expander Header Style (Kateqoriyalar üçün) */
    .streamlit-expanderHeader {
        font-family: 'Oswald', sans-serif;
        font-size: 22px !important;
        font-weight: bold !important;
        color: #2E7D32 !important; /* Yaşıl */
        background-color: #F1F8E9 !important;
        border-radius: 10px;
        border: 1px solid #2E7D32;
        margin-bottom: 10px;
    }

    /* Primary Düymələr (Ödəniş, Backup) */
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
    
    /* 10 Stəkan Qridi */
    .coffee-grid-container {
        display: grid; 
        grid-template-columns: repeat(5, 1fr); 
        gap: 12px; 
        justify-items: center; 
        margin-top: 25px;
    }
    .coffee-icon { width: 50px; height: 50px; transition: all 0.3s ease; }
    
    /* Hədiyyə Qutusu Animasiyası (10-cu stəkan) */
    .gift-box-anim {
        width: 60px; height: 60px;
        animation: bounce 2s infinite;
        filter: drop-shadow(0 0 8px gold);
    }
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
        40% {transform: translateY(-15px);}
        60% {transform: translateY(-7px);}
    }
    
    /* PROMOSİYA KARTI (FANCY) */
    .promo-card {
        background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 10px 20px rgba(245, 124, 0, 0.3);
        color: white;
        animation: pulse-border 2s infinite;
    }
    .promo-title {
        font-family: 'Oswald', sans-serif; 
        font-size: 26px; font-weight: bold; margin-bottom: 5px;
        text-transform: uppercase; text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    .promo-desc {
        font-size: 18px; font-weight: 500;
    }

    /* Motivasiya Yazısı */
    .inner-motivation {
        font-size: 24px; color: #2E7D32; font-family: 'Oswald', sans-serif;
        font-weight: 700; font-style: italic; margin-bottom: 20px; text-align: center;
        background: #F1F8E9; padding: 15px; border-radius: 15px;
        border: 2px dashed #2E7D32;
    }

    .feedback-box {
        margin-top: 30px; padding: 15px; border: 1px dashed #ccc;
        border-radius: 10px; background-color: #fff;
    }

    .emergency-refresh {
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        background: #333; color: white; border-radius: 50%;
        width: 50px; height: 50px; border: none; font-size: 24px;
        cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; text-decoration: none;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("Database URL not found!"); st.stop()
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
INSTAGRAM_LINK = get_config("instagram_link", "https://instagram.com")
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

# --- UI HEADER ---
def render_header():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{SHOP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<div class='shop-info'>📍 {SHOP_ADDRESS}</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="social-links"><a href="{INSTAGRAM_LINK}" target="_blank">Instagram</a></div>""", unsafe_allow_html=True)

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
    quotes = [
        "Bu gün əla görünürsən! 🧡", "Enerjini bərpa etmək vaxtıdır! ⚡", "Sən ən yaxşısına layiqsən! ✨",
        "Kofe ilə gün daha gözəldir! ☀️", "Gülüşün dünyanı dəyişə bilər! 😊", "Uğur cəsarət edənlərindir! 🚀",
        "Həyat bir qurtum kofe kimidir! ☕", "Pozitiv ol, möcüzələr baş verir! 🌟"
    ]
    return random.choice(quotes)

# --- CRM MOTIVATION LIST ---
CRM_QUOTES = [
    "Səni görmək çox xoşdur! ☕", "Həftəsonun əla keçsin! 🎉", "Yeni həftəyə enerji ilə başla! 🚀",
    "Sənin üçün darıxdıq! ❤️", "Bu gün özünə bir yaxşılıq et! 🍰", "Kofe ətri səni çağırır! ☕",
    "Dostlarınla gözəl vaxt keçir! 👯", "Emalatxana səni sevir! 🧡", "Hava soyuqdur, kofe istidir! ❄️",
    "Gülüşünlə ətrafı işıqlandır! ✨", "Uğurlu bir gün olsun! 💼", "Sən bizim üçün dəyərlisən! 💎",
    "Kiçik xoşbəxtliklər böyükdür! 🎈", "Özünə vaxt ayır! ⏳", "Dadlı bir fasilə ver! 🥐",
    "Hər qurtumda ləzzət! 😋", "Bu gün möcüzəvidir! 🌟", "Sən özəl birisən! 🎁", "Həyat gözəldir, dadını çıxar! 🌈",
    "Bizimlə olduğun üçün təşəkkürlər! 🙏", "Kofe sənin haqqındır! ☕", "Ulduzun parlasın! ⭐",
    "Xoşbəxtlik bir fincan uzaqlıqdadır! 💖", "Enerjini bizimlə bərpa et! 🔋", "Günün aydın olsun! ☀️",
    "Həmişə belə gülümsə! 😊", "Sənə uğurlar arzulayırıq! 👍", "Kofe bəhanə, söhbət şahanə! 🗣️",
    "Gözəl anlar birikdir! 📸", "Sən bir dənəsən! 💎", "Dadlı kofe, şirin söhbət! 🍰",
    "Həyat qısadır, kofeni soyutma! ⏳", "Yeni dadlar kəşf et! 🌍", "Səni yenidən gözləyirik! 👋",
    "Bu gün sənin şans günündür! 🍀", "Hər şey qaydasındadır! 👌", "Rahatla və həzz al! 🛋️",
    "Sevgi ilə hazırlanmış kofe! ❤️", "Dostluq kofe ilə başlayar! 🤝", "Günəş kimi parla! 🌞",
    "Sənin enerjin bizə ilham verir! 💡", "Möhtəşəm görünürsən! 😎", "Uğurlu başlanğıclar! 🌱",
    "Xəyallarını gerçəkləşdir! 🌠", "Kofe əhvalını qaldıracaq! 🚀", "Sadəcə gülümsə! 😄",
    "Özünə güvən! 💪", "Bu anın dadını çıxar! 🕰️", "Sən bacararsan! 🏆", "Emalatxana sənin evindir! 🏠"
]

# --- BIRTHDAY CHECKER ---
def check_and_send_birthday_emails():
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        with conn.session as s:
            res = s.execute(text("SELECT value FROM settings WHERE key = 'last_birthday_check'")).fetchone()
            last_run = res[0] if res else None
            if last_run == today_str: return 
            today_mm_dd = datetime.date.today().strftime("%m-%d")
            birthdays = s.execute(text("SELECT card_id, email FROM customers WHERE RIGHT(birth_date, 5) = :td AND email IS NOT NULL AND is_active = TRUE"), {"td": today_mm_dd}).fetchall()
            for user in birthdays:
                if send_email(user[1], f"🎉 {SHOP_NAME}: Ad Günün Mübarək!", "Sənə 1 pulsuz kofe hədiyyə!"):
                    s.execute(text("INSERT INTO notifications (card_id, message) VALUES (:cid, '🎂 Ad Günün Mübarək! Hədiyyə Kofen Var!')"), {"cid": user[0]})
                    s.execute(text("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:cid, 'birthday_gift')"), {"cid": user[0]})
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
        if user['secret_token'] and user['secret_token'] != token: st.error("⛔ İcazəsiz Giriş!"); st.stop()

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"📩 {row['message']}"); run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        if not user['is_active']:
            st.warning(f"🎉 {SHOP_NAME}-a Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email"); dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                st.markdown("### 📜 Qaydalar"); st.info("1. Məlumatlar məxfidir.\n2. 9 Ulduz = 1 Hədiyyə.")
                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                    st.balloons(); st.rerun()
            st.stop()

        st.markdown(f"<div class='inner-motivation'>{get_random_quote()}</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="digital-card"><h3 style="margin-top:0">{SHOP_NAME} BONUS</h3><h1 style="color:#2E7D32; font-size: 48px; margin:0;">{user['stars']} / 10</h1><p style="color:#777">Balansınız</p></div>""", unsafe_allow_html=True)
        
        # 0/10 STARS LOGIC (10-cu HƏDİYYƏ)
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            if i == 9: # 10-cu element (Hədiyyə Qutusu)
                icon = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png" 
                if user['stars'] >= 10: # Əgər 10 ulduz varsa aktivləşsin
                    cls = "gift-box-anim"
                    style = "opacity: 1;"
                else:
                    cls = "coffee-icon"
                    style = "opacity: 0.3; filter: grayscale(100%);"
            else: # Adi Kofe
                icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
                cls = "coffee-icon"
                if i < user['stars']: style = "opacity: 1;"
                else: style = "opacity: 0.2; filter: grayscale(100%);"
            
            html += f'<img src="{icon}" class="{cls}" style="{style}">'
        html += '</div>'; st.markdown(html, unsafe_allow_html=True)
        
        rem = 10 - user['stars']
        if rem <= 0: st.markdown("<h3 style='text-align:center; color:#E65100 !important;'>🎉 TƏBRİKLƏR! Hədiyyə Kofeniz Hazırdır!</h3>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='heartbeat-text'>🎁 Hədiyyəyə {rem} kofe qaldı!</div>", unsafe_allow_html=True)
        
        # PROMOSİYA KARTI (FANCY)
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE", {"id": card_id})
        for _, cp in my_coupons.iterrows():
            name = "🎁 Xüsusi Hədiyyə"
            if cp['coupon_type'] == 'birthday_gift': name = "🎂 Ad Günü Hədiyyəsi!"
            elif cp['coupon_type'] == '50_percent': name = "🏷️ 50% Endirim!"
            elif cp['coupon_type'] == 'free_cookie': name = "🍪 Pulsuz Peceniya"
            
            st.markdown(f"""
            <div class='promo-card'>
                <div class='promo-title'>TƏBRİKLƏR!</div>
                <div class='promo-desc'>{name}</div>
            </div>
            """, unsafe_allow_html=True)

        last_fb_star = int(user['last_feedback_star']) if user['last_feedback_star'] is not None else -1
        current_stars = int(user['stars'])
        
        st.markdown("<div class='feedback-box'><h4 style='text-align:center; margin:0; color:#2E7D32'>💌 Rəy Bildir</h4>", unsafe_allow_html=True)
        if last_fb_star < current_stars:
            with st.form("feed"):
                s = st.feedback("stars"); m = st.text_input("Şərhiniz")
                if st.form_submit_button("Rəy Göndər"):
                    if s is not None: 
                        run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                        run_action("UPDATE customers SET last_feedback_star = :s WHERE card_id = :i", {"s":int(current_stars), "i":card_id})
                        st.success("Təşəkkürlər!"); time.sleep(1); st.rerun()
        else: st.info("⭐ Rəy bildirdiyiniz üçün təşəkkürlər!")
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
        st.markdown("""<a href="/" target="_self" class="emergency-refresh">🔄</a>""", unsafe_allow_html=True)

    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1]); 
        with c2: 
            if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
            else: st.markdown(f"<h2 style='text-align:center'>{SHOP_NAME}</h2>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align:center'>GİRİŞ</h3>", unsafe_allow_html=True)
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
        
        # --- POS RENDER ---
        def render_pos():
            layout_col1, layout_col2 = st.columns([1.2, 3]) 
            
            # --- SOL: SƏBƏT ---
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
                    cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id": curr['card_id']})
                    if not cps.empty:
                        cp_ops = {f"{r['coupon_type']}": r['id'] for _, r in cps.iterrows()}
                        sel_cp = st.selectbox("Kupon:", ["Yox"] + list(cp_ops.keys()))
                        if sel_cp != "Yox": st.session_state.active_coupon = {"id": cp_ops[sel_cp], "type": sel_cp}
                        else: st.session_state.active_coupon = None
                    if st.button("Ləğv Et", key="pcl"): st.session_state.current_customer = None; st.rerun()
                
                st.markdown("<div style='background:white; height:60vh; overflow-y:scroll; border:1px solid #ddd; padding:10px;'>", unsafe_allow_html=True)
                total = 0; coffs = 0
                if st.session_state.cart:
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([4, 2, 1])
                        c1.write(f"**{item['item_name']}**")
                        c2.write(f"{item['price']}")
                        if c3.button("x", key=f"d_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price'])
                        if item.get('is_coffee', False): coffs += 1
                else: st.info("Səbət boşdur")
                st.markdown("</div>", unsafe_allow_html=True)
                
                disc, coupon_disc = 0, 0
                if curr:
                    if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x.get('is_coffee')]) * 0.2
                    if curr['stars'] >= 10: # 10-cu pulsuz
                        c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                        if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                    if st.session_state.active_coupon:
                        if st.session_state.active_coupon['type'] == '50_percent': coupon_disc = total * 0.5
                        elif st.session_state.active_coupon['type'] == 'birthday_gift' and st.session_state.cart: coupon_disc = float(min(st.session_state.cart, key=lambda x: float(x['price']))['price'])

                final = max(0, total - disc - coupon_disc)
                st.markdown(f"<div style='font-size:24px; font-weight:bold; text-align:right; color:#D32F2F; margin-top:10px;'>YEKUN: {final:.2f} ₼</div>", unsafe_allow_html=True)
                
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
                                    if ns >= 10 and any(x.get('is_coffee') for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                if st.session_state.active_coupon: s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                            s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final, "p":p_code})
                            s.commit()
                        st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; st.session_state.active_coupon = None; time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Xəta: {e}")

            # --- SAĞ: EXPANDERS (GİZLİ KATEQORİYALAR) ---
            with layout_col2:
                # POPUP MƏNTİQİ
                @st.dialog("Ölçü Seçimi")
                def show_variants(base_name, items):
                    st.write(f"**{base_name}**")
                    cols = st.columns(len(items))
                    for i, item in enumerate(items):
                        label = item['item_name'].split()[-1] # S, M, L
                        with cols[i]:
                            if st.button(f"{label}\n{item['price']}₼", key=f"v_{item['id']}"):
                                st.session_state.cart.append(item)
                                st.rerun()

                # MENU DATA
                menu_coffee = run_query("SELECT * FROM menu WHERE category='Qəhvə' AND is_active=TRUE ORDER BY item_name")
                menu_drinks = run_query("SELECT * FROM menu WHERE category='İçkilər' AND is_active=TRUE ORDER BY item_name")
                menu_desert = run_query("SELECT * FROM menu WHERE category='Desert' AND is_active=TRUE ORDER BY item_name")

                # HELPER FOR RENDERING BUTTONS INSIDE EXPANDER
                def render_grid(dataframe, key_prefix):
                    if dataframe.empty:
                        st.info("Məhsul yoxdur")
                        return
                        
                    groups = {}
                    for idx, row in enumerate(dataframe.to_dict('records')):
                        name = row['item_name']
                        parts = name.split()
                        if parts[-1] in ['S', 'M', 'L', 'XL']: 
                            base = " ".join(parts[:-1])
                            if base not in groups: groups[base] = []
                            groups[base].append(row)
                        else:
                            groups[name] = [row]

                    cols = st.columns(4)
                    for i, (base_name, items) in enumerate(groups.items()):
                        with cols[i % 4]:
                            if len(items) > 1:
                                if st.button(f"{base_name}\n(Seçim)", key=f"{key_prefix}_grp_{i}"):
                                    show_variants(base_name, items)
                            else:
                                item = items[0]
                                if st.button(f"{item['item_name']}\n{item['price']}₼", key=f"{key_prefix}_itm_{item['id']}"):
                                    st.session_state.cart.append(item); st.rerun()

                # EXPANDERLƏR
                with st.expander("☕ Qəhvə", expanded=False):
                    render_grid(menu_coffee, "cof")
                
                with st.expander("🥤 İçkilər", expanded=False):
                    render_grid(menu_drinks, "drk")
                
                with st.expander("🍰 Desert", expanded=False):
                    render_grid(menu_desert, "dst")

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
            with tabs[0]: render_pos()
            
            # --- BƏRPA OLUNMUŞ ANALİTİKA ---
            with tabs[1]:
                st.markdown("### 📊 Satış Analitikası")
                today = datetime.date.today()
                sel_date = st.date_input("Ay Seçin", today)
                sel_month = sel_date.strftime("%Y-%m")
                
                sales = run_query("SELECT * FROM sales WHERE TO_CHAR(created_at, 'YYYY-MM') = :m ORDER BY created_at DESC", {"m": sel_month})
                
                if not sales.empty:
                    tot = sales['total'].sum()
                    cash = sales[sales['payment_method'] == 'Cash']['total'].sum()
                    card = sales[sales['payment_method'] == 'Card']['total'].sum()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Ümumi", f"{tot:.2f}")
                    m2.metric("💵 Nağd", f"{cash:.2f}")
                    m3.metric("💳 Kart", f"{card:.2f}")
                    
                    sales['day'] = pd.to_datetime(sales['created_at']).dt.day
                    daily = sales.groupby('day')['total'].sum()
                    st.bar_chart(daily)
                    
                    with st.expander("Siyahı"):
                        st.dataframe(sales)
                else: st.info("Satış yoxdur.")

            # --- BƏRPA OLUNMUŞ CRM ---
            with tabs[2]:
                st.markdown("### 📧 CRM")
                m_df = run_query("SELECT card_id, email, stars FROM customers WHERE email IS NOT NULL")
                
                if not m_df.empty:
                    if 'crm_selections' not in st.session_state: st.session_state.crm_selections = [False] * len(m_df)
                    
                    c_all, c_none = st.columns(2)
                    if c_all.button("✅ Hamısını Seç"): st.session_state.crm_selections = [True] * len(m_df); st.rerun()
                    if c_none.button("❌ Sıfırla"): st.session_state.crm_selections = [False] * len(m_df); st.rerun()
                    
                    m_df['Seç'] = st.session_state.crm_selections
                    edited = st.data_editor(m_df, hide_index=True, use_container_width=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)})
                    
                    st.divider()
                    st.markdown("#### 📢 Kampaniya Göndər")
                    
                    # Hazır Motivasiya Seçimi
                    sel_quote = st.selectbox("Motivasiya Seç:", ["(Özün Yaz)"] + CRM_QUOTES)
                    custom_msg_val = sel_quote if sel_quote != "(Özün Yaz)" else ""
                    
                    with st.form("custom_crm"):
                        txt = st.text_area("Mesaj Mətni", value=custom_msg_val)
                        if st.form_submit_button("Seçilənlərə Göndər"):
                            cnt = 0
                            for i, r in edited.iterrows():
                                if r['Seç']:
                                    send_email(r['email'], "Emalatxana Coffee", txt)
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :m)", {"id":r['card_id'], "m":txt}); cnt+=1
                            st.success(f"{cnt} mesaj göndərildi!")
                    
                    st.markdown("#### 🎁 Xüsusi Kuponlar")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("🏷️ 50% Endirim"):
                        cnt = 0
                        for i, r in edited.iterrows():
                            if r['Seç']:
                                send_email(r['email'], "50% Endirim!", "Sizə özəl!")
                                run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:id, '50_percent')", {"id":r['card_id']}); cnt+=1
                        st.success(f"{cnt} göndərildi")
                    
                    if c2.button("🎂 Ad Günü"):
                        cnt = 0
                        for i, r in edited.iterrows():
                            if r['Seç']:
                                send_email(r['email'], "Ad Gününüz Mübarək!", "Hədiyyə!")
                                run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:id, 'birthday_gift')", {"id":r['card_id']}); cnt+=1
                        st.success(f"{cnt} göndərildi")

                else: st.info("Müştəri yoxdur")

            with tabs[3]:
                with st.form("add"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                st.dataframe(run_query("SELECT * FROM menu"))
            with tabs[4]:
                st.markdown("### ⚙️ Ayarlar")
                with st.expander("🖼️ Logo və Ad"):
                    new_name = st.text_input("Mağaza Adı", value=SHOP_NAME)
                    uploaded_logo = st.file_uploader("Logo Yüklə", type=['png', 'jpg'])
                    if uploaded_logo and st.button("Logonu Saxla"):
                        logo_str = process_logo_upload(uploaded_logo)
                        if logo_str: set_config("shop_logo_base64", logo_str)
                    if st.button("Adı Saxla"): set_config("shop_name", new_name)
                
                with st.expander("👥 İşçi İdarəetməsi", expanded=True):
                    users_df = run_query("SELECT username, role FROM users")
                    st.dataframe(users_df)
                    c_add, c_del = st.columns(2)
                    with c_add:
                        st.subheader("➕ Yeni İşçi")
                        nu = st.text_input("Username")
                        np = st.text_input("Password", type="password")
                        nr = st.selectbox("Role", ["staff", "admin"])
                        if st.button("Əlavə Et"):
                            if len(np) < 6: st.error("Şifrə qısadır")
                            else:
                                try:
                                    run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", 
                                               {"u":nu, "p":hash_password(np), "r":nr})
                                    st.success("Yaradıldı!"); time.sleep(1); st.rerun()
                                except: st.error("Bu ad artıq var!")
                    with c_del:
                        st.subheader("🗑️ Sil / 🔑 Şifrə")
                        user_list = users_df['username'].tolist()
                        target = st.selectbox("Seç:", user_list) if user_list else None
                        if target:
                            if st.button("Sil"):
                                if target == 'admin': st.error("Admin silinə bilməz!")
                                else:
                                    run_action("DELETE FROM users WHERE username=:u", {"u":target})
                                    st.success("Silindi!"); time.sleep(1); st.rerun()
                            new_p = st.text_input("Yeni Şifrə", type="password", key="new_p_reset")
                            if st.button("Yenilə"):
                                run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_p), "u":target})
                                st.success("Yeniləndi!")

            with tabs[5]:
                st.markdown("### 🛠️ Admin")
                if st.button("📥 BÜTÜN BAZANI YÜKLƏ (BACKUP)", type="primary"):
                    try:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            clean_df_for_excel(run_query("SELECT * FROM customers")).to_excel(writer, sheet_name='Müştərilər', index=False)
                            clean_df_for_excel(run_query("SELECT * FROM sales")).to_excel(writer, sheet_name='Satışlar', index=False)
                        st.download_button("⬇️ Endir", output.getvalue(), f"Backup.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except Exception as e: st.error(f"Xəta: {e}")

            with tabs[6]:
                cnt = st.number_input("Say", 1, 50); is_th = st.checkbox("Termos?")
                if st.button("Yarat"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    typ = "thermos" if is_th else "standard"
                    for i in ids: 
                        token = secrets.token_urlsafe(8)
                        run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":typ, "st":token})
                    if cnt == 1:
                        tkn = run_query("SELECT secret_token FROM customers WHERE card_id=:id", {"id":ids[0]}).iloc[0]['secret_token']
                        d = generate_custom_qr(f"{APP_URL}/?id={ids[0]}&t={tkn}", ids[0])
                        st.image(BytesIO(d), width=200); st.download_button("⬇️", d, f"{ids[0]}.png", "image/png")

        elif role == 'staff': render_pos()
