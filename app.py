import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time
import pandas as pd
import random
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

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

# --- CSS DİZAYN (APP GÖRÜNÜŞÜ) ---
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
    
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; text-transform: uppercase; letter-spacing: 1px; }
    p, div, button, input, li { font-family: 'Oswald', sans-serif; }
    
    [data-testid="stImage"] { display: flex; justify-content: center; }
    .login-header { text-align: center; margin-bottom: 20px; }

    .coffee-grid { display: flex; justify-content: center; gap: 8px; margin-bottom: 5px; margin-top: 5px; }
    .coffee-item { width: 17%; max-width: 50px; transition: transform 0.2s ease; }
    .coffee-item.active { transform: scale(1.1); filter: drop-shadow(0px 3px 5px rgba(0,0,0,0.2)); }

    .promo-box { background-color: #2e7d32; color: white; padding: 15px; border-radius: 12px; text-align: center; margin-top: 15px; }
    .counter-text { text-align: center; font-size: 19px; font-weight: 500; color: #d32f2f; margin-top: 8px; }
    
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
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- KART DİZAYN GENERATORU (Pillow) ---
def create_card_images(card_id, design="orange"):
    # Kredit kartı ölçüsü (300 DPI): 1011 x 638 px
    width, height = 1011, 638
    
    # Rənglər
    ORANGE = (232, 155, 72)
    GREEN = (46, 125, 50)
    BLACK = (20, 20, 20)
    WHITE = (255, 255, 255)
    BEIGE = (245, 245, 220)

    # Şrift Yükləmə (Default fallback)
    try:
        font_large = ImageFont.truetype("arial.ttf", 80)
        font_med = ImageFont.truetype("arial.ttf", 40)
        font_small = ImageFont.truetype("arial.ttf", 30)
    except:
        font_large = ImageFont.load_default()
        font_med = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # --- ÖN TƏRƏF (FRONT) ---
    if design == "orange":
        bg_color = ORANGE
        text_color = GREEN
    elif design == "black":
        bg_color = BLACK
        text_color = WHITE
    else: # Kraft/Beige
        bg_color = BEIGE
        text_color = BLACK

    img_front = Image.new('RGB', (width, height), color=bg_color)
    d_front = ImageDraw.Draw(img_front)
    
    # Loqo / Yazı (Mərkəzdə)
    # Tam mərkəzi tapmaq üçün sadə hesablama əvəzinə təxmini yerləşdiririk
    d_front.text((120, 250), "EMALATKHANA", fill=text_color, font=font_large)
    d_front.text((320, 350), "Daily Coffee & Drinks", fill=text_color, font=font_med)
    d_front.text((420, 550), "SINCE 2019", fill=text_color, font=font_small)

    # --- ARXA TƏRƏF (BACK) ---
    img_back = Image.new('RGB', (width, height), color=WHITE)
    d_back = ImageDraw.Draw(img_back)

    # QR Kodu Yarat və Yerləşdir
    link = f"https://emalatxana-loyalty.streamlit.app/?id={card_id}"
    qr = qrcode.QRCode(box_size=10, border=0)
    qr.add_data(link)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").resize((350, 350))
    
    # QR Kodu sol tərəfə qoyuruq
    img_back.paste(qr_img, (50, 140))
    
    # Sağ tərəfə yazılar
    d_back.text((450, 180), "Sadiqlik Kartı", fill=BLACK, font=font_med)
    d_back.text((450, 250), "Hər 10-cu kofe bizdən!", fill=GREEN, font=font_small)
    d_back.text((450, 400), f"ID: {card_id}", fill=BLACK, font=font_med)
    d_back.text((450, 550), "@emalatxana", fill=BLACK, font=font_small)

    return img_front, img_back

def convert_image_to_bytes(img):
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
        supabase.table("customers").upsert({"card_id": scan_code, "stars": new_stars, "last_visit": datetime.now().isoformat()}).execute()
        supabase.table("logs").insert({"staff_name": user, "card_id": scan_code, "action_type": action}).execute()
        st.session_state['last_result'] = {"msg": msg, "type": type, "card": scan_code, "time": datetime.now().strftime("%H:%M:%S")}
    st.session_state.scanner_input = ""

# --- ƏSAS PROQRAM ---
query_params = st.query_params

# === MÜŞTƏRİ GÖRÜNÜŞÜ ===
if "id" in query_params:
    card_id = query_params["id"]
    show_logo()
    if supabase:
        response = supabase.table("customers").select("*").eq("card_id", card_id).execute()
        user_data = response.data[0] if response.data else None
        stars = user_data['stars'] if user_data else 0
        
        st.markdown(f"<h3 style='text-align: center; margin: 0px; color: #333;'>KARTINIZ: {stars}/10</h3>", unsafe_allow_html=True)
        render_coffee_grid(stars)
        st.markdown(f"<div class='counter-text'>{get_remaining_text(stars)}</div>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="promo-box">
                <div style="font-size: 24px;">🌿</div>
                <div style="font-size: 20px; font-weight: bold; margin-bottom: 5px;">{get_motivational_msg(stars)}</div>
                <div style="font-size: 16px; opacity: 0.9;">Sən kofeni sevirsən, biz isə səni!</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        card_link = f"https://emalatxana-loyalty.streamlit.app/?id={card_id}"
        qr_bytes = generate_qr_image_bytes(card_link)
        
        st.download_button("📥 Kartı Şəkil Kimi Yüklə", data=qr_bytes, file_name=f"emalatxana_{card_id}.png", mime="image/png", use_container_width=True)
        
        if stars == 0 and user_data: st.balloons()

# === SİSTEM GÖRÜNÜŞÜ ===
else:
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    # ADMİN YOXLAMASI
    admin_check = supabase.table("users").select("*").eq("role", "admin").execute()
    if not admin_check.data:
        show_logo()
        st.warning("⚠️ Admin yaradın.")
        with st.form("create_admin"):
            new_admin_user = st.text_input("Admin Adı", value="Admin")
            new_admin_pass = st.text_input("Şifrə", type="password")
            if st.form_submit_button("Yarat"):
                supabase.table("users").insert({"username": new_admin_user, "password": new_admin_pass, "role": "admin"}).execute()
                st.rerun()

    # LOGİN
    elif not st.session_state.logged_in:
        show_logo()
        st.markdown("<br><h3 class='login-header'>SİSTEMƏ GİRİŞ</h3>", unsafe_allow_html=True)
        users_res = supabase.table("users").select("username").execute()
        user_list = [u['username'] for u in users_res.data]
        with st.form("login_form"):
            selected_user = st.selectbox("İstifadəçi:", user_list)
            pwd = st.text_input("Şifrə:", type="password")
            if st.form_submit_button("DAXİL OL", use_container_width=True):
                check = supabase.table("users").select("*").eq("username", selected_user).eq("password", pwd).execute()
                if check.data:
                    st.session_state.logged_in = True
                    st.session_state.current_user = selected_user
                    st.session_state.role = check.data[0]['role']
                    st.rerun()
                else: st.error("Yanlış şifrə!")

    # DAXİL OLDUQDAN SONRA
    else:
        role = st.session_state.role
        user = st.session_state.current_user
        col1, col2 = st.columns([3,1])
        col1.write(f"👤 **{user}** ({role.upper()})")
        if col2.button("Çıxış"): st.session_state.logged_in = False; st.rerun()
        show_logo()

        if role == 'admin':
            tabs = st.tabs(["📠 Terminal", "👥 İdarəetmə", "📊 Baza", "🖨️ Kart Çapı"])
            
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
                target_user = st.selectbox("İşçi:", staff_list)
                new_pass = st.text_input("Yeni Şifrə:", type="password")
                if st.button("Yenilə"):
                    supabase.table("users").update({"password": new_pass}).eq("username", target_user).execute()
                    st.success("Yeniləndi!")
                st.divider()
                st.markdown("### ➕ Yeni İşçi")
                new_staff_name = st.text_input("Ad:")
                new_staff_pass = st.text_input("Şifrə:", type="password", key="new_s_p")
                if st.button("Əlavə et"):
                    supabase.table("users").insert({"username": new_staff_name, "password": new_staff_pass, "role": "staff"}).execute()
                    st.success("Əlavə olundu!")
                    time.sleep(1); st.rerun()

            with tabs[2]: # Baza
                st.markdown("### 📋 Loglar")
                logs = supabase.table("logs").select("*").order("created_at", desc=True).limit(50).execute()
                st.dataframe(pd.DataFrame(logs.data), use_container_width=True)
                st.divider()
                st.markdown("### 👥 Müştərilər")
                custs = supabase.table("customers").select("*").order("last_visit", desc=True).execute()
                st.dataframe(pd.DataFrame(custs.data), use_container_width=True)

            with tabs[3]: # Kart Dizaynı (YENİ HİSSƏ)
                st.markdown("### 🖨️ Kart Çap Mərkəzi")
                
                # Seçimlər
                design_choice = st.selectbox("Dizayn Növü:", ["Narıncı (Signature)", "Qara (Premium)", "Bej (Kraft)"], index=0)
                count = st.number_input("Say:", min_value=1, max_value=10, value=1)
                
                design_map = {"Narıncı (Signature)": "orange", "Qara (Premium)": "black", "Bej (Kraft)": "beige"}
                selected_design = design_map[design_choice]

                if st.button("Dizayn Et və Yarat"):
                    for i in range(count):
                        r_id = str(random.randint(10000000, 99999999))
                        
                        # Kartları yarat
                        front_img, back_img = create_card_images(r_id, design=selected_design)
                        
                        # Bayt formatına çevir
                        front_bytes = convert_image_to_bytes(front_img)
                        back_bytes = convert_image_to_bytes(back_img)
                        
                        st.divider()
                        st.markdown(f"**Kart ID:** `{r_id}`")
                        
                        # Ekranda göstər (kiçildilmiş halda)
                        c1, c2 = st.columns(2)
                        with c1:
                            st.image(front_img, caption="Ön Tərəf", use_container_width=True)
                            st.download_button("⬇️ Ön Tərəfi Yüklə", data=front_bytes, file_name=f"front_{r_id}.png", mime="image/png")
                        with c2:
                            st.image(back_img, caption="Arxa Tərəf", use_container_width=True)
                            st.download_button("⬇️ Arxa Tərəfi Yüklə", data=back_bytes, file_name=f"back_{r_id}.png", mime="image/png")

        else: # Staff
            st.markdown("<h3 style='text-align: center;'>TERMİNAL</h3>", unsafe_allow_html=True)
            st.text_input("Barkod:", key="scanner_input", on_change=process_scan, label_visibility="collapsed")
            if 'last_result' in st.session_state:
                res = st.session_state['last_result']
                if res['type'] == 'error': st.error(res['msg']); st.balloons()
                else: st.success(res['msg'])
