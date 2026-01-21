import streamlit as st
import pandas as pd
import random
import qrcode
from io import BytesIO
import altair as alt
from datetime import datetime
import time
from sqlalchemy import text
import os

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana", page_icon="☕", layout="centered")

# --- DATABASE CONNECTION (NEON/POSTGRES) ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url:
        st.error("⚠️ XƏTA: Railway Variables bölməsində 'STREAMLIT_CONNECTIONS_NEON_URL' tapılmadı!")
        st.stop()
    
    db_url = db_url.strip().strip('"').strip("'")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    conn = st.connection("neon", type="sql", url=db_url)

except Exception as e:
    st.error(f"Bağlantı xətası yarandı: {e}")
    st.stop()

# --- SQL KÖMƏKÇİ FUNKSİYALAR ---
def run_query(query, params=None):
    try:
        return conn.query(query, params=params, ttl=0)
    except Exception as e:
        st.error(f"Sorğu xətası: {e}")
        return pd.DataFrame()

def run_action(query, params=None):
    try:
        with conn.session as s:
            s.execute(text(query), params if params else {})
            s.commit()
        return True
    except Exception as e:
        st.error(f"Əməliyyat xətası: {e}")
        return False

# --- CSS DİZAYN ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');
    
    header[data-testid="stHeader"], div[data-testid="stDecoration"], footer, 
    div[data-testid="stToolbar"], div[class*="stAppDeployButton"], 
    div[data-testid="stStatusWidget"], #MainMenu { display: none !important; }
    
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .stApp { background-color: #ffffff; }
    
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; text-transform: uppercase; letter-spacing: 1px; }
    p, div, button, input, li { font-family: 'Oswald', sans-serif; }
    
    [data-testid="stImage"] { display: flex; justify-content: center; }
    .coffee-grid { display: flex; justify-content: center; gap: 8px; margin-bottom: 5px; margin-top: 5px; }
    .coffee-item { width: 17%; max-width: 50px; transition: transform 0.2s ease; }
    .coffee-item.active { transform: scale(1.1); filter: drop-shadow(0px 3px 5px rgba(0,0,0,0.2)); }
    
    .promo-box { background-color: #2e7d32; color: white; padding: 15px; border-radius: 12px; text-align: center; margin-top: 15px; }
    .thermos-box { background-color: #e65100; color: white; padding: 15px; border-radius: 12px; text-align: center; margin-top: 15px; }
    .counter-text { text-align: center; font-size: 19px; font-weight: 500; color: #d32f2f; margin-top: 8px; }
    .menu-item { border: 1px solid #eee; padding: 10px; border-radius: 8px; margin-bottom: 10px; background: #f9f9f9; }
    .stTextInput input { text-align: center; font-size: 18px; }
    .archive-row { border-bottom: 1px solid #eee; padding: 10px 0; }
    
    div[data-testid="stFeedback"] > div {
        transform: scale(1.5);
        transform-origin: left top;
        margin-bottom: 20px;
        margin-left: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNKSİYALAR ---
def show_logo():
    try: st.image("emalatxana.png", width=180) 
    except: pass

def get_motivational_msg(stars):
    if stars == 0: return "YENİ BİR BAŞLANĞIC!"
    if stars < 10: return "BU GÜN ENERJİN ƏLADIR!"
    return "BU GÜNÜN QƏHRƏMANI SƏNSƏN!"

def get_remaining_text(stars):
    left = 10 - stars
    return f"🎁 <b>{left}</b> kofedən sonra qonağımızsan" if left > 0 else "🎉 TƏBRİKLƏR! BU KOFE BİZDƏN!"

def render_coffee_grid(stars):
    active = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
    inactive = "https://cdn-icons-png.flaticon.com/512/1174/1174444.png"
    html = ""
    for row in range(2):
        html += '<div class="coffee-grid">'
        for col in range(5):
            idx = (row * 5) + col + 1 
            src = active if idx <= stars else inactive
            style = "" if idx <= stars else "opacity: 0.25;"
            html += f'<img src="{src}" class="coffee-item {"active" if idx<=stars else ""}" style="{style}">'
        html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def generate_qr_image_bytes(data):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def check_manual_input_status():
    df = run_query("SELECT value FROM settings WHERE key = 'manual_input'")
    if not df.empty:
        return df.iloc[0]['value'] == 'true'
    return True

# --- SCAN PROSESİ (SQL) ---
def process_scan():
    scan_code = st.session_state.scanner_input
    user = st.session_state.get('current_user', 'Unknown')
    
    if scan_code:
        df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": scan_code})
        
        if not df.empty:
            customer = df.iloc[0]
            current_stars = int(customer['stars'])
            cust_type = customer['type']
            is_first = customer['is_first_fill']
            
            if cust_type == 'thermos':
                if is_first:
                    msg = "🎁 TERMOS: İLK DOLUM PULSUZ!"
                    msg_type = "info"
                    action = "Thermos First Free"
                    run_action("UPDATE customers SET is_first_fill = FALSE, stars = stars + 1, last_visit = NOW() WHERE card_id = :id", {"id": scan_code})
                else:
                    msg = "🏷️ TERMOS: 20% ENDİRİM TƏTBİQ ET!"
                    msg_type = "warning"
                    action = "Thermos Discount 20%"
                    new_stars = current_stars + 1
                    if new_stars >= 10:
                        new_stars = 0
                        msg = "🎁 TERMOS: 10-cu KOFE PULSUZ!"
                        msg_type = "error"
                        action = "Free Coffee"
                    run_action("UPDATE customers SET stars = :stars, last_visit = NOW() WHERE card_id = :id", {"stars": new_stars, "id": scan_code})
            else: # Standard
                new_stars = current_stars + 1
                msg_type = "success"
                action = "Star Added"
                if new_stars >= 10:
                    new_stars = 0
                    msg = "🎁 PULSUZ KOFE VERİLDİ!"
                    msg_type = "error"
                    action = "Free Coffee"
                else:
                    msg = f"✅ Əlavə olundu. (Cəmi: {new_stars})"
                
                run_action("UPDATE customers SET stars = :stars, last_visit = NOW() WHERE card_id = :id", {"stars": new_stars, "id": scan_code})

            run_action("INSERT INTO logs (staff_name, card_id, action_type) VALUES (:staff, :card, :action)", 
                       {"staff": user, "card": scan_code, "action": action})
            
            st.session_state['last_result'] = {"msg": msg, "type": msg_type}
        
        else:
            st.error("Kart bazada tapılmadı! Adminə müraciət edin.")
            
    st.session_state.scanner_input = ""

# --- ƏSAS PROQRAM ---
query_params = st.query_params

if "id" in query_params:
    card_id = query_params["id"]
    show_logo()
    
    df = run_query("SELECT * FROM customers WHERE card_id = :id", {"id": card_id})
    
    if not df.empty:
        user_data = df.iloc[0]
        stars = int(user_data['stars'])
        cust_type = user_data['type']

        if cust_type == 'thermos':
            st.markdown("""<div class="thermos-box"><b>⭐ VIP TERMOS KLUBU ⭐</b><br>Hər kofe <b>20% ENDİRİMLƏ!</b></div>""", unsafe_allow_html=True)
        
        st.markdown(f"<h3 style='text-align: center; margin: 0px; color: #2e7d32;'>KARTINIZ: {stars}/10</h3>", unsafe_allow_html=True)
        render_coffee_grid(stars)
        st.markdown(f"<div class='counter-text'>{get_remaining_text(stars)}</div>", unsafe_allow_html=True)
        
        if cust_type != 'thermos':
            st.markdown(f"""<div class="promo-box"><div style="font-weight: bold;">{get_motivational_msg(stars)}</div></div>""", unsafe_allow_html=True)

        st.markdown("<br><h3 style='color: #2e7d32;'>📋 MENYU</h3>", unsafe_allow_html=True)
        menu_df = run_query("SELECT * FROM menu WHERE is_active = TRUE ORDER BY id")
        if not menu_df.empty:
            for index, item in menu_df.iterrows():
                st.markdown(f"""
                <div class="menu-item">
                    <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:18px;">
                        <span>{item['item_name']}</span><span style="color:#2e7d32;">{item['price']}</span>
                    </div>
                    <div style="font-size:14px; color:gray;">{item['category']}</div>
                </div>""", unsafe_allow_html=True)
        else: st.caption("Menyu boşdur.")

        st.markdown("<br><h3 style='color: #2e7d32;'>⭐ BİZİ QİYMƏTLƏNDİR</h3>", unsafe_allow_html=True)
        
        selected_stars = st.feedback("stars")
        review_msg = st.text_area("Rəyiniz:")
        
        if st.button("Rəyi Göndər", key="btn_send_feedback"):
            if selected_stars is not None:
                real_rating = selected_stars + 1
                run_action("INSERT INTO feedback (card_id, rating, message) VALUES (:id, :rat, :msg)", 
                          {"id": card_id, "rat": real_rating, "msg": review_msg})
                st.success("Təşəkkürlər! Rəyiniz qeydə alındı.")
            else:
                st.warning("Zəhmət olmasa ulduz seçin.")

        st.markdown("<br>", unsafe_allow_html=True)
        card_link = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
        st.download_button("📥 Kartı Yüklə", data=generate_qr_image_bytes(card_link), file_name=f"card_{card_id}.png", mime="image/png", use_container_width=True)
        if stars == 0: st.balloons()
    else:
        st.error("Bu kart aktiv deyil.")

else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_logo()
        st.markdown("<br><h3 class='login-header'>SİSTEMƏ GİRİŞ</h3>", unsafe_allow_html=True)
        
        users_df = run_query("SELECT username FROM users")
        if not users_df.empty:
            user_list = users_df['username'].tolist()
            with st.form("login_form"):
                selected_user = st.selectbox("İstifadəçi:", user_list)
                pwd = st.text_input("Şifrə:", type="password")
                if st.form_submit_button("DAXİL OL", use_container_width=True):
                    check = run_query("SELECT * FROM users WHERE username = :u AND password = :p", {"u": selected_user, "p": pwd})
                    if not check.empty:
                        st.session_state.logged_in = True
                        st.session_state.current_user = selected_user
                        st.session_state.role = check.iloc[0]['role']
                        st.rerun()
                    else: st.error("Yanlış şifrə!")
        else:
            st.error("Bazada istifadəçi yoxdur.")

    else:
        role = st.session_state.role
        user = st.session_state.current_user
        is_input_allowed = check_manual_input_status()
        
        c1, c2 = st.columns([3,1])
        c1.write(f"👤 **{user}** ({role.upper()})")
        if c2.button("Çıxış"): st.session_state.logged_in = False; st.rerun()
        show_logo()

        if role == 'admin':
            tabs = st.tabs(["📠 Terminal", "📊 Statistika", "📋 Menyu", "💬 Rəylər", "👥 İdarəetmə", "🖨️ QR & Baza"])
            
            with tabs[0]: 
                st.markdown("<h3 style='text-align: center;'>TERMİNAL</h3>", unsafe_allow_html=True)
                if not is_input_allowed:
                    st.caption("🔒 *Diqqət: İşçilər üçün manual giriş bağlıdır.*")
                
                st.text_input("Barkod:", key="scanner_input", on_change=process_scan, label_visibility="collapsed")
                
                if 'last_result' in st.session_state:
                    res = st.session_state['last_result']
                    if res['type'] == 'error': st.error(res['msg']); st.balloons()
                    elif res['type'] == 'warning': st.warning(res['msg'])
                    elif res['type'] == 'info': st.info(res['msg'])
                    else: st.success(res['msg'])

            with tabs[1]:
                st.markdown("### 📊 Satış Analizi")
                logs_df = run_query("SELECT * FROM logs ORDER BY created_at DESC")
                if not logs_df.empty:
                    logs_df['created_at'] = pd.to_datetime(logs_df['created_at']).dt.date
                    daily = logs_df.groupby('created_at').size().reset_index(name='count')
                    chart = alt.Chart(daily).mark_bar().encode(x='created_at', y='count').properties(title="Günlük Aktivlik")
                    st.altair_chart(chart, use_container_width=True)
                    st.markdown("### 🏆 İşçi Performansı")
                    st.bar_chart(logs_df['staff_name'].value_counts())

            with tabs[2]:
                st.markdown("### 📋 Menyu")
                with st.form("add_menu"):
                    c1, c2, c3 = st.columns(3)
                    name = c1.text_input("Ad")
                    price = c2.text_input("Qiymət")
                    cat = c3.text_input("Kateqoriya")
                    if st.form_submit_button("Əlavə Et"):
                        run_action("INSERT INTO menu (item_name, price, category) VALUES (:n, :p, :c)", {"n": name, "p": price, "c": cat})
                        st.success("OK"); st.rerun()
                
                st.markdown("---")
                menu_df = run_query("SELECT * FROM menu WHERE is_active = TRUE ORDER BY id")
                if not menu_df.empty:
                    for i, row in menu_df.iterrows():
                        c1, c2 = st.columns([4, 1])
                        c1.write(f"**{row['item_name']}** - {row['price']}")
                        if c2.button("Sil", key=f"m_{row['id']}"):
                            run_action("DELETE FROM menu WHERE id = :id", {"id": row['id']})
                            st.rerun()

            with tabs[3]:
                st.markdown("### 💬 Rəylər")
                feed_df = run_query("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 20")
                if not feed_df.empty:
                    for i, r in feed_df.iterrows():
                        st.info(f"Kart: {r['card_id']} | {r['rating']}⭐\n\n{r['message']}")

            with tabs[4]:
                st.markdown("### 🔐 İdarəetmə Paneli")
                st.markdown("#### ⚙️ Terminal Ayarları")
                col_set1, col_set2 = st.columns([3, 1])
                col_set1.write("Baristalar üçün Manual Giriş (Əllə yazmaq):")
                
                current_status = is_input_allowed
                if col_set2.button("YANDIR" if not current_status else "SÖNDÜR", 
                                  type="primary" if not current_status else "secondary", 
                                  key="btn_toggle_input"):
                    new_val = 'true' if not current_status else 'false'
                    run_action("INSERT INTO settings (key, value) VALUES ('manual_input', :v) ON CONFLICT (key) DO UPDATE SET value = :v", {"v": new_val})
                    st.rerun()
                
                if current_status:
                    st.success("✅ Giriş AÇIQDIR")
                else:
                    st.error("⛔ Giriş BAĞLIDIR")
                
                st.divider()

                with st.expander("🔑 Öz Şifrəni Dəyiş"):
                    with st.form("change_own_pass"):
                        own_new_pass = st.text_input("Yeni Şifrəniz:", type="password")
                        if st.form_submit_button("Mənim Şifrəmi Dəyiş"):
                            run_action("UPDATE users SET password = :p WHERE username = :u", {"p": own_new_pass, "u": user})
                            st.success("Şifrəniz yeniləndi! Çıxış edilir...")
                            time.sleep(2)
                            st.session_state.logged_in = False
                            st.rerun()

                with st.expander("👥 İşçi Şifrələrini Yenilə"):
                    users_df = run_query("SELECT username FROM users WHERE role != 'admin'")
                    if not users_df.empty:
                        target = st.selectbox("İşçi Seç:", users_df['username'].tolist())
                        staff_new_pass = st.text_input("İşçi üçün Yeni Şifrə:", type="password")
                        if st.button("İşçi Şifrəsini Yenilə", key="btn_staff_pass_update"):
                            run_action("UPDATE users SET password = :p WHERE username = :u", {"p": staff_new_pass, "u": target})
                            st.success(f"{target} üçün şifrə yeniləndi!")
                
                st.divider()
                st.markdown("### ➕ Yeni İşçi")
                n_name = st.text_input("Ad:")
                n_pass = st.text_input("Şifrə:", type="password", key="np")
                if st.button("Yarat", key="btn_new_user"):
                    run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, 'staff')", {"u": n_name, "p": n_pass})
                    st.success("Hazır!"); st.rerun()

            with tabs[5]:
                st.markdown("### 🖨️ QR Kod")
                
                # --- YENİ FORM SİSTEMİ (STABİLLİK ÜÇÜN) ---
                with st.form("qr_create_form"):
                    c_qr1, c_qr2 = st.columns(2)
                    cnt = c_qr1.number_input("Say:", 1, 20, 1)
                    is_th = c_qr2.checkbox("Bu Termosdur? (20%)")
                    
                    if st.form_submit_button("Yarat"):
                        typ = "thermos" if is_th else "standard"
                        ff = True if is_th else False
                        for i in range(cnt):
                            r_id = str(random.randint(10000000, 99999999))
                            run_action("INSERT INTO customers (card_id, stars, type, is_first_fill) VALUES (:id, 0, :t, :f)", {"id": r_id, "t": typ, "f": ff})
                        st.success(f"{cnt} ədəd yeni kart yaradıldı! Aşağıdan baxa bilərsiniz.")
                        time.sleep(1)
                        st.rerun()

                st.divider()
                
                with st.expander("📂 Bütün Kartlar (Arxiv) - Axtarış"):
                    st.caption("Burada sistemdəki bütün kartlar saxlanılır. İstədiyinizi tapıb yenidən yükləyə bilərsiniz.")
                    search_qr = st.text_input("Kart ID ilə axtar:", placeholder="Məs: 84930211")
                    base_sql = "SELECT * FROM customers"
                    params = {}
                    if search_qr:
                        base_sql += " WHERE card_id LIKE :s"
                        params = {"s": f"%{search_qr}%"}
                    base_sql += " ORDER BY last_visit DESC LIMIT 50"
                    archive_df = run_query(base_sql, params)
                    if not archive_df.empty:
                        for i, row in archive_df.iterrows():
                            c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
                            with c1: st.write(f"🆔 **{row['card_id']}**")
                            with c2: st.write(f"⭐ {row['stars']}")
                            with c3: st.write(f"☕ {row['type'][:1].upper()}") 
                            with c4:
                                lnk = f"https://emalatxana-loyalty-production.up.railway.app/?id={row['card_id']}"
                                b_data = generate_qr_image_bytes(lnk)
                                st.download_button("⬇️ QR", data=b_data, file_name=f"{row['card_id']}.png", mime="image/png", key=f"dl_{row['card_id']}")
                            st.markdown("<div class='archive-row'></div>", unsafe_allow_html=True)
                    else:
                        st.info("Kart tapılmadı.")
                
                st.divider()
                with st.expander("🗑️ Silmə Paneli"):
                    d_id = st.text_input("Kart ID Sil:")
                    if st.button("Sil", key="btn_del_card"):
                        run_action("DELETE FROM customers WHERE card_id = :id", {"id": d_id})
                        st.success("Silindi")
                        st.rerun()

        else: # Staff
            st.markdown("<h3 style='text-align: center;'>TERMİNAL</h3>", unsafe_allow_html=True)
            if is_input_allowed:
                st.text_input("Barkod:", key="scanner_input", on_change=process_scan, label_visibility="collapsed")
            else:
                st.warning("⛔ DİQQƏT: Admin manual girişi bağlayıb.")
                st.info("Zəhmət olmasa fiziki QR Skaner istifadə edin.")
            
            if 'last_result' in st.session_state:
                res = st.session_state['last_result']
                if res['type'] == 'error': st.error(res['msg']); st.balloons()
                elif res['type'] == 'warning': st.warning(res['msg'])
                elif res['type'] == 'info': st.info(res['msg'])
                else: st.success(res['msg'])
