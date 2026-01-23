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

# --- EMAIL AYARLARI ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = "info@emalatxana.az" 
SENDER_NAME = "Emalatxana Coffee"
APP_URL = "https://emalatxana-loyalty-production.up.railway.app" 

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(
    page_title="Emalatxana POS", 
    page_icon="☕", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# === DİZAYN KODLARI & CSS ===
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
    .block-container { padding-top: 0rem !important; padding-bottom: 2rem !important; max-width: 100%; }

    /* --- POS GRID SISTEMI (VEND STYLE) --- */
    .pos-btn-container {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        padding: 10px;
    }
    
    .pos-btn {
        border: none;
        color: white;
        padding: 15px;
        text-align: center;
        text-decoration: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
        border-radius: 4px;
        height: 100px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: transform 0.1s;
    }
    .pos-btn:active { transform: scale(0.98); }
    
    /* Kateqoriya Rəngləri */
    .btn-coffee { background-color: #81C784; color: #1B5E20; } /* Yaşıl */
    .btn-drinks { background-color: #9575CD; color: #311B92; } /* Bənövşəyi */
    .btn-desert { background-color: #E57373; color: #B71C1C; } /* Qırmızı */
    
    /* CART STYLES */
    .cart-container {
        background-color: white;
        border-right: 2px solid #eee;
        height: 85vh;
        padding: 15px;
        display: flex;
        flex-direction: column;
    }
    .cart-item {
        display: flex;
        justify-content: space-between;
        padding: 10px 0;
        border-bottom: 1px solid #eee;
        font-size: 16px;
    }
    .cart-total {
        margin-top: auto;
        border-top: 2px solid #333;
        padding-top: 15px;
        font-size: 24px;
        font-weight: bold;
        text-align: right;
        color: #D32F2F;
    }

    /* CUSTOMER SCREEN STYLES */
    .digital-card {
        background: white; border-radius: 25px; padding: 20px;
        box-shadow: 0 10px 40px rgba(46, 125, 50, 0.1); border: 2px solid #E8F5E9;
        margin-bottom: 25px; text-align: center;
    }
    .heartbeat-text {
        color: #D32F2F !important; font-weight: bold; font-size: 22px;
        margin-top: 15px; text-align: center; animation: pulse-text 1.2s infinite;
    }
    @keyframes pulse-text { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }

    .coffee-grid-container {
        display: grid; grid-template-columns: repeat(5, 1fr); 
        gap: 8px; justify-items: center; margin-top: 15px;
    }
    .coffee-icon { width: 100%; max-width: 65px; transition: transform 0.2s; }
    
    .emergency-refresh {
        position: fixed; bottom: 20px; right: 20px; z-index: 99999;
        background-color: #D32F2F; color: white; border: none;
        border-radius: 50%; width: 60px; height: 60px; font-size: 30px;
        cursor: pointer; display: flex; align-items: center; justify-content: center;
    }
    </style>
    
    <button onclick="window.parent.location.reload();" class="emergency-refresh" title="Yenilə">🔄</button>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("URL yoxdur!"); st.stop()
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://")
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA ---
def ensure_schema_and_seed():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, last_feedback_star INTEGER DEFAULT -1);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT);"))
        s.commit()
ensure_schema_and_seed()

# --- HELPERS ---
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h

def run_query(q, p=None): 
    try: return conn.query(q, params=p, ttl=0)
    except: return pd.DataFrame()

def run_action(q, p=None):
    try:
        with conn.session as s: s.execute(text(q), p); s.commit()
        return True
    except: return False

def send_email(to_email, subject, body):
    if not BREVO_API_KEY: return False 
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": SENDER_NAME, "email": SENDER_EMAIL}, "to": [{"email": to_email}], "subject": subject, "textContent": body}
    try: return requests.post(url, json=payload, headers=headers).status_code == 201
    except: return False

@st.cache_data(persist="disk")
def generate_custom_qr(url_data, center_text):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url_data); qr.make(fit=True)
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
    return random.choice(["Bu gün əla görünürsən! 🧡", "Enerjini bərpa etmək vaxtıdır! ⚡", "Sən ən yaxşısına layiqsən! ✨", "Kofe ilə gün daha gözəldir! ☀️", "Gülüşün dünyanı dəyişə bilər! 😊"])

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
                send_email(user[1], "🎉 Ad Günün Mübarək!", "Sənə 1 pulsuz kofe hədiyyə!")
                s.execute(text("INSERT INTO notifications (card_id, message) VALUES (:cid, '🎂 Ad Günün Mübarək!')"), {"cid": user[0]})
                s.execute(text("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:cid, 'birthday_gift')"), {"cid": user[0]})
            s.execute(text("INSERT INTO settings (key, value) VALUES ('last_birthday_check', :val) ON CONFLICT (key) DO UPDATE SET value = :val"), {"val": today_str})
            s.commit()
    except: pass

if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = True
    threading.Thread(target=check_and_send_birthday_emails, daemon=True).start()

# --- POPUP DIALOGS ---
@st.dialog("⚠️ TƏSDİQLƏ")
def confirm_delete(card_id):
    st.write(f"**{card_id}** silinsin?")
    if st.button("Bəli, Sil", type="primary"):
        run_action("DELETE FROM customers WHERE card_id=:id", {"id":card_id}); st.rerun()

@st.dialog("📥 BACKUP")
def confirm_backup():
    if st.button("Yüklə", type="primary"):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            run_query("SELECT * FROM customers").to_excel(writer, sheet_name='Müştərilər', index=False)
            run_query("SELECT * FROM sales").to_excel(writer, sheet_name='Satışlar', index=False)
        st.download_button("⬇️ Endir", output.getvalue(), f"Backup.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
    c1, c2, c3 = st.columns([1,2,1]); 
    with c2: st.image("emalatxana.png", width=180) # Logo faylı varsa
    
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and user['secret_token'] != token: st.error("⛔ İcazəsiz Giriş!"); st.stop()

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for i, row in notifs.iterrows():
            st.info(f"📩 {row['message']}")
            run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        if not user['is_active']:
            st.warning("🎉 KARTI AKTİVLƏŞDİRİN")
            with st.form("act"):
                em = st.text_input("📧 Email")
                dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                st.markdown("### 📜 Qaydalar"); st.info("1. Məlumatlar məxfidir.\n2. 9 Ulduz = 1 Hədiyyə.")
                if st.form_submit_button("Təsdiq") and em:
                    run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                    st.balloons(); st.rerun()
            st.stop()

        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        st.markdown(f"<div class='inner-motivation'>{get_random_quote()}</div>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:center; margin:0; color:#2E7D32'>BALANS: {user['stars']}/10</h2>", unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            style = "opacity: 1;" if i < user['stars'] else "opacity: 0.2; filter: grayscale(100%);"
            if i == user['stars']: style = "opacity: 0.8; animation: pulse-text 1s infinite;"
            html += f'<img src="{icon}" class="coffee-icon" style="{style}">'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.markdown("<h3 style='text-align:center; color:#E65100 !important;'>🎉 TƏBRİKLƏR! 10-cu Kofe Bizdən!</h3>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='heartbeat-text'>❤️ Cəmi {rem} kofedən sonra qonağımızsan! ❤️</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE", {"id": card_id})
        if not my_coupons.empty: st.markdown(f"<div class='coupon-alert'>🎁 {len(my_coupons)} aktiv kuponunuz var!</div>", unsafe_allow_html=True)

        # FEEDBACK FIX (INT CASTING)
        last_fb_star = int(user['last_feedback_star']) if user['last_feedback_star'] is not None else -1
        current_stars = int(user['stars'])

        st.divider(); st.markdown("<h4 style='text-align:center; color:#2E7D32'>💌 Rəy Bildir</h4>", unsafe_allow_html=True)
        if last_fb_star < current_stars:
            with st.form("feed"):
                s = st.feedback("stars")
                m = st.text_input("Fikriniz")
                if st.form_submit_button("Göndər"):
                    if s is not None:
                        run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                        # BUG FIX: cast current_stars to int explicitly
                        run_action("UPDATE customers SET last_feedback_star = :s WHERE card_id = :i", {"s": int(current_stars), "i":card_id})
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
        if st.sidebar.button("🔄 Yenilə"): st.rerun()

    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1]); 
        with c2: 
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
        
        # --- POS RENDER (VEND STYLE SPLIT) ---
        def render_pos():
            # 2 SÜTUNLU LAYOUT: SOL=CART, SAĞ=GRID
            col_cart, col_grid = st.columns([1.2, 3], gap="medium")
            
            # --- SOL: CART ---
            with col_cart:
                st.markdown("<div style='background:#333; color:white; padding:10px; text-align:center; font-weight:bold;'>SƏBƏT</div>", unsafe_allow_html=True)
                
                # MÜŞTƏRİ AXTARIŞI
                c1, c2 = st.columns([3, 1])
                scan_val = c1.text_input("QR", label_visibility="collapsed", placeholder="Müştəri...")
                if c2.button("🔍"):
                    if scan_val:
                        c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                        if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                
                curr = st.session_state.current_customer
                if curr:
                    st.success(f"{curr['card_id']} | ⭐ {curr['stars']}")
                    if st.button("Ləğv Et"): st.session_state.current_customer = None; st.rerun()

                # SƏBƏT ELEMENTLƏRİ
                st.markdown("<div class='cart-container'>", unsafe_allow_html=True)
                total = 0; coffs = 0
                if st.session_state.cart:
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([4, 2, 1])
                        c1.write(item['item_name'])
                        c2.write(f"{item['price']}")
                        if c3.button("x", key=f"d_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price'])
                        if item.get('is_coffee', False): coffs += 1
                else: st.info("Boşdur")
                st.markdown("</div>", unsafe_allow_html=True)

                # HESABLAMA & ÖDƏNİŞ
                disc = 0
                if curr:
                    if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x.get('is_coffee')]) * 0.2
                    if curr['stars'] >= 9:
                        c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                        if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                
                final = max(0, total - disc)
                st.markdown(f"<div class='cart-total'>{final:.2f} ₼</div>", unsafe_allow_html=True)
                
                pay_m = st.radio("Metod:", ["Nəğd", "Kart"], horizontal=True, label_visibility="collapsed")
                if st.button("ÖDƏNİŞ ET (PAY)", type="primary", use_container_width=True):
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
                            s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final, "p":p_code})
                            s.commit()
                        st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()
                    except: st.error("Xəta")

            # --- SAĞ: GRID ---
            with col_grid:
                cats = ["Qəhvə", "İçkilər", "Desert"]
                sel_cat = st.radio("Kateqoriya", cats, horizontal=True, label_visibility="collapsed")
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": sel_cat})
                
                # GRID RENDER (HTML/CSS Buttons)
                cols = st.columns(4)
                for idx, row in enumerate(menu_df.to_dict('records')):
                    with cols[idx % 4]:
                        color_class = "btn-coffee" if sel_cat == "Qəhvə" else "btn-drinks" if sel_cat == "İçkilər" else "btn-desert"
                        if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"p_{row['id']}", use_container_width=True):
                            st.session_state.cart.append(row); st.rerun()
                        # Stil tətbiqi (Button key-ə görə)
                        st.markdown(f"""<style>div[data-testid="column"] button:nth-of-type(1) {{ 
                            background-color: {'#C8E6C9' if sel_cat=='Qəhvə' else '#D1C4E9' if sel_cat=='İçkilər' else '#FFCDD2'} !important;
                            color: black !important; border: 1px solid #ccc; height: 80px; font-weight: bold;
                        }}</style>""", unsafe_allow_html=True)

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Satış")
                sales = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
                if not sales.empty:
                    st.metric("Cəm", f"{sales['total'].sum():.2f}")
                    st.dataframe(sales)
            with tabs[2]:
                st.markdown("### 📧 CRM")
                if st.button("Toplu Email Göndər"):
                    ids = run_query("SELECT email FROM customers WHERE email IS NOT NULL")
                    for _, r in ids.iterrows(): send_email(r['email'], "Endirim", "Sizə özəl!")
                    st.success("Göndərildi!")
            with tabs[3]:
                with st.form("add"):
                    n=st.text_input("Ad"); p=st.number_input("Qiymət"); c=st.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofe?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                st.dataframe(run_query("SELECT * FROM menu"))
            with tabs[4]:
                st.markdown("### ⚙️ Ayarlar")
                if st.button("Backup Yüklə"): confirm_backup()
                with st.expander("İstifadəçilər"):
                    us = run_query("SELECT username FROM users")
                    st.dataframe(us)
                    nu=st.text_input("User"); np=st.text_input("Pass", type="password"); nr=st.selectbox("Rol", ["staff","admin"])
                    if st.button("Yarat"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)", {"u":nu, "p":hash_password(np), "r":nr}); st.rerun()
            with tabs[5]:
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
