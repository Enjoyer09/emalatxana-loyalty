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

# --- INFRASTRUKTUR AYARLARI (IRONWAVES & RESEND) ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(
    page_title="Emalatxana POS", 
    page_icon="☕", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# === CSS & DİZAYN ===
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
    
    /* POS DÜYMƏLƏRİ */
    div.stButton > button {
        background-color: white; border: 2px solid #FF9800; color: #E65100 !important;
        font-weight: 700; border-radius: 12px; min-height: 80px; width: 100%; transition: 0.1s;
    }
    div.stButton > button:active { transform: translateY(3px); }
    div.stButton > button[kind="primary"] {
        background-color: #F1F8E9; border: 2px solid #2E7D32 !important;
        color: #2E7D32 !important; min-height: 60px !important;
    }
    
    /* KART DİZAYNI */
    .digital-card {
        background: white; border-radius: 20px; padding: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #eee;
        text-align: center; margin-bottom: 20px;
    }
    
    .coffee-grid-container {
        display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 20px;
    }
    .coffee-icon { width: 50px; height: 50px; transition: all 0.3s ease; }
    
    /* ANIMASIYALAR */
    .heartbeat-text {
        font-size: 20px; font-weight: bold; color: #D32F2F; text-align: center;
        animation: heartbeat 1.5s infinite; margin-top: 20px;
    }
    @keyframes heartbeat {
        0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); }
    }
    
    .coupon-alert {
        background-color: #E8F5E9; border: 2px dashed #2E7D32;
        padding: 15px; border-radius: 15px; text-align: center;
        color: #1B5E20; font-weight: bold; font-size: 20px;
        margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(46, 125, 50, 0); } 100% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0); } }

    .emergency-refresh {
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        background: #D32F2F; color: white; border-radius: 50%;
        width: 50px; height: 50px; border: none; font-size: 24px;
        cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    </style>
    <button onclick="window.parent.location.reload();" class="emergency-refresh" title="Yenilə">🔄</button>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION (FIXED) ---
try:
    # 1. URL-i ətraf mühitdən (Environment Variables) oxuyuruq
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    
    if not db_url:
        st.error("🚨 Verilənlər bazası URL-i tapılmadı! Railway Variables yoxlayın.")
        st.stop()
    
    # 2. SQLAlchemy uyğunluğu üçün düzəliş
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        
    # 3. Connection yaradarkən URL-i MÜTLƏQ arqument kimi ötürürük
    conn = st.connection("neon", type="sql", url=db_url)

except Exception as e:
    st.error(f"DB Error: {e}")
    st.stop()

# --- SCHEMA ---
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
        try:
            s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_feedback_star INTEGER DEFAULT -1;"))
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
    # NUMPY FIX: Bütün parametrləri yoxlayır və int-ə çevirir
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
            base_width = 200
            w_percent = (base_width / float(image.size[0]))
            h_size = int((float(image.size[1]) * float(w_percent)))
            image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except: return None
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
                st.markdown("### 📜 Qaydalar və Şərtlər")
                st.markdown("""
                <div style="height: 150px; overflow-y: scroll; background: #fff; padding: 10px; border: 1px solid #ccc; font-size: 14px;">
                    1. <b>Sadiqlik Proqramı:</b> Endirimlər və hədiyyələr üçündür.<br>
                    2. <b>Bonuslar:</b> 9 ulduz = 1 pulsuz kofe.<br>
                    3. <b>Məxfilik:</b> Məlumatlar üçüncü tərəflərlə paylaşılmır.<br>
                </div>
                """, unsafe_allow_html=True)
                agree = st.checkbox("Qaydalarla tanış oldum və razıyam")
                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    if agree and em:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons(); st.rerun()
                    else: st.error("Qaydaları qəbul edin.")
            st.stop()

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
        if not my_coupons.empty:
            for _, cp in my_coupons.iterrows():
                # Düzgün Kupon Adı
                name = "🎁 Xüsusi Hədiyyə"
                if cp['coupon_type'] == 'birthday_gift': name = "🎂 Ad Günü: 1 Pulsuz Kofe"
                elif cp['coupon_type'] == '50_percent': name = "🏷️ 50% Endirim Kuponu"
                elif cp['coupon_type'] == 'free_cookie': name = "🍪 Pulsuz Peceniya"
                
                st.markdown(f"<div class='coupon-alert'>{name}</div>", unsafe_allow_html=True)

        last_fb_star = int(user['last_feedback_star']) if user['last_feedback_star'] is not None else -1
        current_stars = int(user['stars'])
        
        st.divider(); st.markdown("<h4 style='text-align:center; color:#555'>💌 Bizim haqqımızda fikriniz</h4>", unsafe_allow_html=True)
        if last_fb_star < current_stars:
            with st.form("feed"):
                s = st.feedback("stars"); m = st.text_input("Şərhiniz")
                if st.form_submit_button("Rəy Göndər"):
                    if s is not None: 
                        run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                        run_action("UPDATE customers SET last_feedback_star = :s WHERE card_id = :i", {"s":int(current_stars), "i":card_id})
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
        st.markdown("""<a href="/" target="_self" class="emergency-refresh" style="background:#333; font-size:16px; width:100px; height:40px; border-radius:10px;">🔄 Yenilə</a>""", unsafe_allow_html=True)

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
                    if curr['stars'] >= 9:
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
                                    if ns >= 9 and any(x.get('is_coffee') for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                if st.session_state.active_coupon: s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                            s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final, "p":p_code})
                            s.commit()
                        st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Xəta: {e}")

            # --- SAĞ: GRID ---
            with layout_col2:
                cats = ["Qəhvə", "İçkilər", "Desert"]
                sel_cat = st.radio("Kateqoriya", cats, horizontal=True, label_visibility="collapsed")
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": sel_cat})
                
                cols = st.columns(4)
                for idx, row in enumerate(menu_df.to_dict('records')):
                    with cols[idx % 4]:
                        if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"p_{row['id']}", use_container_width=True):
                            st.session_state.cart.append(row); st.rerun()

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Satış")
                sales = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
                if not sales.empty:
                    st.metric("Cəm", f"{sales['total'].sum():.2f}")
                    st.dataframe(sales)
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
                with st.form("add"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofe?")
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
                
                # --- YENİLİK: İŞÇİ İDARƏETMƏSİ ---
                with st.expander("👥 İşçi İdarəetməsi (Staff Management)", expanded=True):
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
                if st.button("Backup Yüklə"):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        run_query("SELECT * FROM customers").to_excel(writer, sheet_name='Müştərilər', index=False)
                    st.download_button("⬇️ Endir", output.getvalue(), f"Backup.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
