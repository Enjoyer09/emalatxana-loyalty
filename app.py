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

st.set_page_config(page_title="IronWaves POS", page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("Database URL not found!"); st.stop()
    conn = st.connection("neon", type="sql", url=db_url.replace("postgres://", "postgresql+psycopg2://"), pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA FIX (AVTOMATİK DÜZƏLİŞ) ---
def fix_missing_columns():
    """Bazaya sonradan əlavə olunan sütunları yoxlayır və yaradır"""
    with conn.session as s:
        try:
            # last_feedback_star sütunu yoxdursa əlavə edir
            s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_feedback_star INTEGER DEFAULT -1;"))
            s.commit()
        except Exception:
            s.rollback()

def ensure_schema():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, last_feedback_star INTEGER DEFAULT -1);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS quotes (id SERIAL PRIMARY KEY, text TEXT);"))
        s.commit()

# İlk işə düşəndə bazanı yoxla və düzəlt
ensure_schema()
fix_missing_columns()

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

# --- EMAIL SYSTEM ---
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
# === CSS (POS & MÜŞTƏRİ DİZAYNI) ===
# ==========================================
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&display=swap');
    
    #MainMenu, header, footer {{ display: none !important; }}
    .stApp {{ font-family: 'Roboto', sans-serif !important; background-color: #E0E0E0; }}
    .block-container {{ padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 100%; }}

    /* --- POS DESIGN (VEND STYLE) --- */
    
    /* Düymə Stilləri */
    div[data-testid="column"] button {{
        height: 100px !important;
        width: 100% !important;
        border-radius: 4px !important;
        border: 1px solid rgba(0,0,0,0.1) !important;
        font-weight: bold !important;
        font-size: 16px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        transition: all 0.1s !important;
    }}
    div[data-testid="column"] button:active {{ transform: scale(0.98); }}

    /* Qəhvə Düymələri - Yaşıl */
    .coffee-btn button {{ background-color: #C8E6C9 !important; color: #2E7D32 !important; }}
    
    /* İçki Düymələri - Mavi/Bənövşəyi */
    .drink-btn button {{ background-color: #E1BEE7 !important; color: #4A148C !important; }}
    
    /* Desert Düymələri - Qırmızı/Çəhrayı */
    .desert-btn button {{ background-color: #FFCDD2 !important; color: #C62828 !important; }}

    /* Sol Tərəf - Çek Paneli */
    .cart-container {{
        background: white;
        border-right: 1px solid #ccc;
        height: 80vh;
        padding: 10px;
        display: flex;
        flex-direction: column;
    }}
    
    /* MÜŞTƏRİ EKRANI ELEMENTLƏRİ */
    .special-offer-card {{
        background: white;
        border: 2px solid #D32F2F;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 5px 15px rgba(211, 47, 47, 0.1);
    }}
    .offer-title {{
        color: #D32F2F;
        font-family: 'Playfair Display', serif;
        font-size: 32px;
        font-weight: 700;
        letter-spacing: 1px;
        margin: 0;
        text-transform: uppercase;
    }}
    .offer-subtitle {{
        color: #2E7D32;
        font-family: 'Dancing Script', cursive;
        font-size: 24px;
        margin-top: 5px;
    }}

    /* COFFEE GRID */
    .coffee-grid-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 20px; }}
    .coffee-icon {{ width: 40px; height: 40px; transition: all 0.3s ease; }}
    
    /* FEEDBACK */
    div[data-testid="stFeedback"] {{ transform: scale(2.0); margin: 20px auto; display: flex; justify-content: center; }}
    </style>
""", unsafe_allow_html=True)

# --- UI COMPONENTS ---
def render_header():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{SHOP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<div class='shop-info'>📍 {SHOP_ADDRESS}</div>", unsafe_allow_html=True)

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

        if not user['is_active']:
            st.warning(f"🎉 {SHOP_NAME}-a Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email"); dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                st.markdown("### 📜 Qaydalar və Şərtlər")
                st.markdown("""
                <div style="height: 150px; overflow-y: scroll; background: #f0f0f0; padding: 10px; border: 1px solid #ccc; font-size: 14px;">
                    1. <b>Sadiqlik Proqramı:</b> Endirimlər və hədiyyələr üçündür.<br>
                    2. <b>Bonuslar:</b> 9 ulduz = 1 pulsuz kofe.<br>
                    3. <b>Məxfilik:</b> Məlumatlar üçüncü tərəflərlə paylaşılmır.<br>
                    4. <b>Termos:</b> Termosla gələnlərə endirim var.
                </div>
                """, unsafe_allow_html=True)
                agree = st.checkbox("Qaydalarla razıyam")
                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    if agree and em:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons(); st.rerun()
                    else: st.error("Qaydaları qəbul edin.")
            st.stop()

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"📩 {row['message']}"); run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        st.markdown(f"<div style='text-align:center; color:#2E7D32; font-style:italic; margin-bottom:15px;'>✨ {get_random_quote_from_db()} ✨</div>", unsafe_allow_html=True)
        st.markdown(f"""<div style="background:white; border-radius:20px; padding:20px; text-align:center; box-shadow:0 4px 10px rgba(0,0,0,0.1);"><h3 style="margin-top:0">{SHOP_NAME} BONUS</h3><h1 style="color:#2E7D32; font-size: 48px; margin:0;">{user['stars']} / 9</h1><p style="color:#777">Balansınız</p></div>""", unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; style = "opacity: 1;" if i < user['stars'] else "opacity: 0.2; filter: grayscale(100%);"
            if i == 9: icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; style += " filter: hue-rotate(45deg);" 
            html += f'<img src="{icon}" class="coffee-icon" style="{style}">'
        html += '</div>'; st.markdown(html, unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.success("🎉 TƏBRİKLƏR! Pulsuz Kofeniz Hazırdır!")
        else: st.markdown(f"<div style='text-align:center; color:#E65100; font-weight:bold; margin-top:10px;'>❤️ Cəmi {rem} kofedən sonra qonağımızsan! ❤️</div>", unsafe_allow_html=True)
        
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE", {"id": card_id})
        for _, cp in my_coupons.iterrows():
            if cp['coupon_type'] == '50_percent':
                st.markdown(f"""
                <div class='special-offer-card'>
                    <p class='offer-title'>50% ENDİRİM</p>
                    <p class='offer-subtitle'>Bu gün sizə özəldir!</p>
                </div>
                """, unsafe_allow_html=True)
            else: st.info(f"🎁 Aktiv Kupon: {cp['coupon_type']}")

        # RƏY SİSTEMİ (DÜZƏLİŞLİ)
        last_fb_star = user['last_feedback_star'] if user['last_feedback_star'] is not None else -1
        current_stars = user['stars']
        
        st.divider(); st.markdown("<h4 style='text-align:center; color:#555'>💌 Bizim haqqımızda fikriniz</h4>", unsafe_allow_html=True)
        if last_fb_star < current_stars:
            with st.form("feed"):
                s = st.feedback("stars"); m = st.text_input("Şərhiniz")
                if st.form_submit_button("Rəy Göndər"):
                    if s is not None: 
                        run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                        run_action("UPDATE customers SET last_feedback_star = :s WHERE card_id = :i", {"s":current_stars, "i":card_id})
                        st.success("Təşəkkürlər!"); time.sleep(1); st.rerun()
        else: st.info("⭐ Rəy bildirdiyiniz üçün təşəkkürlər!")

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
        st.markdown("""<style>div.stButton > button:first-child { background-color: #333; color: white; border: none; }</style>""", unsafe_allow_html=True)
        if st.sidebar.button("🔄 Yenilə"): st.rerun()

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
        
        # --- NEW POS LAYOUT (VEND STYLE) ---
        def render_pos():
            # 2 Sütunlu Dizayn: Sol (Səbət), Sağ (Məhsullar)
            layout_col1, layout_col2 = st.columns([1.2, 3]) 
            
            # --- SOL TƏRƏF: SƏBƏT ---
            with layout_col1:
                st.markdown("<h3 style='text-align:center; background:#4CAF50; color:white; padding:10px; border-radius:5px;'>SATIŞ</h3>", unsafe_allow_html=True)
                
                # Müştəri Paneli
                c_scan, c_search = st.columns([2,1])
                scan_val = c_scan.text_input("QR Oxut", key="ps", label_visibility="collapsed", placeholder="Müştəri Kartı...")
                if c_search.button("🔍", key="psb"):
                    if scan_val:
                        c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                        if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.session_state.active_coupon = None; st.rerun()
                        else: st.error("Yoxdur")
                
                curr = st.session_state.current_customer
                if curr:
                    st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                    # Kupon Seçimi
                    cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id": curr['card_id']})
                    if not cps.empty:
                        cp_ops = {f"{r['coupon_type']}": r['id'] for _, r in cps.iterrows()}
                        sel_cp = st.selectbox("Kupon:", ["Yox"] + list(cp_ops.keys()))
                        if sel_cp != "Yox": st.session_state.active_coupon = {"id": cp_ops[sel_cp], "type": sel_cp}
                        else: st.session_state.active_coupon = None
                    if st.button("Ləğv Et", key="pcl"): st.session_state.current_customer = None; st.rerun()
                
                st.divider()
                
                # Səbət Listi
                total, coffs = 0, 0
                if st.session_state.cart:
                    for i, item in enumerate(st.session_state.cart):
                        cc1, cc2, cc3 = st.columns([4, 2, 1])
                        cc1.write(f"**{item['item_name']}**")
                        cc2.write(f"{item['price']}")
                        if cc3.button("✖", key=f"del_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price']); coffs += 1 if item['is_coffee'] else 0
                else:
                    st.info("Səbət boşdur")
                
                st.divider()
                
                # Hesablama
                disc, coupon_disc = 0, 0
                if curr:
                    if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                    if curr['stars'] >= 9:
                        c_items = [x for x in st.session_state.cart if x['is_coffee']]
                        if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                    if st.session_state.active_coupon:
                        if st.session_state.active_coupon['type'] == '50_percent': coupon_disc = total * 0.5
                        elif st.session_state.active_coupon['type'] == 'birthday_gift' and st.session_state.cart: coupon_disc = float(min(st.session_state.cart, key=lambda x: float(x['price']))['price'])

                final = max(0, total - disc - coupon_disc)
                
                st.markdown(f"<div style='font-size:20px; font-weight:bold; display:flex; justify-content:space-between;'><span>CƏM:</span> <span>{total:.2f}</span></div>", unsafe_allow_html=True)
                if disc > 0: st.markdown(f"<div style='color:green; display:flex; justify-content:space-between;'><span>Endirim:</span> <span>-{disc:.2f}</span></div>", unsafe_allow_html=True)
                if coupon_disc > 0: st.markdown(f"<div style='color:blue; display:flex; justify-content:space-between;'><span>Kupon:</span> <span>-{coupon_disc:.2f}</span></div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:32px; font-weight:bold; color:#D32F2F; text-align:right; margin-top:10px;'>{final:.2f} ₼</div>", unsafe_allow_html=True)

                # Ödəniş Düymələri
                pay_m = st.radio("Ödəniş:", ["Nəğd", "Kart"], horizontal=True, label_visibility="collapsed")
                
                b1, b2 = st.columns(2)
                if b1.button("TƏMİZLƏ (Void)", type="primary"): st.session_state.cart = []; st.rerun()
                if b2.button("ÖDƏNİŞ ET", type="secondary"): # Green style via CSS won't apply easily to secondary, keeping logic simple
                    if not st.session_state.cart: st.error("Səbət boşdur"); return
                    p_code = "Cash" if pay_m == "Nəğd" else "Card"
                    items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                    try:
                        with conn.session as s:
                            if curr:
                                ns = curr['stars']
                                if coffs > 0:
                                    if curr['stars'] >= 9 and any(x['is_coffee'] for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                if st.session_state.active_coupon: s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                            s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final, "p":p_code})
                            s.commit()
                        st.success("Satış Bitdi!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Xəta: {e}")

            # --- SAĞ TƏRƏF: MƏHSUL GRID ---
            with layout_col2:
                # Kateqoriyalar üçün Tabs
                cats = ["Qəhvə", "İçkilər", "Desert"]
                sel_cat = st.radio("Kateqoriya", cats, horizontal=True, label_visibility="collapsed")
                
                # Məhsulları Gətir
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": sel_cat})
                
                # Grid Yaradılması
                cols = st.columns(4) # 4 sütunlu grid
                for idx, row in enumerate(menu_df.to_dict('records')):
                    with cols[idx % 4]:
                        # Rəng təyini (Kateqoriyaya görə)
                        btn_class = "coffee-btn" if sel_cat == "Qəhvə" else "drink-btn" if sel_cat == "İçkilər" else "desert-btn"
                        
                        # Düyməni yaratmaq üçün div içinə alırıq (CSS tətbiqi üçün)
                        st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
                        if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"prod_{row['id']}"):
                            st.session_state.cart.append(row)
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)


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
                st.markdown("### 📧 CRM")
                with st.expander("📢 Yeni Kampaniya"):
                    camp_name = st.text_input("Mövzu"); camp_msg = st.text_area("Mətn")
                    if st.button("Hazırla"):
                        if camp_name: st.session_state.camp_data = {'subject': camp_name, 'body': camp_msg}; st.success("Hazırdır, aşağıdan seçin.")
                
                m_df = run_query("SELECT card_id, email, stars FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    if 'crm_selections' not in st.session_state: st.session_state.crm_selections = [False] * len(m_df)
                    c_all, c_none = st.columns(2)
                    if c_all.button("✅ Hamısını Seç"): st.session_state.crm_selections = [True] * len(m_df); st.rerun()
                    if c_none.button("❌ Sıfırla"): st.session_state.crm_selections = [False] * len(m_df); st.rerun()
                    
                    m_df['Seç'] = st.session_state.crm_selections
                    edited_df = st.data_editor(m_df, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, hide_index=True, use_container_width=True)
                    
                    if st.button("🚀 Göndər"):
                        if 'camp_data' in st.session_state:
                            sub = st.session_state.camp_data['subject']; bod = st.session_state.camp_data['body']; cnt = 0
                            for index, row in edited_df.iterrows():
                                if row['Seç']: send_email(row['email'], sub, bod); cnt+=1
                            st.success(f"{cnt} email göndərildi!")
                        else: st.error("Kampaniya yaradın")

            with tabs[3]:
                with st.form("addm"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"): run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                st.dataframe(run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id"))
            
            with tabs[4]:
                st.markdown("### ⚙️ Ayarlar")
                with st.expander("🖼️ Logo və Ad"):
                    new_name = st.text_input("Mağaza Adı", value=SHOP_NAME)
                    uploaded_logo = st.file_uploader("Logo Yüklə", type=['png', 'jpg'])
                    if uploaded_logo and st.button("Logonu Saxla"):
                        logo_str = process_logo_upload(uploaded_logo)
                        if logo_str: set_config("shop_logo_base64", logo_str)
                    if st.button("Adı Saxla"): set_config("shop_name", new_name)

            with tabs[5]:
                st.markdown("### 👥 İstifadəçi İdarəetməsi")
                users_df = run_query("SELECT username, role FROM users")
                st.dataframe(users_df)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("Yeni İstifadəçi")
                    nu = st.text_input("User"); np = st.text_input("Pass", type="password"); nr = st.selectbox("Role", ["staff", "admin"])
                    if st.button("Yarat"):
                        try: run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":nu, "p":hash_password(np), "r":nr}); st.success("OK"); time.sleep(1); st.rerun()
                        except: st.error("Xəta")
                with c2:
                    st.subheader("Sil / Dəyiş")
                    tu = st.selectbox("Seç", users_df['username'].tolist())
                    if st.button("Sil"):
                        if tu!='admin': run_action("DELETE FROM users WHERE username=:u", {"u":tu}); st.rerun()
                    np2 = st.text_input("Yeni Pass", type="password")
                    if st.button("Şifrəni Dəyiş"):
                         run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(np2), "u":tu}); st.success("OK")

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
                        st.image(BytesIO(qr_img_data), width=200); st.download_button("⬇️ Yüklə", qr_img_data, f"{ids[0]}.png", "image/png")
        elif role == 'staff': render_pos()
