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

# --- EMAIL AYARLARI ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY") or "xkeysib-..."
SENDER_EMAIL = "info@emalatxana.az" 
SENDER_NAME = "Emalatxana Coffee"
APP_URL = "https://emalatxana-loyalty-production.up.railway.app" 

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(
    page_title="Emalatxana Coffee", 
    page_icon="☕", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- CSS STYLES (SİZİN KODLAR + GİZLƏTMƏ KODLARI) ---
st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700&display=swap');
    
    /* 1. INTERFEYS ELEMENTLƏRİNİ GİZLƏT (CLEAN UI) */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stStatusWidget"] { visibility: hidden; height: 0%; position: fixed; }

    /* 2. ÜMUMİ FONT VƏ RƏNGLƏR */ 
    html, body, .stApp { font-family: 'Oswald', sans-serif !important; } 
    .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; } 
    h1, h2, h3, h4, span { color: #2E7D32 !important; }

    /* 3. DİZAYN KODLARI (SİZİN GÖNDƏRDİYİNİZ) */
    
    /* Customer Card */ 
    .digital-card { 
        background: linear-gradient(145deg, #ffffff, #f1f8e9); 
        border-radius: 20px; padding: 20px; 
        box-shadow: 0 10px 25px rgba(46, 125, 50, 0.15); 
        border: 2px solid #2E7D32; margin-bottom: 20px; 
    }
    
    /* 5-5 Coffee Grid */ 
    .coffee-grid-container { 
        display: grid; grid-template-columns: repeat(5, 1fr); 
        gap: 12px; justify-items: center; margin-top: 15px; 
    } 
    .coffee-icon { width: 100%; max-width: 50px; transition: all 0.3s ease; }
    
    /* Animasiyalar */ 
    .pulse-anim { animation: pulse 1.5s infinite; filter: drop-shadow(0 0 5px #2E7D32); } 
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } } 
    .orange-gift { filter: sepia(100%) saturate(500%) hue-rotate(320deg) brightness(100%) contrast(100%); }
    
    /* POS Düymələri */ 
    div.stButton > button { 
        min-height: 65px; font-size: 18px !important; 
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
        font-weight: bold; border: 1px solid #2E7D32; 
    } 
    div.stButton > button:hover { background-color: #E8F5E9; border-color: #1B5E20; }
    
    /* Mətnlər */ 
    .quote-text { text-align: center; color: #555 !important; font-style: italic; margin-bottom: 10px; font-size: 16px; } 
    .basket-total { font-size: 28px; font-weight: bold; text-align: right; margin-top: 20px; color: #2E7D32; } 
    
    /* Analytics Metric */ 
    div[data-testid="stMetricValue"] { font-size: 24px !important; color: #2E7D32 !important; }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("URL yoxdur!"); st.stop()
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://")
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA & SEED ---
def ensure_schema_and_seed():
    for _ in range(3):
        try:
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
            break
        except exc.OperationalError: time.sleep(1)
        except: break
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

def get_random_quote():
    quotes = ["Bu gün əla görünürsən! ☕", "Enerjini bərpa etmək vaxtıdır! ⚡", "Sən ən yaxşısına layiqsən! 💖", "Kofe ilə gün daha gözəldir! ☀️"]
    return random.choice(quotes)

# --- POS DIALOG ---
@st.dialog("📏 ÖLÇÜ SEÇİN")
def show_size_selector(base_name, variants):
    st.markdown(f"<h3 style='text-align:center; color:#2E7D32'>{base_name}</h3>", unsafe_allow_html=True)
    cols = st.columns(len(variants))
    for idx, item in enumerate(variants):
        name_parts = item['item_name'].split()
        size_label = name_parts[-1] if name_parts[-1] in ['S', 'M', 'L'] else item['item_name']
        with cols[idx]:
            if st.button(f"{size_label}\n{item['price']} ₼", key=f"sz_{item['id']}", use_container_width=True):
                st.session_state.cart.append(item)
                st.rerun()

# --- SESSION STATE ---
if 'cart' not in st.session_state: st.session_state.cart = []
if 'current_customer' not in st.session_state: st.session_state.current_customer = None

# ===========================
# === 1. MÜŞTƏRİ EKRANI ===
# ===========================
query_params = st.query_params
if "id" in query_params:
    card_id = query_params["id"]
    c1, c2, c3 = st.columns([1,2,1])
    with c2: st.image("emalatxana.png", width=160)
    
    notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
    with c3:
        if not notifs.empty: st.markdown(f"<div style='text-align:right'>🔔<span style='color:red; font-weight:bold'>{len(notifs)}</span></div>", unsafe_allow_html=True)
    if not notifs.empty:
        for i, row in notifs.iterrows():
            st.warning(f"📩 {row['message']}")
            run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        
        # --- AKTİVASİYA FORMASI ---
        if not user['is_active']:
            st.info("🎉 KARTI AKTİVLƏŞDİRİN")
            st.markdown("Xoş gəlmisiniz! Endirimlər üçün qeydiyyatdan keçin.")
            
            with st.form("act"):
                em = st.text_input("📧 Email ünvanınız")
                dob = st.date_input("🎂 Doğum Tarixiniz", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                
                with st.expander("📜 Qaydalar və Şərtlər"):
                    st.markdown("""
                    * **Məxfilik:** Email və doğum tarixiniz yalnız endirim üçün istifadə olunur.
                    * **Sadiqlik:** **9 ulduz toplandıqda, sistem avtomatik olaraq 1 (bir) ədəd standart ölçülü kofeni (10-cu kofeni) ödənişsiz (hədiyyə) təklif edir.**
                    * **Termos:** Termosla gələnlərə 20% endirim.
                    """)
                
                agree = st.checkbox("Qaydaları oxudum və qəbul edirəm")
                
                if st.form_submit_button("Təsdiq və Giriş"):
                    if not em or "@" not in em:
                        st.error("Düzgün email yazın.")
                    elif not agree:
                        st.error("Qaydaları qəbul etməlisiniz.")
                    else:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", 
                                  {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons()
                        st.success("Təbriklər! Kartınız hazırdır.")
                        time.sleep(1.5)
                        st.rerun()
            st.stop()

        st.markdown(f"<p class='quote-text'>{get_random_quote()}</p>", unsafe_allow_html=True)
        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        if user['type'] == 'thermos': st.info("⭐ VIP TERMOS KLUBU")
        
        st.markdown(f"<h2 style='text-align:center; margin:0; color:#2E7D32'>BALANS: {user['stars']}/10</h2>", unsafe_allow_html=True)
        
        # --- 5-5 GRID ---
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            if i < 9: icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; cls = ""
            else: icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; cls = "orange-gift" 
            
            if i < user['stars']: style = "opacity: 1;"
            else: style = "opacity: 0.2; filter: grayscale(100%);"
            
            if i == user['stars']: style = "opacity: 0.6;"; cls += " pulse-anim"
            html += f'<img src="{icon}" class="coffee-icon {cls}" style="{style}">'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.markdown("<h3 style='text-align:center; color:#FF9800 !important; margin-top:10px;'>🎉 TƏBRİKLƏR! 10-cu Kofe Bizdən!</h3>", unsafe_allow_html=True)
        else: st.markdown(f"<p style='text-align:center; margin-top:10px;'>🎁 Hədiyyəyə <b>{rem}</b> kofe qaldı</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("💬 Rəy Bildir"):
            with st.form("feed"):
                s = st.feedback("stars")
                m = st.text_area("Fikriniz")
                if st.form_submit_button("Göndər"):
                    if s is not None:
                        run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                        st.success("Təşəkkürlər!")
                    else: st.warning("Ulduz seçin")

        st.divider()
        st.download_button("📥 KARTI YÜKLƏ (Offline)", generate_custom_qr(f"{APP_URL}/?id={card_id}", card_id), f"{card_id}.png", "image/png", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Yenilə", type="secondary", use_container_width=True): st.rerun()
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
            if st.button("🔄 Yenilə", key="lr"): st.rerun()
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
            if st.button("🔄", key="mr"): st.rerun()

        role = st.session_state.role
        
        def render_pos():
            left_col, right_col = st.columns([2, 1])
            with left_col:
                c_scan, c_info = st.columns([2, 2])
                with c_scan:
                    scan_val = st.text_input("Müştəri QR", key="ps")
                    if st.button("🔍", key="psb"):
                        if scan_val:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                            if not c_df.empty: st.session_state.current_customer = c_df.iloc[0].to_dict(); st.rerun()
                            else: st.error("Tapılmadı")
                with c_info:
                    curr = st.session_state.current_customer
                    if curr:
                        st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                        if st.button("❌ Ləğv", key="pcl"): st.session_state.current_customer = None; st.rerun()
                
                cats = ["Qəhvə", "İçkilər", "Desert"]
                sel_cat = st.radio(" ", cats, horizontal=True, label_visibility="collapsed")
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": sel_cat})
                grouped_items = {}
                for _, row in menu_df.iterrows():
                    name_parts = row['item_name'].split()
                    if name_parts[-1] in ['S', 'M', 'L', 'XL']:
                        base_name = " ".join(name_parts[:-1])
                        if base_name not in grouped_items: grouped_items[base_name] = []
                        grouped_items[base_name].append(row.to_dict())
                    else:
                        grouped_items[row['item_name']] = [row.to_dict()]
                
                item_names = list(grouped_items.keys())
                cols = st.columns(3)
                for idx, name in enumerate(item_names):
                    variants = grouped_items[name]
                    with cols[idx % 3]:
                        if len(variants) > 1:
                            if st.button(f"{name}\n(Seçim)", key=f"g_{idx}", use_container_width=True):
                                show_size_selector(name, variants)
                        else:
                            item = variants[0]
                            if st.button(f"{item['item_name']}\n{item['price']}₼", key=f"s_{item['id']}", use_container_width=True):
                                st.session_state.cart.append(item)
                                st.rerun()

            with right_col:
                st.markdown("### 🧾 ÇEK")
                if st.session_state.cart:
                    total, coffs = 0, 0
                    for i, item in enumerate(st.session_state.cart):
                        c1, c2, c3 = st.columns([3,1,1])
                        c1.write(item['item_name']); c2.write(f"{item['price']}")
                        if c3.button("🗑️", key=f"d_{i}"): st.session_state.cart.pop(i); st.rerun()
                        total += float(item['price'])
                        if item['is_coffee']: coffs += 1
                    
                    disc, curr = 0, st.session_state.current_customer
                    if curr:
                        # Termos Endirimi
                        if curr['type'] == 'thermos': 
                            disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                        
                        # Hədiyyə Kofe (9 Ulduz = 10-cu Pulsuz)
                        if curr['stars'] >= 9: 
                            c_items = [x for x in st.session_state.cart if x['is_coffee']]
                            if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                    
                    final = max(0, total - disc)
                    st.markdown(f"<div class='basket-total'>YEKUN: {final:.2f} ₼</div>", unsafe_allow_html=True)
                    if disc > 0: st.caption(f"Endirim: -{disc:.2f}")
                    
                    # Ödəniş Metodu (Aydın Seçim)
                    pay_method = st.radio("Ödəniş Növü:", ["Nəğd (Cash)", "Kart (Card)"], horizontal=True)
                    
                    if st.button("✅ TƏSDİQLƏ", type="primary", use_container_width=True, key="py"):
                        p_code = "Cash" if "Nəğd" in pay_method else "Card"
                        items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                        
                        run_action("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())", 
                                  {"i":items_str, "t":final, "p":p_code})
                        
                        if curr:
                            ns = curr['stars']
                            if coffs > 0:
                                # 10-cu kofe alındısa (stars >= 9), sıfırla
                                if curr['stars'] >= 9 and any(x['is_coffee'] for x in st.session_state.cart): 
                                    ns = 0 
                                else: 
                                    ns += 1
                            run_action("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id", {"s":ns, "id":curr['card_id']})
                        
                        st.success("Satış Uğurlu!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()
                else: st.info("Səbət boşdur")

        if role == 'admin':
            tabs = st.tabs(["🛒 POS", "📊 Analitika", "📧 CRM", "📋 Menyu", "👥 Admin", "🖨️ QR"])
            with tabs[0]: render_pos()
            
            with tabs[1]: # YENİLƏNMİŞ ANALİTİKA (AYLIQ)
                st.markdown("### 📊 Aylıq Satış Hesabatı")
                
                today = datetime.date.today()
                sel_date = st.date_input("Ay Seçin", today)
                sel_month = sel_date.strftime("%Y-%m")
                
                sales = run_query(f"SELECT * FROM sales WHERE TO_CHAR(created_at, 'YYYY-MM') = '{sel_month}' ORDER BY created_at DESC")
                
                if not sales.empty:
                    tot = sales['total'].sum()
                    cash = sales[sales['payment_method'] == 'Cash']['total'].sum()
                    card = sales[sales['payment_method'] == 'Card']['total'].sum()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Ümumi", f"{tot:.2f} ₼")
                    m2.metric("💵 Nağd", f"{cash:.2f} ₼")
                    m3.metric("💳 Kart", f"{card:.2f} ₼")
                    
                    st.divider()
                    sales['day'] = pd.to_datetime(sales['created_at']).dt.day
                    daily = sales.groupby('day')['total'].sum()
                    st.bar_chart(daily)
                    with st.expander("📄 Detallı Siyahı"): st.dataframe(sales)
                else: st.info("Satış yoxdur.")

            with tabs[2]: # CRM
                st.markdown("### 📧 CRM")
                m_df = run_query("SELECT card_id, email, birth_date FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    m_df['50% Endirim'] = False; m_df['Ad Günü'] = False
                    ed = st.data_editor(m_df, hide_index=True, use_container_width=True)
                    if st.button("🚀 Seçilənləri Göndər", key="crm_s"):
                        cnt = 0
                        for i, r in ed.iterrows():
                            if r['50% Endirim']: send_email(r['email'], "50% Endirim!", "Sizə özəl 50% endirim!"); run_action("INSERT INTO notifications (card_id, message) VALUES (:id, '50% Endirim!')", {"id":r['card_id']}); cnt+=1
                            if r['Ad Günü']: send_email(r['email'], "Ad Gününüz Mübarək!", "Bir kofe bizdən hədiyyə!"); run_action("INSERT INTO notifications (card_id, message) VALUES (:id, 'Ad Günü Hədiyyəsi!')", {"id":r['card_id']}); cnt+=1
                        st.success(f"{cnt} mesaj göndərildi!")
                    
                    st.divider()
                    with st.form("bulk"):
                        txt = st.text_area("Ümumi Bildiriş")
                        if st.form_submit_button("Hamıya Göndər"):
                            ids = run_query("SELECT card_id FROM customers")
                            for _, r in ids.iterrows(): run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :m)", {"id":r['card_id'], "m":txt})
                            st.success("Göndərildi!")
                else: st.info("Müştəri yoxdur")
            
            with tabs[3]:
                with st.form("addm"):
                    c1,c2,c3 = st.columns(3)
                    n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"])
                    cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                md = run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id")
                st.dataframe(md)
            
            with tabs[4]:
                with st.expander("🔑 Şifrə Dəyiş"):
                    all_us = run_query("SELECT username FROM users")
                    target = st.selectbox("Seç:", all_us['username'].tolist())
                    np = st.text_input("Yeni Şifrə", type="password", key="np_adm")
                    if st.button("Yenilə", key="upd_pass"):
                        run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(np), "u":target}); st.success("OK")
                with st.expander("➕ Yeni İşçi"):
                    un = st.text_input("User"); ps = st.text_input("Pass", type="password")
                    if st.button("Yarat", key="crt_stf"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u":un, "p":hash_password(ps)}); st.success("OK")
            with tabs[5]:
                cnt = st.number_input("Say", 1, 50); is_th = st.checkbox("Termos?")
                if st.button("Yarat", key="crt_qr"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    typ = "thermos" if is_th else "standard"
                    for i in ids: run_action("INSERT INTO customers (card_id, stars, type) VALUES (:i, 0, :t)", {"i":i, "t":typ})
                    
                    if cnt == 1:
                        d = generate_custom_qr(f"{APP_URL}/?id={ids[0]}", ids[0])
                        st.image(BytesIO(d), width=200); st.download_button("⬇️ PNG", d, f"{ids[0]}.png", "image/png")
                    else:
                        z = BytesIO()
                        with zipfile.ZipFile(z, "w") as zf:
                            for i in ids: zf.writestr(f"{i}.png", generate_custom_qr(f"{APP_URL}/?id={i}", i))
                        st.download_button("📦 ZIP", z.getvalue(), "qr.zip", "application/zip")

        elif role == 'staff':
            render_pos()
