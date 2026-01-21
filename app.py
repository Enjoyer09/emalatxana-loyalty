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
import datetime
import requests

# --- EMAIL AYARLARI (BREVO API) ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY") or "xkeysib-..."
SENDER_EMAIL = "info@emalatxana.az" 
SENDER_NAME = "Emalatxana Loyalty"

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(
    page_title="Emalatxana System", 
    page_icon="☕", 
    layout="wide", # POS üçün geniş ekran vacibdir
    initial_sidebar_state="collapsed"
)

# --- META TAGS ---
st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("URL yoxdur!"); st.stop()
    db_url = db_url.strip().strip('"').strip("'")
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"): db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA MIGRATION & SEED ---
def ensure_schema_and_seed():
    with conn.session as s:
        # Cədvəllər
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        
        # Customers Updates
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS email TEXT;"))
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS birth_date TEXT;"))
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE;"))
        
        # Menu Table
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS menu (
                id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT,
                is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE
            );
        """))
        # Menu Column Update
        try: s.execute(text("ALTER TABLE menu ADD COLUMN IF NOT EXISTS is_coffee BOOLEAN DEFAULT FALSE;"))
        except: pass
        s.commit()
        
        # Seed Menu (Əgər boşdursa)
        if s.execute(text("SELECT count(*) FROM menu")).scalar() == 0:
            menu_items = [
                ("Su", 2, "İçkilər", False), ("Çay", 3, "İçkilər", False), 
                ("Americano S", 3.9, "Qəhvə", True), ("Cappuccino S", 4.5, "Qəhvə", True),
                ("Latte S", 4.5, "Qəhvə", True), ("San Sebastian", 6, "Desert", False)
            ]
            for n, p, c, ic in menu_items:
                s.execute(text("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n, :p, :c, :ic)"), {"n":n, "p":p, "c":c, "ic":ic})
            s.commit()

ensure_schema_and_seed()

# --- HELPER FUNCTIONS ---
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
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": SENDER_NAME, "email": SENDER_EMAIL}, "to": [{"email": to_email}], "subject": subject, "textContent": body}
    try:
        if "xkeysib" not in BREVO_API_KEY: return True # Simulyasiya
        r = requests.post(url, json=payload, headers=headers)
        return r.status_code == 201
    except: return True

@st.cache_data(persist="disk")
def generate_custom_qr(data, center_text):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    try: font = ImageFont.truetype("arial.ttf", int(img.size[1]*0.06))
    except: pass
    bbox = draw.textbbox((0,0), center_text, font=font)
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    px, py = 10, 5
    x0, y0 = (img.size[0]-(w+2*px))//2, (img.size[1]-(h+2*py))//2
    draw.rectangle([x0, y0, x0+w+2*px, y0+h+2*py], fill="white", outline="black", width=2)
    draw.text((x0+px, y0+py-2), center_text, fill="black", font=font)
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

def check_manual_input_status():
    df = run_query("SELECT value FROM settings WHERE key = 'manual_input'")
    return df.iloc[0]['value'] == 'true' if not df.empty else True

# --- STYLES ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Anton'; letter-spacing: 1px; }
    p, div, button { font-family: 'Oswald'; }
    
    /* POS */
    .pos-btn { background: white; border: 1px solid #ddd; padding: 15px; text-align: center; border-radius: 8px; cursor: pointer; height: 100%; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .pos-btn:hover { border-color: #2e7d32; background: #f1f8e9; }
    .basket-total { font-size: 24px; font-weight: bold; text-align: right; margin-top: 20px; color: #2e7d32; }
    
    /* CUSTOMER */
    .digital-card { background: linear-gradient(145deg, #ffffff, #f9f9f9); border-radius: 20px; padding: 20px; margin-bottom: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); }
    .coffee-grid { display: flex; justify-content: center; gap: 10px; }
    .notification-box { background: #e3f2fd; padding: 10px; border-left: 5px solid #2196f3; margin-bottom: 10px; }
    div[data-testid="stFeedback"] svg { fill: #FF9800 !important; color: #FF9800 !important; }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'cart' not in st.session_state: st.session_state.cart = []
if 'current_customer' not in st.session_state: st.session_state.current_customer = None

# ===========================
# === 1. MÜŞTƏRİ EKRANI ===
# ===========================
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]
    c1, c2, c3 = st.columns([1,3,1])
    with c2: st.image("emalatxana.png", width=150)
    
    # Bildirişlər
    notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
    with c3:
        if not notifs.empty: st.markdown(f"<div style='text-align:right'>🔔<span style='color:red'>{len(notifs)}</span></div>", unsafe_allow_html=True)
    if not notifs.empty:
        for i, row in notifs.iterrows():
            st.markdown(f"<div class='notification-box'>📩 {row['message']}</div>", unsafe_allow_html=True)
            run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        
        # Aktivasiya
        if not user['is_active']:
            st.info("🎉 KARTI AKTİVLƏŞDİRİN")
            with st.form("act"):
                em = st.text_input("Email")
                dob = st.date_input("Doğum Tarixi", min_value=datetime.date(1960,1,1))
                if st.form_submit_button("Təsdiq"):
                    run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob, "i":card_id})
                    st.rerun()
            st.stop()

        # Kart
        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        if user['type'] == 'thermos': st.info("⭐ TERMOS KLUBU (20% Endirim)")
        st.markdown(f"<h3 style='text-align:center'>KART: {user['stars']}/10</h3>", unsafe_allow_html=True)
        html = '<div class="coffee-grid">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png" if i < user['stars'] else "https://cdn-icons-png.flaticon.com/512/1174/1174444.png"
            op = "1" if i < user['stars'] else "0.2"
            html += f'<img src="{icon}" style="width:35px; opacity:{op}">'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Rəy
        st.markdown("### ⭐ Bizi Qiymətləndir")
        stars_val = st.feedback("stars")
        msg_val = st.text_area("Rəyiniz:")
        if st.button("Göndər"):
            if stars_val is not None:
                run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:id, :r, :m)", {"id":card_id, "r":stars_val+1, "m":msg_val})
                st.success("Təşəkkürlər!")
            else: st.warning("Ulduz seçin")

        st.divider()
        lnk = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
        st.download_button("📥 KARTI YÜKLƏ (Offline)", generate_custom_qr(lnk, card_id), f"{card_id}.png", "image/png", use_container_width=True)
        
    else: st.error("Kart tapılmadı")

# ========================
# === 2. ADMIN & POS ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1])
        with c2: 
            st.image("emalatxana.png", width=150)
            st.markdown("<h3 style='text-align:center'>GİRİŞ</h3>", unsafe_allow_html=True)
            if st.button("🔄 Yenilə"): st.rerun()
            with st.form("login"):
                u = st.text_input("User")
                p = st.text_input("Pass", type="password")
                if st.form_submit_button("GİRİŞ", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(:u)", {"u":u})
                    if not udf.empty and verify_password(p, udf.iloc[0]['password']):
                        st.session_state.logged_in = True; st.session_state.role = udf.iloc[0]['role']; st.session_state.user = u
                        st.rerun()
                    else: st.error("Səhvdir")
    else:
        # Header
        h1, h2, h3 = st.columns([2,6,1])
        with h1: 
            if st.button("🔴 Çıxış"): st.session_state.logged_in = False; st.rerun()
        with h3:
            if st.button("🔄"): st.rerun()

        role = st.session_state.role
        
        # --- STAFF GÖRÜNÜŞÜ (YALNIZ POS) ---
        if role == 'staff':
            st.markdown("### 🛒 KASSA")
            # (Eyni POS kodu aşağıda Admin daxilində də var, Staff üçün sadələşdirilmiş)
            # ... (Staff üçün sadəcə POS terminalı göstərəcəyik) ...
            # Aşağıdakı Admin blokundakı POS kodunu buraya da kopyalaya bilərik, amma
            # gəlin Admin-də Tab sistemini quraq, Staff-da isə birbaşa POS-u.
            
            # --- POS KODU (STAFF ÜÇÜN) ---
            left_col, right_col = st.columns([2, 1])
            with left_col:
                c_scan, c_info = st.columns([2, 2])
                with c_scan:
                    scan_val = st.text_input("Müştəri QR", key="staff_scan")
                    if st.button("🔍 Axtar", key="staff_search"):
                        if scan_val:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                            if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                            else: st.error("Tapılmadı")
                with c_info:
                    curr = st.session_state.current_customer
                    if curr:
                        st.info(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                        if st.button("❌ Ləğv", key="staff_cncl"): st.session_state.current_customer = None; st.rerun()
                
                cats = ["Qəhvə", "İçkilər", "Desert"]
                sel_cat = st.radio("Kat:", cats, horizontal=True, key="staff_cat")
                m_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY id", {"c": sel_cat})
                cols = st.columns(3)
                for i, row in m_df.iterrows():
                    with cols[i % 3]:
                        if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"sbtn_{row['id']}", use_container_width=True):
                            st.session_state.cart.append(row.to_dict()); st.rerun()
            
            with right_col:
                st.markdown("### 🧾 ÇEK")
                if st.session_state.cart:
                    total, coffs = 0, 0
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([3,1,1])
                        c1.write(item['item_name']); c2.write(f"{item['price']}"); 
                        if c3.button("x", key=f"sdel_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price']); 
                        if item['is_coffee']: coffs += 1
                    
                    disc, curr = 0, st.session_state.current_customer
                    if curr:
                        if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                        if curr['stars'] >= 10: 
                            c_items = [x for x in st.session_state.cart if x['is_coffee']]
                            if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                    
                    final = max(0, total - disc)
                    st.markdown(f"<h3 style='text-align:right; color:#2e7d32'>{final:.2f} ₼</h3>", unsafe_allow_html=True)
                    if st.button("✅ TƏSDİQLƏ", type="primary", use_container_width=True):
                        items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                        run_action("INSERT INTO sales (items, total, payment_method) VALUES (:i, :t, 'Cash')", {"i":items_str, "t":final})
                        if curr:
                            ns = curr['stars']
                            if coffs > 0:
                                if curr['stars'] >= 10 and any(x['is_coffee'] for x in st.session_state.cart): ns = 0
                                else: ns += 1
                            run_action("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id", {"s":ns, "id":curr['card_id']})
                        st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()

        # --- ADMIN GÖRÜNÜŞÜ (TABLAR) ---
        elif role == 'admin':
            tabs = st.tabs(["🛒 POS", "📧 Marketinq", "📊 Analitika", "📋 Menyu", "💬 Rəylər", "⚙️ Ayarlar", "🖨️ QR"])
            
            with tabs[0]: # POS (Admin üçün də eyni POS)
                left_col, right_col = st.columns([2, 1])
                with left_col:
                    c_scan, c_info = st.columns([2, 2])
                    with c_scan:
                        scan_val = st.text_input("Müştəri QR", key="admin_scan")
                        if st.button("🔍 Axtar", key="admin_search"):
                            if scan_val:
                                c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                                if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                                else: st.error("Tapılmadı")
                    with c_info:
                        curr = st.session_state.current_customer
                        if curr:
                            st.info(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                            if st.button("❌ Ləğv", key="admin_cncl"): st.session_state.current_customer = None; st.rerun()
                    
                    cats = ["Qəhvə", "İçkilər", "Desert"]
                    sel_cat = st.radio("Kat:", cats, horizontal=True, key="admin_cat")
                    m_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY id", {"c": sel_cat})
                    cols = st.columns(3)
                    for i, row in m_df.iterrows():
                        with cols[i % 3]:
                            if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"abtn_{row['id']}", use_container_width=True):
                                st.session_state.cart.append(row.to_dict()); st.rerun()
                
                with right_col:
                    st.markdown("### 🧾 ÇEK")
                    if st.session_state.cart:
                        total, coffs = 0, 0
                        for i, item in enumerate(st.session_state.cart):
                            c1, c2, c3 = st.columns([3,1,1])
                            c1.write(item['item_name']); c2.write(f"{item['price']}")
                            if c3.button("x", key=f"adel_{i}"): st.session_state.cart.pop(i); st.rerun()
                            total += float(item['price']); 
                            if item['is_coffee']: coffs += 1
                        
                        disc, curr = 0, st.session_state.current_customer
                        if curr:
                            if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                            if curr['stars'] >= 10: 
                                c_items = [x for x in st.session_state.cart if x['is_coffee']]
                                if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                        
                        final = max(0, total - disc)
                        st.markdown(f"<h3 style='text-align:right; color:#2e7d32'>{final:.2f} ₼</h3>", unsafe_allow_html=True)
                        if st.button("✅ TƏSDİQLƏ", type="primary", use_container_width=True, key="admin_pay"):
                            items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                            run_action("INSERT INTO sales (items, total, payment_method) VALUES (:i, :t, 'Cash')", {"i":items_str, "t":final})
                            if curr:
                                ns = curr['stars']
                                if coffs > 0:
                                    if curr['stars'] >= 10 and any(x['is_coffee'] for x in st.session_state.cart): ns = 0
                                    else: ns += 1
                                run_action("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id", {"s":ns, "id":curr['card_id']})
                            st.success("OK!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()

            with tabs[1]: # MARKETINQ
                st.markdown("### 📧 CRM")
                m_df = run_query("SELECT card_id, email, birth_date FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    m_df['50%'] = False; m_df['Birthday'] = False
                    ed = st.data_editor(m_df, hide_index=True, use_container_width=True)
                    if st.button("🚀 Göndər"):
                        cnt = 0
                        for i, r in ed.iterrows():
                            if r['50%']: 
                                send_email(r['email'], "50% Endirim", "Sizə özəl 50% endirim!")
                                run_action("INSERT INTO notifications (card_id, message) VALUES (:id, '50% Endirim!')", {"id":r['card_id']}); cnt+=1
                            if r['Birthday']: 
                                send_email(r['email'], "Ad Günü", "Bir kofe bizdən!")
                                run_action("INSERT INTO notifications (card_id, message) VALUES (:id, 'Ad Günü Hədiyyəsi!')", {"id":r['card_id']}); cnt+=1
                        st.success(f"{cnt} mesaj göndərildi!")
                else: st.info("Aktiv müştəri yoxdur")
                
                with st.form("push"):
                    msg = st.text_area("Hamıya Mesaj")
                    if st.form_submit_button("Göndər"):
                        ids = run_query("SELECT card_id FROM customers")
                        for _, r in ids.iterrows(): run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :m)", {"id":r['card_id'], "m":msg})
                        st.success("OK")

            with tabs[2]: # ANALITIKA
                st.markdown("### 📊 Analitika")
                sales = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
                st.dataframe(sales)
                ts = run_query("SELECT SUM(total) as t FROM sales WHERE created_at::date = CURRENT_DATE")
                val = ts.iloc[0]['t'] if not ts.empty and ts.iloc[0]['t'] else 0
                st.metric("Günlük Satış", f"{val} ₼")

            with tabs[3]: # MENU
                with st.form("addm"):
                    c1,c2,c3 = st.columns(3)
                    n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"])
                    cf=st.checkbox("Bu Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                md = run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id")
                for i,r in md.iterrows():
                    c1,c2 = st.columns([4,1])
                    c1.write(f"{r['item_name']} - {r['price']}")
                    if c2.button("Sil", key=f"md{r['id']}"): run_action("DELETE FROM menu WHERE id=:id", {"id":r['id']}); st.rerun()

            with tabs[4]: # RƏYLƏR
                f_df = run_query("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 20")
                for i, r in f_df.iterrows(): st.info(f"{r['rating']}⭐: {r['message']}")

            with tabs[5]: # AYARLAR
                with st.expander("➕ Yeni İşçi"):
                    un = st.text_input("User"); ps = st.text_input("Pass", type="password")
                    if st.button("Yarat"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u":un, "p":hash_password(ps)}); st.success("OK")
                
                with st.expander("🔑 Şifrə Dəyiş"):
                    target = st.text_input("İstifadəçi adı")
                    npass = st.text_input("Yeni Şifrə", type="password")
                    if st.button("Dəyiş"):
                        run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(npass), "u":target}); st.success("OK")

            with tabs[6]: # QR
                cnt = st.number_input("Say", 1, 50)
                if st.button("Yarat", key="qr_gen"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    for i in ids: run_action("INSERT INTO customers (card_id, stars, type) VALUES (:i, 0, 'standard')", {"i":i})
                    z = BytesIO(); 
                    with zipfile.ZipFile(z, "w") as zf:
                        for i in ids: zf.writestr(f"{i}.png", generate_custom_qr(f"https://emalatxana.az/?id={i}", i))
                    st.download_button("📦 ZIP Yüklə", z.getvalue(), "qr.zip", "application/zip")
