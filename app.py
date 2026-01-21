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
import bcrypt  # YENİ: Şifrələmə üçün

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana", page_icon="☕", layout="centered")

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

# --- ŞİFRƏLƏMƏ FUNKSİYALARI (BCRYPT) ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, stored_password):
    # Əgər şifrə köhnədirsə (bcrypt deyil), birbaşa yoxla
    if not stored_password.startswith('$2b$'):
        return plain_password == stored_password
    # Əgər yenidirsə, bcrypt ilə yoxla
    return bcrypt.checkpw(plain_password.encode('utf-8'), stored_password.encode('utf-8'))

# --- QR CACHE (PERFORMANS ÜÇÜN) ---
@st.cache_data(show_spinner=False) 
def generate_custom_qr(data, center_text):
    # QR CPU-nu çox yorur, ona görə cache edirik. Eyni ID üçün təkrar hesablamır.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    draw = ImageDraw.Draw(img)
    width, height = img.size

    font = ImageFont.load_default()
    try:
        possible_fonts = ["arial.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
        for f in possible_fonts:
            try:
                font_size = int(height * 0.06) 
                font = ImageFont.truetype(f, font_size)
                break
            except:
                continue
    except:
        pass

    # Mətn ölçüləri
    try:
        bbox = draw.textbbox((0, 0), center_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except:
        text_w, text_h = draw.textsize(center_text, font=font)

    pad_x = 10
    pad_y = 5
    box_w = text_w + (pad_x * 2)
    box_h = text_h + (pad_y * 2)
    x0 = (width - box_w) // 2
    y0 = (height - box_h) // 2
    x1 = x0 + box_w
    y1 = y0 + box_h

    draw.rectangle([x0, y0, x1, y1], fill="white", outline="white")
    draw.rectangle([x0, y0, x1, y1], outline="black", width=1)

    txt_x = x0 + pad_x
    txt_y = y0 + pad_y - 2
    draw.text((txt_x, txt_y), center_text, fill="black", font=font)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- SQL HELPERS ---
def run_query(query, params=None):
    try:
        return conn.query(query, params=params, ttl=0, show_spinner=False)
    except Exception as e:
        st.error(f"SQL Xətası: {e}")
        return pd.DataFrame()

def run_action(query, params=None):
    try:
        with conn.session as s:
            s.execute(text(query), params if params else {})
            s.commit()
        return True
    except Exception as e:
        st.error(f"Action Xətası: {e}")
        return False

def check_manual_input_status():
    df = run_query("SELECT value FROM settings WHERE key = 'manual_input'")
    if not df.empty:
        return df.iloc[0]['value'] == 'true'
    return True

# --- HELPER UI ---
def show_logo():
    try: st.image("emalatxana.png", width=180) 
    except: pass

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
            style = "" if idx <= stars else "opacity: 0.25;"
            html += f'<img src="{src}" class="coffee-item" style="{style}">'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# --- SCAN PROSESİ (ATOMIC TRANSACTION) ---
def process_scan():
    scan_code = st.session_state.scanner_input
    user = st.session_state.get('current_user', 'Unknown')
    
    if scan_code:
        # 1. Oxumaq (Read)
        df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": scan_code})
        
        if not df.empty:
            customer = df.iloc[0]
            current_stars = int(customer['stars'])
            cust_type = customer['type']
            is_first = customer['is_first_fill']
            
            # Logic
            new_stars = current_stars
            msg = ""
            action_type = ""
            
            if cust_type == 'thermos':
                if is_first:
                    msg = "🎁 TERMOS: İLK DOLUM PULSUZ!"
                    action_type = "Thermos First Free"
                    # Update queries list
                    q1 = "UPDATE customers SET is_first_fill = FALSE, stars = stars + 1, last_visit = NOW() WHERE card_id = :id"
                    p1 = {"id": scan_code}
                else:
                    msg = "🏷️ TERMOS: 20% ENDİRİM!"
                    action_type = "Thermos Discount 20%"
                    new_stars += 1
                    if new_stars >= 10:
                        new_stars = 0
                        msg = "🎁 TERMOS: 10-cu KOFE PULSUZ!"
                        action_type = "Free Coffee"
                    q1 = "UPDATE customers SET stars = :stars, last_visit = NOW() WHERE card_id = :id"
                    p1 = {"stars": new_stars, "id": scan_code}
            else: # Standard
                new_stars += 1
                action_type = "Star Added"
                if new_stars >= 10:
                    new_stars = 0
                    msg = "🎁 PULSUZ KOFE!"
                    action_type = "Free Coffee"
                else:
                    msg = f"✅ Əlavə olundu. (Cəmi: {new_stars})"
                q1 = "UPDATE customers SET stars = :stars, last_visit = NOW() WHERE card_id = :id"
                p1 = {"stars": new_stars, "id": scan_code}

            # --- ATOMIC TRANSACTION (Biri olmazsa, heç biri olmur) ---
            try:
                with conn.session as s:
                    # 1. Update Customer
                    s.execute(text(q1), p1)
                    # 2. Insert Log
                    s.execute(text("INSERT INTO logs (staff_name, card_id, action_type) VALUES (:staff, :card, :action)"),
                              {"staff": user, "card": scan_code, "action": action_type})
                    s.commit()
                
                st.session_state['last_result'] = {"msg": msg, "type": "success" if "PULSUZ" not in msg else "error"}
            
            except Exception as e:
                st.error(f"Sistem xətası (Transaction Failed): {e}")
        
        else:
            st.error("Kart tapılmadı!")
            
    st.session_state.scanner_input = ""

# --- CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');
    header[data-testid="stHeader"], footer, #MainMenu { display: none !important; }
    .block-container { padding-top: 2rem !important; }
    
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; letter-spacing: 1px; }
    p, div, button, input { font-family: 'Oswald', sans-serif; }
    
    .coffee-grid { display: flex; justify-content: center; gap: 8px; margin: 10px 0; flex-wrap: wrap; }
    .coffee-item { width: 45px; transition: transform 0.2s; }
    
    .counter-text { text-align: center; font-size: 20px; font-weight: 500; color: #d32f2f; }
    .menu-item { border: 1px solid #eee; padding: 10px; border-radius: 8px; margin-bottom: 10px; background: #f9f9f9; }
    .stTextInput input { text-align: center; font-size: 18px; }
    
    /* ULDUZLAR */
    div[data-testid="stFeedback"] button svg {
        width: 40px !important; height: 40px !important;
        fill: #FF9800 !important; color: #FF9800 !important;
    }
    div[data-testid="stFeedback"] { justify-content: center !important; gap: 10px !important; }
    
    /* DASHBOARD CARDS */
    .metric-card {
        background-color: #f8f9fa; border: 1px solid #ddd;
        padding: 15px; border-radius: 10px; text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #2e7d32; }
    .metric-label { font-size: 14px; color: #666; }
    </style>
    """, unsafe_allow_html=True)

# --- MAIN APP ---
query_params = st.query_params

if "id" in query_params:
    # --- MÜŞTƏRİ EKRANI ---
    card_id = query_params["id"]
    show_logo()
    
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    
    if not df.empty:
        user_data = df.iloc[0]
        stars = int(user_data['stars'])
        cust_type = user_data['type']

        if cust_type == 'thermos':
            st.warning("⭐ VIP TERMOS KLUBU: 20% ENDİRİM ⭐")
        
        st.markdown(f"<h3 style='text-align: center; color: #2e7d32;'>KARTINIZ: {stars}/10</h3>", unsafe_allow_html=True)
        render_coffee_grid(stars)
        st.markdown(f"<div class='counter-text'>{get_remaining_text(stars)}</div>", unsafe_allow_html=True)

        st.markdown("<br><h3 style='color: #2e7d32;'>📋 MENYU</h3>", unsafe_allow_html=True)
        menu_df = run_query("SELECT * FROM menu WHERE is_active = TRUE ORDER BY id")
        for index, item in menu_df.iterrows():
            st.markdown(f"<div class='menu-item'><b>{item['item_name']}</b> <span style='float:right; color:#2e7d32'>{item['price']}</span><br><small style='color:gray'>{item['category']}</small></div>", unsafe_allow_html=True)

        st.markdown("<br><h3 style='color: #2e7d32;'>⭐ BİZİ QİYMƏTLƏNDİR</h3>", unsafe_allow_html=True)
        
        if 'submitted_reviews' not in st.session_state: st.session_state['submitted_reviews'] = []
        
        if card_id in st.session_state['submitted_reviews']:
            st.success("✅ Rəyiniz qeydə alındı!")
        else:
            stars_val = st.feedback("stars")
            msg_val = st.text_area("Rəyiniz:")
            if st.button("Rəyi Göndər", type="primary"):
                if stars_val is not None:
                    run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:id, :rat, :msg)", 
                              {"id": card_id, "rat": stars_val + 1, "msg": msg_val})
                    st.session_state['submitted_reviews'].append(card_id)
                    st.rerun()
                else:
                    st.warning("Ulduz seçin!")

        st.divider()
        card_link = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
        st.download_button("📥 Kartı Yüklə", data=generate_custom_qr(card_link, card_id), file_name=f"card_{card_id}.png", mime="image/png", use_container_width=True)
    else:
        st.error("Kart tapılmadı.")

else:
    # --- ADMIN/STAFF EKRANI ---
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_logo()
        st.markdown("<h3 style='text-align:center'>GİRİŞ</h3>", unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("İstifadəçi")
            p = st.text_input("Şifrə", type="password")
            if st.form_submit_button("Daxil Ol", use_container_width=True):
                udf = run_query("SELECT * FROM users WHERE username = :u", {"u": u})
                if not udf.empty:
                    stored_pass = udf.iloc[0]['password']
                    # Şifrəni yoxlayırıq (bcrypt və ya plain)
                    if verify_password(p, stored_pass):
                        st.session_state.logged_in = True
                        st.session_state.current_user = u
                        st.session_state.role = udf.iloc[0]['role']
                        st.rerun()
                    else:
                        st.error("Yanlış şifrə")
                else:
                    st.error("İstifadəçi yoxdur")
    else:
        role = st.session_state.role
        user = st.session_state.current_user
        
        c1, c2 = st.columns([3,1])
        c1.write(f"👤 **{user}** ({role})")
        if c2.button("Çıxış"): st.session_state.logged_in = False; st.rerun()

        if role == 'admin':
            tabs = st.tabs(["📠 Terminal", "📊 Biznes Analizi", "📋 Menyu", "💬 Rəylər", "👥 İdarəetmə", "🖨️ QR"])
            
            with tabs[0]: # TERMINAL
                st.markdown("### 📠 Skaner")
                allowed = check_manual_input_status()
                if not allowed: st.caption("🔒 *Manual giriş bağlıdır*")
                st.text_input("Barkod:", key="scanner_input", on_change=process_scan)
                if 'last_result' in st.session_state:
                    res = st.session_state['last_result']
                    if res['type'] == 'success': st.success(res['msg'])
                    else: st.error(res['msg'])

            with tabs[1]: # ANALITIKA (YENİ)
                st.markdown("### 📊 Biznes Göstəriciləri")
                
                # 1. Conversion Funnel (Satış vs Hədiyyə)
                c_df = run_query("""
                    SELECT 
                        COUNT(*) FILTER (WHERE action_type = 'Star Added') as paid,
                        COUNT(*) FILTER (WHERE action_type = 'Free Coffee') as free
                    FROM logs
                """)
                if not c_df.empty:
                    c1, c2 = st.columns(2)
                    c1.markdown(f"<div class='metric-card'><div class='metric-value'>{c_df.iloc[0]['paid']}</div><div class='metric-label'>☕ Satılan Kofe</div></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='metric-card'><div class='metric-value'>{c_df.iloc[0]['free']}</div><div class='metric-label'>🎁 Hədiyyə Kofe</div></div>", unsafe_allow_html=True)
                
                st.divider()
                
                # 2. Peak Hours (Ən aktiv saatlar)
                st.markdown("##### ⏰ Ən Aktiv Saatlar")
                h_df = run_query("""
                    SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count 
                    FROM logs GROUP BY hour ORDER BY hour
                """)
                if not h_df.empty:
                    st.bar_chart(h_df.set_index('hour'))

                # 3. Staff Efficiency
                st.markdown("##### 🏆 İşçi Performansı")
                s_df = run_query("""
                    SELECT staff_name, COUNT(*) as ops FROM logs GROUP BY staff_name ORDER BY ops DESC
                """)
                if not s_df.empty:
                    st.dataframe(s_df, use_container_width=True)

                # 4. Loyal Customers
                with st.expander("👑 Top 10 Loyal Müştəri"):
                    l_df = run_query("SELECT card_id, COUNT(*) as visits FROM logs GROUP BY card_id ORDER BY visits DESC LIMIT 10")
                    st.table(l_df)

            with tabs[2]: # MENYU
                with st.form("add_menu"):
                    c1, c2, c3 = st.columns(3)
                    n = c1.text_input("Ad")
                    p = c2.text_input("Qiymət")
                    c = c3.text_input("Kat")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category) VALUES (:n, :p, :c)", {"n":n, "p":p, "c":c})
                        st.rerun()
                m_df = run_query("SELECT * FROM menu WHERE is_active=TRUE ORDER BY id")
                for i, r in m_df.iterrows():
                    c1, c2 = st.columns([4,1])
                    c1.write(f"{r['item_name']} - {r['price']}")
                    if c2.button("Sil", key=f"del_{r['id']}"):
                        run_action("DELETE FROM menu WHERE id=:id", {"id":r['id']})
                        st.rerun()

            with tabs[3]: # RƏYLƏR
                r_df = run_query("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 20")
                for i, r in r_df.iterrows():
                    st.info(f"{r['rating']}⭐ - {r['message']}")

            with tabs[4]: # İDARƏETMƏ (Şifrə + Toggle)
                st.markdown("### ⚙️ Ayarlar")
                
                # Manual Input Toggle
                curr_status = check_manual_input_status()
                c_btn, c_txt = st.columns([1,3])
                if c_btn.button("DƏYİŞ", type="primary"):
                    new_val = 'false' if curr_status else 'true'
                    run_action("INSERT INTO settings (key, value) VALUES ('manual_input', :v) ON CONFLICT (key) DO UPDATE SET value = :v", {"v": new_val})
                    st.rerun()
                c_txt.write(f"Manual Giriş: **{'AÇIQ ✅' if curr_status else 'BAĞLI ⛔'}**")
                
                st.divider()
                
                # Şifrə Dəyişmə (Özünün)
                with st.expander("🔑 Şifrəmi Dəyiş"):
                    new_p = st.text_input("Yeni Şifrə", type="password", key="new_pass_own")
                    if st.button("Yenilə"):
                        hashed = hash_password(new_p)
                        run_action("UPDATE users SET password = :p WHERE username = :u", {"p": hashed, "u": user})
                        st.success("Yeniləndi!")

                # İşçi Yaratma (Hashed)
                with st.expander("➕ Yeni İşçi"):
                    nn = st.text_input("Ad")
                    np = st.text_input("Şifrə", type="password")
                    if st.button("Yarat"):
                        h_np = hash_password(np)
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u":nn, "p":h_np})
                        st.success("Yaradıldı!")

            with tabs[5]: # QR (Cache + Zip)
                with st.form("qr_gen"):
                    cnt = st.number_input("Say", 1, 50, 1)
                    is_th = st.checkbox("Termos")
                    if st.form_submit_button("Yarat"):
                        ids = []
                        typ = "thermos" if is_th else "standard"
                        ff = True if is_th else False
                        for _ in range(cnt):
                            rid = str(random.randint(10000000, 99999999))
                            run_action("INSERT INTO customers (card_id, stars, type, is_first_fill) VALUES (:id, 0, :t, :f)", {"id":rid, "t":typ, "f":ff})
                            ids.append(rid)
                        st.session_state['new_qrs'] = ids
                        st.rerun()
                
                if 'new_qrs' in st.session_state:
                    ids = st.session_state['new_qrs']
                    st.success(f"{len(ids)} kart yaradıldı!")
                    
                    # ZIP
                    z_buf = BytesIO()
                    with zipfile.ZipFile(z_buf, "w") as zf:
                        for i in ids:
                            l = f"https://emalatxana-loyalty-production.up.railway.app/?id={i}"
                            d = generate_custom_qr(l, i)
                            zf.writestr(f"{i}.png", d)
                    st.download_button("📦 Hamsını Yüklə (ZIP)", z_buf.getvalue(), "qrs.zip", "application/zip", type="primary")
                    
                    if st.button("Bağla"):
                        del st.session_state['new_qrs']
                        st.rerun()

        else: # STAFF EKRANI
            st.markdown("### 📠 Terminal")
            allowed = check_manual_input_status()
            if allowed:
                st.text_input("Barkod:", key="scanner_input", on_change=process_scan)
            else:
                st.warning("⛔ Manual giriş bağlıdır. Skaner istifadə edin.")
            
            if 'last_result' in st.session_state:
                res = st.session_state['last_result']
                if res['type'] == 'success': st.success(res['msg'])
                else: st.error(res['msg'])
