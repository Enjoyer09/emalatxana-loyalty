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
# === EMALATKHANA POS - V6.72 (LOGIN & TABS FIXED) ===
# ==========================================

VERSION = "v6.72 (Fixed: Staff Login Error, Empty Tabs, Structure)"
BRAND_NAME = "Emalatkhana Daily Drinks and Coffee"

# --- CONFIG ---
st.set_page_config(page_title=BRAND_NAME, page_icon="☕", layout="wide", initial_sidebar_state="collapsed")
ADMIN_DEFAULT_PASS = os.environ.get("ADMIN_PASS", "admin123") 
BONUS_RECIPIENTS = ["Sabina", "Samir"] 

# --- CONSTANTS ---
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
PRESET_CATEGORIES = ["Kofe (Dənələr)", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar"]
CAT_ORDER_MAP = {cat: i for i, cat in enumerate(PRESET_CATEGORIES)}

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"
APP_URL = "https://emalatxana.ironwaves.store"
ALLOWED_TABLES = ["users", "menu", "sales", "ingredients", "recipes", "customers", "notifications", "settings", "system_logs", "tables", "promo_codes", "customer_coupons", "expenses", "finance", "admin_notes", "bonuses"]

# --- STATE MANAGEMENT ---
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
if 'calc_received' not in st.session_state: st.session_state.calc_received = 0.0
if 'tip_input_val' not in st.session_state: st.session_state.tip_input_val = 0.0
if 'rec_qty_val' not in st.session_state: st.session_state.rec_qty_val = 0.0

# --- MULTI CART STATE ---
if 'multi_carts' not in st.session_state:
    st.session_state.multi_carts = {
        1: {'cart': [], 'customer': None},
        2: {'cart': [], 'customer': None},
        3: {'cart': [], 'customer': None}
    }
if 'active_cart_id' not in st.session_state:
    st.session_state.active_cart_id = 1

# --- CSS (METALLIC UI) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;700&display=swap');
    :root { --primary-color: #2E7D32; }
    .stApp { background-color: #F4F5F7 !important; color: #333 !important; font-family: 'Arial', sans-serif !important; }
    div[data-testid="stStatusWidget"] { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    
    div.stRadio > div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        justify-content: center;
        overflow-x: auto;
        background: white;
        padding: 10px;
        border-radius: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div.stRadio > div[role="radiogroup"] > label {
        background: transparent;
        border: 1px solid #ddd;
        border-radius: 8px;
        margin: 0 5px;
        padding: 5px 15px;
        cursor: pointer;
        transition: all 0.2s;
    }
    div.stRadio > div[role="radiogroup"] > label[data-checked="true"] {
        background: #2E7D32 !important;
        color: white !important;
        border-color: #2E7D32;
    }

    /* --- METALLIC BUTTONS --- */
    div.stButton > button { 
        border-radius: 12px !important; 
        font-weight: bold !important; 
        border: 1px solid #999 !important; 
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2) !important; 
        transition: all 0.1s;
    }
    div.stButton > button:active { 
        transform: scale(0.98); 
        box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3) !important;
    }
    
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #FF6B35, #FF8C00) !important; color: white !important; border: none !important; }
    
    div.stButton > button[kind="secondary"] { 
        background: linear-gradient(145deg, #f8f9fa, #cfd8dc) !important; 
        color: #263238 !important; 
        min-height: 90px !important; 
        white-space: pre-wrap !important;
        font-size: 16px !important;
        line-height: 1.3 !important;
        padding: 8px !important;
    }
    
    .header-btn button {
        min-height: 40px !important;
        font-size: 14px !important;
        padding: 5px !important;
    }

    .cartoon-quote { font-family: 'Comfortaa', cursive; color: #E65100; font-size: 22px; font-weight: 700; text-align: center; margin-bottom: 20px; animation: float 3s infinite; }
    .msg-box { background: linear-gradient(45deg, #FF9800, #FFC107); padding: 15px; border-radius: 15px; color: white; font-weight: bold; text-align: center; margin-bottom: 20px; font-family: 'Comfortaa', cursive !important; animation: pulse 2s infinite; }
    .stamp-container { display: flex; justify-content: center; margin-bottom: 20px; }
    .stamp-card { background: white; padding: 15px 30px; text-align: center; font-family: 'Courier Prime', monospace; font-weight: bold; transform: rotate(-3deg); border-radius: 12px; border: 4px solid #B71C1C; color: #B71C1C; box-shadow: 0 0 0 4px white, 0 0 0 7px #B71C1C; }
    .coffee-grid-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; justify-items: center; margin-top: 20px; max-width: 400px; margin-left: auto; margin-right: auto; }
    .coffee-icon-img { width: 50px; height: 50px; transition: all 0.5s ease; }
    .cup-earned { filter: invert(24%) sepia(96%) saturate(1720%) hue-rotate(94deg) brightness(92%) contrast(102%); opacity: 1; transform: scale(1.1); }
    .cup-red-base { filter: invert(18%) sepia(90%) saturate(6329%) hue-rotate(356deg) brightness(96%) contrast(116%); }
    .cup-anim { animation: bounce 1s infinite; }
    .cup-empty { filter: grayscale(100%); opacity: 0.2; }
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
        try: s.execute(text("ALTER TABLE sales ADD COLUMN IF NOT EXISTS tip_amount DECIMAL(10,2) DEFAULT 0")); s.commit()
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP);"))
        try: s.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0")); s.commit()
        except: pass
        try: s.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP")); s.commit()
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        try: s.execute(text("ALTER TABLE active_sessions ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP")); s.commit()
        except: pass
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
        s.execute(text("CREATE TABLE IF NOT EXISTS admin_notes (id SERIAL PRIMARY KEY, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        try: s.execute(text("ALTER TABLE admin_notes ADD COLUMN IF NOT EXISTS title TEXT")); s.commit()
        except: pass
        try: s.execute(text("ALTER TABLE admin_notes ADD COLUMN IF NOT EXISTS amount DECIMAL(10,2) DEFAULT 0")); s.commit()
        except: pass
        s.execute(text("CREATE TABLE IF NOT EXISTS bonuses (id SERIAL PRIMARY KEY, employee TEXT, amount DECIMAL(10,2), is_paid BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
        try:
            p_hash = bcrypt.hashpw(ADMIN_DEFAULT_PASS.encode(), bcrypt.gensalt()).decode()
            s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin') ON CONFLICT (username) DO NOTHING"), {"p": p_hash})
            s.commit()
        except: s.rollback()
    return True
ensure_schema()

# --- HELPERS ---
def get_baku_now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=4))).replace(tzinfo=None)

def get_logical_date():
    now = get_baku_now()
    if now.hour < 8: return (now - datetime.timedelta(days=1)).date()
    return now.date()

def get_shift_range(date_obj=None):
    if date_obj is None: date_obj = get_logical_date()
    start = datetime.datetime.combine(date_obj, datetime.time(8, 0, 0))
    end = start + datetime.timedelta(hours=24)
    return start, end

def clean_qr_code(raw_code):
    if not raw_code: return ""
    code = raw_code.strip()
    if "id=" in code:
        try: return code.split("id=")[1].split("&")[0]
        except: pass
    return re.sub(r'[^a-zA-Z0-9]', '', code)

def run_query(q, p=None): return conn.query(q, params=p if p else {}, ttl=0)
def run_action(q, p=None): 
    with conn.session as s: s.execute(text(q), p if p else {}); s.commit()
    return True
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): 
    try: return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
    except: return False
def log_system(user, action, cid=None):
    try: run_action("INSERT INTO system_logs (username, action, customer_id, created_at) VALUES (:u, :a, :c, :t)", {"u":user, "a":action, "c":cid, "t":get_baku_now()})
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

# --- CACHE ---
@st.cache_data(ttl=600)
def get_cached_menu(): return run_query("SELECT * FROM menu WHERE is_active=TRUE")
@st.cache_data(ttl=600)
def get_cached_users(): return run_query("SELECT * FROM users")

# --- AUTH FUNCTIONS ---
def create_session(username, role):
    token = secrets.token_urlsafe(32)
    run_action("INSERT INTO active_sessions (token, username, role, created_at, last_activity) VALUES (:t, :u, :r, :c, :c)", {"t":token, "u":username, "r":role, "c":get_baku_now()})
    return token

def check_url_token_login():
    qp = st.query_params; token_in_url = qp.get("token")
    if token_in_url and not st.session_state.logged_in:
        res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t":token_in_url})
        if not res.empty:
            r = res.iloc[0]
            if (get_baku_now() - (pd.to_datetime(r['last_activity']) if r['last_activity'] else pd.to_datetime(r['created_at']))).total_seconds() > 28800:
                 run_action("DELETE FROM active_sessions WHERE token=:t", {"t":token_in_url}); st.error("Sessiya bitib."); return False
            st.session_state.logged_in = True; st.session_state.user = r['username']; st.session_state.role = r['role']; st.session_state.session_token = token_in_url
            run_action("UPDATE active_sessions SET last_activity=:n WHERE token=:t", {"n":get_baku_now(), "t":token_in_url})
            st.query_params.clear(); return True
    return False

def validate_session():
    if not st.session_state.session_token: return False
    res = run_query("SELECT * FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token})
    if res.empty: return False
    run_action("UPDATE active_sessions SET last_activity=:n WHERE token=:t", {"n":get_baku_now(), "t":st.session_state.session_token})
    return True

def logout_user():
    if st.session_state.session_token: run_action("DELETE FROM active_sessions WHERE token=:t", {"t":st.session_state.session_token})
    st.session_state.logged_in = False; st.session_state.session_token = None; st.query_params.clear(); st.rerun()

# --- CALLBACKS ---
def clear_customer_data_callback():
    st.session_state.current_customer_ta = None
    st.session_state["search_input_ta"] = ""

def set_received_amount(amount):
    st.session_state.calc_received = float(amount)

def reset_recipe_inputs():
    st.session_state.rec_qty_val = 0.0

# --- V6.69: MULTI-CART SWITCHER ---
def switch_cart(new_id):
    # Save current cart to storage
    st.session_state.multi_carts[st.session_state.active_cart_id]['cart'] = st.session_state.cart_takeaway
    st.session_state.multi_carts[st.session_state.active_cart_id]['customer'] = st.session_state.current_customer_ta
    
    # Load new cart from storage
    st.session_state.active_cart_id = new_id
    st.session_state.cart_takeaway = st.session_state.multi_carts[new_id]['cart']
    st.session_state.current_customer_ta = st.session_state.multi_carts[new_id]['customer']

@st.dialog("🔐 Admin Təsdiqi")
def admin_confirm_dialog(action_name, callback, *args):
    st.warning(f"⚠️ {action_name}")
    with st.form("admin_conf_form"):
        pwd = st.text_input("Admin Şifrəsi", type="password")
        if st.form_submit_button("Təsdiqlə"):
            adm = run_query("SELECT password FROM users WHERE role='admin' LIMIT 1")
            if not adm.empty and verify_password(pwd, adm.iloc[0]['password']): callback(*args); st.success("İcra olundu!"); time.sleep(1); st.rerun()
            else: st.error("Yanlış Şifrə!")

@st.dialog("🗑️ Seçilən Satışları Sil")
def smart_bulk_delete_dialog(selected_sales):
    cnt = len(selected_sales); total_val = selected_sales['total'].sum()
    st.warning(f"Seçilən Satış Sayı: {cnt}"); st.error(f"Cəmi Məbləğ: {total_val:.2f} ₼")
    st.write("---"); reason = st.radio("Səbəb seçin:", ["🅰️ Səhv Vurulub / Test (Mallar Anbara Qayıtsın) 🔄", "🅱️ Zay Olub / Dağılıb (Mallar Qayıtmasın) 🗑️"])
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
                                        s.execute(text("UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:n"), {"q":float(r[1])*iqty, "n":r[0]})
                for i in ids_to_del: s.execute(text("DELETE FROM sales WHERE id=:id"), {"id":int(i)})
                s.commit()
            log_system(st.session_state.user, f"Toplu Silmə ({cnt} ədəd)"); st.success("Uğurla Silindi!"); time.sleep(1.5); st.rerun()
        except Exception as e: st.error(f"Xəta: {e}")

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0):
    total = 0.0; disc_rate = 0.0; current_stars = 0
    if manual_discount_percent > 0:
        disc_rate = manual_discount_percent / 100.0; final_total = 0.0
        for i in cart: line = i['qty'] * i['price']; total += line; final_total += (line - (line * disc_rate))
        if is_table: final_total += final_total * 0.07
        return total, final_total, disc_rate, 0, 0, 0, False
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'ikram': return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20}; disc_rate = rates.get(ctype, 0.0)
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')]); free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty); final_total = 0.0
    for i in cart:
        line = i['qty'] * i['price']; total += line
        if i.get('is_coffee'): final_total += (line - (line * disc_rate))
        else: final_total += line
    if is_table: final_total += final_total * 0.07
    return total, final_total, disc_rate, free_cof, 0, 0, False

def get_receipt_html_string(cart, total):
    store = get_setting("receipt_store_name", BRAND_NAME); addr = get_setting("receipt_address", "Baku"); phone = get_setting("receipt_phone", ""); logo = get_setting("receipt_logo_base64"); time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<img src="data:image/png;base64,{logo}" style="width:80px; filter:grayscale(100%);">' if logo else ""
    rows = "".join([f"<tr><td style='border-bottom:1px dashed #000; padding:5px;'>{int(i['qty'])}</td><td style='border-bottom:1px dashed #000; padding:5px;'>{i['item_name']}</td><td style='border-bottom:1px dashed #000; padding:5px; text-align:right;'>{i['qty']*i['price']:.2f}</td></tr>" for i in cart])
    return f"""<div id='receipt-area' style="font-family:'Courier New'; width:300px; margin:0 auto; text-align:center;">{img_tag}<h3>{store}</h3><p>{addr}<br>{phone}</p><p>{time_str}</p><table style="width:100%; text-align:left; border-collapse:collapse;"><tr><th style='border-bottom:1px dashed #000;'>Say</th><th style='border-bottom:1px dashed #000;'>Mal</th><th style='border-bottom:1px dashed #000; text-align:right;'>Məb</th></tr>{rows}</table><h3>YEKUN: {total:.2f} ₼</h3><p>Təşəkkürlər!</p></div>"""

@st.dialog("🧾 Çek")
def show_receipt_dialog(cart_data, total_amt, cust_email):
    html = get_receipt_html_string(cart_data, total_amt); components.html(html, height=450, scrolling=True); st.markdown(f'<div id="hidden-print-area">{html}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: components.html(f"""<button onclick="window.print()" style="background:#2E7D32;color:white;padding:10px;border-radius:5px;width:100%;">🖨️ ÇAP ET</button>""", height=50)
    with c2: 
        if cust_email and st.button("📧 Email"): send_email(cust_email, "Çekiniz", html); st.success("Getdi!")
    if st.button("❌ Bağla"): st.session_state.show_receipt_popup=False; st.session_state.last_receipt_data=None; st.rerun()

# ==========================================
# === MAIN APP ===
# ==========================================
if not st.session_state.logged_in: check_url_token_login()

if "id" in st.query_params and not st.session_state.logged_in:
    # --- CUSTOMER QR PAGE ---
    card_id = st.query_params["id"]; token = st.query_params.get("t"); c1, c2, c3 = st.columns([1,2,1]); logo = get_setting("receipt_logo_base64")
    with c2: 
        if logo: st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" width="120"></div>', unsafe_allow_html=True)
    st.markdown("""<style>.stApp{background-color:#FFFFFF!important;}h1,h2,h3,h4,h5,h6,p,div,span,label,li{color:#000000!important;}</style>""", unsafe_allow_html=True)
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
                st.markdown(terms, unsafe_allow_html=True); agree = st.checkbox("Qaydaları oxudum və qəbul edirəm", value=False); st.divider(); st.write("**Könüllü:**"); em = st.text_input("Email"); dob = st.date_input("Doğum Tarixi", value=None, min_value=datetime.date(1950,1,1))
                if st.form_submit_button("TƏSDİQLƏ VƏ QOŞUL"):
                    if agree: run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":str(dob) if dob else None, "i":card_id}); st.rerun()
                    else: st.error("Zəhmət olmasa, qaydaları qəbul edin.")
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
            icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; style = ""; cls = "cup-empty"
            if i == 9: 
                if user['stars'] >= 10: cls = "cup-red-base cup-anim"; style = "opacity: 1;"
                else: op = 0.1 + (user['stars'] * 0.09); cls = "cup-red-base"; style = f"opacity: {op};"
            elif i < user['stars']: cls = "cup-earned"
            html += f'<img src="{icon}" class="{cls} coffee-icon-img" style="{style}">'
        st.markdown(html + "</div>", unsafe_allow_html=True)
        if user['stars'] >= 10: st.success("🎉 Təbriklər! Bu kofeniz bizdəndir!")
        with st.form("fd"):
            s = st.feedback("stars"); m = st.text_input("Fikriniz...")
            if st.form_submit_button("Göndər") and s: run_action("INSERT INTO feedbacks (card_id,rating,comment,created_at) VALUES (:c,:r,:m,:t)", {"c":card_id,"r":s+1,"m":m,"t":get_baku_now()}); st.success("Təşəkkürlər!")
        st.stop()

if not st.session_state.logged_in:
    # --- LOGIN PAGE ---
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center; color:#2E7D32;'>{BRAND_NAME}</h1><h5 style='text-align:center;'>{VERSION}</h5>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["STAFF", "ADMIN"])
        with t1:
            # --- V6.72: FIXED STAFF LOGIN LOOP ---
            with st.form("sl"):
                p = st.text_input("PIN", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    u = get_cached_users()
                    found_user = None
                    for _, r in u.iterrows():
                        if r['role'] in ['staff','manager']:
                            # Check lock
                            if r['locked_until'] and pd.to_datetime(r['locked_until']) > get_baku_now():
                                st.error(f"{r['username']} BLOKLANDI! 5 dəqiqə gözləyin.")
                                found_user = "LOCKED"
                                break
                            
                            # Verify Pass
                            if verify_password(p, r['password']):
                                found_user = r
                                break
                    
                    if isinstance(found_user, pd.Series):
                        # SUCCESS
                        r = found_user
                        st.session_state.logged_in=True; st.session_state.user=r['username']; st.session_state.role=r['role']
                        token = create_session(r['username'],r['role']); st.session_state.session_token = token
                        run_action("UPDATE users SET failed_attempts=0 WHERE username=:u", {"u":r['username']})
                        st.query_params.clear()
                        st.rerun()
                    elif found_user == "LOCKED":
                        pass # Message already shown
                    else:
                        st.error("PIN Tapılmadı")
        with t2:
            with st.form("al"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    ud = run_query("SELECT * FROM users WHERE username=:u", {"u":u})
                    if not ud.empty and verify_password(p, ud.iloc[0]['password']):
                        st.session_state.logged_in=True; st.session_state.user=u; st.session_state.role=ud.iloc[0]['role']; token = create_session(u,ud.iloc[0]['role']); st.session_state.session_token = token; st.query_params.clear(); st.rerun()
                    else: st.error("Səhv")

else:
    if not validate_session(): logout_user()
    
    if st.session_state.show_receipt_popup and st.session_state.last_receipt_data: show_receipt_dialog(st.session_state.last_receipt_data['cart'], st.session_state.last_receipt_data['total'], st.session_state.last_receipt_data['email'])

    # --- HEADER ---
    h1, h2, h3 = st.columns([4,1,1])
    with h1: st.markdown(f"**👤 {st.session_state.user}** | {st.session_state.role.upper()}")
    with h2: 
        if st.button("🔄 YENİLƏ", key="refresh_top", use_container_width=True, type="secondary"): st.rerun()
    with h3: 
        if st.button("🚪 ÇIXIŞ", type="primary", key="logout_top", use_container_width=True): logout_user()
    st.divider()

    role = st.session_state.role
    
    # --- BUILD TABS LIST ---
    tabs_list = []
    if role in ['admin', 'manager', 'staff']: tabs_list.append("🏃‍♂️ AL-APAR")
    show_tables_staff = get_setting("staff_show_tables", "TRUE") == "TRUE"; show_tables_mgr = get_setting("manager_show_tables", "TRUE") == "TRUE"
    if role == 'admin' or (role == 'manager' and show_tables_mgr) or (role == 'staff' and show_tables_staff): tabs_list.append("🍽️ MASALAR")
    if role in ['admin', 'manager']: tabs_list.extend(["💰 Maliyyə", "📦 Anbar", "📊 Analitika", "📜 Loglar", "👥 CRM"])
    if role == 'manager':
         if get_setting("manager_perm_menu", "FALSE") == "TRUE": tabs_list.append("📋 Menyu")
         if get_setting("manager_perm_recipes", "FALSE") == "TRUE": tabs_list.append("📜 Resept")
    if role == 'admin':
        if "📋 Menyu" not in tabs_list: tabs_list.append("📋 Menyu")
        if "📜 Resept" not in tabs_list: tabs_list.append("📜 Resept")
        tabs_list.extend(["📝 Qeydlər", "⚙️ Ayarlar", "💾 Baza", "QR"])
    if role in ['staff', 'manager', 'admin']: tabs_list.append("📊 Z-Hesabat")

    # --- PERSISTENT NAVIGATION ---
    if "current_tab" not in st.session_state: st.session_state.current_tab = tabs_list[0]
    selected_tab = st.radio("Menu", tabs_list, horizontal=True, label_visibility="collapsed", key="main_nav_radio", index=tabs_list.index(st.session_state.current_tab) if st.session_state.current_tab in tabs_list else 0)
    if selected_tab != st.session_state.current_tab: st.session_state.current_tab = selected_tab
    
    def add_to_cart(cart, item):
        for i in cart: 
            if i['item_name'] == item['item_name'] and i.get('status')=='new': i['qty']+=1; return
        cart.append(item)

    def render_menu(cart, key):
        menu_df = get_cached_menu()
        menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER_MAP).fillna(99)
        menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])
        
        pos_search = st.text_input("🔍 Menyu Axtarış", key=f"pos_s_{key}")
        if pos_search: menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]

        cats = ["Hamısı"] + sorted(menu_df['category'].unique().tolist(), key=lambda x: CAT_ORDER_MAP.get(x, 99))
        sc = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_{key}")
        prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]
        
        if not prods.empty:
            groups = {}
            for _, r in prods.iterrows():
                n = r['item_name']; base = n
                for s in [" S", " M", " L", " XL", " Single", " Double"]:
                    if n.endswith(s): base = n[:-len(s)]; break
                if base not in groups: groups[base] = []
                groups[base].append(r)
            # --- METALLIC BIG BUTTONS (3 COLUMNS) ---
            cols = st.columns(3)
            i = 0
            for base, items in groups.items():
                with cols[i%3]:
                    if len(items) > 1:
                        @st.dialog(f"{base}")
                        def show_variants(its, grp_key):
                            for it in its:
                                if st.button(f"{it['item_name']}\n{it['price']}₼", key=f"v_{it['id']}_{grp_key}", use_container_width=True, type="secondary"):
                                    add_to_cart(cart, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'category':it['category'], 'status':'new'}); st.rerun()
                        if st.button(f"{base}\n▾", key=f"grp_{base}_{key}_{sc}", use_container_width=True, type="secondary"): show_variants(items, f"{key}_{sc}")
                    else:
                        r = items[0]
                        if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}_{sc}", use_container_width=True, type="secondary"):
                            add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'category':r['category'], 'status':'new'}); st.rerun()
                i+=1

    # --- TAB CONTENT ---
    if selected_tab == "🏃‍♂️ AL-APAR":
            # --- MULTI-CART HEADER ---
            c_carts = st.columns(3)
            for cid in [1, 2, 3]:
                count = len(st.session_state.multi_carts[cid]['cart'])
                if cid == st.session_state.active_cart_id: count = len(st.session_state.cart_takeaway)
                btn_type = "primary" if cid == st.session_state.active_cart_id else "secondary"
                label = f"🛒 Səbət {cid} ({count})"
                if c_carts[cid-1].button(label, key=f"cart_sw_{cid}", type=btn_type, use_container_width=True):
                    switch_cart(cid); st.rerun()
            st.divider()

            c1, c2 = st.columns([1.5, 3])
            with c1:
                st.info(f"🧾 Al-Apar (Səbət {st.session_state.active_cart_id})")
                with st.form("scta", clear_on_submit=False): 
                    code = st.text_input("Müştəri (QR)", label_visibility="collapsed", placeholder="Skan...", key="search_input_ta")
                    if st.form_submit_button("🔍") or code:
                        cid = clean_qr_code(code)
                        try: 
                            r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                            if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.toast(f"✅ Müştəri: {cid}"); st.rerun()
                            else: st.error("Tapılmadı")
                        except: pass
                
                cust = st.session_state.current_customer_ta
                if cust: 
                    c_head, c_del = st.columns([4,1])
                    c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                    c_del.button("❌", key="clear_cust", on_click=clear_customer_data_callback)
                
                with st.expander("💙 Yalnız Çayvoy (Satışsız)"):
                    t_amt = st.number_input("Tip Məbləği (AZN)", min_value=0.0, step=1.0, value=st.session_state.tip_input_val, key="tip_standalone_inp")
                    if st.button("💳 Karta Tip Vur", key="tip_only_btn"):
                        if t_amt > 0:
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Tips / Çayvoy', :a, 'Bank Kartı', 'Satışsız Tip', :u)", {"a":t_amt, "u":st.session_state.user})
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Tips / Çayvoy', :a, 'Kassa', 'Satışsız Tip (Staffa)', :u)", {"a":t_amt, "u":st.session_state.user})
                            run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, 'Tips / Çayvoy', :u, 'Kassa')", {"a":t_amt, "u":st.session_state.user})
                            st.success(f"✅ {t_amt} AZN Tip qeyd olundu!")
                            st.toast(f"💵 {t_amt} AZN-i KASSADAN GÖTÜRÜN!", icon="🤑")
                            st.session_state.tip_input_val = 0.0; time.sleep(2); st.rerun()
                        else: st.error("Məbləğ yazın.")

                man_disc_val = st.selectbox("Endirim (%)", [0, 10, 20, 30, 40, 50], index=0, key="manual_disc_sel"); disc_note = ""
                if man_disc_val > 0:
                    disc_note = st.text_input("Səbəb (Məcburi!)", placeholder="Məs: Dost, Menecer jesti", key="disc_reason_inp")
                    if not disc_note: st.warning("⚠️ Endirim üçün səbəb yazmalısınız!")

                raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust, manual_discount_percent=man_disc_val)
                if st.session_state.cart_takeaway:
                    for i, item in enumerate(st.session_state.cart_takeaway):
                        c_n, c_d, c_q, c_u = st.columns([3, 1, 1, 1]); c_n.write(f"{item['item_name']}"); c_q.write(f"x{item['qty']}")
                        if c_d.button("➖", key=f"dec_{i}"): 
                             if item['qty'] > 1: item['qty'] -= 1
                             else: st.session_state.cart_takeaway.pop(i)
                             st.rerun()
                        if c_u.button("➕", key=f"inc_{i}"): item['qty'] += 1; st.rerun()
                st.markdown(f"<h2 style='text-align:right;color:#E65100'>{final:.2f} ₼</h2>", unsafe_allow_html=True)
                if is_ikram: st.success("🎁 İKRAM")
                elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
                
                # --- CALCULATOR ---
                if final > 0:
                    st.markdown("---")
                    cb1, cb2, cb3, cb4, cb
