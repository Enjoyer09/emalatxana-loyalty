import streamlit as st
import pandas as pd
from database import run_query
import datetime
from utils import get_baku_now

# --- 1. POP-UP (DİALOQ) PƏNCƏRƏLƏRİ ---

@st.dialog("📱 Sizin QR Kodunuz")
def show_qr_dialog(customer_id):
    st.markdown("<p style='text-align:center; color:#555;'>Sifariş verərkən ulduz qazanmaq üçün bu kodu kassada oxudun.</p>", unsafe_allow_html=True)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=2A4B2D&bgcolor=ffffff"
    st.markdown(f"<div style='text-align:center;'><img src='{qr_url}' style='width:200px; height:200px; box-shadow: 0 5px 15px rgba(42,75,45,0.15); border-radius:15px; border: 4px solid #E88D48;'/></div>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center; margin-top:20px; font-weight:900; color:#2A4B2D; letter-spacing: 2px;'>{customer_id}</h3>", unsafe_allow_html=True)
    st.info("💡 Şəklin üzərinə basılı tutaraq 'Save Image' seçin və Qalereyada saxlayın.")

@st.dialog("📋 Emalatkhana Menyusu")
def show_menu_dialog():
    menu_df = run_query("SELECT id, item_name, price, category FROM menu WHERE is_active=TRUE")
    if menu_df.empty:
        st.warning("Menyu hazırda yenilənir...")
    else:
        st.markdown("<p style='text-align:center; font-size:14px; color:#555;'>Sifarişlərinizi kassada ofisianta yaxınlaşaraq verə bilərsiniz.</p>", unsafe_allow_html=True)
        cats = ["HAMISI"] + sorted(menu_df['category'].dropna().unique().tolist())
        selected_cat = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed")
        if selected_cat != "HAMISI": 
            menu_df = menu_df[menu_df['category'] == selected_cat]

        for _, item in menu_df.iterrows():
            st.markdown(f"""
            <div style="background:#f8f9fa; padding:15px; margin-bottom:10px; border-radius:12px; border:1px solid #eee; display:flex; justify-content:space-between;">
                <b style="color:#2A4B2D; font-size:16px;">{item['item_name']}</b>
                <span style="color:#E88D48; font-weight:900; font-size:16px;">{float(item['price']):.2f} ₼</span>
            </div>
            """, unsafe_allow_html=True)

