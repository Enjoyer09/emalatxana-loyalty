import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time

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

# --- CSS DİZAYN (MOBİL KOMPAKT) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');

    /* Mobil üçün yuxarı boşluğu ləğv etmək (Scroll etməmək üçün) */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    
    .stApp { background-color: #ffffff; }

    /* Fontlar */
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; text-transform: uppercase; letter-spacing: 1px; }
    p, div { font-family: 'Oswald', sans-serif; }

    /* Kofe Grid Sistemi */
    .coffee-grid {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin-bottom: 5px;
        margin-top: 10px;
    }
    
    .coffee-item {
        width: 17%; 
        max-width: 50px;
        transition: transform 0.2s ease;
    }
    
    .coffee-item.active { transform: scale(1.1); filter: drop-shadow(0px 3px 5px rgba(0,0,0,0.2)); }

    /* Yaşıl Mesaj Qutusu */
    .promo-box {
        background-color: #2e7d32;
        color: white;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-top: 15px;
        box-shadow: 0 4px 8px rgba(46, 125, 50, 0.25);
    }
    
    /* Qalan Sayğac Mətni */
    .counter-text {
        text-align: center;
        font-size: 18px;
        font-weight: 500;
        color: #d32f2f; /* Diqqət çəkən qırmızı ton */
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKSİYALAR ---
def get_motivational_msg(stars):
    # Emosional cümlələr
    if stars == 0: return "YENİ BİR BAŞLANĞIC!"
    if stars < 3: return "KOFE ƏTRİ SƏNİ ÇAĞIRIR..."
    if stars < 5: return "NUŞ OLSUN, DAVAM ET!"
    if stars < 8: return "BU GÜN ENERJİN ƏLADIR!"
    if stars < 10: return "SƏNƏ HƏYRANIQ!"
    return "BU GÜNÜN QƏHRƏMANI SƏNSƏN!"

def get_remaining_text(stars):
    # Ağıllı Sayğac Məntiqi
    left = 10 - stars
    if left > 0:
        return f"🎁 Hədiyyə üçün daha <b>{left}</b> kofe dadmalısan"
    else:
        return "🎉 TƏBRİKLƏR! 10-cu KOFE BİZDƏN!"

# --- STƏKANLARI ÇƏKMƏK ---
def render_coffee_grid(stars):
    active_img = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
    inactive_img = "https://cdn-icons-png.flaticon.com/512/1174/1174444.png" 

    html_content = ""
    for row in range(2):
        html_content += '<div class="coffee-grid">'
        for col in range(5):
            idx = (row * 5) + col + 1 
            if idx <= stars:
                html_content += f'<img src="{active_img}" class="coffee-item active">'
            else:
                html_content += f'<img src="{inactive_img}" class="coffee-item" style="opacity: 0.25;">'
        html_content += '</div>'
    st.markdown(html_content, unsafe_allow_html=True)

# --- LOGO (KİÇİLDİLMİŞ) ---
def show_logo(location="main"):
    try:
        if location == "sidebar":
            st.sidebar.image("emalatxana.png", use_container_width=True)
        else:
            # Mobil üçün mərkəzləşmiş və kiçik logo (width=160 idealdır)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image("emalatxana.png", width=160) 
    except: pass

# --- SCAN (BARISTA) ---
def process_scan():
    scan_code = st.session_state.scanner_input
    if scan_code and supabase:
        res = supabase.table("customers").select("*").eq("card_id", scan_code).execute()
        current_stars = res.data[0]['stars'] if res.data else 0
        
        new_stars = current_stars + 1
        is_free = False
        msg_type = "success"
        
        if new_stars >= 10:
            new_stars = 0
            is_free = True
            msg = "🎁 PULSUZ KOFE!"
            msg_type = "error"
        else:
            msg = f"✅ Əlavə olundu. (Cəmi: {new_stars})"
            
        data = {"card_id": scan_code, "stars": new_stars, "last_visit": datetime.now().isoformat()}
        supabase.table("customers").upsert(data).execute()
        st.session_state['last_result'] = {"msg": msg, "type": msg_type, "card": scan_code, "time": datetime.now().strftime("%H:%M:%S")}
    st.session_state.scanner_input = ""

# --- ƏSAS PROQRAM ---
query_params = st.query_params
card_id = query_params.get("id", None)

# === MÜŞTƏRİ PORTALI (MOBİL) ===
if card_id:
    # 1. Logo (Kiçik)
    show_logo("main")
    
    if supabase:
        response = supabase.table("customers").select("*").eq("card_id", card_id).execute()
        user_data = response.data[0] if response.data else None
        stars = user_data['stars'] if user_data else 0
        
        # 2. Başlıq
        st.markdown(f"<h3 style='text-align: center; margin: 0px; color: #333;'>KARTINIZ: {stars}/10</h3>", unsafe_allow_html=True)
        
        # 3. Grid (Stəkanlar)
        render_coffee_grid(stars)
        
        # 4. Sayğac (Qırmızı yazı)
        remaining_msg = get_remaining_text(stars)
        st.markdown(f"<div class='counter-text'>{remaining_msg}</div>", unsafe_allow_html=True)

        # 5. Emosional Mesaj (Yaşıl Qutu)
        emotional_note = get_motivational_msg(stars)
        st.markdown(f"""
            <div class="promo-box">
                <div style="font-size: 24px;">🌿</div>
                <div style="font-size: 20px; font-weight: bold; margin-bottom: 5px;">{emotional_note}</div>
                <div style="font-size: 16px; opacity: 0.9;">Sən kofeni sevirsən, biz isə səni!</div>
            </div>
        """, unsafe_allow_html=True)
        
        if stars == 0 and user_data: st.balloons()

# === BARISTA PANELİ (PC) ===
else:
    show_logo("sidebar")
    st.sidebar.header("🔐 Giriş")
    
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in:
        pwd = st.sidebar.text_input("Şifrə", type="password")
        if pwd == "1234":
            st.session_state.logged_in = True
            st.rerun()
    else:
        st.title("☕ Terminal")
        st.text_input("Barkod:", key="scanner_input", on_change=process_scan)
        
        if 'last_result' in st.session_state:
            res = st.session_state['last_result']
            if res['type'] == 'error':
                st.error(res['msg'])
                st.balloons()
            else:
                st.success(res['msg'])
            
        st.divider()
        recent = supabase.table("customers").select("*").order("last_visit", desc=True).limit(5).execute()
        st.dataframe(recent.data)
