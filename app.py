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

# ==========================================
# === IRONWAVES POS - VERSION 1.2.2 (SECURE LAB) ===
# ==========================================

# --- CONFIG ---
# 🔐 LABORATORİYA ÜÇÜN XÜSUSİ ŞİFRƏ (BUNU DƏYİŞƏ BİLƏRSİNİZ)
V2_LAB_PASSWORD = "iron2026" 

st.set_page_config(page_title="Ironwaves POS", page_icon="☕", layout="wide", initial_sidebar_state="expanded")

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("DB URL not found!"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- INFRASTRUKTUR AYARLARI ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

# --- STYLES ---
st.markdown("""
    <script>
    function keepAlive() { fetch("/"); }
    setInterval(keepAlive, 30000); 
    </script>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    #MainMenu, header, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .stApp { font-family: 'Oswald', sans-serif !important; background-color: #FAFAFA; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; }
    
    /* POS Buttons */
    div.stButton > button { border-radius: 12px !important; font-weight: bold !important; height: 60px !important; }
    div.stButton > button[kind="secondary"] { border: 2px solid #2E7D32; color: #2E7D32; background: white; }
    div.stButton > button[kind="primary"] { background: #D32F2F; color: white; border: none; }
    
    /* Customer Screen */
    .digital-card { background: white; border-radius: 20px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center; }
    .thermos-vip { background: linear-gradient(135deg, #2E7D32, #66BB6A); color: white; padding: 15px; border-radius: 15px; text-align: center; margin-bottom: 15px; }
    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; justify-items: center; margin-top: 20px; }
    .coffee-icon { width: 45px; height: 45px; transition: all 0.3s ease; }
    .gift-box-anim { width: 60px; height: 60px; animation: bounce 2s infinite; }
    @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-10px);} }
    
    /* Status Dots */
    .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
    .status-online { background-color: #4CAF50; box-shadow: 0 0 5px #4CAF50; }
    .status-offline { background-color: #BDBDBD; }
    </style>
""", unsafe_allow_html=True)

# --- HELPERS ---
def run_query(q, p=None): return conn.query(q, params=p, ttl=0)
def run_action(q, p=None): 
    with conn.session as s: s.execute(text(q), p if p else {}); s.commit()

def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): 
    try: return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
    except: return False

def get_config(key, default=""):
    try:
        df = conn.query("SELECT value FROM settings WHERE key = :k", params={"k": key})
        return df.iloc[0]['value'] if not df.empty else default
    except: return default

def set_config(key, value):
    run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = :v", {"k": key, "v": value})
    st.cache_data.clear()

SHOP_NAME = get_config("shop_name", "Emalatxana Coffee")
SHOP_ADDRESS = get_config("shop_address", "Bakı şəhəri")
INSTAGRAM_LINK = get_config("instagram_link", "https://instagram.com")
LOGO_BASE64 = get_config("shop_logo_base64", "")

