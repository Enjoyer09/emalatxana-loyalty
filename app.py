import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana Loyalty", page_icon="☕", layout="centered")

# --- CSS DİZAYN (MOBİL OPTİMİZASİYA) ---
st.markdown("""
    <style>
    /* Ümumi fon və şrift */
    .stApp {
        background-color: #f9f9f9; /* Göz yormayan açıq fon */
    }
    
    /* Mobil üçün stəkanların düzülüşü */
    .coffee-grid {
        display: flex;
        justify-content: center;
        gap: 8px; /* Stəkanlar arası məsafə */
        margin-bottom: 15px;
    }
    
    .coffee-item {
        width: 18%; /* Ekranın 1/5 hissəsi */
        max-width: 60px; /* Çox böyüməsin */
        transition: transform 0.3s ease;
    }
    
    /* Aktiv stəkan biraz böyük görünsün */
    .coffee-item.active {
        transform: scale(1.1);
    }
    
    /* Barista paneli üçün giriş */
    .stTextInput > div > div > input {
        text-align: center;
        font-size: 18px;
    }
    </style>
    """, unsafe_allow_html=True)

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

# --- MOTİVASİYA MESAJLARI ---
def get_motivational_msg(stars):
    messages = {
        0: "🌱 Xoş gəldin! İlk dad, yeni başlanğıc.",
        1: "✨ Hər böyük hekayə bir kofe ilə başlayır.",
        3: "☕ Sən kofeni sevirsən, biz də səni.",
        5: "🔥 Yarı yoldasan! Enerjin hiss olunur.",
        7: "😎 Buraların ən sadiq müştərisi sənsən!",
        8: "🚀 Az qaldı, hədəf görünür!",
        9: "💎 Sən dəyərlisən. Bir addım qaldı!",
        10: "👑 Təbriklər! Bu kofe bizdən sənə hədiyyə!"
    }
    # Ən uyğun mesajı seçmək
    key = max([k for k in messages.keys() if k <= stars], default=0)
    return messages[key]

# --- HTML İLƏ STƏKANLARI ÇƏKMƏK (Optimallaşdırılmış) ---
def render_coffee_grid(stars):
    # GIF və Şəkil linkləri
    active_gif = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmZpbW92cnV4enh5Z2I3M281NXI4Z2U4dmZ0azF5M2Rra2Z5bG91ZSZlcD12MV9zdGlja2VyX3NlYXJjaCZjdD1z/DyBc6G8y0yJ9u/giphy.gif"
    inactive_img = "https://cdn-icons-png.flaticon.com/512/10360/10360639.png" # Boz stəkan

    html_content = ""
    
    # 2 Sətir yaradacağıq (1-5 və 6-10)
    for row in range(2):
        html_content += '<div class="coffee-grid">'
        for col in range(5):
            idx = (row * 5) + col + 1 # 1-dən 10-a qədər rəqəm
            
            if idx <= stars:
                # Dolu (GIF)
                src = active_gif
                cls = "coffee-item active"
            else:
                # Boş (PNG)
                src = inactive_img
                cls = "coffee-item"
                
            html_content += f'<img src="{src}" class="{cls}">'
        html_content += '</div>'
    
    st.markdown(html_content, unsafe_allow_html=True)

# --- LOGO FUNKSİYASI ---
def show_logo(location="main"):
    try:
        if location == "sidebar":
            st.sidebar.image("emalatxana.png", use_container_width=True)
        else:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image("emalatxana.png", use_container_width=True)
    except:
        pass

# --- SCAN PROSESİ (BARİSTA) ---
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
            msg = "🎁 PULSUZ KOFE VERİLMƏLİDİR!"
            msg_type = "error"
        else:
            msg = f"✅ Ulduz əlavə olundu. (Cəmi: {new_stars})"
            
        data = {
            "card_id": scan_code, 
            "stars": new_stars, 
            "last_visit": datetime.now().isoformat()
        }
        supabase.table("customers").upsert(data).execute()
        
        st.session_state['last_result'] = {
            "msg": msg, "type": msg_type, "card": scan_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
    st.session_state.scanner_input = ""

# --- ƏSAS MƏNTİQ ---
query_params = st.query_params
card_id = query_params.get("id", None)

# === MÜŞTƏRİ PORTALI (MOBİL) ===
if card_id:
    show_logo("main")
    
    if supabase:
        response = supabase.table("customers").select("*").eq("card_id", card_id).execute()
        user_data = response.data[0] if response.data else None
        stars = user_data['stars'] if user_data else 0
        
        # Başlıq
        st.markdown(f"<h3 style='text-align: center; margin-bottom: 20px;'>Sənin Kartın: {stars}/10</h3>", unsafe_allow_html=True)
        
        # HTML GRID SİSTEMİ (Yeni dizayn)
        render_coffee_grid(stars)
        
        # Məsafə və Mesaj
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(get_motivational_msg(stars))
        
        if stars == 0 and user_data:
            st.success("🎉 Nuş olsun! Sayğac sıfırlandı.")

# === BARISTA PANELİ (PC) ===
else:
    show_logo("sidebar")
    st.sidebar.header("🔐 Giriş")
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        pwd = st.sidebar.text_input("Şifrə", type="password")
        if pwd == "1234":
            st.session_state.logged_in = True
            st.rerun()
    else:
        st.title("☕ Barista Terminalı")
        
        st.text_input("Barkodu Oxut:", key="scanner_input", on_change=process_scan, help="Skaner bura yazır")
        
        if 'last_result' in st.session_state:
            res = st.session_state['last_result']
            st.caption(f"Son: {res['time']} | Kart: {res['card']}")
            
            if res['type'] == 'error':
                st.error(res['msg'], icon="🎁")
                st.balloons()
                st.audio("https://www.soundjay.com/buttons/sounds/button-3.mp3")
            else:
                st.success(res['msg'], icon="☕")
            
        st.divider()
        st.caption("📋 Son aktivliklər:")
        if supabase:
            recent = supabase.table("customers").select("*").order("last_visit", desc=True).limit(5).execute()
            st.dataframe(recent.data)
