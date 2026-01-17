import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# --- Səhifə Ayarları ---
st.set_page_config(page_title="Emalatxana Loyalty", page_icon="☕", layout="centered")

# CSS - Dizaynı səliqəyə salmaq üçün
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 10px; height: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- Supabase Qoşulması ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        st.error("Supabase əlaqəsi qurulmadı. Secrets-i yoxlayın.")
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

# --- Əsas Məntiq ---
# URL parametrlərini oxu
query_params = st.query_params
card_id = query_params.get("id", None)

# === MÜŞTƏRİ PORTALI (Əgər linkdə ?id= varsa) ===
if card_id:
    # Şəkil (Header)
    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf", use_container_width=True)
    
    # Məlumatı çək
    if supabase:
        response = supabase.table("customers").select("*").eq("card_id", card_id).execute()
        user_data = response.data[0] if response.data else None
        
        stars = user_data['stars'] if user_data else 0
        
        # Başlıq
        st.markdown(f"<h2 style='text-align: center;'>Sənin Kartın: {stars}/10</h2>", unsafe_allow_html=True)
        
        # Ulduz Vizualizasiyası
        cols = st.columns(5)
        for i in range(10):
            if i == 5: cols = st.columns(5) # İkinci sətrə keçid
            icon = "⭐" if i < stars else "⚪"
            cols[i % 5].markdown(f"<h3 style='text-align: center;'>{icon}</h3>", unsafe_allow_html=True)

        st.progress(stars / 10)
        st.info(get_motivational_msg(stars))
        
        if stars == 0 and user_data:
            st.success("🎉 Nuş olsun! Pulsuz kofeniz verildikdən sonra sayğac sıfırlandı.")

# === BARISTA PANELİ (Əgər link sadədirsə) ===
else:
    st.sidebar.header("🔐 Giriş")
    pwd = st.sidebar.text_input("Şifrə", type="password")
    
    if pwd == "1234": # Şifrəni burdan dəyişə bilərsən
        st.title("☕ Barista Terminalı")
        
        # Skaner avtomatik "Enter" basır
        scan_code = st.text_input("Barkodu Oxut:", key="scanner", help="Skaneri bura tuşla")
        
        if scan_code and supabase:
            # Müştərini yoxla
            res = supabase.table("customers").select("*").eq("card_id", scan_code).execute()
            current_stars = res.data[0]['stars'] if res.data else 0
            
            # Məntiq
            new_stars = current_stars + 1
            msg = "✅ Ulduz əlavə olundu."
            is_free = False
            
            if new_stars >= 10:
                new_stars = 0 # 10 olanda sıfırlanır
                is_free = True
                msg = "🎁 PULSUZ KOFE VERİLMƏLİDİR!"
            
            # Bazanı yenilə
            data = {
                "card_id": scan_code, 
                "stars": new_stars, 
                "last_visit": datetime.now().isoformat()
            }
            supabase.table("customers").upsert(data).execute()
            
            # Ekrana nəticə çıxar
            if is_free:
                st.balloons()
                st.error(msg, icon="🎁")
                st.audio("https://www.soundjay.com/buttons/sounds/button-3.mp3")
            else:
                st.success(f"{msg} (Hazırda: {new_stars})", icon="☕")
                
            # Son 5 müştəri (Admin üçün)
            st.divider()
            st.caption("Son aktivliklər:")
            recent = supabase.table("customers").select("*").order("last_visit", desc=True).limit(5).execute()
            st.dataframe(recent.data)
            
    elif pwd:
        st.warning("Şifrə səhvdir")