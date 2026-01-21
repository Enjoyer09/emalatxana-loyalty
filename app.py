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

# --- EMAIL AYARLARI (BREVO) ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY") or "xkeysib-..."
SENDER_EMAIL = "info@emalatxana.az" 
SENDER_NAME = "Emalatxana Loyalty"
APP_URL = "https://emalatxana-loyalty-production.up.railway.app" # SİZİN REAL URL

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana POS", page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# --- META TAGS (MOBİL EKRAN ÜÇÜN) ---
st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
""", unsafe_allow_html=True)

# --- DATABASE ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("URL yoxdur!"); st.stop()
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://")
    conn = st.connection("neon", type="sql", url=db_url)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA ---
def ensure_schema_and_seed():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS email TEXT;"))
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS birth_date TEXT;"))
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE;"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        try: s.execute(text("ALTER TABLE menu ADD COLUMN IF NOT EXISTS is_coffee BOOLEAN DEFAULT FALSE;"))
        except: pass
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
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": SENDER_NAME, "email": SENDER_EMAIL}, "to": [{"email": to_email}], "subject": subject, "textContent": body}
    try:
        if "xkeysib" not in BREVO_API_KEY: return True
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

# --- POS DIALOG (POPUP SİSTEMİ) ---
@st.dialog("📏 ÖLÇÜ SEÇİN")
def show_size_selector(base_name, variants):
    st.markdown(f"<h3 style='text-align:center'>{base_name}</h3>", unsafe_allow_html=True)
    
    # 3 sütunlu grid yaradırıq (S, M, L və ya digərləri üçün)
    cols = st.columns(len(variants))
    
    for idx, item in enumerate(variants):
        # Size adını tapırıq (Məs: "Americano S" -> "S")
        name_parts = item['item_name'].split()
        size_label = name_parts[-1] if name_parts[-1] in ['S', 'M', 'L'] else item['item_name']
        
        with cols[idx]:
            # Böyük düymələr
            if st.button(f"{size_label}\n{item['price']} ₼", key=f"sz_{item['id']}", use_container_width=True):
                st.session_state.cart.append(item)
                st.rerun()

# --- CSS STYLES ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500;700&display=swap');
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Anton'; letter-spacing: 1px; }
    p, div, button { font-family: 'Oswald'; }
    
    /* POS BUTTONS (TOUCH FRIENDLY) */
    div.stButton > button {
        min-height: 70px; /* Hündür düymələr */
        font-size: 20px !important;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        font-weight: bold;
    }
    
    /* CUSTOMER CARD */
    .digital-card { background: linear-gradient(145deg, #ffffff, #f9f9f9); border-radius: 20px; padding: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); }
    .coffee-grid { display: flex; justify-content: center; gap: 10px; }
    
    /* BASKET */
    .basket-total { font-size: 28px; font-weight: bold; text-align: right; margin-top: 20px; color: #2e7d32; }
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
    
    notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
    with c3:
        if not notifs.empty: st.markdown(f"<div style='text-align:right'>🔔<span style='color:red'>{len(notifs)}</span></div>", unsafe_allow_html=True)
    if not notifs.empty:
        for i, row in notifs.iterrows():
            st.info(f"📩 {row['message']}")
            run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        if not user['is_active']:
            st.info("KARTI AKTİVLƏŞDİRİN")
            with st.form("act"):
                em = st.text_input("Email")
                if st.form_submit_button("Təsdiq"):
                    run_action("UPDATE customers SET email=:e, is_active=TRUE WHERE card_id=:i", {"e":em, "i":card_id})
                    st.rerun()
            st.stop()

        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        if user['type'] == 'thermos': st.info("⭐ VIP TERMOS KLUBU")
        st.markdown(f"<h3 style='text-align:center'>KART: {user['stars']}/10</h3>", unsafe_allow_html=True)
        html = '<div class="coffee-grid">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png" if i < user['stars'] else "https://cdn-icons-png.flaticon.com/512/1174/1174444.png"
            op = "1" if i < user['stars'] else "0.2"
            html += f'<img src="{icon}" style="width:35px; opacity:{op}">'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        st.download_button("📥 KARTI YÜKLƏ (Offline)", generate_custom_qr(f"{APP_URL}/?id={card_id}", card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS & ADMIN ===
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
        h1, h2, h3 = st.columns([2,6,1])
        with h1: 
            if st.button("🔴 Çıxış"): st.session_state.logged_in = False; st.rerun()
        with h3:
            if st.button("🔄"): st.rerun()

        role = st.session_state.role
        
        # --- POS MƏNTİQİ (ORTAQ) ---
        def render_pos():
            left_col, right_col = st.columns([2, 1])
            with left_col:
                # 1. Müştəri Skaneri
                c_scan, c_info = st.columns([2, 2])
                with c_scan:
                    scan_val = st.text_input("Müştəri QR", key="pos_scan_input")
                    if st.button("🔍", key="pos_search"):
                        if scan_val:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                            if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                            else: st.error("Tapılmadı")
                with c_info:
                    curr = st.session_state.current_customer
                    if curr:
                        st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                        if st.button("❌ Ləğv"): st.session_state.current_customer = None; st.rerun()
                
                # 2. Menyu (Qruplaşdırılmış)
                cats = ["Qəhvə", "İçkilər", "Desert"]
                sel_cat = st.radio(" ", cats, horizontal=True, label_visibility="collapsed")
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": sel_cat})
                
                # Qruplaşdırma Məntiqi (Americano S, M, L -> Americano)
                grouped_items = {}
                for _, row in menu_df.iterrows():
                    name_parts = row['item_name'].split()
                    # Əgər son söz S, M, L və ya XL-dirsə, onu əsas addan ayırırıq
                    if name_parts[-1] in ['S', 'M', 'L', 'XL']:
                        base_name = " ".join(name_parts[:-1])
                        if base_name not in grouped_items: grouped_items[base_name] = []
                        grouped_items[base_name].append(row.to_dict())
                    else:
                        # Tək məhsullar (Su, Cola)
                        grouped_items[row['item_name']] = [row.to_dict()]
                
                # Düymələrin düzülüşü
                item_names = list(grouped_items.keys())
                cols = st.columns(3)
                for idx, name in enumerate(item_names):
                    variants = grouped_items[name]
                    with cols[idx % 3]:
                        # Düymə mətni
                        if len(variants) > 1:
                            # Çox variantlı (Popup açacaq)
                            btn_text = f"{name}\n(Seçim)"
                            if st.button(btn_text, key=f"grp_{idx}", use_container_width=True):
                                show_size_selector(name, variants)
                        else:
                            # Tək variantlı (Birbaşa səbətə)
                            item = variants[0]
                            if st.button(f"{item['item_name']}\n{item['price']}₼", key=f"sng_{item['id']}", use_container_width=True):
                                st.session_state.cart.append(item)
                                st.rerun()

            with right_col:
                st.markdown("### 🧾 ÇEK")
                if st.session_state.cart:
                    total, coffs = 0, 0
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([3,1,1])
                        c1.write(item['item_name']); c2.write(f"{item['price']}")
                        if c3.button("🗑️", key=f"del_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price'])
                        if item['is_coffee']: coffs += 1
                    
                    disc, curr = 0, st.session_state.current_customer
                    if curr:
                        if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                        if curr['stars'] >= 10: 
                            c_items = [x for x in st.session_state.cart if x['is_coffee']]
                            if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                    
                    final = max(0, total - disc)
                    st.markdown(f"<div class='basket-total'>YEKUN: {final:.2f} ₼</div>", unsafe_allow_html=True)
                    if disc > 0: st.caption(f"Endirim: -{disc:.2f}")
                    
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
                else: st.info("Səbət boşdur")

        # --- ADMIN TABLAR ---
        if role == 'admin':
            tabs = st.tabs(["🛒 POS", "📧 CRM", "📊 Analitika", "📋 Menyu", "👥 Admin", "🖨️ QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📧 CRM")
                m_df = run_query("SELECT card_id, email FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    ed = st.data_editor(m_df, hide_index=True, use_container_width=True)
                    if st.button("🚀 Hamıya Göndər"):
                        st.success("Test rejimi: Göndərildi!")
                else: st.info("Müştəri yoxdur")
            with tabs[2]:
                sales = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
                st.dataframe(sales)
            with tabs[3]:
                with st.form("addm"):
                    c1,c2,c3 = st.columns(3)
                    n=c1.text_input("Ad (Məs: Americano S)"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"])
                    cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                md = run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id")
                st.dataframe(md)
            with tabs[4]:
                with st.expander("➕ Yeni İşçi"):
                    un = st.text_input("User"); ps = st.text_input("Pass", type="password")
                    if st.button("Yarat"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u":un, "p":hash_password(ps)}); st.success("OK")
            with tabs[5]:
                cnt = st.number_input("Say", 1, 50); is_th = st.checkbox("Termos?")
                if st.button("Yarat"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    typ = "thermos" if is_th else "standard"
                    for i in ids: run_action("INSERT INTO customers (card_id, stars, type) VALUES (:i, 0, :t)", {"i":i, "t":typ})
                    z = BytesIO()
                    with zipfile.ZipFile(z, "w") as zf:
                        for i in ids: zf.writestr(f"{i}.png", generate_custom_qr(f"{APP_URL}/?id={i}", i))
                    st.download_button("📦 ZIP", z.getvalue(), "qr.zip", "application/zip")

        elif role == 'staff':
            render_pos()
