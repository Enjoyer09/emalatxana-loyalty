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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- EMAIL AYARLARI ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("MY_EMAIL") or "emalatkhanacoffee@gmail.com"
SENDER_PASSWORD = os.environ.get("MY_PASSWORD") or "Pezoxano@2025"

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(
    page_title="Emalatxana", 
    page_icon="☕", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- META TAGS ---
st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
    <meta name="theme-color" content="#ffffff">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url:
        st.error("⚠️ URL tapılmadı!")
        st.stop()
    
    db_url = db_url.strip().strip('"').strip("'")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    conn = st.connection("neon", type="sql", url=db_url)

except Exception as e:
    st.error(f"Bağlantı xətası: {e}")
    st.stop()

# --- SCHEMA MIGRATION ---
def ensure_schema():
    try:
        with conn.session as s:
            s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS email TEXT;"))
            s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS birth_date TEXT;"))
            s.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE;"))
            
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    card_id TEXT,
                    message TEXT,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            s.commit()
    except exc.OperationalError:
        st.warning("⚠️ Baza ilə əlaqə yenilənir...")
    except Exception:
        pass

ensure_schema()

# --- HELPER FUNCTIONS ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, stored_password):
    if not stored_password.startswith('$2b$'): return plain_password == stored_password
    return bcrypt.checkpw(plain_password.encode('utf-8'), stored_password.encode('utf-8'))

def run_query(query, params=None):
    try: return conn.query(query, params=params, ttl=0, show_spinner=False)
    except: return pd.DataFrame()

def run_action(query, params=None):
    try:
        with conn.session as s:
            s.execute(text(query), params if params else {})
            s.commit()
        return True
    except: return False

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except:
        return False

@st.cache_data(show_spinner=False, persist="disk")
def generate_custom_qr(data, center_text):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    font = ImageFont.load_default()
    try:
        font_size = int(height * 0.06)
        font = ImageFont.truetype("arial.ttf", font_size)
    except: pass

    try:
        bbox = draw.textbbox((0, 0), center_text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        text_w, text_h = draw.textsize(center_text, font=font)

    pad_x, pad_y = 10, 5
    box_w, box_h = text_w + (pad_x * 2), text_h + (pad_y * 2)
    x0, y0 = (width - box_w) // 2, (height - box_h) // 2
    x1, y1 = x0 + box_w, y0 + box_h

    draw.rectangle([x0, y0, x1, y1], fill="white", outline="black", width=1)
    draw.text((x0 + pad_x, y0 + pad_y - 2), center_text, fill="black", font=font)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def check_manual_input_status():
    df = run_query("SELECT value FROM settings WHERE key = 'manual_input'")
    if not df.empty: return df.iloc[0]['value'] == 'true'
    return True

# --- UI HELPERS ---
def show_logo():
    try: st.image("emalatxana.png", width=160) 
    except: pass

def get_motivational_msg(stars):
    if stars == 0: return "YENİ BİR BAŞLANĞIC! 🚀"
    if stars < 10: return "QƏHRƏMANLIĞA DOĞRU! 💪"
    return "BU GÜNÜN QƏHRƏMANI SƏNSƏN! 👑"

def get_remaining_text(stars):
    left = 10 - stars
    return f"🎁 <b>{left}</b> kofedən sonra qonağımızsan" if left > 0 else "🎉 TƏBRİKLƏR! BU KOFE BİZDƏN!"

def render_coffee_grid(stars):
    active = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
    inactive = "https://cdn-icons-png.flaticon.com/512/1174/1174444.png"
    html = '<div class="coffee-grid">'
    for row in range(2):
        for col in range(5):
            idx = (row * 5) + col + 1 
            src = active if idx <= stars else inactive
            anim = "pulse" if idx == stars else ""
            style = "" if idx <= stars else "opacity: 0.2; filter: grayscale(100%);"
            html += f'<img src="{src}" class="coffee-item {anim}" style="{style}">'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# --- SCAN PROSESİ ---
def process_scan():
    scan_code = st.session_state.scanner_input
    user = st.session_state.get('current_user', 'Unknown')
    
    if scan_code:
        df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": scan_code})
        if not df.empty:
            customer = df.iloc[0]
            curr_stars = int(customer['stars'])
            c_type = customer['type']
            is_first = customer['is_first_fill']
            
            new_stars = curr_stars
            msg = ""
            action = ""
            
            if c_type == 'thermos':
                if is_first:
                    msg, action = "🎁 TERMOS: İLK PULSUZ!", "Thermos First Free"
                    q1 = "UPDATE customers SET is_first_fill = FALSE, stars = stars + 1, last_visit = NOW() WHERE card_id = :id"
                    p1 = {"id": scan_code}
                else:
                    msg, action = "🏷️ TERMOS: 20% ENDİRİM!", "Thermos Discount 20%"
                    new_stars += 1
                    if new_stars >= 10: new_stars, msg, action = 0, "🎁 TERMOS: 10-cu KOFE PULSUZ!", "Free Coffee"
                    q1 = "UPDATE customers SET stars = :stars, last_visit = NOW() WHERE card_id = :id"
                    p1 = {"stars": new_stars, "id": scan_code}
            else:
                new_stars += 1
                action = "Star Added"
                if new_stars >= 10: new_stars, msg, action = 0, "🎁 PULSUZ KOFE!", "Free Coffee"
                else: msg = f"✅ Əlavə olundu. (Cəmi: {new_stars})"
                q1 = "UPDATE customers SET stars = :stars, last_visit = NOW() WHERE card_id = :id"
                p1 = {"stars": new_stars, "id": scan_code}

            try:
                with conn.session as s:
                    s.execute(text(q1), p1)
                    s.execute(text("INSERT INTO logs (staff_name, card_id, action_type) VALUES (:staff, :card, :action)"),
                              {"staff": user, "card": scan_code, "action": action})
                    s.commit()
                st.session_state['last_result'] = {"msg": msg, "type": "success" if "PULSUZ" not in msg else "error"}
            except Exception as e: st.error(f"Xəta: {e}")
        else: st.error("Kart tapılmadı!")
    st.session_state.scanner_input = ""

# --- CSS STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500;700&display=swap');
    
    header[data-testid="stHeader"], footer, #MainMenu, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; }
    
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; letter-spacing: 1px; text-transform: uppercase; }
    p, div, button, input, li, span { font-family: 'Oswald', sans-serif; }
    
    /* DIGITAL CARD */
    .digital-card {
        background: linear-gradient(145deg, #ffffff, #f9f9f9);
        border-radius: 20px; padding: 20px 10px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08);
        margin-bottom: 15px; border: 1px solid #fff;
    }
    
    .coffee-grid { display: flex; justify-content: center; gap: 12px; margin: 15px 0; flex-wrap: wrap; }
    .coffee-item { width: 16%; max-width: 50px; transition: all 0.3s; }
    .coffee-item.pulse { animation: pulse 2s infinite; transform: scale(1.1); }
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.15); } 100% { transform: scale(1); } }
    
    .counter-text { text-align: center; font-size: 18px; font-weight: 500; color: #d32f2f; margin-top: 5px; }
    .menu-item { background: white; border-bottom: 1px solid #eee; padding: 12px; margin-bottom: 5px; border-radius: 8px; }
    
    /* NOTIFICATIONS & ACTIVATION */
    .notification-box {
        background-color: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 10px; margin-bottom: 10px; border-radius: 5px;
        font-size: 14px; color: #0d47a1;
    }
    .activation-box {
        background-color: #fff3e0; border: 2px solid #ff9800;
        padding: 20px; border-radius: 15px; text-align: center;
        margin-bottom: 20px;
    }
    
    /* ULDUZLAR */
    div[data-testid="stFeedback"] {
        width: 100% !important; display: flex !important; justify-content: space-between !important; padding: 10px 15px !important;
    }
    div[data-testid="stFeedback"] > div { display: flex !important; justify-content: space-between !important; width: 100% !important; }
    div[data-testid="stFeedback"] button { flex: 1 !important; transform: scale(2.2); margin: 0 5px !important; }
    div[data-testid="stFeedback"] svg { fill: #FF9800 !important; color: #FF9800 !important; stroke: #FF9800 !important; }
    
    /* BUTTONS */
    div.stDownloadButton > button, button[kind="primary"] {
        width: 100%; border-radius: 12px; height: 50px; font-size: 18px !important;
        background-color: #2e7d32 !important; color: white !important; border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* REFRESH BUTTON STYLE */
    .refresh-btn {
        margin-top: 10px;
    }
    
    .metric-card {
        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 12px; text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #2e7d32; }
    .selected-qr-box { border: 2px solid #2e7d32; padding: 15px; border-radius: 10px; background-color: #f1f8e9; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- MAIN LOGIC ---
query_params = st.query_params

# ================================================
# === 1. MÜŞTƏRİ GÖRÜNÜŞÜ (ACTIVATION & LOYALTY) ===
# ================================================
if "id" in query_params:
    card_id = query_params["id"]
    
    # --- HEADER ---
    head1, head2, head3 = st.columns([1,3,1])
    with head2: show_logo()
    
    # Bildirişləri yoxla (Əgər aktivdirsə)
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    
    if not df.empty:
        user_data = df.iloc[0]
        email = user_data.get('email')
        is_active = user_data.get('is_active')
        
        # --- AKTİVASİYA ---
        if not is_active or not email:
            st.markdown("""
                <div class="activation-box">
                    <h3>🎉 KARTI AKTİVLƏŞDİRİN</h3>
                    <p>Kampaniyalardan və hədiyyələrdən yararlanmaq üçün zəhmət olmasa məlumatları doldurun.</p>
                </div>
            """, unsafe_allow_html=True)
            
            with st.form("activation_form"):
                user_email = st.text_input("📧 Email ünvanınız")
                user_dob = st.date_input("🎂 Doğum tarixiniz", min_value=datetime.date(1950, 1, 1))
                
                if st.form_submit_button("AKTİVLƏŞDİR"):
                    if user_email:
                        dob_str = user_dob.strftime("%Y-%m-%d")
                        run_action("UPDATE customers SET email = :em, birth_date = :bd, is_active = TRUE WHERE card_id = :id", 
                                  {"em": user_email, "bd": dob_str, "id": card_id})
                        st.success("✅ Kartınız uğurla aktivləşdirildi!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Zəhmət olmasa email daxil edin.")
            st.stop()

        # --- LOYALTY ---
        notifs = run_query("SELECT * FROM notifications WHERE card_id = :id AND is_read = FALSE ORDER BY created_at DESC", {"id": card_id})
        with head3:
            if not notifs.empty:
                st.markdown(f"<div style='text-align:right; font-size:24px;'>🔔<span style='color:red; font-size:14px; vertical-align:top;'>{len(notifs)}</span></div>", unsafe_allow_html=True)
        
        if not notifs.empty:
            for i, row in notifs.iterrows():
                st.markdown(f"<div class='notification-box'>📩 <b>YENİ MESAJ:</b> {row['message']}</div>", unsafe_allow_html=True)
                run_action("UPDATE notifications SET is_read = TRUE WHERE id = :nid", {"nid": row['id']})

        stars = int(user_data['stars'])
        cust_type = user_data['type']

        st.markdown('<div class="digital-card">', unsafe_allow_html=True)
        if cust_type == 'thermos': st.info("⭐ VIP TERMOS KLUBU")
        
        st.markdown(f"<h3 style='text-align: center; color: #333; margin:0;'>KARTINIZ: {stars}/10</h3>", unsafe_allow_html=True)
        render_coffee_grid(stars)
        st.markdown(f"<div class='counter-text'>{get_remaining_text(stars)}</div>", unsafe_allow_html=True)
        if cust_type != 'thermos': st.markdown(f"<p style='text-align:center; color:gray; font-size:14px; margin-top:5px;'>{get_motivational_msg(stars)}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("📋 MENYUYA BAX", expanded=False):
            menu_df = run_query("SELECT * FROM menu WHERE is_active = TRUE ORDER BY id")
            if not menu_df.empty:
                for i, r in menu_df.iterrows():
                    st.markdown(f"<div class='menu-item'><div style='display:flex;justify-content:space-between;font-weight:bold;font-size:16px;'><span>{r['item_name']}</span><span style='color:#2e7d32;'>{r['price']}</span></div><div style='font-size:12px;color:gray;'>{r['category']}</div></div>", unsafe_allow_html=True)
            else: st.caption("Boşdur.")

        st.markdown("### ⭐ BİZİ QİYMƏTLƏNDİR")
        if 'submitted_reviews' not in st.session_state: st.session_state['submitted_reviews'] = []
        
        if card_id in st.session_state['submitted_reviews']:
            st.success("✅ Rəyiniz qeydə alındı!")
            st.feedback("stars", disabled=True, key="ds")
            st.button("Göndərildi", disabled=True)
        else:
            stars_val = st.feedback("stars")
            msg_val = st.text_area("Fikirləriniz:", placeholder="Xidmətimizi necə qiymətləndirirsiniz?")
            if st.button("Rəyi Göndər", type="primary"):
                if stars_val is not None:
                    run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:id, :rat, :msg)", 
                              {"id": card_id, "rat": stars_val + 1, "msg": msg_val})
                    st.session_state['submitted_reviews'].append(card_id)
                    st.rerun()
                else: st.toast("⚠️ Zəhmət olmasa ulduz seçin!")

        st.markdown("---")
        lnk = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
        st.download_button("📥 KARTI YÜKLƏ (Offline Mode)", data=generate_custom_qr(lnk, card_id), file_name=f"card_{card_id}.png", mime="image/png", use_container_width=True)
        
        # --- REFRESH BUTTON FOR CUSTOMER ---
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Səhifəni Yenilə", type="secondary", use_container_width=True):
            st.rerun()
        
    else: st.error("Kart tapılmadı.")

else:
    # --- ADMIN LOGIN ---
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,2,1])
        with c2: show_logo()
        st.markdown("<h3 style='text-align:center'>SİSTEMƏ GİRİŞ</h3>", unsafe_allow_html=True)
        
        # Giriş səhifəsində də yenilə düyməsi
        if st.button("🔄 Yenilə", key="refresh_login"): st.rerun()
        
        with st.form("login"):
            u = st.text_input("İstifadəçi")
            p = st.text_input("Şifrə", type="password")
            if st.form_submit_button("DAXİL OL", use_container_width=True):
                udf = run_query("SELECT * FROM users WHERE LOWER(username) = LOWER(:u)", {"u": u})
                if not udf.empty:
                    if verify_password(p, udf.iloc[0]['password']):
                        st.session_state.logged_in = True
                        st.session_state.current_user = u
                        st.session_state.role = udf.iloc[0]['role']
                        st.rerun()
                    else: st.error("Yanlış şifrə")
                else: st.error("İstifadəçi yoxdur")
    else:
        role = st.session_state.role
        user = st.session_state.current_user
        c1, c2, c3 = st.columns([2,3,1]) # Logo və Refresh üçün yer ayırırıq
        
        with c1:
            st.write(f"👤 **{user}**")
            if st.button("Çıxış"): st.session_state.logged_in = False; st.rerun()
        with c2: show_logo()
        with c3:
            # --- ADMIN REFRESH BUTTON ---
            if st.button("🔄", key="admin_refresh", help="Sistemi Yenilə"): st.rerun()

        if role == 'admin':
            tabs = st.tabs(["📠 Terminal", "📧 Marketinq", "📊 Analitika", "📋 Menyu", "💬 Rəylər", "⚙️ Ayarlar", "🖨️ QR"])
            
            with tabs[0]: 
                st.markdown("### 📠 Skaner")
                if not check_manual_input_status(): st.caption("🔒 *Manual giriş bağlıdır*")
                st.text_input("Barkod:", key="scanner_input", on_change=process_scan)
                if 'last_result' in st.session_state:
                    r = st.session_state['last_result']
                    if r['type'] == 'success': st.success(r['msg'])
                    else: st.error(r['msg'])

            with tabs[1]:
                st.markdown("### 📧 Müştəri CRM")
                m_df = run_query("SELECT card_id, email, birth_date, stars FROM customers WHERE email IS NOT NULL")
                if not m_df.empty:
                    st.info(f"Cəmi {len(m_df)} aktiv müştəri.")
                    m_df['50% Endirim'], m_df['Ad Günü Hədiyyəsi'] = False, False
                    edited_df = st.data_editor(
                        m_df,
                        column_config={
                            "50% Endirim": st.column_config.CheckboxColumn("50% Göndər", default=False),
                            "Ad Günü Hədiyyəsi": st.column_config.CheckboxColumn("🎁 Ad Günü", default=False),
                            "card_id": "Kart ID", "email": "Email", "birth_date": "Doğum Tarixi"
                        },
                        disabled=["card_id", "email", "birth_date", "stars"],
                        hide_index=True, use_container_width=True
                    )
                    
                    if st.button("🚀 SEÇİLƏNLƏRƏ GÖNDƏR", type="primary"):
                        c50, cb = 0, 0
                        prog = st.progress(0)
                        for i, row in edited_df.iterrows():
                            if row['50% Endirim']:
                                if send_email(row['email'], "🎉 Emalatxana: 50% ENDİRİM!", f"Kart ID: {row['card_id']}\nSizə özəl 50% endirim!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :msg)", {"id": row['card_id'], "msg": "50% Endirim kuponu göndərildi!"})
                                    c50 += 1
                            if row['Ad Günü Hədiyyəsi']:
                                if send_email(row['email'], "🎂 Ad Gününüz Mübarək!", f"Kart ID: {row['card_id']}\nBir kofe bizdən hədiyyə!"):
                                    run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :msg)", {"id": row['card_id'], "msg": "Ad günü hədiyyəsi göndərildi!"})
                                    cb += 1
                            prog.progress((i + 1) / len(edited_df))
                        st.success(f"Nəticə: {c50} Endirim, {cb} Ad Günü mesajı göndərildi!")
                else: st.warning("Aktiv müştəri yoxdur.")

                st.divider()
                st.markdown("#### 🔔 Ümumi Bildiriş")
                with st.form("push_notify"):
                    p_msg = st.text_area("Mesaj:")
                    if st.form_submit_button("Hamıya Göndər"):
                        all_users = run_query("SELECT card_id FROM customers")
                        for _, r in all_users.iterrows():
                            run_action("INSERT INTO notifications (card_id, message) VALUES (:id, :msg)", {"id": r['card_id'], "msg": p_msg})
                        st.success("Göndərildi!")

            with tabs[2]:
                st.markdown("### 📊 Biznes")
                df = run_query("SELECT COUNT(*) FILTER (WHERE action_type = 'Star Added') as paid, COUNT(*) FILTER (WHERE action_type = 'Free Coffee') as free FROM logs")
                if not df.empty:
                    c1, c2 = st.columns(2)
                    c1.markdown(f"<div class='metric-card'><div class='metric-value'>{df.iloc[0]['paid']}</div><div>☕ Satış</div></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='metric-card'><div class='metric-value'>{df.iloc[0]['free']}</div><div>🎁 Hədiyyə</div></div>", unsafe_allow_html=True)
                st.divider()
                st.markdown("##### ⏰ Pik Saatlar")
                hdf = run_query("SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count FROM logs GROUP BY hour ORDER BY hour")
                if not hdf.empty: st.bar_chart(hdf.set_index('hour'))

            with tabs[3]:
                with st.form("add_menu"):
                    c1, c2, c3 = st.columns(3)
                    n = c1.text_input("Ad")
                    p = c2.text_input("Qiymət")
                    c = c3.text_input("Kat")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category) VALUES (:n, :p, :c)", {"n":n, "p":p, "c":c})
                        st.rerun()
                mdf = run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id")
                for i, r in mdf.iterrows():
                    c1, c2 = st.columns([4,1])
                    c1.write(f"{r['item_name']} - {r['price']}")
                    if c2.button("Sil", key=f"d{r['id']}"):
                        run_action("DELETE FROM menu WHERE id=:id", {"id":r['id']})
                        st.rerun()

            with tabs[4]:
                rdf = run_query("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 20")
                for i, r in rdf.iterrows(): st.info(f"{r['rating']}⭐ - {r['message']}")

            with tabs[5]:
                st.markdown("### ⚙️ Ayarlar")
                cs = check_manual_input_status()
                c1, c2 = st.columns([1,3])
                if c1.button("DƏYİŞ", type="primary"):
                    run_action("INSERT INTO settings (key, value) VALUES ('manual_input', :v) ON CONFLICT (key) DO UPDATE SET value = :v", {"v": 'false' if cs else 'true'})
                    st.rerun()
                c2.write(f"Manual Giriş: **{'AÇIQ ✅' if cs else 'BAĞLI ⛔'}**")
                
                with st.expander("🔑 Şifrəmi Dəyiş"):
                    np = st.text_input("Yeni Şifrə", type="password", key="upd_own_p")
                    if st.button("Yenilə", key="upd_own"):
                        run_action("UPDATE users SET password = :p WHERE username = :u", {"p": hash_password(np), "u": user})
                        st.success("OK!")
                
                with st.expander("👥 İşçi Şifrəsini Yenilə"):
                    staff_users = run_query("SELECT username FROM users WHERE role != 'admin'")
                    if not staff_users.empty:
                        target_user = st.selectbox("İşçi Seç", staff_users['username'].tolist())
                        new_staff_pass = st.text_input("Yeni Şifrə", type="password", key="staff_pass_reset")
                        if st.button("Yenilə", key="upd_staff"):
                            run_action("UPDATE users SET password = :p WHERE username = :u", {"p": hash_password(new_staff_pass), "u": target_user})
                            st.success(f"{target_user} şifrəsi yeniləndi!")
                    else: st.info("İşçi yoxdur.")

                with st.expander("➕ Yeni İşçi"):
                    nn, npp = st.text_input("Ad"), st.text_input("Şifrə", type="password", key="newst")
                    if st.button("Yarat"):
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u":nn, "p":hash_password(npp)})
                        st.success("OK!")

            with tabs[6]:
                with st.form("qr_gen"):
                    cnt = st.number_input("Say", 1, 50, 1)
                    is_th = st.checkbox("Termos")
                    if st.form_submit_button("Yarat"):
                        ids, typ, ff = [], "thermos" if is_th else "standard", True if is_th else False
                        for _ in range(cnt):
                            rid = str(random.randint(10000000, 99999999))
                            run_action("INSERT INTO customers (card_id, stars, type, is_first_fill) VALUES (:id, 0, :t, :f)", {"id":rid, "t":typ, "f":ff})
                            ids.append(rid)
                        st.session_state['new_qrs'], st.session_state['last_qr_type'] = ids, typ
                        st.rerun()
                
                if 'new_qrs' in st.session_state:
                    ids = st.session_state['new_qrs']
                    st.success(f"{len(ids)} kart yaradıldı!")
                    if len(ids) == 1:
                        lnk = f"https://emalatxana-loyalty-production.up.railway.app/?id={ids[0]}"
                        d = generate_custom_qr(lnk, ids[0])
                        st.image(BytesIO(d), width=250)
                        st.download_button("⬇️ Yüklə", d, f"{ids[0]}.png", "image/png", type="primary")
                    else:
                        zb = BytesIO()
                        with zipfile.ZipFile(zb, "w") as zf:
                            for i in ids:
                                l = f"https://emalatxana-loyalty-production.up.railway.app/?id={i}"
                                zf.writestr(f"{i}.png", generate_custom_qr(l, i))
                        st.download_button("📦 ZIP Yüklə", zb.getvalue(), "qrs.zip", "application/zip", type="primary")
                    if st.button("Bağla"): del st.session_state['new_qrs']; st.rerun()
                
                st.divider()
                if 'view_qr_id' in st.session_state:
                    vid = st.session_state['view_qr_id']
                    st.markdown(f"<div class='selected-qr-box'><h3>SEÇİLMİŞ: {vid}</h3></div>", unsafe_allow_html=True)
                    l = f"https://emalatxana-loyalty-production.up.railway.app/?id={vid}"
                    d = generate_custom_qr(l, vid)
                    st.image(BytesIO(d), width=250)
                    c1, c2 = st.columns(2)
                    if c1.button("❌"): del st.session_state['view_qr_id']; st.rerun()
                    c2.download_button("📥", d, f"{vid}.png", "image/png")
                
                with st.expander("📂 Arxiv"):
                    sq = st.text_input("Axtar", placeholder="ID...")
                    sql = "SELECT * FROM customers" + (" WHERE card_id LIKE :s" if sq else "") + " ORDER BY last_visit DESC LIMIT 50"
                    adf = run_query(sql, {"s": f"%{sq}%"} if sq else {})
                    for i, r in adf.iterrows():
                        c1, c2, c3 = st.columns([2,1,1])
                        c1.write(f"**{r['card_id']}**")
                        c2.write(f"⭐{r['stars']}")
                        if c3.button("👁️", key=f"v{r['card_id']}"): st.session_state['view_qr_id'] = r['card_id']; st.rerun()

        else:
            st.markdown("### 📠 Terminal")
            if check_manual_input_status(): st.text_input("Barkod:", key="scanner_input", on_change=process_scan)
            else: st.warning("⛔ Manual giriş bağlıdır.")
            if 'last_result' in st.session_state:
                r = st.session_state['last_result']
                if r['type'] == 'success': st.success(r['msg'])
                else: st.error(r['msg'])
