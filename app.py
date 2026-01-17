import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import time

# --- Səhifə Ayarları ---
st.set_page_config(page_title="Emalatxana Loyalty", page_icon="☕", layout="centered")

# --- Supabase Qoşulması ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

# --- Mesajlar ---
def get_motivational_msg(stars):
    messages = {
        0: "🌱 Xoş gəldin! İlk dad, yeni başlanğıc.",
        3: "☕ Sən kofeni sevirsən, biz də səni.",
        5: "🔥 Yarı yoldasan! Davam et.",
        8: "🚀 Az qaldı, hədəf görünür!",
        9: "💎 Sən dəyərlisən. Bir addım qaldı!",
        10: "👑 Təbriklər! Qəhvən bizdən olsun."
    }
    key = max([k for k in messages.keys() if k <= stars], default=0)
    return messages[key]

# --- SCAN PROSESİ (Avtomatik Təmizləmə üçün) ---
def process_scan():
    # Skan olunan kodu götürürük
    scan_code = st.session_state.scanner_input
    
    if scan_code and supabase:
        # 1. Müştərini tap
        res = supabase.table("customers").select("*").eq("card_id", scan_code).execute()
        current_stars = res.data[0]['stars'] if res.data else 0
        
        # 2. Hesabla
        new_stars = current_stars + 1
        is_free = False
        
        if new_stars >= 10:
            new_stars = 0
            is_free = True
            msg = "🎁 PULSUZ KOFE VERİLMƏLİDİR!"
            msg_type = "error" # Qırmızı rəng
        else:
            msg = f"✅ Ulduz əlavə olundu. (Cəmi: {new_stars})"
            msg_type = "success" # Yaşıl rəng
            
        # 3. Bazanı yenilə
        data = {
            "card_id": scan_code, 
            "stars": new_stars, 
            "last_visit": datetime.now().isoformat()
        }
        supabase.table("customers").upsert(data).execute()
        
        # 4. Nəticəni yaddaşda saxla (Çünki input silinəcək)
        st.session_state['last_result'] = {
            "msg": msg,
            "type": msg_type,
            "card": scan_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
    # 5. INPUT XANASINI TƏMİZLƏ (Əsas məqam budur)
    st.session_state.scanner_input = ""

# --- ƏSAS MƏNTİQ ---
query_params = st.query_params
card_id = query_params.get("id", None)

# === MÜŞTƏRİ PORTALI ===
if card_id:
    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf", use_container_width=True)
    if supabase:
        response = supabase.table("customers").select("*").eq("card_id", card_id).execute()
        user_data = response.data[0] if response.data else None
        stars = user_data['stars'] if user_data else 0
        
        st.markdown(f"<h2 style='text-align: center;'>Sənin Kartın: {stars}/10</h2>", unsafe_allow_html=True)
        
        cols = st.columns(5)
        for i in range(10):
            if i == 5: cols = st.columns(5)
            icon = "⭐" if i < stars else "⚪"
            cols[i % 5].markdown(f"<h3 style='text-align: center;'>{icon}</h3>", unsafe_allow_html=True)

        st.progress(stars / 10)
        st.info(get_motivational_msg(stars))
        if stars == 0 and user_data:
            st.success("🎉 Nuş olsun! Pulsuz kofeniz verildikdən sonra sayğac sıfırlandı.")

# === BARISTA PANELİ (Avtomatik Rejim) ===
else:
    st.sidebar.header("🔐 Giriş")
    
    # Giriş edilməyibsə
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        pwd = st.sidebar.text_input("Şifrə", type="password")
        if pwd == "1234":
            st.session_state.logged_in = True
            st.rerun()
    
    # Giriş edilibsə
    else:
        st.title("☕ Barista Terminalı")
        
        # --- INPUT XANASI ---
        # on_change=process_scan -> Enter basılan kimi funksiya işə düşür və xananı təmizləyir
        st.text_input("Barkodu Oxut:", key="scanner_input", on_change=process_scan, help="Skaneri bura tuşla")
        
        st.markdown("---")
        
        # --- NƏTİCƏNİ GÖSTƏR ---
        if 'last_result' in st.session_state:
            res = st.session_state['last_result']
            
            st.caption(f"Son əməliyyat: {res['time']} | Kart: {res['card']}")
            
            if res['type'] == 'error':
                st.error(res['msg'], icon="🎁")
                st.balloons()
            else:
                st.success(res['msg'], icon="☕")
            
        # Son Aktivliklər Cədvəli
        st.divider()
        st.caption("📋 Son aktivliklər:")
        if supabase:
            recent = supabase.table("customers").select("*").order("last_visit", desc=True).limit(5).execute()
            st.dataframe(recent.data)
