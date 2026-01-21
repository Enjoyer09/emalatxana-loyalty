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
import smtplib
import datetime
import requests

# --- EMAIL AYARLARI ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY") or "xkeysib-..."
SENDER_EMAIL = "info@emalatxana.az" 
SENDER_NAME = "Emalatxana Loyalty"

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(
    page_title="Emalatxana POS", 
    page_icon="☕", 
    layout="wide", # POS üçün geniş ekran
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
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://")
    conn = st.connection("neon", type="sql", url=db_url)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- SCHEMA & SEED (MENYU BAZASI) ---
def ensure_schema_and_seed():
    with conn.session as s:
        # Tables
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS email TEXT;"))
        
        # Menu Table Update
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS menu (
                id SERIAL PRIMARY KEY,
                item_name TEXT,
                price DECIMAL(10,2),
                category TEXT,
                is_coffee BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE
            );
        """))
        s.commit()
        
        # MENYUNU DOLDURMAQ (Əgər boşdursa)
        check = s.execute(text("SELECT count(*) FROM menu")).scalar()
        if check == 0:
            # Sizin verdiyiniz menyu
            menu_items = [
                # Alkaqolsuz
                ("Su", 2, "İçkilər", False), ("Çay (şirniyyat)", 3, "İçkilər", False), 
                ("Yaşıl çay", 4, "İçkilər", False), ("Meyvəli çay", 4, "İçkilər", False),
                ("Portağal şirəsi", 6, "İçkilər", False), ("Meyvə şirəsi", 4, "İçkilər", False),
                ("Limonad", 6, "İçkilər", False), ("Kola", 4, "İçkilər", False),
                ("Tonik", 5, "İçkilər", False), ("Energetik", 6, "İçkilər", False),
                # Qəhvə (S, M, L) - Hamısı Coffee True
                ("Americano S", 3.9, "Qəhvə", True), ("Americano M", 4.9, "Qəhvə", True), ("Americano L", 5.9, "Qəhvə", True),
                ("Ice Americano S", 4.5, "Qəhvə", True), ("Ice Americano M", 5.5, "Qəhvə", True), ("Ice Americano L", 6.5, "Qəhvə", True),
                ("Cappuccino S", 4.5, "Qəhvə", True), ("Cappuccino M", 5.5, "Qəhvə", True), ("Cappuccino L", 6.5, "Qəhvə", True),
                ("Iced Cappuccino S", 4.7, "Qəhvə", True), ("Iced Cappuccino M", 5.7, "Qəhvə", True), ("Iced Cappuccino L", 6.7, "Qəhvə", True),
                ("Latte S", 4.5, "Qəhvə", True), ("Latte M", 5.5, "Qəhvə", True), ("Latte L", 6.5, "Qəhvə", True),
                ("Iced Latte S", 4.7, "Qəhvə", True), ("Iced Latte M", 5.7, "Qəhvə", True), ("Iced Latte L", 6.7, "Qəhvə", True),
                ("Raf S", 4.7, "Qəhvə", True), ("Raf M", 5.7, "Qəhvə", True), ("Raf L", 6.7, "Qəhvə", True),
                ("Mocha S", 4.7, "Qəhvə", True), ("Mocha M", 5.7, "Qəhvə", True), ("Mocha L", 6.7, "Qəhvə", True),
                ("Ristretto S", 3, "Qəhvə", True), ("Ristretto M", 4, "Qəhvə", True), ("Ristretto L", 5, "Qəhvə", True),
                ("Espresso S", 3, "Qəhvə", True), ("Espresso M", 4, "Qəhvə", True), ("Espresso L", 5, "Qəhvə", True),
                ("Lungo S", 3, "Qəhvə", True), ("Lungo M", 4, "Qəhvə", True), ("Lungo L", 5, "Qəhvə", True),
                ("Flat White S", 4.5, "Qəhvə", True), ("Flat White M", 5.5, "Qəhvə", True), ("Flat White L", 6.5, "Qəhvə", True),
                ("Affogato S", 4.7, "Qəhvə", True), ("Affogato M", 5.7, "Qəhvə", True), ("Affogato L", 6.7, "Qəhvə", True),
                ("Glisse S", 4.9, "Qəhvə", True), ("Glisse M", 5.9, "Qəhvə", True), ("Glisse L", 6.9, "Qəhvə", True),
                ("İsti Şokolad S", 4.2, "İçkilər", False), ("İsti Şokolad M", 5.2, "İçkilər", False), ("İsti Şokolad L", 6.2, "İçkilər", False),
                ("Milkşeyk S", 4.5, "İçkilər", False), ("Milkşeyk M", 5.5, "İçkilər", False), ("Milkşeyk L", 6.5, "İçkilər", False),
                ("Dondurma S", 3, "Desert", False), ("Dondurma M", 4, "Desert", False), ("Dondurma L", 5, "Desert", False),
            ]
            for name, price, cat, is_cof in menu_items:
                s.execute(text("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n, :p, :c, :ic)"),
                          {"n": name, "p": price, "c": cat, "ic": is_cof})
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

# --- UI STYLES (POS & MOBILE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Anton'; letter-spacing: 1px; }
    p, div, button { font-family: 'Oswald'; }
    
    /* POS BUTTONS */
    .pos-btn {
        background: white; border: 1px solid #ddd; border-radius: 8px;
        padding: 15px; text-align: center; cursor: pointer;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); transition: 0.2s;
        height: 100%; display: flex; flex-direction: column; justify-content: center;
    }
    .pos-btn:hover { border-color: #2e7d32; background: #f1f8e9; }
    .pos-price { color: #2e7d32; font-weight: bold; font-size: 18px; }
    .pos-name { font-size: 16px; font-weight: 500; margin-bottom: 5px; }
    
    /* BASKET */
    .basket-item {
        display: flex; justify-content: space-between; padding: 10px;
        border-bottom: 1px solid #eee; background: white;
    }
    .basket-total {
        font-size: 24px; font-weight: bold; text-align: right; margin-top: 20px; color: #2e7d32;
    }
    
    /* CUSTOMER VIEW */
    .digital-card {
        background: linear-gradient(145deg, #ffffff, #f9f9f9); border-radius: 20px;
        padding: 20px; margin-bottom: 15px; border: 1px solid #fff;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08);
    }
    .coffee-grid { display: flex; justify-content: center; gap: 10px; margin: 15px 0; }
    .coffee-item { width: 40px; }
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
    
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        
        # Aktivasiya
        if not user['is_active']:
            st.warning("⚠️ Kart aktiv deyil!")
            with st.form("act"):
                em = st.text_input("Email")
                if st.form_submit_button("Aktivləşdir"):
                    run_action("UPDATE customers SET email=:e, is_active=TRUE WHERE card_id=:i", {"e":em, "i":card_id})
                    st.rerun()
            st.stop()

        # Kart
        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        if user['type'] == 'thermos': st.info("⭐ VIP TERMOS KLUBU (20% ENDİRİM)")
        st.markdown(f"<h3 style='text-align:center'>KART: {user['stars']}/10</h3>", unsafe_allow_html=True)
        
        # Grid
        cols = st.columns(5)
        html = '<div class="coffee-grid">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png" if i < user['stars'] else "https://cdn-icons-png.flaticon.com/512/1174/1174444.png"
            op = "1" if i < user['stars'] else "0.2"
            html += f'<img src="{icon}" style="width:35px; opacity:{op}; margin:2px;">'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        
        rem = 10 - user['stars']
        msg = f"🎉 TƏBRİKLƏR! 1 Kofe Bizdən!" if rem == 0 else f"🎁 {rem} kofedən sonra hədiyyə!"
        st.markdown(f"<p style='text-align:center;color:#d32f2f;font-weight:bold;font-size:18px;'>{msg}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        lnk = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(lnk, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS TERMİNAL ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1])
        with c2: 
            st.image("emalatxana.png", width=150)
            st.markdown("<h3 style='text-align:center'>POS GİRİŞ</h3>", unsafe_allow_html=True)
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
        # --- POS HEADER ---
        h1, h2, h3 = st.columns([2,6,1])
        with h1: 
            if st.button("🔴 Çıxış"): st.session_state.logged_in = False; st.rerun()
        with h3:
            if st.button("🔄"): st.rerun()

        role = st.session_state.role
        
        # --- POS INTERFACE ---
        if role == 'staff' or role == 'admin':
            
            # Layout: Sol (Menyu) - Sağ (Çek)
            left_col, right_col = st.columns([2, 1])
            
            with left_col:
                st.markdown("### 🛒 MENYU")
                
                # Müştəri Tanıtma
                c_scan, c_info = st.columns([2, 2])
                with c_scan:
                    scan_val = st.text_input("Müştəri QR (və ya boş)", key="pos_scan")
                    if st.button("🔍 Axtar"):
                        if scan_val:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                            if not c_df.empty:
                                st.session_state.current_customer = c_df.iloc[0].to_dict()
                                st.success(f"Müştəri: {scan_val} | ⭐ {c_df.iloc[0]['stars']}")
                            else: st.error("Tapılmadı")
                        else: st.session_state.current_customer = None
                
                with c_info:
                    curr = st.session_state.current_customer
                    if curr:
                        st.info(f"👤 Müştəri: {curr['card_id']}\n\n⭐ Ulduz: {curr['stars']}\n\n🏷️ Tip: {curr['type'].upper()}")
                        if curr['type'] == 'thermos': st.markdown("✅ **20% Termos Endirimi**")
                        if curr['stars'] >= 10: st.markdown("🎁 **1 PULSUZ KOFE VAR!**")
                        if st.button("❌ Ləğv et"): st.session_state.current_customer = None; st.rerun()
                
                # Kateqoriyalar
                cats = ["Qəhvə", "İçkilər", "Desert"]
                selected_cat = st.radio("Kateqoriya:", cats, horizontal=True)
                
                # Məhsullar (Grid)
                menu_df = run_query("SELECT * FROM menu WHERE category=:c ORDER BY id", {"c": selected_cat})
                
                # 3 sütunlu grid
                cols = st.columns(3)
                for i, row in menu_df.iterrows():
                    with cols[i % 3]:
                        # Düymə kimi görünən container
                        if st.button(f"{row['item_name']}\n{row['price']} ₼", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state.cart.append(row.to_dict())
                            st.rerun()

            with right_col:
                st.markdown("### 🧾 ÇEK")
                
                if st.session_state.cart:
                    total = 0
                    coffee_count = 0
                    
                    # Çek Siyahısı
                    for i, item in enumerate(st.session_state.cart):
                        col_name, col_price, col_del = st.columns([3, 1, 1])
                        col_name.write(item['item_name'])
                        col_price.write(f"{item['price']} ₼")
                        if col_del.button("🗑️", key=f"del_{i}"):
                            st.session_state.cart.pop(i)
                            st.rerun()
                        
                        total += float(item['price'])
                        if item['is_coffee']: coffee_count += 1
                    
                    st.divider()
                    
                    # Endirim Hesablaması
                    discount = 0
                    final_total = total
                    customer = st.session_state.current_customer
                    
                    msg = []
                    
                    if customer:
                        # 1. Termos Endirimi (Coffee items only)
                        if customer['type'] == 'thermos':
                            coffee_total = sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']])
                            disc_amount = coffee_total * 0.20
                            if disc_amount > 0:
                                discount += disc_amount
                                msg.append(f"Termos (-{disc_amount:.2f} ₼)")
                        
                        # 2. Pulsuz Kofe (10 Ulduz)
                        if customer['stars'] >= 10:
                            # Səbətdə kofe varsa, ən ucuzunu pulsuz et
                            coffees = [x for x in st.session_state.cart if x['is_coffee']]
                            if coffees:
                                free_item = min(coffees, key=lambda x: float(x['price']))
                                discount += float(free_item['price'])
                                msg.append(f"Hədiyyə Kofe (-{free_item['price']} ₼)")
                    
                    final_total = max(0, total - discount)
                    
                    st.markdown(f"<div class='basket-total'>CƏM: {total:.2f} ₼</div>", unsafe_allow_html=True)
                    if discount > 0:
                        st.markdown(f"<div style='text-align:right;color:red'>Endirim: -{discount:.2f} ₼</div>", unsafe_allow_html=True)
                        for m in msg: st.caption(f"ℹ️ {m}")
                    
                    st.markdown(f"<div class='basket-total' style='font-size:32px; border-top:1px solid #ddd'>YEKUN: {final_total:.2f} ₼</div>", unsafe_allow_html=True)
                    
                    # Ödəniş
                    pay_method = st.radio("Ödəniş:", ["Nəğd", "Kart"], horizontal=True)
                    
                    if st.button("✅ ÖDƏNİŞİ TƏSDİQLƏ", type="primary", use_container_width=True):
                        # 1. Bazaya Yazmaq
                        items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                        run_action("INSERT INTO sales (items, total, payment_method) VALUES (:i, :t, :p)", 
                                  {"i": items_str, "t": final_total, "p": pay_method})
                        
                        # 2. Müştəri Yeniləməsi
                        if customer:
                            new_stars = customer['stars']
                            
                            # Ulduz artımı (Hər kofe üçün +1 ulduz? Yoxsa visit başına?)
                            # Qayda: Adətən hər çek üçün 1 ulduz və ya hər kofe üçün.
                            # Gəlin hələlik 1 kofe varsa +1 ulduz verək.
                            if coffee_count > 0:
                                # Əgər pulsuz kofe istifadə edibsə, ulduzları silirik
                                if customer['stars'] >= 10 and any(x['is_coffee'] for x in st.session_state.cart):
                                    new_stars = 0 # Sıfırla
                                    run_action("INSERT INTO logs (card_id, staff_name, action_type) VALUES (:id, :s, 'Free Coffee Used')", {"id":customer['card_id'], "s":st.session_state.user})
                                else:
                                    # Kofe alıbsa ulduz artır
                                    new_stars += 1 # Və ya coffee_count qədər
                                    run_action("INSERT INTO logs (card_id, staff_name, action_type) VALUES (:id, :s, 'Purchase')", {"id":customer['card_id'], "s":st.session_state.user})
                            
                            run_action("UPDATE customers SET stars = :s, last_visit = NOW() WHERE card_id = :id", 
                                      {"s": new_stars, "id": customer['card_id']})
                        
                        st.success("Satış uğurlu!")
                        st.session_state.cart = []
                        st.session_state.current_customer = None
                        time.sleep(1)
                        st.rerun()
                        
                else:
                    st.info("Səbət boşdur")

        # --- ADMIN DASHBOARD ---
        if role == 'admin':
            st.divider()
            with st.expander("📊 ADMIN STATİSTİKA"):
                # Satışlar
                sales_df = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
                st.dataframe(sales_df)
                
                total_sales = run_query("SELECT SUM(total) as t FROM sales WHERE created_at::date = CURRENT_DATE")
                t_val = total_sales.iloc[0]['t'] if not total_sales.empty and total_sales.iloc[0]['t'] else 0
                st.metric("Bu Günlük Satış", f"{t_val} ₼")
