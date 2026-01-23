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

# --- INFRASTRUKTUR AYARLARI ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana POS", page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# === DİZAYN KODLARI (CSS & JS) ===
# ==========================================
st.markdown("""
    <script>
    function keepAlive() { var xhr = new XMLHttpRequest(); xhr.open("GET", "/", true); xhr.send(); }
    setInterval(keepAlive, 30000); 
    </script>

    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700&display=swap');
    
    #MainMenu, header, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .stApp { font-family: 'Oswald', sans-serif !important; background-color: #F4F6F8; }
    .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; max-width: 100%; }

    /* --- POS DÜYMƏLƏRİ (KLAVİATURA EFFEKTİ) --- */
    /* Məhsul Düymələri (Ağ/Narıcı) */
    div.stButton > button {
        background-color: white; 
        border: 1px solid #FF9800; 
        border-bottom: 4px solid #E65100; /* 3D Effect */
        color: #E65100 !important;
        font-weight: 700; border-radius: 12px; min-height: 80px; width: 100%; 
        transition: all 0.1s;
        margin-bottom: 5px;
    }
    div.stButton > button:active {
        transform: translateY(3px); 
        border-bottom: 1px solid #E65100;
        margin-bottom: 8px;
    }

    /* Kateqoriya Düymələri (Yaşıl) */
    button[kind="secondary"] {
        background-color: #2E7D32 !important; 
        color: white !important; 
        border: none;
        border-bottom: 4px solid #1B5E20 !important;
        border-radius: 10px;
        height: 50px !important;
        font-size: 18px !important;
    }
    button[kind="secondary"]:active {
        transform: translateY(3px);
        border-bottom: 1px solid #1B5E20 !important;
    }

    /* MÜŞTƏRİ EKRANI */
    .digital-card {
        background: white; border-radius: 20px; padding: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1); border: 2px solid #E8F5E9;
        text-align: center; margin-bottom: 15px;
    }
    .motivation-box {
        background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
        color: #E65100; padding: 15px; border-radius: 15px;
        font-size: 20px; font-weight: bold; text-align: center;
        border: 2px dashed #FFB74D; margin-bottom: 20px;
        font-family: 'Oswald', sans-serif;
    }
    
    .coffee-grid-container {
        display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 10px;
    }
    .coffee-icon { width: 45px; height: 45px; transition: all 0.3s ease; opacity: 0.3; filter: grayscale(100%); }
    .coffee-icon.active { opacity: 1; filter: none; }
    .gift-icon { width: 55px; height: 55px; filter: drop-shadow(0 0 5px gold); animation: pulse 1.5s infinite; }
    
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }

    /* CHECKBOX STİLİ */
    .stCheckbox label { font-size: 18px; font-weight: bold; color: #333; }

    .refresh-btn {
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        background: #D32F2F; color: white; border-radius: 50%;
        width: 50px; height: 50px; border: none; font-size: 24px;
        cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    </style>
    <button onclick="window.parent.location.reload();" class="refresh-btn" title="Yenilə">🔄</button>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("Database URL yoxdur!"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

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
    if uploaded_file:
        try:
            image = Image.open(uploaded_file)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except: return None
    return None

# --- RESEND EMAIL ---
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return False
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "from": f"{SHOP_NAME} <{DEFAULT_SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "reply_to": "taliyev.abbas84@gmail.com",
        "html": f"<div style='font-family:sans-serif; padding:20px; border:1px solid #ddd;'><h2>{SHOP_NAME}</h2><p>{body.replace(chr(10), '<br>')}</p></div>"
    }
    try: return requests.post(url, json=payload, headers=headers).status_code == 200
    except: return False

@st.cache_data
def generate_custom_qr(data, center_text):
    qr = qrcode.QRCode(box_size=10, border=2)
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

def get_motivation_quote():
    quotes = [
        "Gülüşün dünyanı dəyişə bilər! 😊", "Sən ən yaxşısına layiqsən! ✨", "Kofe ilə gün daha gözəldir! ☕",
        "Bu gün sənin günündür! 🚀", "Möcüzələrə inan! 🌟", "Pozitiv ol, həyat gözəldir! 🌈",
        "Enerjini topla və başla! 💪", "Uğur səninlə olsun! 💼", "Sevgi dolu bir gün arzular! ❤️",
        "Hər şey çox gözəl olacaq! 👍"
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
    "Bizimlə olduğun üçün təşəkkürlər! 🙏"
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
                    s.execute(text("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:cid, 'birthday_gift')"), {"cid": user[0]})
            s.execute(text("INSERT INTO settings (key, value) VALUES ('last_birthday_check', :val) ON CONFLICT (key) DO UPDATE SET value = :val"), {"val": today_str})
            s.commit()
    except: pass

if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = True
    threading.Thread(target=check_and_send_birthday_emails, daemon=True).start()

# --- BACKUP CLEANER ---
def clean_df_for_excel(df):
    for col in df.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]']).columns:
        df[col] = df[col].astype(str) # Convert datetimes to string to avoid TZ issues
    return df

# --- UI COMPONENTS ---
def render_header():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{SHOP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<div class='shop-info'>📍 {SHOP_ADDRESS}</div>", unsafe_allow_html=True)

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
                st.markdown("""<div style="height:100px; overflow-y:scroll; padding:10px; background:white; border:1px solid #ddd;">1. Məlumatlar məxfidir.<br>2. 9 ulduz = 1 hədiyyə.<br>3. Termosla gələnlərə endirim var.</div>""", unsafe_allow_html=True)
                agree = st.checkbox("Razıyam")
                if st.form_submit_button("Tamamla"):
                    if agree and em:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons(); st.rerun()
                    else: st.error("Qaydaları qəbul edin.")
            st.stop()

        # MOTIVATION
        st.markdown(f"<div class='motivation-box'>{get_motivation_quote()}</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="digital-card"><h3 style="margin-top:0; color:#2E7D32;">BALANS</h3><h1 style="color:#2E7D32; font-size: 56px; margin:0;">{user['stars']} / 10</h1></div>""", unsafe_allow_html=True)
        
        # 0/10 STARS LOGIC
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            if i == 9: # 10-cu stəkan (Index 9)
                icon = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png" # Hədiyyə qutusu
                cls = "gift-icon"
            else:
                icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
                cls = "coffee-icon"
            
            if i < user['stars']: cls += " active"
            html += f'<img src="{icon}" class="{cls}">'
        html += '</div>'; st.markdown(html, unsafe_allow_html=True)
        
        rem = 10 - user['stars']
        if rem <= 1: st.success("🎉 TƏBRİKLƏR! Növbəti Kofe Bizdən!")
        else: st.markdown(f"<div style='text-align:center; margin-top:15px; color:#777;'>🎁 Hədiyyəyə {rem} kofe qaldı!</div>", unsafe_allow_html=True)
        
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE", {"id": card_id})
        for _, cp in my_coupons.iterrows():
            name = "🎁 Hədiyyə"
            if cp['coupon_type'] == 'birthday_gift': name = "🎂 Ad Günü Hədiyyəsi!"
            st.markdown(f"<div style='background:#E8F5E9; padding:10px; border-radius:10px; text-align:center; color:#1B5E20; font-weight:bold; margin-top:10px;'>{name}</div>", unsafe_allow_html=True)

        st.divider()
        qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS & ADMIN ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if st.session_state.logged_in:
        st.markdown("""<a href="/" target="_self" class="refresh-btn" style="text-decoration:none; display:flex; align-items:center; justify-content:center;">🔄</a>""", unsafe_allow_html=True)

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
                        st.session_state.logged_in = True; st.session_state.role = udf.iloc[0]['role']; st.session_state.user = u; st.rerun()
                    else: st.error("Səhvdir!")
    else:
        role = st.session_state.role
        
        # --- POPUP HELPER ---
        @st.dialog("Ölçü Seçimi")
        def show_variant_selector(base_name, items):
            st.markdown(f"### {base_name}")
            cols = st.columns(len(items))
            for i, item in enumerate(items):
                label = item['item_name'].split()[-1] # S, M, L
                with cols[i]:
                    if st.button(f"{label}\n{item['price']}₼", key=f"v_{item['id']}", use_container_width=True):
                        st.session_state.cart.append(item)
                        st.rerun()

        def render_pos():
            layout_col1, layout_col2 = st.columns([1.2, 3]) 
            
            with layout_col1: # LEFT: CART
                st.markdown("<div style='background:#333; color:white; padding:10px; border-radius:5px; text-align:center; font-weight:bold;'>SƏBƏT</div>", unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1])
                scan_val = c1.text_input("QR", label_visibility="collapsed", placeholder="Müştəri...")
                if c2.button("🔍"):
                    if scan_val:
                        c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                        if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                
                curr = st.session_state.current_customer
                if curr:
                    st.success(f"{curr['card_id']} | ⭐ {curr['stars']}")
                    cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id": curr['card_id']})
                    if not cps.empty:
                        sel_cp = st.selectbox("Kupon:", ["Yox"] + [r['coupon_type'] for _, r in cps.iterrows()])
                        if sel_cp != "Yox": st.session_state.active_coupon = {"type": sel_cp, "id": cps[cps['coupon_type']==sel_cp].iloc[0]['id']}
                    if st.button("Ləğv Et"): st.session_state.current_customer = None; st.rerun()

                # Cart Items
                st.markdown("<div style='background:white; height:50vh; overflow-y:scroll; border:1px solid #ddd; padding:5px;'>", unsafe_allow_html=True)
                total = 0; coffs = 0
                if st.session_state.cart:
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([4, 2, 1])
                        c1.write(f"**{item['item_name']}**")
                        c2.write(f"{item['price']}")
                        if c3.button("✖", key=f"d_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price']); 
                        if item.get('is_coffee'): coffs += 1
                st.markdown("</div>", unsafe_allow_html=True)
                
                disc, coupon_disc = 0, 0
                if curr:
                    if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x.get('is_coffee')]) * 0.1
                    if curr['stars'] >= 9:
                        c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                        if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                    if st.session_state.active_coupon:
                        if st.session_state.active_coupon['type'] == '50_percent': coupon_disc = total * 0.5
                        elif st.session_state.active_coupon['type'] == 'birthday_gift': coupon_disc = float(min(st.session_state.cart, key=lambda x: float(x['price']))['price']) if st.session_state.cart else 0

                final = max(0, total - disc - coupon_disc)
                st.markdown(f"<div style='font-size:28px; font-weight:bold; text-align:right; color:#D32F2F;'>{final:.2f} ₼</div>", unsafe_allow_html=True)
                
                pay_m = st.radio("Metod:", ["Nəğd", "Kart"], horizontal=True)
                if st.button("ÖDƏNİŞ ET", type="primary", use_container_width=True):
                    if not st.session_state.cart: return
                    p_code = "Cash" if pay_m == "Nəğd" else "Card"
                    items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
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

            with layout_col2: # RIGHT: GRID
                # KATEQORIYA DÜYMƏLƏRİ (Yaşıl)
                c1, c2, c3 = st.columns(3)
                if c1.button("☕ Qəhvə", key="cat_c", type="secondary", use_container_width=True): st.session_state.pos_category = "Qəhvə"; st.rerun()
                if c2.button("🥤 İçkilər", key="cat_d", type="secondary", use_container_width=True): st.session_state.pos_category = "İçkilər"; st.rerun()
                if c3.button("🍰 Desert", key="cat_ds", type="secondary", use_container_width=True): st.session_state.pos_category = "Desert"; st.rerun()
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": st.session_state.pos_category})
                
                # GROUPING LOGIC
                groups = {}
                for idx, row in enumerate(menu_df.to_dict('records')):
                    name = row['item_name']
                    parts = name.split()
                    if parts[-1] in ['S', 'M', 'L']: base = " ".join(parts[:-1])
                    else: base = name
                    if base not in groups: groups[base] = []
                    groups[base].append(row)
                
                # RENDER BUTTONS
                cols = st.columns(4)
                for i, (base_name, items) in enumerate(groups.items()):
                    with cols[i % 4]:
                        if len(items) > 1:
                            if st.button(f"{base_name}\n(Seçim)", key=f"grp_{i}"):
                                show_variant_selector(base_name, items)
                        else:
                            item = items[0]
                            if st.button(f"{item['item_name']}\n{item['price']}₼", key=f"itm_{item['id']}"):
                                st.session_state.cart.append(item); st.rerun()

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "⚙️ Ayarlar", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Satış Analitikası")
                df = run_query("SELECT * FROM sales")
                if not df.empty:
                    df['created_at'] = pd.to_datetime(df['created_at'])
                    today_sales = df[df['created_at'].dt.date == datetime.date.today()]
                    m1, m2 = st.columns(2)
                    m1.metric("Bu gün", f"{today_sales['total'].sum():.2f} ₼")
                    m2.metric("Ümumi", f"{df['total'].sum():.2f} ₼")
                    
                    st.subheader("Son 7 Gün")
                    daily = df.groupby(df['created_at'].dt.date)['total'].sum().tail(7)
                    st.bar_chart(daily)
                    
                    with st.expander("Son 50 Əməliyyat"):
                        st.dataframe(df.sort_values('created_at', ascending=False).head(50))
            
            with tabs[2]:
                st.markdown("### 📧 CRM")
                st.info("💡 Hazır motivasiya cümləsi seçin və ya özünüz yazın.")
                
                target_group = st.radio("Kimə göndərilsin?", ["Hamıya", "Seçilmişlərə"], horizontal=True)
                
                sel_quote = st.selectbox("Motivasiya Seç:", ["(Özün Yaz)"] + CRM_QUOTES)
                custom_msg = st.text_area("Mesaj Mətni", value=sel_quote if sel_quote != "(Özün Yaz)" else "")
                
                m_df = run_query("SELECT card_id, email FROM customers WHERE email IS NOT NULL")
                recipients = []
                
                if target_group == "Seçilmişlərə":
                    m_df['Select'] = False
                    edited = st.data_editor(m_df, hide_index=True)
                    recipients = edited[edited['Select']]['email'].tolist()
                else:
                    recipients = m_df['email'].tolist()
                
                if st.button(f"🚀 Göndər ({len(recipients)} nəfər)"):
                    for em in recipients: send_email(em, "Emalatxana Coffee", custom_msg)
                    st.success("Göndərildi!")

            with tabs[3]:
                with st.form("add"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofe?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                st.dataframe(run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id"))

            with tabs[4]:
                st.markdown("### 👥 İşçi İdarəetməsi")
                users = run_query("SELECT username, role FROM users")
                st.dataframe(users)
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("Yeni İşçi")
                    nu=st.text_input("User"); np=st.text_input("Pass", type="password"); nr=st.selectbox("Rol", ["staff","admin"])
                    if st.button("Yarat"):
                        try: run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":nu, "p":hash_password(np), "r":nr}); st.success("OK"); st.rerun()
                        except: st.error("Xəta")
                with c2:
                    st.subheader("Sil")
                    du = st.selectbox("Silinəcək:", users['username'].tolist())
                    if st.button("Sil"):
                        if du!='admin': run_action("DELETE FROM users WHERE username=:u", {"u":du}); st.rerun()

            with tabs[5]:
                st.markdown("### 🛠️ Admin")
                if st.button("📥 BÜTÜN BAZANI YÜKLƏ (BACKUP)", type="primary"):
                    try:
                        out = BytesIO()
                        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                            clean_df_for_excel(run_query("SELECT * FROM customers")).to_excel(writer, sheet_name='Customers')
                            clean_df_for_excel(run_query("SELECT * FROM sales")).to_excel(writer, sheet_name='Sales')
                        st.download_button("⬇️ Endir", out.getvalue(), "Backup.xlsx")
                    except Exception as e: st.error(f"Xəta: {e}")

            with tabs[6]:
                cnt = st.number_input("Say", 1, 50)
                if st.button("QR Yarat"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    for i in ids: 
                        tkn = secrets.token_urlsafe(8)
                        run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, 'standard', :t)", {"i":i, "t":tkn})
                    st.success("Yarandı!")

        elif role == 'staff': render_pos()
