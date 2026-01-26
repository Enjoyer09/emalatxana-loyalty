import streamlit as st
import pandas as pd
import random
import qrcode
from io import BytesIO
import zipfile
from PIL import Image, ImageDraw, ImageFont
import time
from sqlalchemy import text
import os
import bcrypt
import requests
import datetime
import secrets
import threading

# ==========================================
# === IRONWAVES UNIFIED SYSTEM (POS + INVENTORY) ===
# ==========================================

# --- INFRASTRUKTUR & AYARLAR ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SHOP_NAME_DEFAULT = "Emalatxana Coffee"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"
DOMAIN = "emalatxana.ironwaves.store"
APP_URL = f"https://{DOMAIN}"

st.set_page_config(page_title="Ironwaves POS & Inventory", page_icon="☕", layout="wide", initial_sidebar_state="expanded")

# --- DATABASE BAĞLANTISI ---
try:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        st.error("DATABASE_URL tapılmadı!")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e:
    st.error(f"DB Xətası: {e}")
    st.stop()

# --- SCHEMA YOXLANILMASI (V1 + V2 CƏDVƏLLƏRİ) ---
def ensure_schema():
    with conn.session as s:
        # V1 Tables
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))

        # V2 Tables (Inventory & Recipes)
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY, 
                name TEXT, 
                unit TEXT, 
                stock_level DECIMAL(10,3) DEFAULT 0, 
                cost_per_unit DECIMAL(10,2) DEFAULT 0, 
                alert_limit DECIMAL(10,3) DEFAULT 5
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS recipes (
                id SERIAL PRIMARY KEY, 
                menu_item_name TEXT, 
                inventory_item_id INTEGER REFERENCES inventory(id), 
                quantity_required DECIMAL(10,3)
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY, 
                description TEXT, 
                amount DECIMAL(10,2), 
                category TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        s.commit()
ensure_schema()

# --- HELPER FUNCTIONS ---
def get_config(key, default=""):
    try:
        df = conn.query("SELECT value FROM settings WHERE key = :k", params={"k": key})
        return df.iloc[0]['value'] if not df.empty else default
    except: return default

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

def run_query(q, p=None): return conn.query(q, params=p, ttl=0)

def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h

# --- INVENTORY LOGIC (V2 CORE) ---
def deduct_inventory_for_sale(items_list):
    """Satış zamanı anbardan silinmə funksiyası"""
    log_msgs = []
    with conn.session as s:
        for item in items_list:
            item_name = item['item_name']
            # Resepti tapırıq
            recipes = s.execute(text("SELECT inventory_item_id, quantity_required FROM recipes WHERE menu_item_name = :n"), {"n": item_name}).fetchall()
            
            if recipes:
                for inv_id, qty in recipes:
                    # Anbardan silirik
                    s.execute(text("UPDATE inventory SET stock_level = stock_level - :q WHERE id = :id"), {"q": qty, "id": inv_id})
                log_msgs.append(f"✅ {item_name}: Resept əsasında silindi.")
            else:
                log_msgs.append(f"⚠️ {item_name}: Resept tapılmadı, stok dəyişmədi.")
        s.commit()
    return log_msgs

# --- LOGIN & SESSION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'current_customer' not in st.session_state: st.session_state.current_customer = None

def check_session_token():
    token = st.query_params.get("token")
    if token:
        res = run_query("SELECT username, role FROM active_sessions WHERE token=:t", {"t":token})
        if not res.empty:
            st.session_state.logged_in = True
            st.session_state.user = res.iloc[0]['username']
            st.session_state.role = res.iloc[0]['role']
check_session_token()

# ==========================================
# === UI: MÜŞTƏRİ EKRANI (Əgər ID varsa) ===
# ==========================================
if "id" in st.query_params:
    # (Bu hissə V1 kodu ilə eynidir - Müştəri kartını göstərir)
    card_id = st.query_params["id"]
    st.markdown(f"<h1 style='text-align:center'>Xoş Gəldiniz!</h1>", unsafe_allow_html=True)
    cust = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":card_id})
    if not cust.empty:
        row = cust.iloc[0]
        st.info(f"Bonus Balınız: {row['stars']} ⭐")
        st.success("Kassanı yaxınlaşın və endirimdən yararlanın!")
    else:
        st.error("Kart tapılmadı.")
    st.stop()

# ==========================================
# === UI: ADMIN & POS PANELİ ===
# ==========================================

if not st.session_state.logged_in:
    # --- Login Screen ---
    st.markdown("<h2 style='text-align:center'>Ironwaves POS & Inventory</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        tab1, tab2 = st.tabs(["STAFF", "ADMIN"])
        with tab1:
            pin = st.text_input("PIN Kodu", type="password")
            if st.button("Daxil Ol", key="btn_staff"):
                user = run_query("SELECT * FROM users WHERE role='staff'")
                for _, u in user.iterrows():
                    if verify_password(pin, u['password']):
                        st.session_state.logged_in = True; st.session_state.role = 'staff'; st.session_state.user = u['username']
                        st.rerun()
                st.error("Yanlış PIN")
        with tab2:
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.button("Admin Giriş", key="btn_admin"):
                adm = run_query("SELECT * FROM users WHERE role='admin' AND username=:u", {"u":u})
                if not adm.empty and verify_password(p, adm.iloc[0]['password']):
                    st.session_state.logged_in = True; st.session_state.role = 'admin'; st.session_state.user = u
                    st.rerun()
                else: st.error("Səhvdir")

else:
    # --- Main App (Logged In) ---
    st.sidebar.title(f"👤 {st.session_state.user}")
    
    app_mode = st.sidebar.radio("Menyu", ["🛍️ POS (Satış)", "📦 Anbar & Resept", "📊 Hesabatlar", "⚙️ Ayarlar"])
    
    if st.sidebar.button("🔴 Çıxış"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

    # --- 1. POS MODULE ---
    if app_mode == "🛍️ POS (Satış)":
        c1, c2 = st.columns([1.5, 2.5])
        
        with c1: # POS Sol (Səbət)
            st.markdown("### 🛒 Səbət")
            if st.session_state.current_customer:
                curr = st.session_state.current_customer
                st.success(f"Müştəri: {curr['card_id']} | ⭐ {curr['stars']}")
                if st.button("Müştərini Çıxar"): st.session_state.current_customer = None; st.rerun()
            else:
                card_input = st.text_input("Müştəri QR (Skan)", key="qr_scan")
                if st.button("Axtar") and card_input:
                     # Sadə QR parse
                    clean_id = card_input.split("id=")[1].split("&")[0] if "id=" in card_input else card_input
                    c_data = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":clean_id})
                    if not c_data.empty: st.session_state.current_customer = c_data.iloc[0].to_dict(); st.rerun()
            
            # Cart Display
            total = 0
            if st.session_state.cart:
                for i, item in enumerate(st.session_state.cart):
                    cc1, cc2, cc3 = st.columns([3, 1, 1])
                    cc1.write(item['item_name']); cc2.write(f"{item['price']}₼")
                    if cc3.button("❌", key=f"del_{i}"): st.session_state.cart.pop(i); st.rerun()
                    total += float(item['price'])
                
                st.markdown(f"### Cəm: {total:.2f} ₼")
                
                # PAYMENT
                pay_method = st.radio("Ödəniş:", ["Nəğd", "Kart"], horizontal=True)
                if st.button("✅ SATIŞI TAMAMLA", type="primary", use_container_width=True):
                    items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                    
                    # 1. Bazaya Yaz (Sales)
                    run_action("INSERT INTO sales (items, total, payment_method, cashier, created_at) VALUES (:i, :t, :p, :c, NOW())",
                               {"i":items_str, "t":total, "p": ("Cash" if pay_method=="Nəğd" else "Card"), "c":st.session_state.user})
                    
                    # 2. Bonus Hesabla (Sadə)
                    if st.session_state.current_customer:
                         new_stars = st.session_state.current_customer['stars'] + 1
                         run_action("UPDATE customers SET stars=:s WHERE card_id=:id", {"s":new_stars, "id":st.session_state.current_customer['card_id']})

                    # 3. ANBAR SİLİNMƏSİ (V2 LOGIC)
                    try:
                        logs = deduct_inventory_for_sale(st.session_state.cart)
                        for l in logs: st.toast(l)
                    except Exception as e:
                        st.error(f"Anbar xətası: {e}")

                    st.success("Satış uğurlu!"); st.session_state.cart = []; st.session_state.current_customer = None; time.sleep(1); st.rerun()
            else:
                st.info("Səbət boşdur")

        with c2: # POS Sağ (Menyu)
            st.markdown("### 📋 Menyu")
            cats = run_query("SELECT DISTINCT category FROM menu WHERE is_active=True")
            if not cats.empty:
                sel_cat = st.pills("Kateqoriya", cats['category'].tolist())
                if sel_cat:
                    items = run_query("SELECT * FROM menu WHERE category=:c AND is_active=True", {"c":sel_cat})
                    col_grid = st.columns(3)
                    for idx, row in items.iterrows():
                        with col_grid[idx % 3]:
                            if st.button(f"{row['item_name']}\n{row['price']}₼", key=f"add_{row['id']}"):
                                st.session_state.cart.append(row.to_dict())
                                st.rerun()

    # --- 2. INVENTORY & RECIPES MODULE (V2) ---
    elif app_mode == "📦 Anbar & Resept":
        sub_tab = st.radio("Bölmə:", ["Xammal (Inventory)", "Reseptlər (Recipes)"], horizontal=True)
        
        if sub_tab == "Xammal (Inventory)":
            st.markdown("#### 📦 Xammal Anbarı")
            with st.expander("➕ Yeni Xammal Əlavə Et"):
                with st.form("new_inv"):
                    c1, c2 = st.columns(2)
                    n = c1.text_input("Ad (məs: Süd)")
                    u = c2.selectbox("Vahid", ["litr", "kq", "ədəd", "qr"])
                    s = c1.number_input("Stok", 0.0)
                    c = c2.number_input("Vahid Qiyməti (AZN)", 0.0)
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO inventory (name, unit, stock_level, cost_per_unit) VALUES (:n, :u, :s, :c)", {"n":n, "u":u, "s":s, "c":c})
                        st.success("Əlavə edildi!"); st.rerun()
            
            # Cədvəl
            inv_df = run_query("SELECT * FROM inventory ORDER BY id")
            edited_inv = st.data_editor(inv_df, key="inv_edit", num_rows="dynamic")
            if st.button("Dəyişiklikləri Yadda Saxla (Stok)"):
                # Burada sadə update məntiqi yazıla bilər, hələlik sadə saxlayırıq
                st.warning("Data editor hələ tam aktiv deyil, birbaşa DB-dən oxuyur.")

        elif sub_tab == "Reseptlər (Recipes)":
            st.markdown("#### 📜 Məhsul Reseptləri")
            st.info("Burada menyu məhsulunu seçib, tərkibində hansı xammalın getdiyini yazırsan.")
            
            col1, col2 = st.columns(2)
            with col1:
                menu_items = run_query("SELECT item_name FROM menu WHERE is_active=True")
                sel_menu = st.selectbox("Menyu Məhsulu:", menu_items['item_name'].tolist() if not menu_items.empty else [])
            
            with col2:
                inv_items = run_query("SELECT id, name, unit FROM inventory")
                inv_dict = {f"{r['name']} ({r['unit']})": r['id'] for _, r in inv_items.iterrows()}
                sel_inv = st.selectbox("Xammal Seç:", list(inv_dict.keys()) if inv_dict else [])
            
            qty = st.number_input("Miqdar (Seçilən vahiddə)", 0.001, step=0.001, format="%.3f")
            
            if st.button("Reseptə Əlavə Et"):
                if sel_menu and sel_inv:
                    run_action("INSERT INTO recipes (menu_item_name, inventory_item_id, quantity_required) VALUES (:m, :i, :q)",
                               {"m":sel_menu, "i":inv_dict[sel_inv], "q":qty})
                    st.success(f"{sel_menu} reseptinə əlavə edildi!"); st.rerun()
            
            st.divider()
            st.markdown("##### Mövcud Reseptlər")
            rec_view = run_query("""
                SELECT r.id, r.menu_item_name, i.name as xammal, r.quantity_required, i.unit 
                FROM recipes r 
                JOIN inventory i ON r.inventory_item_id = i.id
                ORDER BY r.menu_item_name
            """)
            st.dataframe(rec_view, use_container_width=True)

    # --- 3. REPORTS MODULE ---
    elif app_mode == "📊 Hesabatlar":
        st.markdown("### 📊 Satış Hesabatı")
        sales = run_query("SELECT * FROM sales ORDER BY created_at DESC LIMIT 50")
        st.dataframe(sales)
        st.metric("Ümumi Satış", f"{sales['total'].sum():.2f} ₼")

    # --- 4. SETTINGS ---
    elif app_mode == "⚙️ Ayarlar":
        st.write("Sistem Ayarları")
        if st.button("Keşi Təmizlə"): st.cache_data.clear(); st.success("Təmizləndi")