def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return False
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    payload = {"from": f"{SHOP_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}
    try: return requests.post(url, json=payload, headers=headers).status_code == 200
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

# --- SCHEMA CHECK ---
def ensure_schema():
    with conn.session as s:
        # V1 Tables
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        # V2 Tables (Inventory)
        s.execute(text("CREATE TABLE IF NOT EXISTS inventory (id SERIAL PRIMARY KEY, name TEXT NOT NULL, unit TEXT NOT NULL, stock_level DECIMAL(10,3) DEFAULT 0, cost_per_unit DECIMAL(10,2) DEFAULT 0, alert_limit DECIMAL(10,3) DEFAULT 5, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS recipes (id SERIAL PRIMARY KEY, menu_item_id INTEGER, item_name_cached TEXT, inventory_item_id INTEGER, quantity_required DECIMAL(10,3));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, description TEXT, amount DECIMAL(10,2), category TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_by TEXT);"))
        
        # Migrations
        try: s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender TEXT;"))
        except: pass
        try: s.execute(text("ALTER TABLE customer_coupons ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;"))
        except: pass
        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS cashier TEXT;"))
        except: pass
        try: s.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP;"))
        except: pass
        s.commit()
ensure_schema()

# --- APP LOGIC ---

# 1. CUSTOMER SCREEN CHECK
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]
    token = query_params.get("t")
    
    # Header
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        if LOGO_BASE64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{LOGO_BASE64}" width="150"></div>', unsafe_allow_html=True)
        else: st.markdown(f"<h1 style='text-align:center; color:#2E7D32'>{SHOP_NAME}</h1>", unsafe_allow_html=True)

    try: df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    except: st.stop()

    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token:
            st.warning("⚠️ QR kod köhnəlib. Xahiş olunur kassadan yeni QR istəyin.")

        # Notifications
        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        for _, row in notifs.iterrows():
            st.info(f"📩 {row['message']}"); run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        # Registration
        if not user['is_active']:
            st.warning(f"🎉 {SHOP_NAME}-a Xoş Gəldiniz!")
            with st.form("act"):
                em = st.text_input("📧 Email")
                dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                gender = st.radio("Cinsiyyət:", ["Kişi", "Qadın", "Qeyd etmirəm"], horizontal=True)
                
                with st.expander("📜 Qaydalar və İstifadəçi Razılaşması"):
                    st.markdown(f"""
                    <div style="font-size:14px; color:#333; line-height: 1.6;">
                        <b>1. Sadiqlik Proqramı:</b> Bu rəqəmsal kartla həyata keçirilən hər kofe alış-verişi zamanı bonus (ulduz) toplayır və eksklüziv hədiyyələr əldə edirsiniz.<br>
                        <b>2. Bonus Hesablanması:</b> Hər <b>tam qiymətli</b> (endirimsiz) kofe alışı = 1 Ulduz. Endirimli, kampaniya çərçivəsində və ya kuponla alınan məhsullarda ulduz hesablanmır.<br>
                        <b>3. Hədiyyə Sistemi:</b> Balansda 9 ulduz toplandıqda, növbəti kofe "Emalatxana" tərəfindən ödənişsiz (HƏDİYYƏ) təqdim olunur. ☕<br>
                        <b>4. EKO-TERM Klubu:</b> "Emalatxana" termosu əldə edən müştərilərə ilk kofe hədiyyə edilir. Növbəti ziyarətlərdə termosun üzərindəki QR kodu skan etdikdə, bütün kofe sifarişlərinə <b>daimi 20% ekoloji endirim</b> tətbiq olunur.<br>
                        <b>5. Ağıllı Endirim Siyasəti:</b> Eyni anda bir neçə endirim imkanı mövcud olduqda, sistem avtomatik alqoritm vasitəsilə <b>Müştəri üçün ən sərfəli olan (ən yüksək endirimli)</b> variantı seçir və tətbiq edir.<br>
                        <b>6. Məxfilik Siyasəti:</b> İstifadəçinin şəxsi məlumatları yalnız fərdi kampaniyalar üçün istifadə olunur. Üçüncü tərəflərə ötürülməsi qadağandır. İstifadəçi istənilən vaxt məlumatlarının silinməsini tələb edə bilər.<br><br>
                        <b>7. Kuponlar:</b> Kampaniya kuponları <b>7 gün</b>, Ad Günü hədiyyəsi isə <b>1 gün</b> keçərlidir. Ad günü hədiyyəsi üçün şəxsiyyət vəsiqəsi tələb edilə bilər.<br>
                    </div>
                    """, unsafe_allow_html=True)
                
                agree = st.checkbox("Qaydalarla tanış oldum və razıyam")
                if st.form_submit_button("Qeydiyyatı Tamamla"):
                    if agree and em:
                        g_code = "M" if gender=="Kişi" else "F" if gender=="Qadın" else "U"
                        run_action("UPDATE customers SET email=:e, birth_date=:b, gender=:g, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "g":g_code, "i":card_id})
                        st.balloons(); st.rerun()
                    else: st.error("Email yazın və qaydaları qəbul edin.")
            st.stop()

        # Dashboard
        if user['type'] == 'thermos': st.markdown("""<div class="thermos-vip"><div class="thermos-title">♻️ EKO-TERM KLUBU (VIP) ♻️</div></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="digital-card"><h1 style="color:#2E7D32; font-size: 48px; margin:0;">{user['stars']} / 10</h1><p>Balansınız</p></div>""", unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/3209/3209955.png" if i==9 else "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            cls = "gift-box-anim" if i==9 and user['stars']>=9 else "coffee-icon"
            style = "opacity: 1;" if i < user['stars'] or (i==9 and user['stars']>=9) else "opacity: 0.2; filter: grayscale(100%);"
            html += f'<img src="{icon}" class="{cls}" style="{style}">'
        st.markdown(html + '</div>', unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.markdown("<div class='progress-text' style='margin-top:20px; text-align:center; color:#D32F2F;'>🎉 TƏBRİKLƏR! Növbəti Kofe Bizdən!</div>", unsafe_allow_html=True)
        
        # Coupons
        cps = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": card_id})
        for _, cp in cps.iterrows():
            name = "🎁 Xüsusi Kupon"
            if cp['coupon_type'] == 'disc_20': name = "🏷️ 20% Endirim"
            elif cp['coupon_type'] == 'disc_100_coffee': name = "🎂 Ad Günü: 1 Pulsuz Kofe"
            elif cp['coupon_type'] == 'thermos_welcome': name = "♻️ Xoşgəldin: İLK KOFE BİZDƏN!"
            st.success(name)

        # Feedback
        with st.form("feed"):
            s = st.feedback("stars"); m = st.text_input("Rəyiniz")
            if st.form_submit_button("Göndər") and s:
                run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                st.success("Təşəkkürlər!")
        
        st.divider()
        qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")
    st.stop() # Stop here for customer screen

# 2. ADMIN/STAFF SCREEN
else:
    # --- SIDEBAR & AUTH ---
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    # Mode Selector (HIDDEN FOR STAFF)
    if st.session_state.logged_in:
        if st.session_state.role == 'admin':
            app_mode = st.sidebar.selectbox("Rejim Seçimi", ["POS (Satış)", "🧪 V2 Anbar (Alpha)"])
        else:
            app_mode = "POS (Satış)" # Staff avtomatik POS-a gedir
        
        st.sidebar.markdown(f"👤 **{st.session_state.user}**")
        if st.sidebar.button("Çıxış"):
            run_action("DELETE FROM active_sessions WHERE token=:t", {"t":st.query_params.get("token")})
            st.session_state.logged_in = False; st.query_params.clear(); st.rerun()
            
        # Online Status
        try:
            run_action("UPDATE users SET last_seen = NOW() WHERE username = :u", {"u": st.session_state.user})
            st.sidebar.divider()
            st.sidebar.markdown("### 👥 Personal")
            stats = run_query("SELECT username, last_seen FROM users ORDER BY username")
            for _, u in stats.iterrows():
                is_on = (datetime.datetime.now() - pd.to_datetime(u['last_seen'])).total_seconds() < 120 if u['last_seen'] else False
                st.sidebar.markdown(f"<span class='status-dot {'status-online' if is_on else 'status-offline'}'></span> {u['username']}", unsafe_allow_html=True)
        except: pass
    
    # --- LOGIN LOGIC ---
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1])
        with c2:
            st.markdown(f"<h2 style='text-align:center'>{SHOP_NAME}</h2>", unsafe_allow_html=True)
            tabs = st.tabs(["STAFF (PIN)", "ADMIN"])
            with tabs[0]:
                pin = st.text_input("PIN", type="password", key="p1")
                if st.button("Giriş", key="b1", use_container_width=True):
                    u = run_query("SELECT * FROM users WHERE role='staff'")
                    for _, r in u.iterrows():
                        if verify_password(pin, r['password']):
                            st.session_state.logged_in = True; st.session_state.user = r['username']; st.session_state.role = 'staff'
                            st.rerun()
            with tabs[1]:
                u = st.text_input("Username"); p = st.text_input("Password", type="password")
                if st.button("Admin Giriş", key="b2", use_container_width=True):
                    ud = run_query("SELECT * FROM users WHERE role='admin' AND LOWER(username)=LOWER(:u)", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in = True; st.session_state.user = u; st.session_state.role = 'admin'
                        st.rerun()
        st.stop()

    # --- APP CONTENT BASED ON MODE ---
    
    # >>> MODE 1: POS (V1.1.2) <<<
    if app_mode == "POS (Satış)":
        if 'cart' not in st.session_state: st.session_state.cart = []
        if 'current_customer' not in st.session_state: st.session_state.current_customer = None
        if 'pos_category' not in st.session_state: st.session_state.pos_category = "Qəhvə"
        if 'active_coupon' not in st.session_state: st.session_state.active_coupon = None
        
        def render_pos_ui():
            lc, rc = st.columns([1.2, 3])
            with lc: # Cart
                st.markdown("<h3 style='background:#4CAF50; color:white; padding:10px; border-radius:5px; text-align:center;'>SATIŞ</h3>", unsafe_allow_html=True)
                with st.form("qr"):
                    q = st.text_input("QR Skan", placeholder="Skan et...", key="qr_in")
                    if st.form_submit_button("Axtar") and q:
                        clean = q.strip().split("id=")[1].split("&")[0] if "id=" in q else q.strip()
                        c = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":clean})
                        if not c.empty: st.session_state.current_customer = c.iloc[0].to_dict()
                        else: st.error("Tapılmadı")
                
                curr = st.session_state.current_customer
                if curr:
                    st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                    # Coupon logic
                    cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE AND (expires_at IS NULL OR expires_at > NOW())", {"id": curr['card_id']})
                    if not cps.empty:
                         cp_ops = {f"{r['coupon_type']}": r['id'] for _, r in cps.iterrows()}
                         sel = st.selectbox("Kupon", ["Yox"] + list(cp_ops.keys()))
                         st.session_state.active_coupon = {"id":cp_ops[sel], "type":sel} if sel != "Yox" else None
                    if st.button("Ləğv Et"): st.session_state.current_customer = None; st.rerun()
                
                # Cart Items
                st.markdown("<div style='background:white; height:50vh; overflow-y:scroll; padding:10px; border:1px solid #eee;'>", unsafe_allow_html=True)
                total = 0
                for i, item in enumerate(st.session_state.cart):
                    c1, c2, c3 = st.columns([4,2,1])
                    c1.write(f"**{item['item_name']}**"); c2.write(f"{item['price']}")
                    if c3.button("x", key=f"rm_{i}"): st.session_state.cart.pop(i); st.rerun()
                    total += float(item['price'])
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Calc Total
                disc = 0
                if curr:
                    c_tot = sum([float(x['price']) for x in st.session_state.cart if x.get('is_coffee')])
                    candidates = []
                    if curr['type']=='thermos' and c_tot>0: candidates.append(c_tot*0.2)
                    if curr['stars']>=9: 
                        c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                        if c_items: candidates.append(float(min(c_items, key=lambda x:float(x['price']))['price']))
                    if st.session_state.active_coupon:
                        cp = st.session_state.active_coupon['type']
                        if 'disc_20' in cp: candidates.append(total*0.2)
                        elif 'disc_100_coffee' in cp: 
                            c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                            if c_items: candidates.append(float(min(c_items, key=lambda x:float(x['price']))['price']))
                        elif 'thermos_welcome' in cp:
                            c_items = [x for x in st.session_state.cart if x.get('is_coffee')]
                            if c_items: candidates.append(float(min(c_items, key=lambda x:float(x['price']))['price']))
                    if candidates: disc = max(candidates)
                
                fin = max(0, total - disc)
                st.markdown(f"<h2 style='text-align:right; color:#D32F2F;'>{fin:.2f} ₼</h2>", unsafe_allow_html=True)
                if disc > 0: st.caption(f"Endirim: -{disc:.2f}")
                
                pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True)
                if st.button("✅ ÖDƏNİŞ", type="primary", use_container_width=True):
                    if st.session_state.cart:
                        try:
                            if curr:
                                ns = int(curr['stars'])
                                if not st.session_state.active_coupon:
                                    if ns >= 9 and any(x.get('is_coffee') for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                run_action("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id", {"s":ns, "id":curr['card_id']})
                                if st.session_state.active_coupon:
                                    run_action("UPDATE customer_coupons SET is_used=TRUE WHERE id=:id", {"id":st.session_state.active_coupon['id']})
                            
                            items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                            run_action("INSERT INTO sales (items, total, payment_method, cashier) VALUES (:i, :t, :p, :c)", 
                                      {"i":items_str, "t":fin, "p":"Cash" if pm=="Nəğd" else "Card", "c":st.session_state.user})
                            
                            st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; st.session_state.active_coupon = None; time.sleep(1); st.rerun()
                        except Exception as e: st.error(e)

            with rc: # Menu
                c1,c2,c3 = st.columns(3)
                if c1.button("☕ Qəhvə", type="secondary", use_container_width=True): st.session_state.pos_category="Qəhvə"; st.rerun()
                if c2.button("🥤 İçkilər", type="secondary", use_container_width=True): st.session_state.pos_category="İçkilər"; st.rerun()
                if c3.button("🍰 Desert", type="secondary", use_container_width=True): st.session_state.pos_category="Desert"; st.rerun()
                
                m = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c":st.session_state.pos_category})
                
                @st.dialog("Seçim")
                def var_sel(base, items):
                    cols = st.columns(len(items))
                    for i, it in enumerate(items):
                        with cols[i]:
                            if st.button(f"{it['item_name'].split()[-1]}\n{it['price']}₼", key=f"v_{it['id']}"): st.session_state.cart.append(it); st.rerun()

                grps = {}
                for _, r in m.iterrows():
                    n = r['item_name']
                    if not n: continue
                    parts = n.split()
                    if parts and parts[-1] in ['S','M','L']: grps.setdefault(" ".join(parts[:-1]), []).append(r.to_dict())
                    else: grps[n] = [r.to_dict()]
                
                gc = st.columns(4)
                for i, (base, itms) in enumerate(grps.items()):
                    with gc[i%4]:
                        if len(itms)>1: 
                            if st.button(f"{base}\n(Seçim)", key=f"g_{i}"): var_sel(base, itms)
                        else:
                            it = itms[0]
                            if st.button(f"{it['item_name']}\n{it['price']}₼", key=f"i_{it['id']}"): st.session_state.cart.append(it); st.rerun()

        if st.session_state.role == 'staff': render_pos_ui()
        else:
            pt = st.tabs(["POS", "Analitika", "CRM", "Menyu", "Ayarlar", "Admin"])
            with pt[0]: render_pos_ui()
            with pt[1]: 
                st.subheader("Satışlar")
                df = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
                st.dataframe(df)
            with pt[3]:
                st.subheader("Menyu")
                with st.expander("Excel Yüklə"):
                    up = st.file_uploader("Excel", type=['xlsx'])
                    if up and st.button("Yüklə"):
                        df = pd.read_excel(up)
                        for _, r in df.iterrows():
                            run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)",
                                       {"n":str(r['item_name']), "p":float(r['price']), "c":str(r['category']), "ic":bool(r.get('is_coffee', False))})
                        st.success("Hazır!")
                m = run_query("SELECT * FROM menu ORDER BY category, item_name")
                st.dataframe(m)
            with pt[4]:
                st.subheader("İstifadəçilər")
                # Fix for text_ issue
                new_pass = st.text_input("Yeni Şifrə", type="password")
                u_sel = st.selectbox("İstifadəçi", run_query("SELECT username FROM users")['username'].tolist())
                if st.button("Yenilə"):
                    run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(new_pass), "u":u_sel})
                    st.success("OK")
    
    # >>> MODE 2: V2 INVENTORY (ALPHA) <<<
    elif app_mode == "🧪 V2 Anbar (Alpha)":
        if st.session_state.role != 'admin':
            st.error("Bu bölməyə yalnız Admin girə bilər!")
        else:
            # --- SECURITY GATE (DOUBLE AUTH) ---
            if 'v2_unlocked' not in st.session_state: st.session_state.v2_unlocked = False

            if not st.session_state.v2_unlocked:
                st.markdown("### 🔒 Laboratoriya Girişi")
                lp = st.text_input("Laboratoriya Şifrəsi", type="password")
                if st.button("Laboratoriyaya Gir"):
                    if lp == V2_LAB_PASSWORD:
                        st.session_state.v2_unlocked = True
                        st.rerun()
                    else:
                        st.error("Yanlış Şifrə!")
                st.stop()
            # -----------------------------------

            st.markdown("### 📦 Ağıllı Anbar (V2)")
            it = st.tabs(["Stok", "Mədaxil", "Reseptlər"])
            
            with it[0]: # Stock
                with st.expander("➕ Yeni Xammal"):
                    with st.form("new_inv"):
                        n = st.text_input("Ad"); u = st.selectbox("Vahid", ["kg","L","pcs","g","ml"]); a = st.number_input("Limit", 0.0)
                        if st.form_submit_button("Yarat"):
                            run_action("INSERT INTO inventory (name, unit, alert_limit) VALUES (:n,:u,:a)", {"n":n,"u":u,"a":a})
                            st.success("Yarandı!"); st.rerun()
                
                inv = run_query("SELECT * FROM inventory ORDER BY name")
                if not inv.empty:
                    for _, r in inv.iterrows():
                        col = "red" if r['stock_level'] <= r['alert_limit'] else "green"
                        st.markdown(f"**{r['name']}**: <span style='color:{col}'>{r['stock_level']} {r['unit']}</span> (Limit: {r['alert_limit']})", unsafe_allow_html=True)
                else: st.info("Boşdur")
            
            with it[1]: # Inbound
                with st.form("inbound"):
                    items = run_query("SELECT name FROM inventory")
                    if not items.empty:
                        s_i = st.selectbox("Məhsul", items['name'].tolist())
                        qty = st.number_input("Miqdar", min_value=0.1)
                        cost = st.number_input("Ümumi Qiymət (AZN)", min_value=0.1)
                        if st.form_submit_button("Əlavə Et"):
                            # Update stock logic
                            run_action("UPDATE inventory SET stock_level = stock_level + :q WHERE name=:n", {"q":qty, "n":s_i})
                            run_action("INSERT INTO expenses (description, amount, category) VALUES (:d, :a, 'Mal Alışı')", {"d":f"{s_i} ({qty})", "a":cost})
                            st.success("Əlavə edildi!")
                    else: st.warning("Xammal yoxdur")
            
            with it[2]: # Recipes
                mi = run_query("SELECT id, item_name FROM menu ORDER BY item_name")
                ii = run_query("SELECT id, name FROM inventory ORDER BY name")
                if not mi.empty and not ii.empty:
                    c1, c2, c3 = st.columns(3)
                    m_sel = c1.selectbox("Menyu", mi['item_name'].tolist())
                    i_sel = c2.selectbox("Xammal", ii['name'].tolist())
                    q_req = c3.number_input("Tələb (Vahidə uyğun)", 0.001, format="%.3f")
                    if st.button("Reseptə Yaz"):
                        mid = mi[mi['item_name']==m_sel].iloc[0]['id']
                        iid = ii[ii['name']==i_sel].iloc[0]['id']
                        run_action("INSERT INTO recipes (menu_item_id, item_name_cached, inventory_item_id, quantity_required) VALUES (:m,:mn,:i,:q)",
                                   {"m":int(mid), "mn":m_sel, "i":int(iid), "q":q_req})
                        st.success("OK")
                    
                    st.divider()
                    st.dataframe(run_query("SELECT item_name_cached, quantity_required FROM recipes"))
