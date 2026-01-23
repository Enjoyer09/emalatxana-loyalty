import streamlit as st
import pandas as pd
import random
import qrcode
from io import BytesIO
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

st.set_page_config(page_title="IronWaves Loyalty", page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("Database URL not found!"); st.stop()
    conn = st.connection("neon", type="sql", url=db_url.replace("postgres://", "postgresql+psycopg2://"), pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA ---
def ensure_schema():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        # last_feedback_star sütunu əlavə olundu ki, rəyləri kontrol edək
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, last_feedback_star INTEGER DEFAULT -1);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS quotes (id SERIAL PRIMARY KEY, text TEXT);"))
        s.commit()
ensure_schema()

# --- CONFIG MANAGER ---
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

# LOAD SETTINGS
SHOP_NAME = get_config("shop_name", "Emalatxana Coffee")
SHOP_ADDRESS = get_config("shop_address", "Bakı şəhəri")
INSTAGRAM_LINK = get_config("instagram_link", "https://instagram.com")
LOGO_BASE64 = get_config("shop_logo_base64", "")

# POS DESIGN SETTINGS
POS_BTN_BG = get_config("pos_btn_bg", "#FFFFFF")
POS_BTN_TEXT = get_config("pos_btn_text", "#E65100")
POS_BTN_HEIGHT = get_config("pos_btn_height", "80")
POS_BTN_WIDTH = get_config("pos_btn_width", "100") # Faizlə
POS_BTN_SHAPE = get_config("pos_btn_shape", "12px") # 0px = kvadrat, 50% = yumru

# --- HELPERS ---
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
def run_query(q, p=None): return conn.query(q, params=p, ttl=0)
def run_action(q, p=None): 
    with conn.session as s: s.execute(text(q), p); s.commit()
    return True

def process_logo_upload(uploaded_file):
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            base_width = 200
            w_percent = (base_width / float(image.size[0]))
            h_size = int((float(image.size[1]) * float(w_percent)))
            image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception as e: return None
    return None

def get_random_quote_from_db():
    df = run_query("SELECT text FROM quotes")
    if df.empty: return "Bu gün əla görünürsən! 🧡"
    return random.choice(df['text'].tolist())

# --- RESEND EMAIL SYSTEM ---
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return False
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    
    motivation = get_random_quote_from_db()
    html_body = body.replace("\n", "<br>")
    
    payload = {
        "from": f"{SHOP_NAME} <{DEFAULT_SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "reply_to": "taliyev.abbas84@gmail.com", 
        "html": f"""
        <div style="font-family: sans-serif; font-size: 16px; color: #333; line-height: 1.6;">
            <p>{html_body}</p>
            <br>
            <div style="border-left: 4px solid #2E7D32; padding-left: 15px; margin: 20px 0; background-color: #f9f9f9; padding: 15px; border-radius: 0 10px 10px 0; color: #555; font-style: italic;">
                "{motivation}"
            </div>
            <br>
            <p style="font-size: 14px; color: #888;">Sevgilərlə,<br><strong>{SHOP_NAME} Komandası</strong></p>
        </div>
        """
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

# --- AVTOMATİK AD GÜNÜ ---
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
                card_id, email = user[0], user[1]
                subject = f"🎉 {SHOP_NAME}: Ad Günün Mübarək!"
                body = f"Salam dəyərli dost! 🎂\n\nBu gün sənin günündür! {SHOP_NAME} olaraq səni təbrik edirik.\n\n🎁 Hədiyyən: 1 ədəd PULSUZ Kofe!\nYaxınlaşanda şəxsiyyət vəsiqəni və QR kodunu göstərməyi unutma."
                if send_email(email, subject, body):
                    s.execute(text("INSERT INTO notifications (card_id, message) VALUES (:cid, '🎂 Ad Günün Mübarək! Hədiyyə Kofen Var!')"), {"cid": card_id})
                    s.execute(text("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:cid, 'birthday_gift')"), {"cid": card_id})
            s.execute(text("INSERT INTO settings (key, value) VALUES ('last_birthday_check', :val) ON CONFLICT (key) DO UPDATE SET value = :val"), {"val": today_str})
            s.commit()
    except Exception as e: print(f"Birthday Error: {e}")

if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = True
    threading.Thread(target=check_and_send_birthday_emails, daemon=True).start()

# ==========================================
# === CSS (TAM DİZAYN) ===
# ==========================================
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&display=swap'); /* Əl yazısı şrifti */
    
    #MainMenu, header, footer {{ display: none !important; }}
    .stApp {{ font-family: 'Oswald', sans-serif !important; background-color: #FAFAFA; }}
    .block-container {{ padding-top: 1rem !important; padding-bottom: 4rem !important; max-width: 100%; }}
    
    /* POS BUTTONS (DYNAMIC) */
    div[data-testid="column"] button {{
        background-color: {POS_BTN_BG} !important;
        border: 2px solid #ddd !important;
        color: {POS_BTN_TEXT} !important;
        font-weight: 700;
        border-radius: {POS_BTN_SHAPE} !important;
        height: {POS_BTN_HEIGHT}px !important;
        width: 100% !important; 
        transition: 0.2s;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    div[data-testid="column"] button:active {{ transform: scale(0.98); }}

    /* DIGITAL CARD */
    .digital-card {{ background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #eee; text-align: center; margin-bottom: 20px; }}
    .shop-info {{ text-align: center; margin-bottom: 5px; color: #555; font-size: 14px; }}
    .social-links {{ text-align: center; margin-top: 10px; font-size: 24px; }}
    .social-links a {{ text-decoration: none; color: #E1306C; font-weight: bold; margin: 0 10px; }}
    
    /* COFFEE GRID */
    .coffee-grid-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 20px; }}
    .coffee-icon {{ width: 40px; height: 40px; transition: all 0.3s ease; }}

    /* 50% COUPON PULSE ANIMATION */
    @keyframes heartbeat {{
        0% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }}
        70% {{ transform: scale(1.05); box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }}
        100% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }}
    }}
    .special-offer {{
        background-color: white;
        border: 2px dashed red;
        color: red;
        font-family: 'Dancing Script', cursive; /* Əl yazısı */
        font-size: 32px;
        text-align: center;
        padding: 20px;
        border-radius: 15px;
        margin: 20px 0;
        animation: heartbeat 1.5s infinite;
    }}

    /* FEEDBACK STARS SCALE */
    div[data-testid="stFeedback"] {{ transform: scale(2.5); margin: 20px auto; display: flex; justify-content: center; }}

    /* REFRESH BTN (ADMIN ONLY) */
    .admin-refresh {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: #333; color: white; border-radius: 5px; padding: 10px 20px; text-decoration: none; font-weight: bold; }}
    </style>
""", unsafe_allow_html=True)

# --- UI COMPONENTS ---
def render_header():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{SHOP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<div class='shop-info'>📍 {SHOP_ADDRESS}</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="social-links"><a href="{INSTAGRAM_LINK}" target="_blank">📸</a></div>""", unsafe_allow_html=True)

# --- SESSION STATE ---
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

        # AKTİVASİYA MƏRHƏLƏSİ (TERMS & CONDITIONS)
        if not user['is_active']:
            st.warning(f"🎉 {SHOP_NAME}-a Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email"); dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                
                # UZUN QAYDALAR QUTUSU
                st.markdown("### 📜 Qaydalar və Şərtlər")
                st.markdown("""
                <div style="height: 150px; overflow-y: scroll; background: #f0f0f0; padding: 10px; border: 1px solid #ccc; font-size: 14px;">
                    1. <b>Sadiqlik Proqramı:</b> Bu proqram müştərilərimizə xüsusi endirimlər və hədiyyələr təqdim etmək üçün yaradılmışdır.<br>
                    2. <b>Bonuslar:</b> Hər 1 ədəd kofe alışı 1 ulduz qazandırır. 9 ulduz topladıqda 10-cu kofe pulsuzdur.<br>
                    3. <b>Məxfilik:</b> Sizin məlumatlarınız (Email, Ad günü) üçüncü tərəflərlə paylaşılmır və yalnız kampaniya məlumatları üçün istifadə olunur.<br>
                    4. <b>Ləğv:</b> Mağaza rəhbərliyi şübhəli fəaliyyət aşkar etdikdə kartı bloklamaq hüququna malikdir.<br>
                    5. <b>Termos Kampaniyası:</b> Öz termosu ilə gələnlərə 10% endirim edilir.<br>
                    6. <b>Qüvvədə olma müddəti:</b> Toplanan ulduzların istifadə müddəti yoxdur.
                </div>
                """, unsafe_allow_html=True)
                
                agree = st.checkbox("Qaydalarla tanış oldum və razıyam")

                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    if agree and em:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons(); st.rerun()
                    else:
                        st.error("Zəhmət olmasa Qaydaları qəbul edin və Email yazın.")
            st.stop()

        # NOTIFICATIONS
        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"📩 {row['message']}"); run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        # MOTIVATION
        st.markdown(f"<div style='text-align:center; color:#2E7D32; font-style:italic; margin-bottom:15px;'>✨ {get_random_quote_from_db()} ✨</div>", unsafe_allow_html=True)

        # DIGITAL CARD
        st.markdown(f"""<div class="digital-card"><h3 style="margin-top:0">{SHOP_NAME} BONUS</h3><h1 style="color:#2E7D32; font-size: 48px; margin:0;">{user['stars']} / 9</h1><p style="color:#777">Balansınız</p></div>""", unsafe_allow_html=True)
        
        # COFFEE GRID
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; style = "opacity: 1;" if i < user['stars'] else "opacity: 0.2; filter: grayscale(100%);"
            if i == 9: icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; style += " filter: hue-rotate(45deg);" 
            html += f'<img src="{icon}" class="coffee-icon" style="{style}">'
        html += '</div>'; st.markdown(html, unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.success("🎉 TƏBRİKLƏR! Pulsuz Kofeniz Hazırdır!")
        else: st.markdown(f"<div style='text-align:center; color:#E65100; font-weight:bold; margin-top:10px;'>❤️ Cəmi {rem} kofedən sonra qonağımızsan! ❤️</div>", unsafe_allow_html=True)
        
        # COUPONS DESIGN (50% SPECIAL)
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE", {"id": card_id})
        for _, cp in my_coupons.iterrows():
            if cp['coupon_type'] == '50_percent':
                st.markdown(f"<div class='special-offer'>❤️ 50% ENDİRİM ❤️<br><span style='font-size:16px; font-family:sans-serif; color:black;'>Bu gün sizə özəldir!</span></div>", unsafe_allow_html=True)
            else:
                st.info(f"🎁 Aktiv Kupon: {cp['coupon_type']}")

        # FEEDBACK SYSTEM (BLOCKED IF ALREADY SENT)
        last_fb_star = user['last_feedback_star']
        current_stars = user['stars']
        
        st.divider()
        st.markdown("<h4 style='text-align:center; color:#555'>💌 Bizim haqqımızda fikriniz</h4>", unsafe_allow_html=True)
        
        if last_fb_star < current_stars:
            with st.form("feed"):
                s = st.feedback("stars") # CSS ilə böyüdülüb
                m = st.text_input("Şərhiniz")
                if st.form_submit_button("Rəy Göndər"):
                    if s is not None: 
                        run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                        run_action("UPDATE customers SET last_feedback_star = :s WHERE card_id = :i", {"s":current_stars, "i":card_id})
                        st.success("Təşəkkürlər! Rəyiniz qeydə alındı.")
                        time.sleep(1); st.rerun()
        else:
            st.info("⭐ Rəy bildirdiyiniz üçün təşəkkürlər! Növbəti ulduz qazananda yenidən yaza bilərsiniz.")

        st.divider()
        qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}" if user['secret_token'] else f"{APP_URL}/?id={card_id}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS & ADMIN ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    # REFRESH BUTTON (ONLY FOR ADMIN/USER)
    st.markdown("""<a href="/" target="_self" class="admin-refresh">🔄 Yenilə</a>""", unsafe_allow_html=True)

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
        h1, h2, h3 = st.columns([2,6,1])
        with h1: 
            if st.button("🔴 Çıxış", key="out"): st.session_state.logged_in = False; st.rerun()

        role = st.session_state.role
        
        def render_pos():
            left_col, right_col = st.columns([2, 1])
            with left_col:
                c_scan, c_info = st.columns([2, 2])
                with c_scan:
                    scan_val = st.text_input("Müştəri QR", key="ps")
                    if st.button("🔍 AXTAR", key="psb"):
                        if scan_val:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                            if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.session_state.active_coupon = None; st.rerun()
                            else: st.error("Tapılmadı")
                with c_info:
                    curr = st.session_state.current_customer
                    if curr:
                        st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                        cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id": curr['card_id']})
                        if not cps.empty:
                            st.info(f"🎫 {len(cps)} Aktiv Kupon!")
                            cp_ops = {f"{r['coupon_type']} (ID:{r['id']})": r['id'] for _, r in cps.iterrows()}
                            sel_cp_label = st.selectbox("Kupon:", ["Yox"] + list(cp_ops.keys()))
                            if sel_cp_label != "Yox": st.session_state.active_coupon = {"id": cp_ops[sel_cp_label], "type": sel_cp_label.split()[0]}
                            else: st.session_state.active_coupon = None
                        if st.button("❌ Ləğv", key="pcl"): st.session_state.current_customer = None; st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                # KATEQORIYALAR
                cat_col1, cat_col2, cat_col3 = st.columns(3)
                if cat_col1.button("Qəhvə", key="cat_coff", type="primary", use_container_width=True): st.session_state.pos_category = "Qəhvə"; st.rerun()
                if cat_col2.button("İçkilər", key="cat_drk", type="primary", use_container_width=True): st.session_state.pos_category = "İçkilər"; st.rerun()
                if cat_col3.button("Desert", key="cat_dst", type="primary", use_container_width=True): st.session_state.pos_category = "Desert"; st.rerun()
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": st.session_state.pos_category})
                
                # POS DÜYMƏLƏRİ (KÖHNƏ STİL - KVADRAT)
                cols = st.columns(3) # 3 Sütunlu Grid
                for idx, row in enumerate(menu_df.to_dict('records')):
                     with cols[idx % 3]:
                         # Custom CSS tətbiq olunur (config-dən gələn)
                         if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"s_{row['id']}"):
                             st.session_state.cart.append(row); st.rerun()

            with right_col:
                st.markdown("### 🧾 ÇEK")
                if st.session_state.cart:
                    total, coffs = 0, 0
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([3,1,1])
                        c1.write(item['item_name']); c2.write(f"{item['price']}")
                        if c3.button("🗑️", key=f"d_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price']); coffs += 1 if item['is_coffee'] else 0
                    
                    disc, curr, coupon_disc = 0, st.session_state.current_customer, 0
                    if curr:
                        if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                        if curr['stars'] >= 9: 
                            c_items = [x for x in st.session_state.cart if x['is_coffee']]
                            if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                        if st.session_state.active_coupon:
                            cp_type = st.session_state.active_coupon['type']
                            if cp_type == '50_percent': coupon_disc = total * 0.5
                            elif cp_type == 'birthday_gift' and st.session_state.cart: coupon_disc = float(min(st.session_state.cart, key=lambda x: float(x['price']))['price'])

                    final = max(0, total - disc - coupon_disc)
                    st.markdown(f"<div style='font-size:24px; font-weight:bold; text-align:right; color:#2E7D32'>YEKUN: {final:.2f} ₼</div>", unsafe_allow_html=True)
                    if disc > 0: st.caption(f"Sadiqlik Endirimi: -{disc:.2f}")
                    if coupon_disc > 0: st.caption(f"Kupon Endirimi: -{coupon_disc:.2f}")
                    
                    pay_method = st.radio("Ödəniş:", ["Nəğd (Cash)", "Kart (Card)"], horizontal=True, key="pm")
                    if st.button("✅ TƏSDİQLƏ", type="primary", use_container_width=True, key="py"):
                        p_code = "Cash" if "Nəğd" in pay_method else "Card"
                        items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                        try:
                            with conn.session as s:
                                if curr:
                                    if curr['last_visit'] and (datetime.datetime.now() - curr['last_visit']) < datetime.timedelta(minutes=1): st.error("⚠️ Gözləyin! Rate Limit."); st.stop()
                                    ns = curr['stars']
                                    if coffs > 0:
                                        if curr['stars'] >= 9 and any(x['is_coffee'] for x in st.session_state.cart): ns = 0
                                        else: ns += 1
                                    s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                    if st.session_state.active_coupon: s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                                s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final, "p":p_code})
                                s.commit()
                            st.success("Uğurlu!"); st.session_state.cart = []; st.session_state.current_customer = None; st.session_state.active_coupon = None; time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Xəta: {e}")
                else: st.info("Səbət boşdur")

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "⚙️ Sazlamalar", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Aylıq Satış"); today = datetime.date.today(); sel_date = st.date_input("Ay Seçin", today); sel_month = sel_date.strftime("%Y-%m")
                sales = run_query("SELECT * FROM sales WHERE TO_CHAR(created_at, 'YYYY-MM') = :m ORDER BY created_at DESC", {"m": sel_month})
                if not sales.empty:
                    st.metric("Ümumi", f"{sales['total'].sum():.2f}")
                    st.dataframe(sales)
                else: st.info("Satış yoxdur.")
            
            with tabs[2]:
                st.markdown("### 📧 CRM və Kampaniya")
                
                # KAMPANIYA YARATMAQ PANELI
                with st.expander("📢 Yeni Kampaniya Yarat", expanded=True):
                    camp_name = st.text_input("Kampaniya Adı (Məs: Novruz Endirimi)")
                    camp_msg = st.text_area("Email Mətni")
                    if st.button("Siyahını Hazırla"):
                        if camp_name and camp_msg:
                            st.session_state.camp_mode = True
                            st.session_state.camp_data = {'subject': camp_name, 'body': camp_msg}
                            st.success("Aşağıdakı cədvəldən müştəriləri seçin!")
                        else: st.error("Məlumatları doldurun")

                st.divider()
                
                # TOPLU SEÇİM SİSTEMİ
                m_df = run_query("SELECT card_id, email, stars FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    # Session state-də seçim cədvəlini saxlamaq
                    if 'crm_selections' not in st.session_state:
                        st.session_state.crm_selections = [False] * len(m_df)
                    
                    # Hamısını Seç Düyməsi
                    c_all, c_none = st.columns(2)
                    if c_all.button("✅ Hamısını Seç"):
                        st.session_state.crm_selections = [True] * len(m_df)
                        st.rerun()
                    if c_none.button("❌ Sıfırla"):
                        st.session_state.crm_selections = [False] * len(m_df)
                        st.rerun()

                    # Data Editor
                    m_df['Seç'] = st.session_state.crm_selections
                    edited_df = st.data_editor(m_df, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, hide_index=True, use_container_width=True)
                    
                    # Göndərmə
                    if st.button("🚀 Kampaniyanı Başlat"):
                        if 'camp_data' in st.session_state:
                            sub = st.session_state.camp_data['subject']
                            bod = st.session_state.camp_data['body']
                            cnt = 0
                            for index, row in edited_df.iterrows():
                                if row['Seç']:
                                    send_email(row['email'], sub, bod)
                                    cnt+=1
                            st.success(f"{cnt} müştəriyə '{sub}' kampaniyası göndərildi!")
                        else:
                            st.error("Əvvəlcə yuxarıdan kampaniya yaradın!")

            with tabs[3]:
                with st.form("addm"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"): run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                st.dataframe(run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id"))
            
            with tabs[4]:
                st.markdown("### ⚙️ Dizayn və Ayarlar")
                
                with st.expander("🎨 POS Dizaynı (Tam Kontrol)", expanded=True):
                    c1, c2 = st.columns(2)
                    c_bg = c1.color_picker("Arxa Fon Rəngi", POS_BTN_BG)
                    c_txt = c2.color_picker("Yazı Rəngi", POS_BTN_TEXT)
                    
                    c3, c4 = st.columns(2)
                    b_h = c3.slider("Hündürlük (px)", 50, 200, int(POS_BTN_HEIGHT))
                    # Shape Selector
                    shape_opt = c4.radio("Forma", ["Kvadrat (Square)", "Yumru (Rounded)"])
                    b_radius = "0px" if "Kvadrat" in shape_opt else "12px"

                    st.markdown(f"""
                    <div style="margin: 20px 0;">
                        <button style="background-color:{c_bg}; color:{c_txt}; height:{b_h}px; border:none; border-radius:{b_radius}; width:100%; font-weight:bold;">
                            NÜMUNƏ DÜYMƏ<br>5.00 ₼
                        </button>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Dizaynı Yadda Saxla"):
                        set_config("pos_btn_bg", c_bg)
                        set_config("pos_btn_text", c_txt)
                        set_config("pos_btn_height", str(b_h))
                        set_config("pos_btn_shape", b_radius)
                        st.success("Yeniləndi! Sol menyudan 'Yenilə' basın.")

                with st.expander("🖼️ Logo və Ad"):
                    new_name = st.text_input("Mağaza Adı", value=SHOP_NAME)
                    uploaded_logo = st.file_uploader("Logo Yüklə", type=['png', 'jpg'])
                    if uploaded_logo and st.button("Logonu Saxla"):
                        logo_str = process_logo_upload(uploaded_logo)
                        if logo_str: set_config("shop_logo_base64", logo_str)
                    if st.button("Adı Saxla"): set_config("shop_name", new_name)

            with tabs[5]:
                st.write("Admin Tools")

            with tabs[6]:
                cnt = st.number_input("Say", 1, 50); is_th = st.checkbox("Termos?")
                if st.button("Yarat", key="gen"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    typ = "thermos" if is_th else "standard"
                    for i in ids: 
                        token = secrets.token_urlsafe(8)
                        run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":typ, "st":token})
                    
                    if cnt == 1:
                        qr_url = f"{APP_URL}/?id={ids[0]}&t={run_query('SELECT secret_token FROM customers WHERE card_id=:id', {'id':ids[0]}).iloc[0]['secret_token']}"
                        qr_img_data = generate_custom_qr(qr_url, ids[0])
                        st.image(BytesIO(qr_img_data), caption=f"ID: {ids[0]}", width=200)
                        st.download_button("⬇️ Yüklə", qr_img_data, f"{ids[0]}.png", "image/png")
        elif role == 'staff': render_pos()
