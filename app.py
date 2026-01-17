import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time

# --- SƏHİFƏ AYARLARI ---
st.set_page_config(page_title="Emalatxana Loyalty", page_icon="☕", layout="centered")

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

# --- CSS DİZAYN (FONTLAR VƏ STİL) ---
st.markdown("""
    <style>
    /* Google Font: Anton (Logoya oxşar şrift) */
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@500&display=swap');

    .stApp {
        background-color: #ffffff;
    }

    /* Ümumi Başlıqlar üçün Şrift */
    h1, h2, h3 {
        font-family: 'Anton', sans-serif !important;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* Kofe Grid Sistemi */
    .coffee-grid {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-bottom: 10px;
    }
    
    .coffee-item {
        width: 16%; 
        max-width: 55px;
        transition: transform 0.2s ease;
    }
    
    /* Aktiv stəkan effekti */
    .coffee-item.active {
        transform: scale(1.15);
        filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.2));
    }

    /* Yaşıl Mesaj Qutusu Dizaynı */
    .promo-box {
        background-color: #2e7d32; /* Tünd Yaşıl */
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-family: 'Oswald', sans-serif;
        font-size: 20px;
        margin-top: 20px;
        box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3);
        border: 2px solid #1b5e20;
    }
    
    .promo-icon {
        font-size: 30px;
    }

    /* Barista Input */
    .stTextInput input {
        text-align: center;
        font-size: 20px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKSİYALAR ---
def get_motivational_msg(stars):
    messages = {
        0: "YENİ BAŞLANĞIC!",
        1: "İLK KOFE DADLI OLDU?",
        3: "SƏN KOFENİ SEVİRSƏN!",
        5: "YARISINI KEÇDİN!",
        7: "SƏN ƏSL QƏHRƏMANSAN!",
        9: "SON BİR ADDIM QALDI!",
        10: "TƏBRİKLƏR! PULSUZ KOFE!"
    }
    key = max([k for k in messages.keys() if k <= stars], default=0)
    return messages[key]

# --- HTML İLƏ STƏKANLARI ÇƏKMƏK ---
def render_coffee_grid(stars):
    # Yeni, daha stabil linklər
    # Dolu Fincan (Rəngli)
    active_img = "https://cdn-icons-png.flaticon.com/512/751/751621.png"
    # Boş Fincan (Bozardılmış)
    inactive_img = "https://cdn-icons-png.flaticon.com/512/1174/1174444.png" 

    html_content = ""
    
    # 2 Sətir (1-5 və 6-10)
    for row in range(2):
        html_content += '<div class="coffee-grid">'
        for col in range(5):
            idx = (row * 5) + col + 1 
            
            if idx <= stars:
                src = active_img
                cls = "coffee-item active"
            else:
                src = inactive_img
                cls = "coffee-item"
                # Boş stəkanları biraz şəffaflaşdırırıq (opacity: 0.3)
                html_content += f'<img src="{src}" class="{cls}" style="opacity: 0.3;">'
                continue 

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

# --- SCAN PROSESİ ---
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
            
        data = {"card_id": scan_code, "stars": new_stars, "last_visit": datetime.now().isoformat()}
        supabase.table("customers").upsert(data).execute()
        
        st.session_state['last_result'] = {"msg": msg, "type": msg_type, "card": scan_code, "time": datetime.now().strftime("%H:%M:%S")}
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
        
        # Başlıq (Anton Fontu ilə)
        st.markdown(f"<h3 style='text-align: center; margin-bottom: 25px; color: #333;'>SƏNİN KARTIN: {stars}/10</h3>", unsafe_allow_html=True)
        
        # Grid Sistemi
        render_coffee_grid(stars)
        
        # Xüsusi Dizaynlı Yaşıl Qutu
        msg_text = get_motivational_msg(stars)
        st.markdown(f"""
            <div class="promo-box">
                <div class="promo-icon">🌿</div>
                {msg_text}<br>
                <span style="font-size: 16px; opacity: 0.9;">Biz səni sevirik, sən də kofeni!</span>
            </div>
        """, unsafe_allow_html=True)
        
        if stars == 0 and user_data:
            st.balloons()

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
        st.text_input("Barkodu Oxut:", key="scanner_input", on_change=process_scan)
        
        if 'last_result' in st.session_state:
            res = st.session_state['last_result']
            st.caption(f"Son: {res['time']} | Kart: {res['card']}")
            if res['type'] == 'error':
                st.error(res['msg'])
                st.balloons()
            else:
                st.success(res['msg'])
            
        st.divider()
        st.caption("Son aktivliklər:")
        if supabase:
            recent = supabase.table("customers").select("*").order("last_visit", desc=True).limit(5).execute()
            st.dataframe(recent.data)
