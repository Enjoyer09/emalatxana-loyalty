import streamlit as st
import pandas as pd
import random
import time
from sqlalchemy import text
import os
import bcrypt
import secrets
import datetime
import math
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from io import BytesIO
import zipfile
import requests
import json
import base64
import streamlit.components.v1 as components
import re
import numpy as np

# ==========================================
# === EMALATKHANA POS - V6.34 (ANTI-CRASH STABLE EDIT) ===
# ==========================================

VERSION = "v6.34 (Stable Edit: No Jumping to POS, Strict Type Casting)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- CONFIG ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")
ADMIN_DEFAULT_PASS = os.environ.get("ADMIN_PASS", "admin123") 

# --- YENİLƏNMİŞ QAYDALAR ---
DEFAULT_TERMS = """
<div style="font-family: 'Arial', sans-serif; color: #333; line-height: 1.6; font-size: 14px; background-color: #e8f5e9; padding: 15px; border-radius: 10px; border-left: 5px solid #2E7D32;">
    <h4 style="color: #2E7D32; margin-top: 0;">
        📜 Xoş Gəldiniz! Qaydalar:
    </h4>
    <ul style="padding-left: 20px; margin-bottom: 0;">
        <li>🔹 <strong>5% Endirim:</strong> Bütün kofe və içkilərə şamil olunur.</li>
        <li>🔹 <strong>Hədiyyə Kofe:</strong> 9 ulduz yığanda 10-cu kofe bizdən Hədiyyə! 🎁</li>
        <li>🔹 Kart yalnız şəxsi istifadə üçündür.</li>
    </ul>
</div>
"""

CARTOON_QUOTES = ["Bu gün sənin günündür! 🚀", "Qəhrəman kimi parılda! ⭐", "Bir fincan kofe = Xoşbəxtlik! ☕", "Enerjini topla, dünyanı fəth et! 🌍"]
SUBJECTS = ["Admin", "Abbas (Manager)", "Nicat (Investor)", "Elvin (Investor)", "Bank Kartı (Şirkət)", "Təchizatçı", "Digər"]

# --- PRESET KATEQORIYALAR ---
PRESET_CATEGORIES = [
    "Kofe (Dənələr)", 
    "Süd Məhsulları", 
    "Bar Məhsulları (Su/Buz)", 
    "Siroplar", 
    "Soslar və Pastalar", 
    "Qablaşdırma (Stəkan/Qapaq)", 
    "Şirniyyat (Hazır)", 
    "İçkilər (Hazır)",
    "Meyvə-Tərəvəz",
    "Təsərrüfat/Təmizlik"
]

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"
APP_URL = "https://emalatxana.ironwaves.store"