@st.dialog("🎁 Günün Təklifləri")
def show_promos_dialog():
    campaigns = run_query("SELECT * FROM campaigns WHERE is_active=TRUE ORDER BY id DESC")
    if not campaigns.empty:
        for _, camp in campaigns.iterrows():
            bg_img = camp['img_url'] if camp['img_url'] else "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&q=80&w=600"
            badge_html = f"<span style='background:#E88D48; color:#fff; padding:3px 8px; border-radius:5px; font-size:11px; font-weight:bold;'>{camp['badge']}</span>" if camp['badge'] else ""
            st.markdown(f"""
            <div style="border-radius:15px; overflow:hidden; border:1px solid #eee; margin-bottom:15px; box-shadow:0 4px 10px rgba(0,0,0,0.05);">
                <div style="height:120px; background-image:url('{bg_img}'); background-size:cover; background-position:center; padding:10px; display:flex; align-items:flex-start;">{badge_html}</div>
                <div style="padding:15px;">
                    <h4 style="margin:0; color:#2A4B2D; font-weight:900;">{camp['title']}</h4>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#666;">{camp['description']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Hazırda aktiv kampaniya yoxdur.")

@st.dialog("🤖 AI Barista & Rəy")
def show_coming_soon_dialog():
    st.markdown("<h3 style='text-align:center; color:#E88D48;'>Tezliklə! 🚀</h3>", unsafe_allow_html=True)
    st.write("Bu funksiya növbəti yenilənmədə aktiv olacaq. Bizimlə qaldığınız üçün təşəkkürlər!")


# --- 2. ƏSAS EKRAN (DASHBOARD) ---
def render_customer_app(customer_id=None):
    # CSS DİZAYNI: Şəkildəki kimi təmiz fon, yuvarlaq kənarlar və spesifik düymələr
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;800;900&display=swap');
.stApp { background: #FAF5EF !important; font-family: 'Nunito', sans-serif !important; }
#MainMenu, header, footer { display: none !important; }
.block-container { padding: 0 !important; max-width: 100%; padding-bottom: 50px !important; }

/* Narıncı Arxa Plan (Hero) */
.hero-bg {
    background: linear-gradient(135deg, #F09A55 0%, #E88D48 100%);
    padding: 40px 20px 80px 20px;
    border-bottom-left-radius: 30px;
    border-bottom-right-radius: 30px;
}

/* Ağ Klub Kartı (Overlap) */
.club-card {
    background: #ffffff;
    border-radius: 20px;
    padding: 20px;
    margin: -60px 20px 20px 20px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #f0f0f0;
}

/* Düymələrin Stilini Dəyişmək */
button[kind="primary"] {
    background-color: #E88D48 !important;
    border: none !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 15px rgba(232, 141, 72, 0.4) !important;
    color: white !important;
    font-weight: 900 !important;
    padding: 15px !important;
    font-size: 16px !important;
}
button[kind="secondary"] {
    background-color: #ffffff !important;
    border: none !important;
    border-radius: 15px !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.04) !important;
    color: #333 !important;
    font-weight: 800 !important;
    height: 80px !important;
}
button[kind="secondary"] p { font-size: 14px !important; }
</style>
    """, unsafe_allow_html=True)

    if not customer_id:
        st.error("⚠️ QR Kod oxunmadı.")
        return

    c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
    if c_df.empty:
        st.error("⚠️ Müştəri tapılmadı.")
        return
        
    cust_data = c_df.iloc[0].to_dict()
    stars = cust_data.get('stars', 0)
    c_type = str(cust_data.get('type', 'Standard')).upper()
    
    current_progress = int(stars % 10)
    remaining = 10 - current_progress
    svg_fill = current_progress * 10
    
    # Dinamik Salamlaşma (Şəkildəki kimi)
    hour = get_baku_now().hour
    if 5 <= hour < 12: greeting = "Sabahınız xeyir! Kofe vaxtıdır ☕"
    elif 12 <= hour < 18: greeting = "Günortanız xeyir! Günə enerji qatın ☀️"
    else: greeting = "Axşamınız xeyir! Rahatlamaq vaxtıdır 🌙"

    # 1. NARINCI HEADER (HERO BG)
    st.markdown(f"""
    <div class="hero-bg">
        <h2 style="text-align:center; color:#ffffff; font-weight:900; margin:0; font-size:22px;">EMALATKHANA POS</h2>
        <p style="text-align:center; color:#ffffff; font-size:13px; margin-top:5px; opacity:0.9;">{greeting}</p>
    </div>
    """, unsafe_allow_html=True)

    # 2. AĞ KLUB KARTI (OVERLAP) - Şəkildəki FÜZULİ CLUB bloku
    badge_color = "#3498db" if c_type == "GOLDEN" else "#e74c3c" if c_type == "PLATINUM" else "#9b59b6" if c_type == "ELITE" else "#95a5a6"
    
    st.markdown(f"""
    <div class="club-card">
        <div>
            <h3 style="margin:0; font-weight:900; color:#2A4B2D; font-size:18px;">EMALATKHANA CLUB</h3>
            <p style="margin:5px 0 10px 0; font-size:12px; color:#666;">Pulsuz içkiyə <b>{remaining}</b> ulduz qaldı!</p>
            <span style="font-size:10px; font-weight:bold; color:{badge_color}; background:rgba(0,0,0,0.05); padding:3px 8px; border-radius:10px;">
                💎 {c_type}
            </span>
        </div>
        <div style="position:relative; width:70px; height:70px;">
            <svg viewBox="0 0 36 36" style="width:70px; height:70px; transform: rotate(-90deg);">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#f0f0f0" stroke-width="3"/>
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#E88D48" stroke-width="3" stroke-linecap="round" stroke-dasharray="{svg_fill}, 100" />
            </svg>
            <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); text-align:center; line-height:1.2;">
                <span style="font-size:16px; font-weight:900; color:#2A4B2D;">{current_progress}<span style="font-size:12px;">/10</span></span><br>
                <span style="font-size:8px; font-weight:bold; color:#888;">ULDUZ</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. QR KOD DÜYMƏSİ (Şəkildəki narıncı düymə)
    st.markdown("<div style='padding: 0 20px;'>", unsafe_allow_html=True)
    if st.button("⏹ MƏNİM QR KODUM", type="primary", use_container_width=True):
        show_qr_dialog(customer_id)
    st.markdown("</div>", unsafe_allow_html=True)

    # 4. 4-LÜ GRID DÜYMƏLƏR (Menyu, AI Barista, Təkliflər, Rəy Bildir)
    st.markdown("<div style='padding: 15px 20px;'>", unsafe_allow_html=True)
    
    r1_col1, r1_col2 = st.columns(2)
    with r1_col1:
        if st.button("📋 Menyu", use_container_width=True): show_menu_dialog()
    with r1_col2:
        if st.button("🤖 AI Barista", use_container_width=True): show_coming_soon_dialog()
        
    r2_col1, r2_col2 = st.columns(2)
    with r2_col1:
        if st.button("🎁 Təkliflər", use_container_width=True): show_promos_dialog()
    with r2_col2:
        if st.button("💬 Rəy Bildir", use_container_width=True): show_coming_soon_dialog()

    st.markdown("</div>", unsafe_allow_html=True)
