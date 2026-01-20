import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time
import pandas as pd
import random
import qrcode
from io import BytesIO

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana", page_icon="☕", layout="centered")

# --- SUPABASE QOŞULMASI ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

# --- CSS DİZAYN (APP GÖRÜNÜŞÜ & TAM GİZLİLİK) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');

    /* GİZLƏTMƏ KODLARI */
    header[data-testid="stHeader"], div[data-testid="stDecoration"], footer, 
    div[data-testid="stToolbar"], div[class*="stAppDeployButton"], 
    div[data-testid="stStatusWidget"], #MainMenu {
        display: none !important; visibility: hidden !important;
    }

    /* DİZAYN TƏNZİMLƏMƏLƏRİ */
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .stApp { background-color: #ffffff; }
    
    /* Fontlar */
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; text-transform: uppercase; letter-spacing: 1px; }
    p, div, button, input, li { font-family: 'Oswald', sans-serif; }
    
    /* Logo Mərkəzləşdirmə */
    [data-testid="stImage"] { display: flex; justify-content: center; }
    .login-header { text-align: center; margin-bottom: 20px; }

    /* Kofe Grid Sistemi */
    .coffee-grid { display: flex; justify-content: center; gap: 8px; margin-bottom: 5px; margin-top: 5px; }
    .coffee-item { width: 17%; max-width: 50px; transition: transform 0.2s ease; }
    .coffee-item.active { transform: scale(1.1); filter: drop-shadow(0px 3px 5px rgba(0,0,0,0.2)); }

    /* Mesaj Qutuları */
    .promo-box { background-color: #2e7d32; color: white; padding: 15px; border-radius: 12px; text-align: center; margin-top: 15px; }
    .counter-text { text-align: center; font-size: 19px; font-weight: 500; color: #d32f2f; margin-top: 8px; }
    
    /* Form Elementleri */
    .stTextInput input { text-align: center; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKSİYALAR ---
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

# --- SCAN PROSESİ ---
def process_scan():
    scan_code = st.session_state.scanner_input
    user = st.session_state.get('current_user', 'Unknown')
    
    if scan_code and supabase:
        res = supabase.table("customers").select("*").eq("card_id", scan_code).execute()
        current = res.data[0]['stars'] if res.data else 0
        new_stars = current + 1
        
        is_free, msg, type = False, f"✅ Əlavə olundu. (Cəmi: {new_stars})", "success"
        action = "Star Added"
        
        if new_stars >= 10:
            new_stars = 0; is_free = True; msg = "🎁 PULSUZ KOFE VERİLDİ!"; type = "error"; action = "Free Coffee"
            
        # Bazaları Yenilə
        supabase.table("customers").upsert({"card_id": scan_code, "stars": new_stars, "last_visit": datetime.now().isoformat()}).execute()
        supabase.table("logs").insert({"staff_name": user, "card_id": scan_code, "action_type": action}).execute()
        
        st.session_state['last_result'] = {"msg": msg, "type": type, "card": scan_code, "time": datetime.now().strftime("%H:%M:%S")}
    st.session_state.scanner_input = ""

# --- ƏSAS PROQRAM ---
query_params = st.query_params

# ================================
# === 1. MÜŞTƏRİ GÖRÜNÜŞÜ (MOBİL) ===
# ================================
if "id" in query_params:
    card_id = query_params["id"]
    show_logo()
    if supabase:
        response = supabase.table("customers").select("*").eq("card_id", card_id).execute()
        user_data = response.data[0] if response.data else None
        stars = user_data['stars'] if user_data else 0
        
        # Başlıq və Grid
        st.markdown(f"<h3 style='text-align: center; margin: 0px; color: #333;'>KARTINIZ: {stars}/10</h3>", unsafe_allow_html=True)
        render_coffee_grid(stars)
        st.markdown(f"<div class='counter-text'>{get_remaining_text(stars)}</div>", unsafe_allow_html=True)
        
        # Emosional Mesaj
        st.markdown(f"""
            <div class="promo-box">
                <div style="font-size: 24px;">🌿</div>
                <div style="font-size: 20px; font-weight: bold; margin-bottom: 5px;">{get_motivational_msg(stars)}</div>
                <div style="font-size: 16px; opacity: 0.9;">Sən kofeni sevirsən, biz isə səni!</div>
            </div>
        """, unsafe_allow_html=True)

        # Kartı Yükləmə Düyməsi
        st.markdown("<br>", unsafe_allow_html=True)
        card_link = f"https://emalatxana-loyalty.streamlit.app/?id={card_id}"
        qr_bytes = generate_qr_image_bytes(card_link)
        
        st.download_button(
            label="📥 Kartı Şəkil Kimi Yüklə",
            data=qr_bytes,
            file_name=f"emalatxana_{card_id}.png",
            mime="image/png",
            use_container_width=True
        )
        
        if stars == 0 and user_data: st.balloons()

# ================================
# === 2. SİSTEM GÖRÜNÜŞÜ (ADMIN/STAFF) ===
# ================================
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    # A. ADMİN YOXLAMASI (İLK DƏFƏ)
    admin_check = supabase.table("users").select("*").eq("role", "admin").execute()
    
    if not admin_check.data:
        show_logo()
        st.warning("⚠️ Admin yoxdur. Zəhmət olmasa yaradın.")
        with st.form("create_admin"):
            new_admin_user = st.text_input("Admin Adı", value="Admin")
            new_admin_pass = st.text_input("Şifrə", type="password")
            if st.form_submit_button("Yarat"):
                supabase.table("users").insert({"username": new_admin_user, "password": new_admin_pass, "role": "admin"}).execute()
                st.success("Admin yaradıldı! Giriş edin.")
                time.sleep(1)
                st.rerun()
                
    # B. LOGİN EKRANI
    elif not st.session_state.logged_in:
        show_logo()
        st.markdown("<br><h3 class='login-header'>SİSTEMƏ GİRİŞ</h3>", unsafe_allow_html=True)
        
        users_res = supabase.table("users").select("username").execute()
        user_list = [u['username'] for u in users_res.data]
        
        with st.form("login_form"):
            selected_user = st.selectbox("İstifadəçi:", user_list)
            pwd = st.text_input("Şifrə:", type="password")
            submit_login = st.form_submit_button("DAXİL OL", use_container_width=True)
        
        if submit_login:
            check = supabase.table("users").select("*").eq("username", selected_user).eq("password", pwd).execute()
            if check.data:
                st.session_state.logged_in = True
                st.session_state.current_user = selected_user
                st.session_state.role = check.data[0]['role']
                st.rerun()
            else:
                st.error("Yanlış şifrə!")

    # C. DAXİL OLDUQDAN SONRA
    else:
        role = st.session_state.role
        user = st.session_state.current_user
        
        col1, col2 = st.columns([3,1])
        col1.write(f"👤 **{user}** ({role.upper()})")
        if col2.button("Çıxış"):
            st.session_state.logged_in = False
            st.rerun()
            
        show_logo()

        # === ADMİN PANELİ ===
        if role == 'admin':
            tabs = st.tabs(["📠 Terminal", "👥 İdarəetmə", "📊 Baza", "🖨️ QR Generator"])
            
            with tabs[0]: # Terminal
                st.markdown("<h3 style='text-align: center;'>TERMİNAL</h3>", unsafe_allow_html=True)
                st.text_input("Barkod:", key="scanner_input", on_change=process_scan, label_visibility="collapsed")
                if 'last_result' in st.session_state:
                    res = st.session_state['last_result']
                    if res['type'] == 'error': st.error(res['msg']); st.balloons()
                    else: st.success(res['msg'])

            with tabs[1]: # İdarəetmə
                st.markdown("### 🔐 Şifrə Dəyişimi")
                users_res = supabase.table("users").select("username").neq("role", "admin").execute()
                staff_list = [u['username'] for u in users_res.data]
                
                target_user = st.selectbox("İşçi seç:", staff_list)
                new_pass = st.text_input("Yeni Şifrə:", type="password")
                
                if st.button("Şifrəni Yenilə"):
                    supabase.table("users").update({"password": new_pass}).eq("username", target_user).execute()
                    st.success(f"{target_user} şifrəsi yeniləndi!")
                    
                st.divider()
                st.markdown("### ➕ Yeni İşçi")
                new_staff_name = st.text_input("Ad:")
                new_staff_pass = st.text_input("Şifrə:", type="password", key="new_s_p")
                if st.button("Əlavə et"):
                    try:
                        supabase.table("users").insert({"username": new_staff_name, "password": new_staff_pass, "role": "staff"}).execute()
                        st.success("İşçi əlavə olundu!")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("Xəta: Bu ad artıq mövcuddur.")

            with tabs[2]: # Baza & Log
                st.markdown("### 📋 Log Tarixçəsi")
                logs = supabase.table("logs").select("*").order("created_at", desc=True).limit(50).execute()
                st.dataframe(pd.DataFrame(logs.data), use_container_width=True)
                
                st.divider()
                st.markdown("### 👥 Müştərilər")
                custs = supabase.table("customers").select("*").order("last_visit", desc=True).execute()
                st.dataframe(pd.DataFrame(custs.data), use_container_width=True)

            with tabs[3]: # QR Generator (KÖHNƏ SADƏ FORMADA)
                st.markdown("### 🖨️ QR Kod Yarat")
                count = st.number_input("Say:", min_value=1, max_value=20, value=1)
                if st.button("Yarat"):
                    for i in range(count):
                        r_id = str(random.randint(10000000, 99999999))
                        link = f"https://emalatxana-loyalty.streamlit.app/?id={r_id}"
                        qr_bytes = generate_qr_image_bytes(link)
                        st.divider()
                        c1, c2 = st.columns([1, 2])
                        with c1: st.image(qr_bytes, width=150)
                        with c2:
                            st.markdown(f"**ID:** `{r_id}`")
                            st.download_button("⬇️ Yüklə", data=qr_bytes, file_name=f"{r_id}.png", mime="image/png")

        # === STAFF PANELİ ===
        else:
            st.markdown("<h3 style='text-align: center;'>TERMİNAL</h3>", unsafe_allow_html=True)
            st.text_input("Barkod:", key="scanner_input", on_change=process_scan, label_visibility="collapsed")
            if 'last_result' in st.session_state:
                res = st.session_state['last_result']
                if res['type'] == 'error': st.error(res['msg']); st.balloons()
                else: st.success(res['msg'])