# --- STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'session_token' not in st.session_state: st.session_state.session_token = None
if 'cart_takeaway' not in st.session_state: st.session_state.cart_takeaway = []
if 'cart_table' not in st.session_state: st.session_state.cart_table = []
if 'current_customer_ta' not in st.session_state: st.session_state.current_customer_ta = None
if 'selected_table' not in st.session_state: st.session_state.selected_table = None
if 'show_receipt_popup' not in st.session_state: st.session_state.show_receipt_popup = False
if 'last_receipt_data' not in st.session_state: st.session_state.last_receipt_data = None
if 'anbar_page' not in st.session_state: st.session_state.anbar_page = 0
if 'anbar_rows_per_page' not in st.session_state: st.session_state.anbar_rows_per_page = 20
if 'edit_item_id' not in st.session_state: st.session_state.edit_item_id = None
if 'edit_finance_id' not in st.session_state: st.session_state.edit_finance_id = None
if 'restock_item_id' not in st.session_state: st.session_state.restock_item_id = None
if 'menu_edit_id' not in st.session_state: st.session_state.menu_edit_id = None
if 'z_report_active' not in st.session_state: st.session_state.z_report_active = False
if 'z_calculated' not in st.session_state: st.session_state.z_calculated = False 
if 'sale_to_delete' not in st.session_state: st.session_state.sale_to_delete = None

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;700&display=swap');

    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F8F9FA !important; color: #333 !important; font-family: 'Arial', sans-serif !important; }
    
    div[data-testid="stStatusWidget"] { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }

    div.stButton > button { 
        border-radius: 12px !important; min-height: 80px !important; 
        font-weight: bold !important; font-size: 18px !important; 
        border: 1px solid #ccc !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important; 
    }
    div.stButton > button:active { transform: scale(0.98); }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #43A047, #2E7D32) !important; color: white !important; }

    .cartoon-quote { font-family: 'Comfortaa', cursive; color: #E65100; font-size: 22px; font-weight: 700; text-align: center; margin-bottom: 20px; animation: float 3s infinite; }
    @keyframes float { 0% {transform: translateY(0px);} 50% {transform: translateY(-8px);} 100% {transform: translateY(0px);} }
    .msg-box { background: linear-gradient(45deg, #FF9800, #FFC107); padding: 15px; border-radius: 15px; color: white; font-weight: bold; text-align: center; margin-bottom: 20px; font-family: 'Comfortaa', cursive !important; animation: pulse 2s infinite; }
    @keyframes pulse { 0% {transform: scale(1);} 50% {transform: scale(1.02);} 100% {transform: scale(1);} }

    .stamp-container { display: flex; justify-content: center; margin-bottom: 20px; }
    .stamp-card { background: white; padding: 15px 30px; text-align: center; font-family: 'Courier Prime', monospace; font-weight: bold; transform: rotate(-3deg); border-radius: 12px; border: 4px solid #B71C1C; color: #B71C1C; box-shadow: 0 0 0 4px white, 0 0 0 7px #B71C1C; }

    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; justify-items: center; margin-top: 20px; max-width: 400px; margin-left: auto; margin-right: auto; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.5s ease; }
    .cup-earned { filter: invert(24%) sepia(96%) saturate(1720%) hue-rotate(94deg) brightness(92%) contrast(102%); opacity: 1; transform: scale(1.1); }
    .cup-red-base { filter: invert(18%) sepia(90%) saturate(6329%) hue-rotate(356deg) brightness(96%) contrast(116%); }
    .cup-anim { animation: bounce 1s infinite; }
    .cup-empty { filter: grayscale(100%); opacity: 0.2; }
    @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-5px);} }

    div[data-testid="stRating"] { justify-content: center !important; transform: scale(1.5); }
    div[data-testid="stRating"] svg { fill: #FF0000 !important; color: #FF0000 !important; }
    @media print { body * { visibility: hidden; } #hidden-print-area, #hidden-print-area * { visibility: visible; } #hidden-print-area { position: fixed; left: 0; top: 0; width: 100%; } }
    </style>
""", unsafe_allow_html=True)

# --- DB ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL") or os.environ.get("DATABASE_URL")
    if not db_url: st.error("DB URL Not Found"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True, pool_size=20, max_overflow=30)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

@st.cache_resource
def ensure_schema():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS tables (id SERIAL PRIMARY KEY, label TEXT, is_occupied BOOLEAN DEFAULT FALSE, items TEXT, total DECIMAL(10,2) DEFAULT 0, opened_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_active BOOLEAN DEFAULT FALSE, is_coffee BOOLEAN DEFAULT FALSE, printer_target TEXT DEFAULT 'kitchen', price_half DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, customer_card_id TEXT);"))
        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS original_total DECIMAL(10,2) DEFAULT 0")); s.commit()
        except: pass
        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS discount_amount DECIMAL(10,2) DEFAULT 0")); s.commit()
        except: pass
        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS note TEXT")); s.commit()
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS ingredients (id SERIAL PRIMARY KEY, name TEXT UNIQUE, stock_qty DECIMAL(10,2) DEFAULT 0, unit TEXT, category TEXT, min_limit DECIMAL(10,2) DEFAULT 10, type TEXT DEFAULT 'ingredient', unit_cost DECIMAL(18,5) DEFAULT 0, approx_count INTEGER DEFAULT 0);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS finance (id SERIAL PRIMARY KEY, type TEXT, category TEXT, amount DECIMAL(10,2), source TEXT, description TEXT, created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        try: s.execute(text("ALTER TABLE finance ADD COLUMN IF NOT EXISTS subject TEXT")); s.commit()
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, amount DECIMAL(10,2), reason TEXT, spender TEXT, source TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS recipes (id SERIAL PRIMARY KEY, menu_item_name TEXT, ingredient_name TEXT, quantity_required DECIMAL(10,2));"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customers (card_id TEXT PRIMARY KEY, stars INTEGER DEFAULT 0, type TEXT, email TEXT, birth_date TEXT, is_active BOOLEAN DEFAULT FALSE, last_visit TIMESTAMP, secret_token TEXT, gender TEXT, staff_note TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS promo_codes (id SERIAL PRIMARY KEY, code TEXT UNIQUE, discount_percent INTEGER, valid_until DATE, assigned_user_id TEXT, is_used BOOLEAN DEFAULT FALSE);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, attached_coupon TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS system_logs (id SERIAL PRIMARY KEY, username TEXT, action TEXT, customer_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        try: s.execute(text("ALTER TABLE system_logs ADD COLUMN IF NOT EXISTS customer_id TEXT")); s.commit()
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS feedbacks (id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        
        # ADMIN NOTES UPDATE
        s.execute(text("CREATE TABLE IF NOT EXISTS admin_notes (id SERIAL PRIMARY KEY, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        try: s.execute(text("ALTER TABLE admin_notes ADD COLUMN IF NOT EXISTS title TEXT")); s.commit()
        except: pass
        try: s.execute(text("ALTER TABLE admin_notes ADD COLUMN IF NOT EXISTS amount DECIMAL(10,2) DEFAULT 0")); s.commit()
        except: pass

        try:
            p_hash = bcrypt.hashpw(ADMIN_DEFAULT_PASS.encode(), bcrypt.gensalt()).decode()
            s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin') ON CONFLICT (username) DO NOTHING"), {"p": p_hash})
            s.commit()
        except: s.rollback()
    return True
ensure_schema()

# --- HELPERS ---
def get_baku_now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=4))).replace(tzinfo=None)
def run_query(q, p=None): return conn.query(q, params=p if p else {}, ttl=0)
def run_action(q, p=None): 
    with conn.session as s: s.execute(text(q), p if p else {}); s.commit()
    return True
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): 
    try: return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
    except: return False
def log_system(user, action, cid=None):
    try: 
        run_action("INSERT INTO system_logs (username, action, customer_id, created_at) VALUES (:u, :a, :c, :t)", {"u":user, "a":action, "c":cid, "t":get_baku_now()})
    except: pass

def delete_sales_transaction(ids, user):
    try:
        with conn.session as s:
            for i in ids: s.execute(text("DELETE FROM sales WHERE id=:id"), {"id": i})
            s.execute(text("INSERT INTO system_logs (username, action, created_at) VALUES (:u, :a, :t)"), {"u": user, "a": f"Satış Silindi ({len(ids)} ədəd)", "t": get_baku_now()})
            s.commit()
    except Exception as e: st.error(f"Xəta: {e}")
def get_setting(key, default=""):
    try: return run_query("SELECT value FROM settings WHERE key=:k", {"k":key}).iloc[0]['value']
    except: return default
def set_setting(key, value): run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v", {"k":key, "v":value})
def image_to_base64(image_file): return base64.b64encode(image_file.getvalue()).decode()
def generate_styled_qr(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(image_factory=StyledPilImage, module_drawer=SquareModuleDrawer(), color_mask=SolidFillColorMask(front_color=(0, 128, 0, 255), back_color=(255, 255, 255, 0)))
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return "API_KEY_MISSING"
    try: requests.post("https://api.resend.com/emails", json={"from": f"{BRAND_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}, headers={"Authorization": f"Bearer {RESEND_API_KEY}"}); return "OK"
    except: return "Error"

# --- CACHED DATA HELPERS ---
@st.cache_data(ttl=300) # Cache for 5 minutes
def get_cached_menu():
    return run_query("SELECT * FROM menu WHERE is_active=TRUE")

@st.cache_data(ttl=300) # Cache for 5 minutes
def get_cached_users():
    return run_query("SELECT * FROM users")

# --- MODIFIED SESSION & LOGIN LOGIC (URL PERSISTENCE) ---
def create_session(username, role):
    token = secrets.token_urlsafe(32)
    run_action("INSERT INTO active_sessions (token, username, role, created_at) VALUES (:t, :u, :r, :c)", {"t":token, "u":username, "r":role, "c":get_baku_now()})
    return token

def check_url_token_login():
    """Checks URL params for token, validates it, and logs user in if valid."""
    qp = st.query_params
    token_in_url = qp.get("token")
    
    if token_in_url and not st.session_state.logged_in:
        res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t":token_in_url})
        if not res.empty:
            r = res.iloc[0]
            st.session_state.logged_in = True
            st.session_state.user = r['username']
            st.session_state.role = r['role']
            st.session_state.session_token = token_in_url
            return True
    return False

def logout_user():
    if st.session_state.session_token:
        run_action("DELETE FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token})
    st.session_state.logged_in = False
    st.session_state.session_token = None
    st.query_params.clear() # Clear URL
    st.rerun()

def validate_session():
    if not st.session_state.session_token: return False
    res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token})
    return not res.empty

def clear_customer_data():
    st.session_state.current_customer_ta = None

# --- GENERATE IDEAL RECIPES EXCEL FUNCTION ---
def generate_ideal_recipes_excel():
    COFFEE_BEAN = "Latina Blend Coffee"; MILK = "Milla Sud 3.2%"; CREAM = "Dom qaymaq 10%"
    SYRUP_VANILLA = "Sirop Barinoff (Vanil)"; SYRUP_CARAMEL = "Sirop Barinoff (Karamel)"
    CHOCO_SAUCE = "Topping Chocolate PS"; WHIPPED_CREAM = "Krem Şanti (President)"
    ICE = "Buz (Ice)"; WATER = "Damacana Su"; ICE_CREAM = "Dondurma (Vanil)"
    ORANGE_FRUIT = "Portağal (Meyvə)"; CUP_XS = "Stəkan Kağız (XS)"; CUP_S = "Stəkan Kağız (S)"
    CUP_M = "Stəkan Kağız (M)"; CUP_L = "Stəkan Kağız (L)"; CUP_PLASTIC_M = "Stəkan Şəffaf (M)"
    LID_S = "Qapaq İsti (Kiçik)"; LID_L = "Qapaq İsti (Böyük)"; LID_PLASTIC = "Qapaq Şəffaf (Stəkan üçün)"

    data = [
        ("Espresso S", COFFEE_BEAN, 0.009), ("Espresso S", CUP_XS, 1),
        ("Americano S", COFFEE_BEAN, 0.009), ("Americano S", WATER, 0.200), ("Americano S", CUP_S, 1), ("Americano S", LID_S, 1),
        ("Cappuccino S", COFFEE_BEAN, 0.009), ("Cappuccino S", MILK, 0.150), ("Cappuccino S", CUP_S, 1), ("Cappuccino S", LID_S, 1),
        ("Latte S", COFFEE_BEAN, 0.009), ("Latte S", MILK, 0.200), ("Latte S", CUP_S, 1), ("Latte S", LID_S, 1),
        ("Raf S", COFFEE_BEAN, 0.009), ("Raf S", MILK, 0.100), ("Raf S", CREAM, 0.050), ("Raf S", SYRUP_VANILLA, 0.015), ("Raf S", CUP_S, 1), ("Raf S", LID_S, 1),
        ("Mocha S", COFFEE_BEAN, 0.009), ("Mocha S", MILK, 0.150), ("Mocha S", CHOCO_SAUCE, 0.020), ("Mocha S", CUP_S, 1), ("Mocha S", LID_S, 1),
        ("Ice Americano S", COFFEE_BEAN, 0.009), ("Ice Americano S", WATER, 0.150), ("Ice Americano S", ICE, 0.100), ("Ice Americano S", CUP_PLASTIC_M, 1),
        ("Iced Latte S", COFFEE_BEAN, 0.009), ("Iced Latte S", MILK, 0.150), ("Iced Latte S", ICE, 0.100), ("Iced Latte S", CUP_PLASTIC_M, 1),
        ("Milkşeyk S", ICE_CREAM, 0.150), ("Milkşeyk S", MILK, 0.050), ("Milkşeyk S", CUP_PLASTIC_M, 1),
        ("Təbii sıxılmış portağal şirəsi", ORANGE_FRUIT, 0.700), ("Təbii sıxılmış portağal şirəsi", CUP_PLASTIC_M, 1)
    ]
    df = pd.DataFrame(data, columns=["menu_item_name", "ingredient_name", "quantity_required"])
    out = BytesIO(); df.to_excel(out, index=False); return out.getvalue()

@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")
    with st.form("admin_conf_form"):
        pwd = st.text_input("Admin Şifrəsi", type="password")
        if st.form_submit_button("Təsdiqlə"):
            adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
            if not adm.empty and verify_password(pwd, adm.iloc[0]['password']):
                callback(*args); st.success("İcra olundu!"); time.sleep(1); st.rerun()
            else: st.error("Yanlış Şifrə!")

@st.dialog("🗑️ Seçilən Satışları Sil")
def smart_bulk_delete_dialog(selected_sales):
    cnt = len(selected_sales); total_val = selected_sales['total'].sum()
    st.warning(f"Seçilən Satış Sayı: {cnt}"); st.error(f"Cəmi Məbləğ: {total_val:.2f} ₼")
    st.write("---"); st.write("❓ **NİYƏ SİLİRSİNİZ?**")
    reason = st.radio("Səbəb seçin:", ["🅰️ Səhv Vurulub / Test (Mallar Anbara Qayıtsın) 🔄", "🅱️ Zay Olub / Dağılıb (Mallar Qayıtmasın) 🗑️"])
    if st.button("🔴 TƏSDİQLƏ VƏ SİL"):
        try:
            restore_stock = "Səhv" in reason; ids_to_del = selected_sales['id'].tolist()
            with conn.session as s:
                if restore_stock:
                    for idx, row in selected_sales.iterrows():
                        if row['items']:
                            parts = str(row['items']).split(", ")
                            for p in parts:
                                match = re.match(r"(.+) x(\d+)", p)
                                if match:
                                    iname = match.group(1).strip(); iqty = int(match.group(2))
                                    recs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":iname}).fetchall()
                                    for r in recs:
                                        qty_to_add = float(r[1]) * iqty
                                        s.execute(text("UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:n"), {"q":qty_to_add, "n":r[0]})
                for i in ids_to_del: s.execute(text("DELETE FROM sales WHERE id=:id"), {"id":int(i)})
                s.commit()
            log_system(st.session_state.user, f"Toplu Silmə ({cnt} ədəd) - {'Stok Bərpa' if restore_stock else 'Stok Silindi'}")
            st.success("Uğurla Silindi!"); time.sleep(1.5); st.rerun()
        except Exception as e: st.error(f"Xəta: {e}")

@st.dialog("🗑️ Satışı Sil")
def smart_delete_sale_dialog(sale_row):
    st.warning(f"Satış ID: {sale_row['id']}"); st.info(f"Mallar: {sale_row['items']}"); st.error(f"Məbləğ: {sale_row['total']} ₼")
    st.write("---"); st.write("❓ **NİYƏ SİLİRSİNİZ?**")
    reason = st.radio("Səbəb seçin:", ["🅰️ Səhv Vurulub / Test (Mal Qayıtsın) 🔄", "🅱️ Zay Olub / Dağılıb (Mal Qayıtmasın) 🗑️"])
    if st.button("🔴 TƏSDİQLƏ VƏ SİL"):
        try:
            restore_stock = "Səhv" in reason; sale_id = int(sale_row['id'])
            with conn.session as s:
                if restore_stock and sale_row['items']:
                    items_str = sale_row['items']; parts = items_str.split(", ")
                    for p in parts:
                        match = re.match(r"(.+) x(\d+)", p)
                        if match:
                            iname = match.group(1).strip(); iqty = int(match.group(2))
                            recs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":iname}).fetchall()
                            for r in recs:
                                qty_to_add = float(r[1]) * iqty
                                s.execute(text("UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:n"), {"q":qty_to_add, "n":r[0]})
                s.execute(text("DELETE FROM sales WHERE id=:id"), {"id":sale_id}); s.commit()
            log_system(st.session_state.user, f"Satış Silindi #{sale_id}: {'Stok Bərpa' if restore_stock else 'Stok Getdi'}")
            st.success("Satış uğurla silindi!"); time.sleep(1.5); st.rerun()
        except Exception as e: st.error(f"Xəta: {e}")

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0):
    total = 0.0; disc_rate = 0.0; current_stars = 0
    
    # 1. Manual Discount Overrides Everything
    if manual_discount_percent > 0:
        disc_rate = manual_discount_percent / 100.0
        final_total = 0.0
        for i in cart:
            line = i['qty'] * i['price']; total += line
            # Discount applies to EVERYTHING if manual
            final_total += (line - (line * disc_rate))
        if is_table: final_total += final_total * 0.07
        return total, final_total, disc_rate, 0, 0, 0, False

    # 2. Customer Loyalty (If no manual discount)
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'ikram': return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20}
        disc_rate = rates.get(ctype, 0.0)
    
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
    final_total = 0.0
    for i in cart:
        line = i['qty'] * i['price']; total += line
        if i.get('is_coffee'): final_total += (line - (line * disc_rate))
        else: final_total += line
    if is_table: final_total += final_total * 0.07
    return total, final_total, disc_rate, free_cof, 0, 0, False

def get_receipt_html_string(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME); addr = get_setting("receipt_address", "Baku"); phone = get_setting("receipt_phone", "")
    logo = get_setting("receipt_logo_base64"); time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<img src="data:image/png;base64,{logo}" style="width:80px; filter:grayscale(100%);">' if logo else ""
    rows = "".join([f"<tr><td style='border-bottom:1px dashed #000; padding:5px;'>{int(i['qty'])}</td><td style='border-bottom:1px dashed #000; padding:5px;'>{i['item_name']}</td><td style='border-bottom:1px dashed #000; padding:5px; text-align:right;'>{i['qty']*i['price']:.2f}</td></tr>" for i in cart])
    return f"""<div id='receipt-area' style="font-family:'Courier New'; width:300px; margin:0 auto; text-align:center;">{img_tag}<h3>{store}</h3><p>{addr}<br>{phone}</p><p>{time_str}</p><table style="width:100%; text-align:left; border-collapse:collapse;"><tr><th style='border-bottom:1px dashed #000;'>Say</th><th style='border-bottom:1px dashed #000;'>Mal</th><th style='border-bottom:1px dashed #000; text-align:right;'>Məb</th></tr>{rows}</table><h3>YEKUN: {total:.2f} ₼</h3><p>Təşəkkürlər!</p></div>"""

@st.dialog("🧾 Çek")
def show_receipt_dialog(cart_data, total_amt, cust_email):
    html = get_receipt_html_string(cart_data, total_amt)
    components.html(html, height=450, scrolling=True)
    st.markdown(f'<div id="hidden-print-area">{html}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: components.html(f"""<button onclick="window.print()" style="background:#2E7D32;color:white;padding:10px;border-radius:5px;width:100%;">🖨️ ÇAP ET</button>""", height=50)
    with c2: 
        if cust_email and st.button("📧 Email"): send_email(cust_email, "Çekiniz", html); st.success("Getdi!")
    if st.button("❌ Bağla"): st.session_state.show_receipt_popup=False; st.session_state.last_receipt_data=None; st.rerun()

# ==========================================
# === MAIN APP ===
# ==========================================
# 1. AUTO-LOGIN CHECK (URL TOKEN)
if not st.session_state.logged_in:
    check_url_token_login()

# 2. CUSTOMER QR SCAN CHECK (Public)
query_params = st.query_params
if "id" in query_params and not st.session_state.logged_in:
    card_id = query_params["id"]; token = query_params.get("t")
    c1, c2, c3 = st.columns([1,2,1]); logo = get_setting("receipt_logo_base64")
    with c2: 
        if logo: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" width="120"></div>', unsafe_allow_html=True)
    
    st.markdown("""
        <style>
        .stApp { background-color: #FFFFFF !important; }
        h1, h2, h3, h4, h5, h6, p, div, span, label, li { color: #000000 !important; }
        input, .stDateInput, .stTextInput { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #cccccc !important; }
        div.stButton > button { background-color: #F0F2F6 !important; color: #000000 !important; border: 2px solid #2E7D32 !important; }
        .streamlit-expanderHeader { background-color: #FFFFFF !important; color: #000000 !important; }
        </style>
    """, unsafe_allow_html=True)

    try: df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":card_id})
    except: st.stop()
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and token and user['secret_token'] != token: st.warning("⚠️ QR kod köhnəlib.")
        st.markdown(f"<div class='cartoon-quote'>{random.choice(CARTOON_QUOTES)}</div>", unsafe_allow_html=True)
        notifs = run_query("SELECT * FROM notifications WHERE card_id=:id AND is_read=FALSE", {"id":card_id})
        for _, n in notifs.iterrows():
            st.markdown(f"<div class='msg-box'>📩 {n['message']}</div>", unsafe_allow_html=True)
            if st.button("Oxudum ✅", key=f"n_{n['id']}"): run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id":n['id']}); st.rerun()
        if not user['is_active']:
            st.info("Xoş Gəldiniz!"); terms = get_setting("customer_rules", DEFAULT_TERMS)
            with st.form("act"):
                st.markdown(terms, unsafe_allow_html=True) # Rules first
                agree = st.checkbox("Qaydaları oxudum və qəbul edirəm", value=False)
                st.divider()
                st.write("**Aşağıdakı məlumatlar könüllüdür (Ad günü hədiyyəsi üçün):**")
                em = st.text_input("Email (Könüllü)")
                dob = st.date_input("Doğum Tarixi (Könüllü)", value=None, min_value=datetime.date(1950,1,1))
                
                if st.form_submit_button("TƏSDİQLƏ VƏ QOŞUL"):
                    if agree:
                         b_date_str = str(dob) if dob else None
                         run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":b_date_str, "i":card_id})
                         st.rerun()
                    else:
                         st.error("Zəhmət olmasa, qaydaları qəbul edin.")
            st.stop()
        ctype = user['type']; st_lbl = "MEMBER"; b_col = "#B71C1C"
        if ctype=='golden': st_lbl="GOLDEN (5%)"; b_col="#D4AF37"
        elif ctype=='platinum': st_lbl="PLATINUM (10%)"; b_col="#78909C"
        elif ctype=='elite': st_lbl="ELITE (20%)"; b_col="#37474F"
        elif ctype=='ikram': st_lbl="İKRAM (100%)"; b_col="#00C853"
        elif ctype=='thermos': st_lbl="EKO-TERM (20%)"; b_col="#2E7D32"
        st.markdown(f"<div class='stamp-container'><div class='stamp-card' style='border-color:{b_col};color:{b_col};box-shadow:0 0 0 4px white, 0 0 0 7px {b_col};'><div style='font-size:20px;border-bottom:2px solid;'>{st_lbl}</div><div style='font-size:50px;'>{user['stars']}/10</div><div>ULDUZ BALANSI</div></div></div>", unsafe_allow_html=True)
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
            style = ""
            if i == 9: 
                if user['stars'] >= 10: cls = "cup-red-base cup-anim"; style = "opacity: 1;"
                else: op = 0.1 + (user['stars'] * 0.09); cls = "cup-red-base"; style = f"opacity: {op};"
            elif i < user['stars']: cls = "cup-earned"
            else: cls = "cup-empty"
            html += f'<img src="{icon}" class="{cls} coffee-icon-img" style="{style}">'
        st.markdown(html + "</div>", unsafe_allow_html=True)
        if user['stars'] >= 10: st.success("🎉 Təbriklər! Bu kofeniz bizdəndir!")
        with st.form("fd"):
            s = st.feedback("stars"); m = st.text_input("Fikriniz...")
            if st.form_submit_button("Göndər") and s: run_action("INSERT INTO feedbacks (card_id,rating,comment,created_at) VALUES (:c,:r,:m,:t)", {"c":card_id,"r":s+1,"m":m,"t":get_baku_now()}); st.success("Təşəkkürlər!")
        st.stop()

# 3. LOGIN PAGE
if not st.session_state.logged_in:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u = get_cached_users() # Use Cached Users
                    found = False
                    for _,r in u.iterrows():
                        if r['role'] in ['staff','manager'] and verify_password(p, r['password']):
                            st.session_state.logged_in=True; st.session_state.user=r['username']; st.session_state.role=r['role']
                            token = create_session(r['username'],r['role'])
                            st.session_state.session_token = token
                            st.query_params['token'] = token # URL PERSISTENCE
                            found = True; st.rerun()
                    if not found: st.error("Səhv PIN")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']
                        token = create_session(u,ud.iloc[0]['role'])
                        st.session_state.session_token = token
                        st.query_params['token'] = token # URL PERSISTENCE
                        st.rerun()
                    else: st.error("Səhv")

# 4. MAIN DASHBOARD
else:
    if st.session_state.show_receipt_popup and st.session_state.last_receipt_data:
        show_receipt_dialog(st.session_state.last_receipt_data['cart'], st.session_state.last_receipt_data['total'], st.session_state.last_receipt_data['email'])

    h1, h2, h3 = st.columns([4,1,1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄"): st.rerun()
    with h3: 
        if st.button("🚪", type="primary"): logout_user()
            
    st.divider()

    role = st.session_state.role
    
    tabs_list = []
    if role in ['admin', 'manager', 'staff']:
        tabs_list.append("🏃‍♂️ AL-APAR")
    
    show_tables_for_staff = get_setting("staff_show_tables", "TRUE") == "TRUE"
    show_tables_for_manager = get_setting("manager_show_tables", "TRUE") == "TRUE"
    
    if role == 'admin':
        tabs_list.append("🍽️ MASALAR")
    elif role == 'manager' and show_tables_for_manager:
        tabs_list.append("🍽️ MASALAR")
    elif role == 'staff' and show_tables_for_staff:
        tabs_list.append("🍽️ MASALAR")

    if role in ['admin', 'manager']:
        tabs_list.extend(["💰 Maliyyə", "📦 Anbar", "📊 Analitika", "📜 Loglar", "👥 CRM"])

    if role == 'manager':
         if get_setting("manager_perm_menu", "FALSE") == "TRUE": tabs_list.append("📋 Menyu")
         if get_setting("manager_perm_recipes", "FALSE") == "TRUE": tabs_list.append("📜 Resept")

    if role == 'admin':
        if "📋 Menyu" not in tabs_list: tabs_list.append("📋 Menyu")
        if "📜 Resept" not in tabs_list: tabs_list.append("📜 Resept")
        tabs_list.extend(["📝 Qeydlər", "⚙️ Ayarlar", "💾 Baza", "QR"])
    
    if role in ['staff', 'manager', 'admin']:
        tabs_list.append("📊 Z-Hesabat")

    my_tabs = st.tabs(tabs_list)
    tab_map = {name: tab for name, tab in zip(tabs_list, my_tabs)}

    def add_to_cart(cart, item):
        for i in cart: 
            if i['item_name'] == item['item_name'] and i.get('status')=='new': i['qty']+=1; return
        cart.append(item)

    def render_menu(cart, key):
        # USE CACHED MENU
        menu_df = get_cached_menu()
        cats = ["Hamısı"] + sorted(menu_df['category'].unique().tolist())
        
        sc = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_{key}")
        
        if sc != "Hamısı":
            prods = menu_df[menu_df['category'] == sc].sort_values(by="price")
        else:
            prods = menu_df.sort_values(by="price")

        if not prods.empty:
            groups = {}
            for _, r in prods.iterrows():
                n = r['item_name']; base = n
                for s in [" S", " M", " L", " XL", " Single", " Double"]:
                    if n.endswith(s): base = n[:-len(s)]; break
                if base not in groups: groups[base] = []
                groups[base].append(r)
            cols = st.columns(4)
            i = 0
            for base, items in groups.items():
                with cols[i%4]:
                    if len(items) > 1:
                        @st.dialog(f"{base}")
                        def show_variants(its, grp_key):
                            for it in its:
                                if st.button(f"{it['item_name']} - {it['price']}₼", key=f"v_{it['id']}_{grp_key}", use_container_width=True):
                                    add_to_cart(cart, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'category':it['category'], 'status':'new'}); st.rerun()
                        if st.button(f"{base} ▾", key=f"grp_{base}_{key}_{sc}", use_container_width=True): show_variants(items, f"{key}_{sc}")
                    else:
                        r = items[0]
                        if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}_{sc}", use_container_width=True):
                            add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'category':r['category'], 'status':'new'}); st.rerun()
                i+=1

    if "🏃‍♂️ AL-APAR" in tab_map:
        with tab_map["🏃‍♂️ AL-APAR"]:
            c1, c2 = st.columns([1.5, 3])
            with c1:
                st.info("🧾 Al-Apar")
                with st.form("scta", clear_on_submit=True):
                    code = st.text_input("Müştəri", label_visibility="collapsed", placeholder="Skan...", key="search_input_ta")
                    if st.form_submit_button("🔍") or code:
                        code = code.strip()
                        if "id=" in code:
                            try: cid = code.split("id=")[1].split("&")[0]
                            except: cid = code
                        else: cid = code
                        
                        try: 
                            r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                            if not r.empty: 
                                st.session_state.current_customer_ta = r.iloc[0].to_dict()
                                cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id":cid})
                                if not cps.empty: st.toast(f"🎁 Aktiv Promo Var: {cps.iloc[0]['coupon_type']}")
                                else: st.toast(f"✅ Müştəri: {cid}"); st.rerun()
                            else: st.error("Tapılmadı")
                        except: pass
                cust = st.session_state.current_customer_ta
                if cust: 
                    c_head, c_del = st.columns([4,1])
                    c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                    c_del.button("❌", key="clear_cust", on_click=clear_customer_data)
                
                # --- MANUAL DISCOUNT SELECTOR ---
                man_disc_val = st.selectbox("Endirim (%)", [0, 10, 20, 30, 40, 50], index=0, key="manual_disc_sel")
                disc_note = ""
                if man_disc_val > 0:
                    disc_note = st.text_input("Səbəb (Məcburi!)", placeholder="Məs: Dost, Menecer jesti", key="disc_reason_inp")
                    if not disc_note: st.warning("⚠️ Endirim üçün səbəb yazmalısınız!")

                raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust, manual_discount_percent=man_disc_val)
                
                if st.session_state.cart_takeaway:
                    for i, item in enumerate(st.session_state.cart_takeaway):
                        c_n, c_d, c_q, c_u = st.columns([3, 1, 1, 1])
                        with c_n: st.write(f"{item['item_name']}")
                        with c_d: 
                            if st.button("➖", key=f"dec_{i}"): 
                                if item['qty'] > 1: item['qty'] -= 1
                                else: st.session_state.cart_takeaway.pop(i)
                                st.rerun()
                        with c_q: st.write(f"x{item['qty']}")
                        with c_u:
                            if st.button("➕", key=f"inc_{i}"): item['qty'] += 1; st.rerun()
                st.markdown(f"<h2 style='text-align:right;color:#E65100'>{final:.2f} ₼</h2>", unsafe_allow_html=True)
                if is_ikram: st.success("🎁 İKRAM")
                elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
                
                # --- PAYMENT METHODS & OWN CUP CHECK ---
                pm = st.radio("Metod", ["Nəğd", "Kart", "Personal (Staff)"], horizontal=True) 
                own_cup = st.checkbox("🥡 Öz Stəkanı / Eko", key="eco_mode_check") 

                # --- VALIDATION FOR BUTTON ---
                btn_disabled = False
                if man_disc_val > 0 and not disc_note: btn_disabled = True
                
                if st.button("✅ ÖDƏNİŞ", type="primary", use_container_width=True, disabled=btn_disabled):
                    if not st.session_state.cart_takeaway: st.error("Boşdur"); st.stop()
                    
                    # --- STAFF LIMIT CHECK ---
                    if pm == "Personal (Staff)":
                        if final > 6.00:
                            st.error("⛔ Limit (6.00 AZN) keçildi! Fərqi ödəyin və ya məhsulu azaldın.")
                            st.stop()
                        for item in st.session_state.cart_takeaway:
                            cat = item.get('category', '')
                            if "Şirniyyat" in cat or "Yemək" in cat or "Qablaşdırma" in cat or "Siroplar" in cat:
                                st.error(f"⛔ {item['item_name']} personal limiti üçün keçərli deyil! Yalnız içki olar.")
                                st.warning("💡 Yemək üçün 'Manual Endirim' (50%) istifadə edin.")
                                st.stop()

                    try:
                        with conn.session as s:
                            for it in st.session_state.cart_takeaway:
                                recs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                                for r in recs:
                                    ing_name = r[0]
                                    ing_info = s.execute(text("SELECT category FROM ingredients WHERE name=:n"), {"n":ing_name}).fetchone()
                                    ing_cat = ing_info[0] if ing_info else ""

                                    if own_cup and ("Qablaşdırma" in ing_cat or "Stəkan" in ing_name or "Qapaq" in ing_name):
                                        continue 

                                    res = s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n AND stock_qty >= :q"), {"q":float(r[1])*it['qty'], "n":ing_name})
                                    if res.rowcount == 0: raise Exception(f"Stok yoxdur: {ing_name}")
                            
                            items_str = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_takeaway])
                            discount_amt = raw - final
                            
                            final_note = disc_note
                            if pm == "Personal (Staff)": final_note = "Staff Limit (6AZN)"
                            if own_cup: final_note += " [Eko Mod]"

                            final_db_total = final
                            if pm == "Personal (Staff)": final_db_total = 0.00

                            s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, note) VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da,:n)"), {"i":items_str,"t":final_db_total,"p":("Cash" if pm=="Nəğd" else "Card" if pm=="Kart" else "Staff"),"c":st.session_state.user,"time":get_baku_now(),"cid":cust['card_id'] if cust else None, "ot":raw, "da":discount_amt, "n":final_note})
                            
                            if cust and not is_ikram and pm != "Personal (Staff)":
                                cf_cnt = sum([x['qty'] for x in st.session_state.cart_takeaway if x.get('is_coffee')])
                                new_s = (cust['stars'] + cf_cnt) - (free * 10)
                                s.execute(text("UPDATE customers SET stars=:s WHERE card_id=:id"), {"s":new_s, "id":cust['card_id']})
                            s.commit()
                        
                        log_msg = f"Satış: {final:.2f} AZN ({items_str})"
                        if man_disc_val > 0: log_msg += f" [Endirim: {man_disc_val}%]"
                        if pm == "Personal (Staff)": log_msg += " [Staff Meal]"
                        
                        log_system(st.session_state.user, log_msg, cust['card_id'] if cust else None)
                        st.session_state.last_receipt_data = {'cart':st.session_state.cart_takeaway.copy(), 'total':final, 'email':cust['email'] if cust else None}
                        st.session_state.cart_takeaway = []; clear_customer_data(); st.session_state.show_receipt_popup=True; st.rerun()
                    except Exception as e: st.error(f"Xəta: {e}")
            with c2: render_menu(st.session_state.cart_takeaway, "ta")

    if "🍽️ MASALAR" in tab_map:
        with tab_map["🍽️ MASALAR"]:
            if st.session_state.selected_table:
                tbl = st.session_state.selected_table
                if st.button("⬅️ Qayıt"): st.session_state.selected_table=None; st.session_state.cart_table=[]; st.rerun()
                st.markdown(f"### {tbl['label']}")
                c1, c2 = st.columns([1.5, 3])
                with c1:
                    raw, final, _, _, _, serv, _ = calculate_smart_total(st.session_state.cart_table, is_table=True)
                    for i, it in enumerate(st.session_state.cart_table): st.write(f"{it['item_name']} x{it['qty']}")
                    st.metric("Yekun", f"{final:.2f} ₼"); st.button("🔥 Mətbəxə", on_click=lambda: (run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id", {"i":json.dumps(st.session_state.cart_table), "t":final, "id":tbl['id']}), st.success("OK")))
                    
                    if role in ['admin','manager']:
                        if st.button("✅ Ödəniş (Masa)", type="primary"):
                            try:
                                with conn.session as s:
                                    s.execute(text("UPDATE tables SET is_occupied=FALSE, items='[]', total=0 WHERE id=:id"), {"id":tbl['id']})
                                    s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, original_total, discount_amount) VALUES (:i,:t,'Table',:c,:tm, :ot, 0)"), {"i":"Table Order", "t":final, "c":st.session_state.user, "tm":get_baku_now(), "ot":final})
                                    s.commit()
                                log_system(st.session_state.user, f"Masa Satış: {tbl['label']} - {final:.2f} AZN"); st.session_state.selected_table=None; st.session_state.cart_table=[]; st.rerun()
                            except: st.error("Xəta")
                with c2: render_menu(st.session_state.cart_table, "tb")
            else:
                if role in ['admin','manager']:
                    with st.expander("🛠️ Masa İdarə"):
                        nl = st.text_input("Ad"); 
                        if st.button("Yarat"): run_action("INSERT INTO tables (label) VALUES (:l)", {"l":nl}); st.rerun()
                        dl = st.selectbox("Sil", run_query("SELECT label FROM tables")['label'].tolist() if not run_query("SELECT label FROM tables").empty else [])
                        if st.button("Sil"): admin_confirm_dialog("Silinsin?", lambda: run_action("DELETE FROM tables WHERE label=:l", {"l":dl}))
                df_t = run_query("SELECT * FROM tables ORDER BY id"); cols = st.columns(3)
                for i, r in df_t.iterrows():
                    with cols[i%3]:
                        if st.button(f"{r['label']}\n{r['total']} ₼", key=f"t_{r['id']}", type="primary" if r['is_occupied'] else "secondary", use_container_width=True):
                            st.session_state.selected_table = r.to_dict(); st.session_state.cart_table = json.loads(r['items']) if r['items'] else []; st.rerun()

    if "📦 Anbar" in tab_map:
        with tab_map["📦 Anbar"]:
            st.subheader("📦 Anbar İdarəetməsi")
            
            if role == 'admin' or role == 'manager':
                with st.expander("➕ Mədaxil / Yeni Mal", expanded=False):
                     st.info("💡 Məs: Qaymaq (0.48 L) = 5.29 AZN. Sistem özü 1 Litrin qiymətini tapacaq.")
                     with st.form("smart_add_item", clear_on_submit=True):
                        c1, c2, c3 = st.columns(3)
                        mn_name = c1.text_input("Malın Adı (Məs: Dom Qaymaq)")
                        sel_cat = c2.selectbox("Kateqoriya", PRESET_CATEGORIES + ["➕ Yeni Yarat..."])
                        mn_unit = c3.selectbox("Əsas Vahid (Resept üçün)", ["L", "KQ", "ƏDƏD"])
                        
                        mn_cat_final = sel_cat
                        if sel_cat == "➕ Yeni Yarat...":
                             mn_cat_final = st.text_input("Yeni Kateqoriya Adı (Məs: Tütün Məmulatları)")
                        
                        st.write("---")
                        c4, c5, c6 = st.columns(3)
                        pack_size = c4.number_input("Aldığın Qabın Həcmi/Çəkisi", min_value=0.001, step=0.001, help="Məs: 0.48 (Litr) və ya 0.5 (KQ)")
                        pack_price = c5.number_input("Aldığın Qabın Qiyməti (AZN)", min_value=0.01, step=0.01, help="Məs: 5.29")
                        pack_count = c6.number_input("Neçə ədəd/qutu almısan?", min_value=0.0, step=0.5, value=1.0)
                        mn_type = st.selectbox("Növ", ["ingredient", "consumable"], index=0)
                        
                        if st.form_submit_button("Hesabla və Yarat / Artır"):
                             if mn_name and pack_size > 0:
                                 calc_unit_cost = pack_price / pack_size 
                                 total_stock_add = pack_size * pack_count 
                                 run_action("""
                                     INSERT INTO ingredients (name, stock_qty, unit, category, type, unit_cost, approx_count) 
                                     VALUES (:n, :q, :u, :c, :t, :uc, 1) 
                                     ON CONFLICT (name) DO UPDATE SET stock_qty = ingredients.stock_qty + :q, unit_cost = :uc
                                 """, {"n":mn_name, "q":total_stock_add, "u":mn_unit, "c":mn_cat_final, "t":mn_type, "uc":calc_unit_cost})
                                 st.success(f"✅ {mn_name} stoka əlavə olundu!")
                                 time.sleep(2); st.rerun()

            c1, c2 = st.columns([3,1])
            search_query = st.text_input("🔍 Axtarış (Bütün Anbar)...", placeholder="Malın adı...")
            if search_query:
                df_i = run_query("SELECT id, name, stock_qty, unit, unit_cost, approx_count, category, type FROM ingredients WHERE name ILIKE :s ORDER BY name", {"s":f"%{search_query}%"})
            else:
                df_i = run_query("SELECT id, name, stock_qty, unit, unit_cost, approx_count, category, type FROM ingredients ORDER BY name")
            
            rows_per_page = st.selectbox("Səhifədə neçə mal olsun?", [20, 40, 60], index=0)
            if rows_per_page != st.session_state.anbar_rows_per_page: st.session_state.anbar_rows_per_page = rows_per_page; st.session_state.anbar_page = 0
            total_rows = len(df_i); total_pages = math.ceil(total_rows / rows_per_page); start_idx = st.session_state.anbar_page * rows_per_page; end_idx = start_idx + rows_per_page
            
            df_page = df_i.iloc[start_idx:end_idx].copy()
            
            if role == 'manager':
                df_page_display = df_page[['id', 'name', 'stock_qty', 'unit', 'category']]
                df_page_display.insert(0, "Seç", False) # Manager checkbox view
                edited_mgr_anbar = st.data_editor(
                    df_page_display, 
                    hide_index=True, 
                    column_config={"Seç": st.column_config.CheckboxColumn(required=True)},
                    disabled=["id","name","stock_qty","unit","category"],
                    use_container_width=True,
                    key="anbar_mgr_ed"
                )
                sel_mgr_rows = edited_mgr_anbar[edited_mgr_anbar["Seç"]]
                if len(sel_mgr_rows) == 1:
                    c_m1, c_m2 = st.columns(2)
                    with c_m1:
                        if st.button("➕ Mədaxil (Artır)", use_container_width=True, key="mgr_restock_btn"):
                            st.session_state.restock_item_id = int(sel_mgr_rows.iloc[0]['id'])
                            st.rerun()
                    with c_m2:
                         if st.button("✏️ Düzəliş (Manager)", use_container_width=True, key="mgr_edit_btn"):
                             st.session_state.edit_item_id = int(sel_mgr_rows.iloc[0]['id']); st.rerun()
                
            else:
                # --- V6.32 CRASH FIX: HANDLE NULLS & TYPES ---
                df_page['stock_qty'] = pd.to_numeric(df_page['stock_qty'], errors='coerce').fillna(0.0)
                df_page['unit_cost'] = pd.to_numeric(df_page['unit_cost'], errors='coerce').fillna(0.0)
                df_page['Total Value'] = df_page['stock_qty'] * df_page['unit_cost']
                
                df_page.insert(0, "Seç", False)
                edited_df = st.data_editor(df_page, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True), "unit_cost": st.column_config.NumberColumn(format="%.5f"), "Total Value": st.column_config.NumberColumn(format="%.2f")}, disabled=["id", "name", "stock_qty", "unit", "unit_cost", "approx_count", "category", "Total Value", "type"], use_container_width=True, key="anbar_editor")
                sel_rows = edited_df[edited_df["Seç"]]; sel_ids = sel_rows['id'].tolist(); sel_count = len(sel_ids)
                st.divider(); ab1, ab2, ab3 = st.columns(3)
                with ab1:
                    if sel_count == 1:
                        if st.button("➕ Seçilənə Mədaxil", use_container_width=True, type="secondary", key="btn_restock_active"): st.session_state.restock_item_id = int(sel_ids[0]); st.rerun()
                with ab2:
                    if sel_count == 1:
                        if st.button("✏️ Seçilənə Düzəliş", use_container_width=True, type="secondary", key="btn_edit_anbar_active"): st.session_state.edit_item_id = int(sel_ids[0]); st.rerun()
                with ab3:
                    if sel_count > 0:
                        if st.button(f"🗑️ Sil ({sel_count})", use_container_width=True, type="primary"): 
                             for i in sel_ids: run_action("DELETE FROM ingredients WHERE id=:id", {"id":int(i)})
                             st.success("Silindi!"); time.sleep(1); st.rerun()

            pc1, pc2, pc3 = st.columns([1,2,1])
            with pc1: 
                if st.button("⬅️ Əvvəlki", disabled=(st.session_state.anbar_page == 0)): st.session_state.anbar_page -= 1; st.rerun()
            with pc2: st.markdown(f"<div style='text-align:center; padding-top:10px;'>Səhifə {st.session_state.anbar_page + 1} / {max(1, total_pages)}</div>", unsafe_allow_html=True)
            with pc3: 
                if st.button("Növbəti ➡️", disabled=(st.session_state.anbar_page >= total_pages - 1)): st.session_state.anbar_page += 1; st.rerun()
            
            if role == 'admin':
                with st.expander("📤 İmport / Export (Excel)"):
                    with st.form("anbar_import_form"):
                        upl = st.file_uploader("📥 Import", type="xlsx"); import_type = st.selectbox("Yüklənəcək Malın Növü", ["Ərzaq (Ingredient)", "Sərfiyyat (Consumable)"])
                        if st.form_submit_button("Yüklə (Anbar)"):
                            if upl:
                                try:
                                    df = pd.read_excel(upl); df.columns = [str(c).lower().strip() for c in df.columns]
                                    header_map = {"ad": "name", "mal": "name", "say": "stock_qty", "vahid": "unit", "kateqoriya": "category", "qiymət": "unit_cost", "qutu sayı": "approx_count"}
                                    df.rename(columns=header_map, inplace=True)
                                    if not all(col in df.columns for col in ['name', 'stock_qty', 'unit', 'category', 'unit_cost']): st.error("Sütunlar əskikdir")
                                    else:
                                        df['stock_qty'] = pd.to_numeric(df['stock_qty'], errors='coerce').fillna(0); df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0); db_type = 'ingredient' if import_type.startswith("Ərzaq") else 'consumable'; count = 0
                                        with conn.session as s:
                                            for _, row in df.iterrows():
                                                if pd.isna(row['name']) or str(row['name']).strip() == "": continue
                                                ac = row['approx_count'] if 'approx_count' in df.columns else 1
                                                s.execute(text("""INSERT INTO ingredients (name, stock_qty, unit, category, type, unit_cost, approx_count) VALUES (:n, :q, :u, :c, :t, :uc, :ac) ON CONFLICT (name) DO UPDATE SET stock_qty = ingredients.stock_qty + :q, unit_cost = :uc"""), {"n": str(row['name']).strip(), "q": float(row['stock_qty']), "u": str(row['unit']).strip(), "c": str(row['category']).strip(), "t": db_type, "uc": float(row['unit_cost']), "ac": int(ac)}); count += 1
                                            s.commit()
                                        log_system(st.session_state.user, f"Anbar Import: {count} mal"); st.success(f"{count} mal yükləndi!")
                                except Exception as e: st.error(f"Xəta: {e}")
                    if st.button("📤 Anbarı Excel Kimi Endir"): out = BytesIO(); run_query("SELECT * FROM ingredients").to_excel(out, index=False); st.download_button("⬇️ Endir (anbar.xlsx)", out.getvalue(), "anbar.xlsx")

            if st.session_state.restock_item_id:
                r_item = run_query("SELECT * FROM ingredients WHERE id=:id", {"id":st.session_state.restock_item_id})
                if not r_item.empty:
                    row = r_item.iloc[0]
                    @st.dialog("➕ Mədaxil")
                    def show_restock(r):
                        st.write(f"**{r['name']}**")
                        with st.form("rs_form", clear_on_submit=True):
                            c1, c2 = st.columns(2); packs = c1.number_input("Neçə ədəd/qutu?", 1); per_pack = c2.number_input(f"Birinin Çəkisi ({r['unit']})", min_value=0.001, step=0.001, value=1.0, format="%.3f"); tot_price = st.number_input("Yekun Məbləğ (AZN)", 0.0)
                            if st.form_submit_button("Təsdiq"):
                                total_new_qty = packs * per_pack; new_cost = tot_price / total_new_qty if total_new_qty > 0 else r['unit_cost']
                                final_cost = float(new_cost if tot_price > 0 else r['unit_cost'])
                                run_action("UPDATE ingredients SET stock_qty=stock_qty+:q, unit_cost=:uc, approx_count=:ac WHERE id=:id", {"q":total_new_qty,"id":int(r['id']), "uc":final_cost, "ac":packs})
                                log_system(st.session_state.user, f"Mədaxil: {r['name']} (+{total_new_qty})"); st.session_state.restock_item_id = None; st.rerun()
                    show_restock(row)

            if st.session_state.edit_item_id and role in ['admin', 'manager']:
                r_item = run_query("SELECT * FROM ingredients WHERE id=:id", {"id":st.session_state.edit_item_id})
                if not r_item.empty:
                    row = r_item.iloc[0]
                    @st.dialog("✏️ Düzəliş")
                    def show_edit(r):
                        with st.form("ed_form"):
                            en = st.text_input("Ad", r['name']); 
                            current_cat = r['category']; idx = 0
                            if current_cat in PRESET_CATEGORIES: idx = PRESET_CATEGORIES.index(current_cat)
                            ec = st.selectbox("Kateqoriya", PRESET_CATEGORIES + ["➕ Yeni Yarat..."], index=idx); 
                            eu = st.selectbox("Vahid", ["KQ", "L", "ƏDƏD"], index=["KQ", "L", "ƏDƏD"].index(r['unit']) if r['unit'] in ["KQ", "L", "ƏDƏD"] else 0); 
                            
                            if role == 'admin':
                                et = st.selectbox("Növ", ["ingredient","consumable"], index=0 if r['type']=='ingredient' else 1); 
                                ecost = st.number_input("Maya Dəyəri", value=float(r['unit_cost']), format="%.5f")
                            else:
                                et = r['type']; ecost = float(r['unit_cost']) # Manager cannot change cost/type

                            if ec == "➕ Yeni Yarat...": ec = st.text_input("Yeni Kateqoriya Adı")
                            
                            if st.form_submit_button("Yadda Saxla"):
                                try:
                                    run_action("UPDATE ingredients SET name=:n, category=:c, unit=:u, unit_cost=:uc, type=:t WHERE id=:id", 
                                            {"n":en, "c":ec, "u":eu, "uc":float(ecost), "t":et, "id":int(r['id'])})
                                    log_system(st.session_state.user, f"Düzəliş: {en}")
                                    st.success("Düzəliş edildi!")
                                    time.sleep(0.5); st.session_state.edit_item_id = None; st.rerun()
                                except Exception as e: st.error(f"Xəta: {e}")
                    show_edit(row)

    if "💰 Maliyyə" in tab_map:
        with tab_map["💰 Maliyyə"]:
            st.subheader("💰 Maliyyə Mərkəzi")
            with st.expander("🔓 Səhər Kassanı Aç (Opening Balance)"):
                st.info("💡 Səhər kassanı açanda bu düyməyə bas.")
                op_bal = st.number_input("Kassada nə qədər pul var? (AZN)", min_value=0.0, step=0.1)
                if st.button("✅ Kassanı Bu Məbləğlə Aç"):
                    set_setting("cash_limit", str(op_bal))
                    st.success(f"Gün {op_bal} AZN ilə başladı!")
                    time.sleep(1); st.rerun()

            view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
            now = get_baku_now()
            if now.hour >= 8: shift_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
            else: shift_start = (now - datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            
            if "Növbə" in view_mode:
                sales_cash = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' AND created_at >= :d", {"d":shift_start}).iloc[0]['s'] or 0.0
                sales_card = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card' AND created_at >= :d", {"d":shift_start}).iloc[0]['s'] or 0.0
                exp_cash = run_query("SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' AND created_at >= :d", {"d":shift_start}).iloc[0]['e'] or 0.0
                inc_cash = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND created_at >= :d", {"d":shift_start}).iloc[0]['i'] or 0.0
                start_lim = float(get_setting("cash_limit", "0.0"))
                disp_cash = start_lim + float(sales_cash) + float(inc_cash) - float(exp_cash)
                disp_card = float(sales_card) 
                inc_safe = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Seyf' AND type='in' AND created_at >= :d", {"d":shift_start}).iloc[0]['i'] or 0.0
                out_safe = run_query("SELECT SUM(amount) as o FROM finance WHERE source='Seyf' AND type='out' AND created_at >= :d", {"d":shift_start}).iloc[0]['o'] or 0.0
                disp_safe = float(inc_safe) - float(out_safe)
                inv_shift_out = run_query("SELECT SUM(amount) as o FROM finance WHERE source='Investor' AND type='out' AND created_at >= :d", {"d":shift_start}).iloc[0]['o'] or 0.0
                disp_investor = float(inv_shift_out)
            else:
                last_z = get_setting("last_z_report_time")
                if last_z: last_z_dt = datetime.datetime.fromisoformat(last_z)
                else: last_z_dt = datetime.datetime.now() - datetime.timedelta(days=365)
                s_cash = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' AND created_at > :d", {"d":last_z_dt}).iloc[0]['s'] or 0.0
                e_cash = run_query("SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' AND created_at > :d", {"d":last_z_dt}).iloc[0]['e'] or 0.0
                i_cash = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND created_at > :d", {"d":last_z_dt}).iloc[0]['i'] or 0.0
                start_lim = float(get_setting("cash_limit", "100.0"))
                disp_cash = start_lim + float(s_cash) + float(i_cash) - float(e_cash)
                s_card = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card'").iloc[0]['s'] or 0.0
                f_card_in = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in'").iloc[0]['i'] or 0.0
                f_card_out = run_query("SELECT SUM(amount) as o FROM finance WHERE source='Bank Kartı' AND type='out'").iloc[0]['o'] or 0.0
                disp_card = float(s_card) + float(f_card_in) - float(f_card_out)
                f_safe_in = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Seyf' AND type='in'").iloc[0]['i'] or 0.0
                f_safe_out = run_query("SELECT SUM(amount) as o FROM finance WHERE source='Seyf' AND type='out'").iloc[0]['o'] or 0.0
                disp_safe = float(f_safe_in) - float(f_safe_out)
                inv_total_out = run_query("SELECT SUM(amount) as o FROM finance WHERE source='Investor' AND type='out'").iloc[0]['o'] or 0.0
                inv_total_in = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Investor' AND type='in'").iloc[0]['i'] or 0.0
                disp_investor = float(inv_total_out) - float(inv_total_in)

            st.divider(); m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏪 Kassa (Cibdə)", f"{disp_cash:.2f} ₼"); m2.metric("💳 Bank Kartı", f"{disp_card:.2f} ₼"); m3.metric("🏦 Seyf", f"{disp_safe:.2f} ₼"); m4.metric("👤 Investor (Borc)", f"{disp_investor:.2f} ₼")
            if role == 'admin' and "Ümumi" in view_mode:
                with st.expander("🛠️ Bank Kartı Balansını Düzəlt (Reset)"):
                    target_val = st.number_input("Kartda Hal-hazırda Olan Real Məbləğ", value=disp_card, step=0.01)
                    if st.button("Balansı Düzəlt"):
                        diff = target_val - disp_card
                        if diff != 0:
                            ftype = 'in' if diff > 0 else 'out'
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES (:t, 'Düzəliş', :a, 'Bank Kartı', 'Admin Reset', :u)", {"t":ftype, "a":abs(diff), "u":st.session_state.user}); st.success("Balans düzəldildi!"); time.sleep(1); st.rerun()
            st.markdown("---")
            with st.expander("➕ Yeni Əməliyyat", expanded=True):
                with st.form("new_fin_trx"):
                    c1, c2, c3 = st.columns(3); f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"]); f_source = c2.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Investor"]); f_subj = c3.selectbox("Subyekt", SUBJECTS)
                    
                    # --- NEW: INVESTOR SELECTOR IN FINANCE FORM ---
                    selected_investor = None
                    if f_source == "Investor":
                         investor_list = [s for s in SUBJECTS if "Investor" in s]
                         selected_investor = st.selectbox("Hansı Investor?", investor_list)
                    
                    c4, c5 = st.columns(2); f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kommunal (İşıq/Su)", "Kirayə", "Maaş/Avans", "Borc Ödənişi", "İnvestisiya", "Təsərrüfat", "Kassa Kəsiri / Bərpası", "İnkassasiya (Seyfə)", "Digər"]); f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01); f_desc = st.text_input("Qeyd")
                    if st.form_submit_button("Təsdiqlə"):
                        final_subject = f_subj
                        if selected_investor: final_subject = selected_investor

                        db_type = 'out' if "Məxaric" in f_type else 'in'
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject) VALUES (:t, :c, :a, :s, :d, :u, :sb)", {"t":db_type, "c":f_cat, "a":f_amt, "s":f_source, "d":f_desc, "u":st.session_state.user, "sb":final_subject})
                        if db_type == 'out': run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, :r, :s, :src)", {"a":f_amt, "r":f"{f_subj} - {f_desc}", "s":st.session_state.user, "src":f_source})
                        log_system(st.session_state.user, f"Maliyyə: {db_type.upper()} {f_amt} ({f_cat})"); st.success("Yazıldı!"); st.rerun()
            
            st.write("📜 Son Əməliyyatlar")
            fin_df = run_query("SELECT * FROM finance ORDER BY created_at DESC")
            
            if role == 'admin':
                # --- ADMIN FINANCE EDIT/DELETE (V6.26) ---
                fin_df.insert(0, "Seç", False)
                edited_fin = st.data_editor(
                    fin_df.head(50), 
                    hide_index=True, 
                    column_config={"Seç": st.column_config.CheckboxColumn(required=True)},
                    disabled=["id","type","category","amount","source","description","created_by","created_at","subject"],
                    use_container_width=True,
                    key="fin_admin_ed"
                )
                sel_fin_rows = edited_fin[edited_fin["Seç"]]
                
                fc1, fc2 = st.columns(2)
                with fc1:
                    if len(sel_fin_rows) == 1:
                        if st.button("✏️ Seçilənə Düzəliş", key="fin_edit_btn"):
                            st.session_state.edit_finance_id = int(sel_fin_rows.iloc[0]['id'])
                            st.rerun()
                with fc2:
                    if not sel_fin_rows.empty:
                        if st.button(f"🗑️ Seçilən {len(sel_fin_rows)} Əməliyyatı Sil"):
                            def delete_finance_records(ids):
                                for i in ids: run_action("DELETE FROM finance WHERE id=:id", {"id":int(i)})
                            admin_confirm_dialog(
                                f"Diqqət! {len(sel_fin_rows)} maliyyə əməliyyatı silinəcək.",
                                delete_finance_records,
                                sel_fin_rows['id'].tolist()
                            )
                
                # --- FINANCE EDIT DIALOG ---
                if st.session_state.edit_finance_id:
                    fin_data = run_query("SELECT * FROM finance WHERE id=:id", {"id":st.session_state.edit_finance_id})
                    if not fin_data.empty:
                        fr = fin_data.iloc[0]
                        @st.dialog("✏️ Maliyyə Düzəliş")
                        def edit_finance_dialog(r):
                            with st.form("fin_edit_form"):
                                new_amt = st.number_input("Məbləğ", value=float(r['amount']), min_value=0.01)
                                new_cat = st.text_input("Kateqoriya", value=r['category'])
                                new_desc = st.text_input("Qeyd", value=r['description'])
                                
                                # Updated Source Selection
                                src_opts = ["Kassa", "Bank Kartı", "Seyf", "Investor"]
                                curr_src = r['source'] if r['source'] in src_opts else "Kassa"
                                new_src = st.selectbox("Mənbə", src_opts, index=src_opts.index(curr_src))
                                
                                # New Subject Selection for Edit
                                curr_subj = r['subject'] if r['subject'] in SUBJECTS else SUBJECTS[0]
                                new_subj = st.selectbox("Subyekt", SUBJECTS, index=SUBJECTS.index(curr_subj) if curr_subj in SUBJECTS else 0)

                                if st.form_submit_button("Yadda Saxla"):
                                    try:
                                        run_action("UPDATE finance SET amount=:a, category=:c, description=:d, source=:s, subject=:sub WHERE id=:id", 
                                                {"a":float(new_amt), "c":new_cat, "d":new_desc, "s":new_src, "sub":new_subj, "id":int(r['id'])})
                                        st.success("Yeniləndi!"); time.sleep(0.5); st.session_state.edit_finance_id = None; st.rerun()
                                    except Exception as e: st.error(f"Xəta: {e}")
                        edit_finance_dialog(fr)

            else:
                st.dataframe(fin_df.head(20), hide_index=True, use_container_width=True)

    if "📝 Qeydlər" in tab_map:
        with tab_map["📝 Qeydlər"]:
            st.subheader("📝 Şəxsi Qeydlər & Hesablayıcı (Admin)")
            st.info("💡 Bu qeydlər 'Maliyyə' və 'Anbar'a təsir etmir. Yalnız şəxsi uçot üçündür.")
            
            # Add Note Form
            with st.form("add_note_form", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 1, 2])
                n_title = c1.text_input("Nə Aldın? (Ad)", placeholder="Məs: Bazarlıq")
                n_amount = c2.number_input("Nə Qədər? (AZN)", min_value=0.0, step=0.1)
                n_desc = c3.text_input("Qeyd (Optional)", placeholder="Məs: Cibimdən verdim")
                
                if st.form_submit_button("➕ Əlavə Et"):
                    if n_title and n_amount > 0:
                        run_action("INSERT INTO admin_notes (title, amount, note) VALUES (:t, :a, :n)", {"t":n_title, "a":n_amount, "n":n_desc})
                        st.success("Yazıldı!"); st.rerun()
            
            # List & Calculate
            notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
            if not notes.empty:
                # Calculate Total
                total_notes = notes['amount'].sum()
                st.markdown(f"### 💰 CƏM: {total_notes:.2f} AZN")
                
                # Show Editable Table (For easy deletion)
                notes['Seç'] = False
                edited_notes = st.data_editor(
                    notes, 
                    hide_index=True,
                    column_config={
                        "Seç": st.column_config.CheckboxColumn(required=True),
                        "amount": st.column_config.NumberColumn(format="%.2f AZN")
                    },
                    use_container_width=True
                )
                
                sel_notes = edited_notes[edited_notes["Seç"]]
                if not sel_notes.empty:
                    if st.button(f"🗑️ Seçilən {len(sel_notes)} Qeydi Sil"):
                        for i in sel_notes['id'].tolist():
                            run_action("DELETE FROM admin_notes WHERE id=:id", {"id":int(i)})
                        st.success("Silindi!"); time.sleep(0.5); st.rerun()
            else:
                st.write("📭 Hələ ki qeyd yoxdur.")

    if "📜 Resept" in tab_map:
        with tab_map["📜 Resept"]:
            st.subheader("📜 Resept")
            sel_prod = st.selectbox("Məhsul", ["(Seçin)"] + run_query("SELECT item_name FROM menu WHERE is_active=TRUE")['item_name'].tolist())
            if sel_prod != "(Seçin)":
                recs = run_query("SELECT id, ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:n ORDER BY id", {"n":sel_prod})
                recs.insert(0, "Seç", False)
                ed_recs = st.data_editor(recs, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True), "quantity_required": st.column_config.NumberColumn(label="Miqdar", min_value=0.0, step=0.001, format="%.3f")}, disabled=["id", "ingredient_name"], use_container_width=True, key="rec_editor")
                sel_rows = ed_recs[ed_recs["Seç"]]; del_ids = sel_rows['id'].tolist()
                c_del, c_upd = st.columns(2)
                with c_del:
                    if role in ['admin', 'manager']: # FIXED: Manager Can Delete
                        if del_ids and st.button(f"🗑️ Seçilənləri Sil ({len(del_ids)})", type="primary"):
                            for i in del_ids: run_action("DELETE FROM recipes WHERE id=:id", {"id":int(i)})
                            log_system(st.session_state.user, f"Resept Silinmə: {sel_prod} ({len(del_ids)} sətir)"); st.success("Silindi!"); time.sleep(0.5); st.rerun()
                with c_upd:
                    if role in ['admin', 'manager']: # FIXED: Manager Can Update
                        if st.button("💾 Dəyişiklikləri Yadda Saxla"):
                            with conn.session as s:
                                for _, row in ed_recs.iterrows():
                                    if not row['Seç']: s.execute(text("UPDATE recipes SET quantity_required=:q WHERE id=:id"), {"q":float(row['quantity_required']), "id":int(row['id'])})
                                s.commit()
                            st.success("Yeniləndi!"); time.sleep(0.5); st.rerun()
                st.divider()
                if role in ['admin', 'manager']: 
                    with st.form("add_rec", clear_on_submit=True):
                        ing_data = run_query("SELECT name, stock_qty, unit FROM ingredients ORDER BY name")
                        ing_options = {f"{r['name']} (Stok: {r['stock_qty']} {r['unit']})": r['name'] for _, r in ing_data.iterrows()}
                        s_label = st.selectbox("Xammal Seç (Stok Görüntülü)", list(ing_options.keys()))
                        real_ing_name = ing_options[s_label]
                        def_val = 1.0 if sel_prod == real_ing_name else 0.0
                        s_q = st.number_input("Miqdar", value=def_val, step=0.001)
                        if st.form_submit_button("Əlavə Et"): 
                            run_action("INSERT INTO recipes (menu_item_name,ingredient_name,quantity_required) VALUES (:m,:i,:q)",{"m":sel_prod,"i":real_ing_name,"q":s_q}); st.rerun()
            
            if role == 'admin':
                with st.expander("📤 Reseptləri İmport / Export (Excel)"):
                    if st.button("⚠️ Bütün Reseptləri Sil (Təmizlə)", type="primary"):
                        admin_confirm_dialog("Bütün reseptlər silinsin? Geri qaytarmaq olmayacaq!", lambda: run_action("DELETE FROM recipes"))
                    with st.form("recipe_import_form"):
                        upl_rec = st.file_uploader("📥 Import", type="xlsx")
                        if st.form_submit_button("Reseptləri Yüklə"):
                            if upl_rec:
                                try:
                                    df_r = pd.read_excel(upl_rec); df_r.columns = [str(c).lower().strip() for c in df_r.columns]; req = ['menu_item_name', 'ingredient_name', 'quantity_required']; r_map = {"mal": "menu_item_name", "məhsul": "menu_item_name", "xammal": "ingredient_name", "miqdar": "quantity_required"}; df_r.rename(columns=r_map, inplace=True)
                                    if not all(col in df_r.columns for col in req): st.error("Sütunlar əskikdir")
                                    else:
                                        cnt = 0; 
                                        with conn.session as s:
                                            for _, r in df_r.iterrows():
                                                if pd.isna(r['menu_item_name']): continue
                                                s.execute(text("INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)"), {"m":str(r['menu_item_name']), "i":str(r['ingredient_name']), "q":float(r['quantity_required'])}); cnt += 1
                                            s.commit()
                                        log_system(st.session_state.user, f"Resept Import: {cnt} sətir"); st.success(f"{cnt} resept sətri yükləndi!")
                                except Exception as e: st.error(f"Xəta: {e}")
                    if st.button("📤 Reseptləri Excel Kimi Endir"): out = BytesIO(); run_query("SELECT * FROM recipes").to_excel(out, index=False); st.download_button("⬇️ Endir (recipes.xlsx)", out.getvalue(), "recipes.xlsx")

    if "📊 Analitika" in tab_map:
        with tab_map["📊 Analitika"]:
            st.subheader("📊 Analitika & Mənfəət")
            c1, c2 = st.columns(2); 
            d1 = c1.date_input("Start", datetime.date.today(), key="ana_date_start"); 
            d2 = c2.date_input("End", datetime.date.today(), key="ana_date_end"); 
            t1 = c1.time_input("Saat Başla", datetime.time(8,0)); t2 = c2.time_input("Saat Bit", datetime.time(23,59)); ts_start = datetime.datetime.combine(d1, t1); ts_end = datetime.datetime.combine(d2 + datetime.timedelta(days=1 if t2 < t1 else 0), t2)
            sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
            exps = run_query("SELECT * FROM expenses WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
            
            total_rev = sales['total'].sum() if not sales.empty else 0.0
            rev_cash = sales[sales['payment_method']=='Cash']['total'].sum() if not sales.empty else 0.0
            rev_card = sales[sales['payment_method']=='Card']['total'].sum() if not sales.empty else 0.0
            
            # --- V6.31 STAFF EXPENSE CALCULATION ---
            # Sum of original_total where payment_method is Staff
            staff_expense_val = sales[sales['payment_method']=='Staff']['original_total'].sum() if not sales.empty else 0.0
            
            total_exp = exps['amount'].sum() if not exps.empty else 0.0
            
            est_cogs = 0.0
            if not sales.empty and role == 'admin':
                all_recs = run_query("SELECT r.menu_item_name, r.quantity_required, i.unit_cost FROM recipes r JOIN ingredients i ON r.ingredient_name = i.name")
                item_costs = {}
                for _, r in all_recs.iterrows():
                    nm = r['menu_item_name']
                    cost = float(r['quantity_required']) * float(r['unit_cost'])
                    item_costs[nm] = item_costs.get(nm, 0.0) + cost
                for items_str in sales['items']:
                    if items_str:
                        parts = items_str.split(", ")
                        for p in parts:
                            try:
                                match = re.match(r"(.+) x(\d+)", p)
                                if match:
                                    iname = match.group(1).strip(); iqty = int(match.group(2))
                                    if iname in item_costs: est_cogs += (item_costs[iname] * iqty)
                            except: pass
            
            gross_profit = total_rev - est_cogs
            
            m1, m2, m3 = st.columns(3); m1.metric("Toplam Satış", f"{total_rev:.2f} ₼"); m2.metric("💳 Kartla", f"{rev_card:.2f} ₼"); m3.metric("💵 Nağd (Kassa)", f"{rev_cash:.2f} ₼")
            st.markdown("---"); k1, k2, k3, k4 = st.columns(4) # Added k4 for Staff
            
            if role == 'admin':
                k1.metric("Kassa Xərci (Real)", f"{total_exp:.2f} ₼", help="Kassadan çıxan canlı pul"); 
                k2.metric("Təxmini Maya Dəyəri", f"{est_cogs:.2f} ₼", help="Resept əsasında silinən mal"); 
                k3.metric("Təxmini Mənfəət", f"{gross_profit:.2f} ₼", delta_color="normal")
                k4.metric("Staff Xərci (Satış Qiyməti)", f"{staff_expense_val:.2f} ₼", help="Personalın içdiyi kofelərin satış dəyəri")
            else:
                k1.metric("Kassa Xərci (Real)", "***"); k2.metric("Təxmini Maya Dəyəri", "***"); k3.metric("Təxmini Mənfəət", "***"); k4.metric("Staff Xərci", "***")

            if role == 'admin' or role == 'manager':
                st.markdown("### 🗑️ Satışların İdarəedilməsi")
                df_to_edit = sales.copy()
                df_to_edit.insert(0, "Seç", False)
                edited_sales = st.data_editor(
                    df_to_edit, 
                    hide_index=True, 
                    column_config={"Seç": st.column_config.CheckboxColumn(required=True)},
                    disabled=["id", "items", "total", "payment_method", "cashier", "created_at", "customer_card_id"],
                    use_container_width=True
                )
                
                selected_sales = edited_sales[edited_sales["Seç"]]
                if not selected_sales.empty:
                    if st.button(f"🗑️ Seçilən {len(selected_sales)} Satışı Sil"):
                        smart_bulk_delete_dialog(selected_sales)
                
            else: st.dataframe(sales, hide_index=True)

    if "📜 Loglar" in tab_map:
        with tab_map["📜 Loglar"]:
            st.dataframe(run_query("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 100"), hide_index=True)
    
    if "👥 CRM" in tab_map:
        with tab_map["👥 CRM"]:
            st.subheader("👥 CRM & Promo")
            
            # --- NEW: PROMO CODE CREATION (V6.27) ---
            if role in ['admin', 'manager']:
                with st.expander("🎫 Yeni Kupon / Promo Kod Yarat", expanded=False):
                    with st.form("new_promo_code_form", clear_on_submit=True):
                        c1, c2, c3 = st.columns(3)
                        pc_code = c1.text_input("Kod (Məs: YAY2026)")
                        pc_disc = c2.number_input("Endirim %", min_value=1, max_value=100, value=10)
                        pc_days = c3.number_input("Neçə gün keçərlidir?", min_value=1, max_value=365, value=30)
                        
                        if st.form_submit_button("Kodu Yarat"):
                            if pc_code:
                                valid_until = get_baku_now() + datetime.timedelta(days=pc_days)
                                try:
                                    run_action("INSERT INTO promo_codes (code, discount_percent, valid_until, assigned_user_id, is_used) VALUES (:c, :d, :v, 'system', FALSE)", 
                                               {"c":pc_code, "d":pc_disc, "v":valid_until})
                                    st.success(f"✅ Kod yaradıldı: {pc_code} ({pc_disc}%)")
                                    time.sleep(1); st.rerun()
                                except Exception as e:
                                    st.error(f"Xəta (Kod mövcud ola bilər): {e}")
            
            cust_df = run_query("SELECT card_id, type, stars, email FROM customers"); cust_df.insert(0, "Seç", False); ed_cust = st.data_editor(cust_df, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, key="crm_sel"); sel_cust_ids = ed_cust[ed_cust["Seç"]]['card_id'].tolist()
            st.divider(); c1, c2 = st.columns(2)
            with c1:
                msg = st.text_area("Ekran Mesajı"); promo_list = ["(Kuponsuz)"] + run_query("SELECT code FROM promo_codes")['code'].tolist(); sel_promo = st.selectbox("Promo Yapışdır (Seçilənlərə)", promo_list)
                if st.button("📢 Seçilənlərə Göndər / Tətbiq Et"):
                    if sel_cust_ids:
                        for cid in sel_cust_ids:
                            if msg: run_action("INSERT INTO notifications (card_id, message) VALUES (:c, :m)", {"c":cid, "m":msg})
                            if sel_promo != "(Kuponsuz)": exp = get_baku_now() + datetime.timedelta(days=30); run_action("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:c, :t, :e)", {"c":cid, "t":sel_promo, "e":exp})
                        st.success(f"{len(sel_cust_ids)} nəfərə tətbiq edildi!")
                    else: st.warning("Müştəri seçin!")

    # 🌟 ADMIN / MANAGER / STAFF Z-REPORT SECTION
    if "📊 Z-Hesabat" in tab_map:
        with tab_map["📊 Z-Hesabat"]:
            st.subheader("📊 Z-Hesabat & Satışlar")
            sc1, sc2 = st.columns([1,3])
            with sc1:
                @st.dialog("💸 Xərc Çıxart")
                def staff_expense_dialog():
                    with st.form("staff_exp"):
                        e_cat = st.selectbox("Nə üçün?", ["Xammal Alışı", "Kommunal (İşıq/Su)", "Kirayə", "Təmizlik", "Digər"]); e_amt = st.number_input("Məbləğ (AZN)", min_value=0.1); e_desc = st.text_input("Qeyd")
                        
                        # --- NEW: ADMIN SOURCE SELECTION (V6.17) ---
                        selected_investor = None
                        if st.session_state.role == 'admin':
                            e_source = st.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Investor"])
                            if e_source == "Investor":
                                # Filter subjects for investors
                                investor_list = [s for s in SUBJECTS if "Investor" in s]
                                selected_investor = st.selectbox("Hansı Investor?", investor_list)
                        else:
                            e_source = 'Kassa'

                        if st.form_submit_button("Təsdiqlə"):
                            # Determine Subject for Finance Table
                            final_subject = st.session_state.user # Default to logged in user
                            if selected_investor:
                                final_subject = selected_investor # If specific investor selected

                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject) VALUES ('out', :c, :a, :src, :d, :u, :sb)", {"c":e_cat, "a":e_amt, "src":e_source, "d":e_desc, "u":st.session_state.user, "sb":final_subject})
                            run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, :r, :s, :src)", {"a":e_amt, "r":f"{e_cat} - {e_desc}", "s":st.session_state.user, "src":e_source})
                            st.success(f"Xərc ({e_source}) qeydə alındı!"); st.rerun()

                if st.button("💸 Xərc Çıxart", use_container_width=True): 
                    if st.session_state.show_receipt_popup: st.error("Əvvəl çeki bağlayın!")
                    else: staff_expense_dialog()
            with sc2:
                btn_lbl = "🔴 Günü Bitir (Z-Hesabat)"
                if get_setting("z_report_test_mode") == "TRUE": btn_lbl += " [TEST MODE]"
                if st.button(btn_lbl, type="primary", use_container_width=True): 
                    if st.session_state.show_receipt_popup: st.error("Əvvəl çeki bağlayın!")
                    else:
                        st.session_state.z_report_active = True; st.session_state.z_calculated = False; st.rerun()
            
            if st.session_state.z_report_active and not st.session_state.show_receipt_popup:
                @st.dialog("📊 GÜNÜN BAĞLANIŞI")
                def z_report_dialog():
                    st.write("---"); st.write("💸 **GÜNLÜK MAAŞLAR ÖDƏNİLDİ?**")
                    c1, c2 = st.columns(2)
                    pay_staff = c1.checkbox("Staff (20 AZN)", key="z_chk_staff"); pay_manager = c2.checkbox("Manager (25 AZN)", key="z_chk_mgr")
                    st.write("---")
                    if st.button("🧮 HESABLA"): st.session_state.z_calculated = True
                    
                    if st.session_state.z_calculated:
                        now = get_baku_now()
                        if now.hour >= 8: shift_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
                        else: shift_start = (now - datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                        sales_cash = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' AND created_at >= :d", {"d":shift_start}).iloc[0]['s'] or 0.0
                        exp_cash = run_query("SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' AND created_at >= :d", {"d":shift_start}).iloc[0]['e'] or 0.0
                        inc_cash = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND created_at >= :d", {"d":shift_start}).iloc[0]['i'] or 0.0
                        
                        salary_deduction = 0
                        if pay_staff: salary_deduction += 20
                        if pay_manager: salary_deduction += 25
                        
                        start_limit = float(get_setting("cash_limit", "100.0"))
                        current_bal = start_limit + float(sales_cash) + float(inc_cash) - float(exp_cash) - salary_deduction
                        diff = current_bal - start_limit
                        
                        st.markdown(f"**Başlanğıc:** {start_limit:.2f} ₼"); st.markdown(f"**+ Satış (Nəğd):** {float(sales_cash):.2f} ₼")
                        st.markdown(f"**- Maaşlar:** {salary_deduction:.2f} ₼"); st.markdown(f"**- Xərclər (Kassa):** {float(exp_cash):.2f} ₼")
                        st.divider(); st.markdown(f"### KASSADA OLMALIDIR: {current_bal:.2f} ₼")
                        if diff > 0: st.info(f"📥 {diff:.2f} AZN Seyfə qoyulacaq.")
                        elif diff < 0: st.error(f"📤 {abs(diff):.2f} AZN Seyfdən götürüləcək.")
                        st.divider()
                        if st.button("✅ TƏSDİQLƏ VƏ GÜNÜ BAĞLA", type="primary"):
                            if pay_staff: run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Maaş', 20, 'Kassa', 'Z-Hesabat: Staff', :u)", {"u":st.session_state.user})
                            if pay_manager: run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Maaş', 25, 'Kassa', 'Z-Hesabat: Manager', :u)", {"u":st.session_state.user})
                            if diff > 0:
                                run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'İnkassasiya', :a, 'Kassa', 'Z-Hesabat: Seyfə Transfer', :u)", {"a":diff, "u":st.session_state.user})
                                run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'İnkassasiya', :a, 'Seyf', 'Z-Hesabat: Kassadan Gələn', :u)", {"a":diff, "u":st.session_state.user})
                            elif diff < 0:
                                needed = abs(diff)
                                run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Kassa Tamamlama', :a, 'Kassa', 'Z-Hesabat: Seyfdən Gələn', :u)", {"a":needed, "u":st.session_state.user})
                                run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Kassa Tamamlama', :a, 'Seyf', 'Z-Hesabat: Kassaya Gedən', :u)", {"a":needed, "u":st.session_state.user})
                            
                            set_setting("last_z_report_time", get_baku_now().isoformat())
                            log_system(st.session_state.user, f"Z-Hesabat Bağlandı. Qalıq: {current_bal}")
                            st.session_state.z_report_active = False; st.session_state.z_calculated = False; st.success("Gün Uğurla Bağlandı! 🎉"); time.sleep(2); st.rerun()
                z_report_dialog()

            st.divider(); st.markdown("### 🔍 Mənim Satışlarım")
            c1, c2 = st.columns(2); 
            
            # --- OPTIMIZATION (V6.33): DEFAULT TO TODAY ---
            default_start = datetime.date.today()
            default_end = datetime.date.today()
            
            d1 = c1.date_input("Start", default_start, key="staff_date_start"); 
            d2 = c2.date_input("End", default_end, key="staff_date_end"); 
            ts_start = datetime.datetime.combine(d1, datetime.time(0,0)); ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
            
            # ONLY FETCH IF DATES ARE VALID (Prevents huge load on init)
            if role == 'admin' or d1 == datetime.date.today():
                    q_staff = """SELECT s.created_at AS "Tarix", s.items AS "Mallar", s.original_total AS "Məbləğ (Endirimsiz)", s.discount_amount AS "Endirim", s.total AS "Yekun", s.payment_method AS "Ödəniş", s.customer_card_id AS "Müştəri ID" FROM sales s WHERE s.cashier = :u AND s.created_at BETWEEN :s AND :e ORDER BY s.created_at DESC"""
                    mys = run_query(q_staff, {"u":st.session_state.user, "s":ts_start, "e":ts_end})
                    total_sales = mys['Yekun'].sum() if not mys.empty else 0.0
                    st.metric(f"Seçilən Tarix Üzrə Cəm", f"{total_sales:.2f} ₼")
                    st.dataframe(mys, hide_index=True, use_container_width=True)
            else:
                    st.info("Keçmiş tarixçə üçün tarix seçin.")

    st.markdown(f"<div style='text-align:center;color:#aaa;margin-top:50px;'>Ironwaves POS {VERSION}</div>", unsafe_allow_html=True)
