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
import threading # Arxa fon prosesləri üçün

# --- EMAIL AYARLARI ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
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

# ==========================================
# === DİZAYN KODLARI (FINAL) ===
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700&display=swap');
    
    #MainMenu, header, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    
    @keyframes heartbeat-enter {
        0% { transform: scale(0.9); opacity: 0; }
        100% { transform: scale(1); opacity: 1; }
    }
    .stApp {
        animation: heartbeat-enter 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;
        font-family: 'Oswald', sans-serif !important;
        background-color: #FAFAFA;
    }
    .block-container { padding-top: 0rem !important; padding-bottom: 2rem !important; max-width: 100%; }

    /* POS BUTTONS - PRODUCTS (ORANGE) */
    div.stButton > button {
        background-color: white;
        border: 2px solid #FF9800; color: #E65100 !important;
        font-size: 20px !important; font-weight: 700;
        border-radius: 15px; min-height: 85px; width: 100%;
        box-shadow: 0 4px 0 #FFCC80; transition: all 0.1s; margin-bottom: 8px;
    }
    div.stButton > button:active { transform: translateY(4px); box-shadow: none; }
    div.stButton > button:hover { background-color: #FFF3E0; }

    /* POS BUTTONS - CATEGORIES (GREEN) */
    div.stButton > button[kind="primary"] {
        background-color: #F1F8E9;
        border: 2px solid #2E7D32 !important; color: #2E7D32 !important;
        font-size: 18px !important; min-height: 60px !important;
        box-shadow: 0 3px 0 #A5D6A7;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #DCEDC8; }

    /* CARDS & UI */
    .digital-card {
        background: white; border-radius: 25px; padding: 20px;
        box-shadow: 0 10px 40px rgba(46, 125, 50, 0.1); border: 2px solid #E8F5E9;
        margin-bottom: 25px; text-align: center; position: relative;
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
    
    .inner-motivation {
        background-color: #FFF3E0; color: #E65100;
        padding: 10px; border-radius: 12px;
        font-size: 18px; font-style: italic; font-weight: bold;
        margin-bottom: 15px; border: 1px dashed #FFB74D;
    }
    .feedback-box { background: #fff; border: 2px solid #EEEEEE; border-radius: 15px; padding: 15px; margin-top: 15px; }

    .js-button {
        display: inline-block; padding: 10px 20px;
        color: white; background-color: #2E7D32;
        border: none; border-radius: 8px;
        font-family: 'Oswald', sans-serif; font-size: 16px;
        text-decoration: none; text-align: center; cursor: pointer;
        width: 100%; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    h1, h2, h3, h4, span { color: #2E7D32 !important; }
    .vip-status-box { background: linear-gradient(135deg, #FF9800 0%, #EF6C00 100%); color: white; padding: 10px; border-radius: 10px; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; }
    .orange-gift { filter: sepia(100%) saturate(3000%) hue-rotate(330deg) brightness(100%) contrast(105%); }
    .pulse-anim { animation: pulse 1.5s infinite; filter: drop-shadow(0 0 5px #FF9800); }
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
    
    .coupon-alert {
        background-color: #D1F2EB; border: 2px dashed #2E7D32;
        padding: 10px; border-radius: 10px; text-align: center;
        color: #145A32; font-weight: bold; font-size: 18px; margin-bottom: 10px;
    }
    </style>
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
                s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_visit TIMESTAMP;"))
                s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS secret_token TEXT;"))
                s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_coffee BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE);"))
                try: s.execute(text("ALTER TABLE menu ADD COLUMN IF NOT EXISTS is_coffee BOOLEAN DEFAULT FALSE;"))
                except: pass
                s.execute(text("CREATE TABLE IF NOT EXISTS customer_coupons (id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
                s.execute(text("UPDATE customers SET secret_token = md5(random()::text) WHERE secret_token IS NULL;"))
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
    if not BREVO_API_KEY: return False 
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": SENDER_NAME, "email": SENDER_EMAIL}, "to": [{"email": to_email}], "subject": subject, "textContent": body}
    try:
        r = requests.post(url, json=payload, headers=headers)
        return r.status_code == 201
    except: return False

@st.cache_data(persist="disk")
def generate_custom_qr(url_data, center_text):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url_data); qr.make(fit=True)
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
    quotes = ["Bu gün əla görünürsən! 🧡", "Enerjini bərpa etmək vaxtıdır! ⚡", "Sən ən yaxşısına layiqsən! ✨", "Kofe ilə gün daha gözəldir! ☀️", "Gülüşün dünyanı dəyişə bilər! 😊"]
    return random.choice(quotes)

# --- 🔥 AVTOMATİK AD GÜNÜ SİSTEMİ ---
def check_and_send_birthday_emails():
    """Gündə 1 dəfə ad günlərini yoxlayır və hədiyyə göndərir"""
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        with conn.session as s:
            res = s.execute(text("SELECT value FROM settings WHERE key = 'last_birthday_check'")).fetchone()
            last_run = res[0] if res else None
            
            if last_run == today_str: return 

            today_mm_dd = datetime.date.today().strftime("%m-%d")
            birthdays = s.execute(text("SELECT card_id, email FROM customers WHERE RIGHT(birth_date, 5) = :td AND email IS NOT NULL AND is_active = TRUE"), {"td": today_mm_dd}).fetchall()
            
            for user in birthdays:
                card_id, email = user[0], user[1]
                subject = "🎉 Ad Günün Mübarək! Kofen Bizdən! ☕"
                body = (
                    f"Salam dəyərli dost! 🎂\n\n"
                    f"Bu gün sənin günündür! Həyat enerjin heç vaxt bitməsin.\n\n"
                    f"🎁 Sənə kiçik bir hədiyyəmiz var: 1 ədəd PULSUZ Kofe!\n"
                    f"Yaxınlaşanda şəxsiyyət vəsiqəni və QR kodunu göstərməyi unutma.\n\n"
                    f"Sevgilərlə,\nEmalatxana Coffee"
                )
                if send_email(email, subject, body):
                    s.execute(text("INSERT INTO notifications (card_id, message) VALUES (:cid, '🎂 Ad Günün Mübarək! Hədiyyə Kofen Var!')"), {"cid": card_id})
                    s.execute(text("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:cid, 'birthday_gift')"), {"cid": card_id})
            
            s.execute(text("INSERT INTO settings (key, value) VALUES ('last_birthday_check', :val) ON CONFLICT (key) DO UPDATE SET value = :val"), {"val": today_str})
            s.commit()
    except Exception as e: print(f"Birthday Error: {e}")

if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = True
    threading.Thread(target=check_and_send_birthday_emails, daemon=True).start()

# --- POPUP DIALOGS ---
@st.dialog("📏 ÖLÇÜ SEÇİN")
def show_size_selector(base_name, variants):
    st.markdown(f"<h3 style='text-align:center; color:#E65100'>{base_name}</h3>", unsafe_allow_html=True)
    cols = st.columns(len(variants))
    for idx, item in enumerate(variants):
        name_parts = item['item_name'].split()
        size_label = name_parts[-1] if name_parts[-1] in ['S', 'M', 'L'] else item['item_name']
        with cols[idx]:
            if st.button(f"{size_label}\n{item['price']} ₼", key=f"sz_{item['id']}", use_container_width=True):
                st.session_state.cart.append(item)
                st.rerun()

@st.dialog("⚠️ TƏSDİQLƏ")
def confirm_delete(card_id):
    st.write(f"**{card_id}** nömrəli müştərini silmək istədiyinizə əminsiniz?")
    if st.button("🗑️ Bəli, Sil", type="primary"):
        if run_action("DELETE FROM customers WHERE card_id=:id", {"id":card_id}):
            st.success("Silindi!"); time.sleep(1); st.rerun()
        else: st.error("Xəta baş verdi.")

@st.dialog("📥 BACKUP TƏSDİQİ")
def confirm_backup():
    st.write("Bütün məlumat bazasını (Excel) yükləmək istəyirsiniz?")
    if st.button("📥 Yüklə", type="primary"):
        try:
            def clean_df(df):
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]): df[col] = df[col].dt.tz_localize(None)
                return df
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                clean_df(run_query("SELECT * FROM customers")).to_excel(writer, sheet_name='Müştərilər', index=False)
                clean_df(run_query("SELECT * FROM sales")).to_excel(writer, sheet_name='Satışlar', index=False)
                clean_df(run_query("SELECT * FROM menu")).to_excel(writer, sheet_name='Menyu', index=False)
                clean_df(run_query("SELECT * FROM feedback")).to_excel(writer, sheet_name='Rəylər', index=False)
            st.download_button("⬇️ Faylı Endir", output.getvalue(), f"Backup_{datetime.date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.success("Hazırdır!")
        except Exception as e: st.error(f"Xəta: {e}")

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
    with c2: st.image("emalatxana.png", width=180)
    
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    if not df.empty:
        user = df.iloc[0]
        if user['secret_token'] and user['secret_token'] != token: st.error("⛔ İcazəsiz Giriş!"); st.stop()

        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE", {"id": card_id})
        if not notifs.empty:
            for i, row in notifs.iterrows():
                st.info(f"📩 {row['message']}")
                run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        if not user['is_active']:
            st.warning("🎉 KARTI AKTİVLƏŞDİRİN")
            with st.form("act"):
                em = st.text_input("📧 Email")
                dob = st.date_input("🎂 Doğum Tarixi", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                
                # --- TAM HÜQUQİ MƏTN (BURA DÜZƏLDİLDİ) ---
                with st.expander("📜 İstifadəçi Razılaşmasını Oxu"):
                    st.markdown("""
                    **EMALATXANA COFFEE — İSTİFADƏÇİ RAZILAŞMASI**

                    **1. Şəxsi Məlumatların Məxfiliyi**
                    Qeydiyyat zamanı təqdim etdiyiniz **E-mail** və **Doğum Tarixi** məlumatları yalnız "Emalatxana Coffee" daxilində istifadə olunur. Bu məlumatlar vasitəsilə sizə endirim kuponları, ad günü hədiyyələri və elektron qəbzlər göndərilir. Məlumatlarınız heç bir halda üçüncü tərəflərlə paylaşılmır.

                    **2. Sadiqlik Proqramı (Ulduz Sistemi)**
                    Hər standart ölçülü kofe alışı sizə **1 ulduz** qazandırır. Balansınızda **9 ulduz** toplandıqda, sistem avtomatik olaraq növbəti (10-cu) kofeni sizə **ÖDƏNİŞSİZ (HƏDİYYƏ)** təklif edir.

                    **3. VIP Termos Klubu**
                    Əgər siz "VIP Termos Klubu" üzvüsünüzsə (öz termosunuzla yaxınlaşdıqda), kofe alışlarında sizə xüsusi endirim tətbiq olunur.

                    **4. Ad Günü və Xüsusi Kampaniyalar**
                    Ad günü münasibətilə göndərilən hədiyyəni (məsələn, pulsuz kofe) əldə etmək üçün, kassada **şəxsiyyət vəsiqənizi** təqdim etməyiniz mütləqdir. Şəxsiyyət vəsiqəsindəki doğum tarixi, sistemdə qeydiyyat zamanı daxil etdiyiniz tarixlə eyni olmalıdır. Sənəd təqdim edilmədikdə və ya tarixlər uyğun gəlmədikdə hədiyyə verilməyə bilər.

                    **5. Qaydaların Yenilənməsi və Razılıq**
                    Gələcəkdə qaydalara ediləcək dəyişikliklər barədə sizə E-mail vasitəsilə bildiriş göndəriləcək. Bildirişdən sonra etiraz etmədən istifadəyə davam etməyiniz, yeni şərtləri avtomatik qəbul etdiyiniz mənasına gəlir.

                    **6. İmtina**
                    Siz istənilən vaxt sistemdən çıxmaq və məlumatlarınızın bazadan tamamilə silinməsini tələb etmək hüququna maliksiniz.
                    """)
                
                agree = st.checkbox("Qaydaları oxudum və qəbul edirəm")
                if st.form_submit_button("Təsdiq"):
                    if not em: st.error("Email yazın")
                    elif not agree: st.error("Qaydaları qəbul etməlisiniz")
                    else:
                        run_action("UPDATE customers SET email=:e, birth_date=:b, is_active=TRUE WHERE card_id=:i", {"e":em, "b":dob.strftime("%Y-%m-%d"), "i":card_id})
                        st.balloons(); st.rerun()
            st.stop()

        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        st.markdown(f"<div class='inner-motivation'>{get_random_quote()}</div>", unsafe_allow_html=True)
        if user['type'] == 'thermos': st.markdown('<div class="vip-status-box">⭐ VIP TERMOS KLUBU</div>', unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:center; margin:0; color:#2E7D32'>BALANS: {user['stars']}/10</h2>", unsafe_allow_html=True)
        
        html = '<div class="coffee-grid-container">'
        for i in range(10):
            if i < 9: icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; cls = ""
            else: icon = "https://cdn-icons-png.flaticon.com/512/751/751621.png"; cls = "orange-gift" 
            if i < user['stars']: style = "opacity: 1;"
            else: style = "opacity: 0.2; filter: grayscale(100%);"
            if i == user['stars']: style = "opacity: 0.8; animation: pulse 1s infinite;"; cls += " pulse-anim"
            html += f'<img src="{icon}" class="coffee-icon {cls}" style="{style}">'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)
        
        rem = 9 - user['stars']
        if rem <= 0: st.markdown("<h3 style='text-align:center; color:#E65100 !important;'>🎉 TƏBRİKLƏR! 10-cu Kofe Bizdən!</h3>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='heartbeat-text'>❤️ Cəmi {rem} kofedən sonra qonağımızsan! ❤️</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        my_coupons = run_query("SELECT * FROM customer_coupons WHERE card_id = :id AND is_used = FALSE", {"id": card_id})
        if not my_coupons.empty:
            st.markdown(f"<div class='coupon-alert'>🎁 Sizin {len(my_coupons)} aktiv kuponunuz var! Kassada təqdim edin.</div>", unsafe_allow_html=True)

        st.markdown("<div class='feedback-box'>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align:center; margin:0; color:#2E7D32'>💌 Rəy Bildir</h4>", unsafe_allow_html=True)
        with st.form("feed"):
            s = st.feedback("stars")
            m = st.text_input("Fikriniz", placeholder="Necə idi?")
            if st.form_submit_button("Göndər"):
                if s is not None:
                    run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:i,:r,:m)", {"i":card_id, "r":s+1, "m":m})
                    st.success("Təşəkkürlər!")
                else: st.warning("Ulduz seçin")
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        qr_url = f"{APP_URL}/?id={card_id}&t={user['secret_token']}" if user['secret_token'] else f"{APP_URL}/?id={card_id}"
        st.download_button("📥 KARTI YÜKLƏ", generate_custom_qr(qr_url, card_id), f"{card_id}.png", "image/png", use_container_width=True)
    else: st.error("Kart tapılmadı")

# ========================
# === 2. POS & ADMIN ===
# ========================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,1,1]); 
        with c2: 
            st.image("emalatxana.png", width=150)
            st.markdown("<h3 style='text-align:center'>GİRİŞ</h3>", unsafe_allow_html=True)
            st.markdown("""<button class="js-button" onclick="window.location.reload();">🔄 Məcburi Yenilə</button>""", unsafe_allow_html=True)
            
            if 'login_attempts' not in st.session_state: st.session_state.login_attempts = 0
            if 'lockout_time' not in st.session_state: st.session_state.lockout_time = None

            if st.session_state.lockout_time:
                if time.time() < st.session_state.lockout_time:
                    wait_sec = int(st.session_state.lockout_time - time.time())
                    st.error(f"⚠️ Çox sayda uğursuz cəhd! {wait_sec} saniyə gözləyin."); st.stop()
                else: st.session_state.login_attempts = 0; st.session_state.lockout_time = None

            with st.form("login"):
                u = st.text_input("User"); p = st.text_input("Pass", type="password")
                if st.form_submit_button("GİRİŞ", use_container_width=True):
                    udf = run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(:u)", {"u":u})
                    if not udf.empty and verify_password(p, udf.iloc[0]['password']):
                        st.session_state.login_attempts = 0; st.session_state.lockout_time = None
                        st.session_state.logged_in = True; st.session_state.role = udf.iloc[0]['role']; st.session_state.user = u
                        st.rerun()
                    else:
                        st.session_state.login_attempts += 1
                        left = 5 - st.session_state.login_attempts
                        if left <= 0:
                            st.session_state.lockout_time = time.time() + 300; st.error("⛔ 5 dəqiqə bloklandınız."); st.rerun()
                        else: st.error(f"Şifrə səhvdir! Qalan: {left}")
    else:
        h1, h2, h3 = st.columns([2,6,1])
        with h1: 
            if st.button("🔴 Çıxış", key="out"): st.session_state.logged_in = False; st.rerun()
        with h3: st.markdown("""<button style="background:none; border:none; font-size:24px; cursor:pointer;" onclick="window.location.reload();">🔄</button>""", unsafe_allow_html=True)

        role = st.session_state.role
        
        def render_pos():
            left_col, right_col = st.columns([2, 1])
            with left_col:
                c_scan, c_info = st.columns([2, 2])
                with c_scan:
                    scan_val = st.text_input("Müştəri QR", key="ps")
                    if st.button("🔍 AXTAR", key="psb"):
                        if scan_val:
                            c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":scan_val})
                            if not c_df.empty: 
                                st.session_state.current_customer = c_df.iloc[0].to_dict()
                                st.session_state.active_coupon = None 
                                st.rerun()
                            else: st.error("Tapılmadı")
                with c_info:
                    curr = st.session_state.current_customer
                    if curr:
                        st.success(f"👤 {curr['card_id']} | ⭐ {curr['stars']}")
                        cps = run_query("SELECT * FROM customer_coupons WHERE card_id=:id AND is_used=FALSE", {"id": curr['card_id']})
                        if not cps.empty:
                            st.info(f"🎫 {len(cps)} Aktiv Kupon Var!")
                            cp_ops = {f"{r['coupon_type']} (ID:{r['id']})": r['id'] for _, r in cps.iterrows()}
                            sel_cp_label = st.selectbox("Kuponu tətbiq et:", ["Yox"] + list(cp_ops.keys()))
                            if sel_cp_label != "Yox": st.session_state.active_coupon = {"id": cp_ops[sel_cp_label], "type": sel_cp_label.split()[0]}
                            else: st.session_state.active_coupon = None
                        if st.button("❌ Ləğv", key="pcl"): st.session_state.current_customer = None; st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
                cat_col1, cat_col2, cat_col3 = st.columns(3)
                if cat_col1.button("Qəhvə", key="cat_coff", type="primary", use_container_width=True): st.session_state.pos_category = "Qəhvə"; st.rerun()
                if cat_col2.button("İçkilər", key="cat_drk", type="primary", use_container_width=True): st.session_state.pos_category = "İçkilər"; st.rerun()
                if cat_col3.button("Desert", key="cat_dst", type="primary", use_container_width=True): st.session_state.pos_category = "Desert"; st.rerun()
                
                menu_df = run_query("SELECT * FROM menu WHERE category=:c AND is_active=TRUE ORDER BY item_name", {"c": st.session_state.pos_category})
                grouped_items = {}
                for _, row in menu_df.iterrows():
                    name_parts = row['item_name'].split()
                    if name_parts[-1] in ['S', 'M', 'L', 'XL']:
                        base_name = " ".join(name_parts[:-1])
                        if base_name not in grouped_items: grouped_items[base_name] = []
                        grouped_items[base_name].append(row.to_dict())
                    else: grouped_items[row['item_name']] = [row.to_dict()]
                
                item_names = list(grouped_items.keys())
                cols = st.columns(3)
                for idx, name in enumerate(item_names):
                    variants = grouped_items[name]
                    with cols[idx % 3]:
                        if len(variants) > 1:
                            if st.button(f"{name}\n(Seçim)", key=f"g_{idx}", use_container_width=True): show_size_selector(name, variants)
                        else:
                            if st.button(f"{variants[0]['item_name']}\n{variants[0]['price']}₼", key=f"s_{variants[0]['id']}", use_container_width=True):
                                st.session_state.cart.append(variants[0]); st.rerun()

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
                    coupon_disc = 0
                    
                    if curr:
                        if curr['type'] == 'thermos': disc += sum([float(x['price']) for x in st.session_state.cart if x['is_coffee']]) * 0.2
                        if curr['stars'] >= 9: 
                            c_items = [x for x in st.session_state.cart if x['is_coffee']]
                            if c_items: disc += float(min(c_items, key=lambda x: float(x['price']))['price'])
                        
                        if st.session_state.active_coupon:
                            cp_type = st.session_state.active_coupon['type']
                            if cp_type == '50_percent': coupon_disc = total * 0.5
                            elif cp_type == 'birthday_gift': 
                                if st.session_state.cart: coupon_disc = float(min(st.session_state.cart, key=lambda x: float(x['price']))['price'])
                            elif cp_type == 'free_cookie':
                                cookie_items = [x for x in st.session_state.cart if x['category'] == 'Desert']
                                if cookie_items: coupon_disc = float(min(cookie_items, key=lambda x: float(x['price']))['price'])

                    final = max(0, total - disc - coupon_disc)
                    st.markdown(f"<div style='font-size:24px; font-weight:bold; text-align:right; color:#2E7D32'>YEKUN: {final:.2f} ₼</div>", unsafe_allow_html=True)
                    if disc > 0: st.caption(f"Sadiqlik Endirimi: -{disc:.2f}")
                    if coupon_disc > 0: st.caption(f"Kupon Endirimi: -{coupon_disc:.2f}")
                    
                    pay_method = st.radio("Ödəniş:", ["Nəğd (Cash)", "Kart (Card)"], horizontal=True, key="pm")
                    
                    if st.button("✅ TƏSDİQLƏ", type="primary", use_container_width=True, key="py"):
                        p_code = "Cash" if "Nəğd" in pay_method else "Card"
                        items_str = ", ".join([x['item_name'] for x in st.session_state.cart])
                        try:
                            with conn.session as s:
                                if curr:
                                    if curr['last_visit'] and (datetime.datetime.now() - curr['last_visit']) < datetime.timedelta(minutes=1):
                                        st.error("⚠️ Gözləyin! Rate Limit."); st.stop()
                                    ns = curr['stars']
                                    if coffs > 0:
                                        if curr['stars'] >= 9 and any(x['is_coffee'] for x in st.session_state.cart): ns = 0
                                        else: ns += 1
                                    s.execute(text("UPDATE customers SET stars=:s, last_visit=NOW() WHERE card_id=:id"), {"s":ns, "id":curr['card_id']})
                                    if st.session_state.active_coupon:
                                        s.execute(text("UPDATE customer_coupons SET is_used=TRUE WHERE id=:cid"), {"cid":st.session_state.active_coupon['id']})
                                s.execute(text("INSERT INTO sales (items, total, payment_method, created_at) VALUES (:i, :t, :p, NOW())"), {"i":items_str, "t":final, "p":p_code})
                                s.commit()
                            st.success("Uğurlu!"); st.session_state.cart = []; st.session_state.current_customer = None; st.session_state.active_coupon = None; time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Xəta: {e}")
                else: st.info("Səbət boşdur")

        if role == 'admin':
            tabs = st.tabs(["POS", "Analitika", "CRM", "Menyu", "Admin", "QR"])
            with tabs[0]: render_pos()
            with tabs[1]:
                st.markdown("### 📊 Aylıq Satış")
                today = datetime.date.today()
                sel_date = st.date_input("Ay Seçin", today)
                sel_month = sel_date.strftime("%Y-%m")
                sales = run_query("SELECT * FROM sales WHERE TO_CHAR(created_at, 'YYYY-MM') = :m ORDER BY created_at DESC", {"m": sel_month})
                if not sales.empty:
                    tot = sales['total'].sum()
                    cash = sales[sales['payment_method'] == 'Cash']['total'].sum()
                    card = sales[sales['payment_method'] == 'Card']['total'].sum()
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Ümumi", f"{tot:.2f}")
                    m2.metric("💵 Nağd", f"{cash:.2f}")
                    m3.metric("💳 Kart", f"{card:.2f}")
                    sales['day'] = pd.to_datetime(sales['created_at']).dt.day
                    daily = sales.groupby('day')['total'].sum()
                    st.bar_chart(daily)
                    with st.expander("Siyahı"): st.dataframe(sales)
                else: st.info("Satış yoxdur.")
            with tabs[2]:
                st.markdown("### 📧 CRM (Kupon & Hədiyyə)")
                with st.expander("🗑️ Müştəri Sil"):
                    all_customers = run_query("SELECT card_id, email FROM customers")
                    if not all_customers.empty:
                        options = [f"{row['card_id']} | {row['email'] if row['email'] else 'Email yoxdur'}" for _, row in all_customers.iterrows()]
                        selected_option = st.selectbox("Seçin:", options)
                        if st.button("Bu Müştərini Sil"):
                            confirm_delete(selected_option.split(" |")[0])
                    else: st.info("Boşdur.")
                st.divider()
                
                m_df = run_query("SELECT card_id, email, birth_date FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    m_df['50% Endirim'] = False; m_df['Ad Günü'] = False; m_df['Pulsuz Peceniya'] = False
                    ed = st.data_editor(m_df, hide_index=True, use_container_width=True)
                    if st.button("🚀 Seçilənləri Göndər", key="crm"):
                        cnt = 0
                        for i, r in ed.iterrows():
                            if r['50% Endirim']: 
                                if send_email(r['email'], "50% Endirim!", "Sizə özəl 50% endirim!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, '50% Endirim!')", {"id":r['card_id']})
                                    run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:id, '50_percent')", {"id":r['card_id']}); cnt+=1
                            if r['Ad Günü']: 
                                if send_email(r['email'], "Ad Gününüz Mübarək!", "Bir kofe bizdən hədiyyə!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, 'Ad Günü Hədiyyəsi!')", {"id":r['card_id']})
                                    run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:id, 'birthday_gift')", {"id":r['card_id']}); cnt+=1
                            if r['Pulsuz Peceniya']: 
                                if send_email(r['email'], "Şirin Hədiyyə!", "Kofe alana Peceniya bizdən!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, 'Pulsuz Peceniya!')", {"id":r['card_id']})
                                    run_action("INSERT INTO customer_coupons (card_id, coupon_type) VALUES (:id, 'free_cookie')", {"id":r['card_id']}); cnt+=1
                        st.success(f"{cnt} kampaniya aktivləşdirildi!")
                    with st.form("bulk"):
                        txt = st.text_area("Ümumi Bildiriş")
                        if st.form_submit_button("Göndər"):
                            ids = run_query("SELECT card_id FROM customers")
                            for _, r in ids.iterrows(): run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :m)", {"id":r['card_id'], "m":txt})
                            st.success("Göndərildi!")
                else: st.info("Müştəri yoxdur")
            with tabs[3]:
                with st.form("addm"):
                    c1,c2,c3 = st.columns(3); n=c1.text_input("Ad"); p=c2.number_input("Qiymət"); c=c3.selectbox("Kat", ["Qəhvə","İçkilər","Desert"]); cf=st.checkbox("Kofedir?")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category, is_coffee) VALUES (:n,:p,:c,:ic)", {"n":n,"p":p,"c":c,"ic":cf}); st.rerun()
                md = run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id")
                st.dataframe(md)
            with tabs[4]:
                st.markdown("### ⚙️ Admin Ayarları")
                if st.button("💾 BÜTÜN BAZANI YÜKLƏ (BACKUP)", type="primary"): confirm_backup()
                st.divider()
                with st.expander("🔑 Şifrə Dəyiş"):
                    all_us = run_query("SELECT username FROM users"); target = st.selectbox("Seç:", all_us['username'].tolist())
                    np = st.text_input("Yeni Şifrə", type="password", key="np_adm")
                    if st.button("Yenilə", key="upd"):
                        if len(np) < 8: st.error("Şifrə 8+ simvol olmalıdır!"); st.stop()
                        run_action("UPDATE users SET password=:p WHERE username=:u", {"p":hash_password(np), "u":target}); st.success("OK")
                with st.expander("➕ Yeni İşçi"):
                    un = st.text_input("User"); ps = st.text_input("Pass", type="password")
                    if st.button("Yarat", key="crt"):
                        if len(ps) < 8: st.error("Şifrə 8+ simvol olmalıdır!"); st.stop()
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u":un, "p":hash_password(ps)}); st.success("OK")
            with tabs[5]:
                cnt = st.number_input("Say", 1, 50); is_th = st.checkbox("Termos?")
                if st.button("Yarat", key="gen"):
                    ids = [str(random.randint(10000000, 99999999)) for _ in range(cnt)]
                    typ = "thermos" if is_th else "standard"
                    for i in ids: 
                        token = secrets.token_urlsafe(8)
                        run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :st)", {"i":i, "t":typ, "st":token})
                    if cnt == 1:
                        tkn = run_query("SELECT secret_token FROM customers WHERE card_id=:id", {"id":ids[0]}).iloc[0]['secret_token']
                        d = generate_custom_qr(f"{APP_URL}/?id={ids[0]}&t={tkn}", ids[0])
                        st.image(BytesIO(d), width=200); st.download_button("⬇️ PNG", d, f"{ids[0]}.png", "image/png")
                    else:
                        z = BytesIO()
                        with zipfile.ZipFile(z, "w") as zf:
                            for i in ids: 
                                tkn = run_query("SELECT secret_token FROM customers WHERE card_id=:id", {"id":i}).iloc[0]['secret_token']
                                zf.writestr(f"{i}.png", generate_custom_qr(f"{APP_URL}/?id={i}&t={tkn}", i))
                        st.download_button("📦 ZIP", z.getvalue(), "qr.zip", "application/zip")

        elif role == 'staff':
            render_pos()
