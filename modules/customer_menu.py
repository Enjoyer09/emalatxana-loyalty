# modules/customer_menu.py — TIM HORTONS STYLE v3.0 (Emalatkhana Edition)
import streamlit as st
import pandas as pd
import json
import logging
import io
import time
import datetime

from database import run_query, run_action, get_setting
from utils import BRAND_NAME, get_baku_now, safe_decimal

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from PIL import Image
except ImportError:
    Image = None


# ============================================================
# MOBİL CSS — TİM HORTONS STİLİ (Qızılı/Tünd)
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;700;800&family=Nunito:wght@400;600;700;800;900&display=swap');

    /* ===== ƏSAS LAYOUT ===== */
    .stApp { 
        background: #0D0D0D !important; 
        color: #E8E8E8 !important; 
        font-family: 'Nunito', sans-serif !important; 
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section.main > div:first-child { padding-top: 0 !important; }

    /* ===== HERO HEADER ===== */
    .ek-hero {
        background: linear-gradient(160deg, #1A1A1A 0%, #0D0D0D 100%);
        padding: 30px 20px 20px 20px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .ek-hero::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle at 30% 50%, rgba(212,175,55,0.08) 0%, transparent 50%);
        pointer-events: none;
    }
    .ek-brand {
        font-family: 'Jura', sans-serif;
        font-weight: 800;
        font-size: 26px;
        color: #D4AF37;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 5px;
        text-shadow: 0 2px 10px rgba(212,175,55,0.3);
    }
    .ek-greeting {
        font-size: 14px;
        color: #888;
        font-weight: 600;
    }

    /* ===== LOYALTY CARD ===== */
    .loyalty-card {
        background: linear-gradient(145deg, #D4AF37 0%, #B8962E 50%, #9A7B22 100%);
        border-radius: 24px;
        padding: 28px 24px;
        margin: 15px 16px;
        position: relative;
        overflow: hidden;
        box-shadow: 
            0 15px 40px rgba(212,175,55,0.25),
            0 5px 15px rgba(0,0,0,0.3),
            inset 0 1px 0 rgba(255,255,255,0.2);
    }
    .loyalty-card::after {
        content: '☕';
        position: absolute;
        right: -10px;
        bottom: -15px;
        font-size: 120px;
        opacity: 0.08;
    }
    .lc-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 20px;
    }
    .lc-club-name {
        font-family: 'Jura', sans-serif;
        font-weight: 800;
        font-size: 13px;
        color: rgba(0,0,0,0.5);
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    .lc-tier {
        background: rgba(0,0,0,0.15);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 800;
        color: #000;
        letter-spacing: 1px;
    }
    .lc-stars-row {
        display: flex;
        justify-content: center;
        gap: 6px;
        margin: 15px 0;
    }
    .lc-star {
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        transition: all 0.3s;
    }
    .lc-star-empty {
        background: rgba(0,0,0,0.12);
        border: 2px solid rgba(0,0,0,0.08);
        color: rgba(0,0,0,0.2);
    }
    .lc-star-filled {
        background: #000;
        border: 2px solid rgba(255,255,255,0.1);
        color: #D4AF37;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .lc-info {
        text-align: center;
        font-size: 13px;
        color: rgba(0,0,0,0.6);
        font-weight: 700;
    }
    .lc-free-badge {
        text-align: center;
        margin-top: 12px;
        padding: 8px;
        background: rgba(0,0,0,0.15);
        border-radius: 12px;
        font-weight: 900;
        font-size: 14px;
        color: #000;
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 
        0%, 100% { transform: scale(1); } 
        50% { transform: scale(1.02); } 
    }

    /* ===== NAV GRID ===== */
    .nav-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        padding: 0 16px;
        margin-bottom: 15px;
    }
    .nav-card {
        background: #1A1A1A;
        border: 1px solid #2A2A2A;
        border-radius: 18px;
        padding: 20px 15px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s;
    }
    .nav-card:active { transform: scale(0.97); background: #222; }
    .nav-icon { font-size: 32px; margin-bottom: 8px; }
    .nav-label { font-size: 13px; font-weight: 800; color: #CCC; }

    /* ===== MENYU ===== */
    .menu-section-title {
        font-family: 'Jura', sans-serif;
        font-size: 16px;
        font-weight: 800;
        color: #D4AF37;
        letter-spacing: 1px;
        margin: 20px 16px 10px;
        text-transform: uppercase;
    }
    .menu-item-card {
        background: #1A1A1A;
        border: 1px solid #2A2A2A;
        border-radius: 16px;
        padding: 16px;
        margin: 0 16px 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .mi-name { font-weight: 700; font-size: 15px; color: #FFF; }
    .mi-cat { font-size: 11px; color: #666; margin-top: 3px; }
    .mi-price { 
        font-weight: 900; 
        font-size: 18px; 
        color: #D4AF37; 
        font-family: 'Jura', sans-serif;
    }
    .mi-star-badge {
        font-size: 10px;
        color: #D4AF37;
        background: rgba(212,175,55,0.1);
        padding: 2px 8px;
        border-radius: 10px;
        margin-top: 4px;
        display: inline-block;
    }

    /* ===== TARİXÇƏ ===== */
    .history-card {
        background: #1A1A1A;
        border: 1px solid #2A2A2A;
        border-radius: 16px;
        padding: 16px;
        margin: 0 16px 10px;
        border-left: 4px solid #D4AF37;
    }
    .hc-date { font-size: 12px; color: #666; margin-bottom: 6px; }
    .hc-items { font-size: 14px; color: #DDD; line-height: 1.4; }
    .hc-total { font-size: 16px; font-weight: 900; color: #D4AF37; margin-top: 8px; font-family: 'Jura'; }

    /* ===== BANNER ===== */
    .promo-banner {
        background: linear-gradient(135deg, #D4AF37, #F0D060);
        color: #000;
        padding: 16px 20px;
        border-radius: 16px;
        margin: 10px 16px;
        text-align: center;
        font-weight: 800;
        font-size: 14px;
        box-shadow: 0 8px 25px rgba(212,175,55,0.3);
        animation: slideIn 0.6s ease-out;
    }
    @keyframes slideIn { from { transform: translateY(-30px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

    /* ===== CHAT ===== */
    .chat-bubble {
        padding: 14px 18px;
        border-radius: 20px;
        margin-bottom: 10px;
        max-width: 85%;
        font-size: 15px;
        line-height: 1.5;
        word-wrap: break-word;
    }
    .chat-user {
        background: #D4AF37;
        color: #000;
        margin-left: auto;
        border-bottom-right-radius: 6px;
        font-weight: 700;
    }
    .chat-ai {
        background: #1E1E1E;
        color: #EEE;
        margin-right: auto;
        border-bottom-left-radius: 6px;
        border: 1px solid #333;
    }

    /* ===== FORTUNE ===== */
    .fortune-zone {
        border: 2px dashed #333;
        border-radius: 24px;
        padding: 40px 20px;
        text-align: center;
        margin: 20px 16px;
        background: #111;
    }
    .fortune-result {
        background: #1A1A1A;
        border: 2px solid #D4AF37;
        border-radius: 20px;
        padding: 24px;
        margin: 20px 16px;
        position: relative;
        overflow: hidden;
    }
    .fortune-result::before {
        content: '🔮';
        position: absolute;
        right: 10px;
        top: 10px;
        font-size: 40px;
        opacity: 0.15;
    }

    /* ===== STREAMLIT OVERRİDES ===== */
    div[data-baseweb="input"] > div { 
        background: #1A1A1A !important; 
        border: 2px solid #333 !important; 
        border-radius: 14px !important; 
    }
    div[data-baseweb="input"] input { 
        color: #FFF !important; 
        font-weight: 600 !important;
        -webkit-text-fill-color: #FFF !important;
    }
    div[data-baseweb="input"] input::placeholder { 
        color: #555 !important; 
        -webkit-text-fill-color: #555 !important;
    }
    
    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #D4AF37 0%, #B8962E 100%) !important;
        border: none !important;
        border-radius: 14px !important;
        color: #000 !important;
        font-weight: 900 !important;
        box-shadow: 0 5px 20px rgba(212,175,55,0.3) !important;
    }
    button[kind="primary"] p { color: #000 !important; font-weight: 900 !important; }
    
    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background: #1A1A1A !important;
        border: 1px solid #333 !important;
        border-radius: 14px !important;
        color: #DDD !important;
    }
    button[kind="secondary"] p { color: #DDD !important; font-weight: 700 !important; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    div[role="radiogroup"] > label {
        background: #1A1A1A !important;
        border: 1px solid #333 !important;
        border-radius: 12px !important;
        padding: 8px 16px !important;
    }
    div[role="radiogroup"] > label p { color: #CCC !important; font-size: 13px !important; }
    div[role="radiogroup"] label:has(input:checked) {
        background: #D4AF37 !important;
        border-color: #D4AF37 !important;
    }
    div[role="radiogroup"] label:has(input:checked) p { color: #000 !important; font-weight: 900 !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 0; background: #111; border-radius: 14px; padding: 4px; margin: 0 16px; }
    .stTabs [data-baseweb="tab"] { 
        border-radius: 12px !important; 
        color: #888 !important; 
        font-weight: 700 !important;
        font-size: 13px !important;
    }
    .stTabs [aria-selected="true"] { 
        background: #D4AF37 !important; 
        color: #000 !important; 
        font-weight: 900 !important;
    }

    div[role="dialog"] > div {
        background: #0D0D0D !important;
        border: 2px solid #D4AF37 !important;
        border-radius: 20px !important;
    }

    .stFileUploader > div { background: #111 !important; border: 2px dashed #333 !important; border-radius: 16px !important; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# AI HELPER
# ============================================================
def get_ai_model():
    api_key = get_setting("gemini_api_key", "")
    if not api_key or genai is None:
        return None, None
    try:
        genai.configure(api_key=api_key)
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not valid_models:
            return None, None
        chosen = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0])
        return genai.GenerativeModel(chosen), valid_models
    except Exception as e:
        logger.error(f"AI model init failed: {e}")
        return None, None


# ============================================================
# LOYALTY CARD
# ============================================================
def render_loyalty_card(stars, cust_type):
    tier_map = {
        "standard": "QONAQ", "golden": "GOLD",
        "platinum": "PLATINUM", "elite": "ELITE",
        "thermos": "THERMOS", "telebe": "TƏLƏBƏ", "ikram": "İKRAM"
    }
    tier = tier_map.get(str(cust_type).lower(), "QONAQ")

    current = int(stars or 0)
    filled = current % 10
    free_count = current // 10
    remaining = 10 - filled

    stars_html = ""
    for i in range(10):
        if i < filled:
            stars_html += '<div class="lc-star lc-star-filled">★</div>'
        else:
            stars_html += '<div class="lc-star lc-star-empty">☆</div>'

    free_html = ""
    if free_count > 0:
        free_html = f'<div class="lc-free-badge">🎁 {free_count} PULSUZ KOFENİZ HAZIRDIR!</div>'

    st.markdown(f"""
    <div class="loyalty-card">
        <div class="lc-header">
            <div class="lc-club-name">EMALATKHANA CLUB</div>
            <div class="lc-tier">💎 {tier}</div>
        </div>
        <div class="lc-stars-row">{stars_html}</div>
        <div class="lc-info">Pulsuz kofeyə <b>{remaining}</b> ulduz qalıb ☕</div>
        {free_html}
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# QR KOD DİALOQ
# ============================================================
@st.dialog("📱 Sizin QR Kodunuz")
def show_qr_dialog(customer_id):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=D4AF37&bgcolor=0D0D0D"
    st.markdown(f"""
    <div style="text-align:center; padding: 20px;">
        <img src="{qr_url}" style="width:200px; height:200px; border-radius:20px; border:4px solid #D4AF37; box-shadow: 0 10px 30px rgba(212,175,55,0.3);"/>
        <h3 style="margin-top:20px; font-family:'Jura'; font-weight:900; color:#D4AF37; letter-spacing:3px;">{customer_id}</h3>
        <p style="color:#888; font-size:13px;">Kassada QR kodunuzu oxudun və ulduz qazanın!</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# MENYU
# ============================================================
def render_menu_section():
    menu_df = run_query("SELECT item_name, price, category, is_coffee FROM menu WHERE is_active=TRUE ORDER BY category, item_name")

    if menu_df.empty:
        st.info("Menyu hazırda yenilənir...")
        return

    st.markdown("<p style='text-align:center; color:#666; font-size:13px; margin: 10px 0;'>Sifarişlərinizi kassada verə bilərsiniz</p>", unsafe_allow_html=True)

    categories = menu_df['category'].dropna().unique().tolist()
    cats = ["Hamısı"] + sorted(categories)
    sel_cat = st.radio("Kateqoriya", cats, horizontal=True, label_visibility="collapsed", key="cust_menu_cat")

    if sel_cat != "Hamısı":
        menu_df = menu_df[menu_df['category'] == sel_cat]

    for _, item in menu_df.iterrows():
        star_badge = '<div class="mi-star-badge">⭐ Ulduz qazan!</div>' if item['is_coffee'] else ""
        st.markdown(f"""
        <div class="menu-item-card">
            <div>
                <div class="mi-name">{item['item_name']}</div>
                <div class="mi-cat">{item['category'] or ''}</div>
                {star_badge}
            </div>
            <div class="mi-price">{float(item['price']):.2f} ₼</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# SİFARİŞ TARİXÇƏSİ
# ============================================================
def render_history_section(card_id):
    sales = run_query(
        "SELECT items, total, created_at, payment_method FROM sales WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) ORDER BY created_at DESC LIMIT 20",
        {"cid": card_id}
    )

    if sales.empty:
        st.markdown("""
        <div style="text-align:center; padding: 40px 20px; color: #555;">
            <div style="font-size: 48px; margin-bottom: 15px;">📋</div>
            <div style="font-size: 16px; font-weight: 700;">Hələ sifariş yoxdur</div>
            <div style="font-size: 13px; margin-top: 5px;">İlk sifarişinizi verin və ulduz qazanmağa başlayın!</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for _, row in sales.iterrows():
        try:
            date_str = row['created_at'].strftime("%d.%m.%Y • %H:%M") if pd.notna(row['created_at']) else "-"
        except:
            date_str = "-"

        try:
            items = json.loads(row['items'])
            items_str = " · ".join([f"{i['item_name']} ×{i['qty']}" for i in items])
        except:
            items_str = str(row['items'])[:60]

        pm_icon = "💵" if row.get('payment_method') in ['Nəğd', 'Cash'] else "💳"

        st.markdown(f"""
        <div class="history-card">
            <div class="hc-date">{date_str} {pm_icon}</div>
            <div class="hc-items">{items_str}</div>
            <div class="hc-total">{float(row['total']):.2f} ₼</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# BİLDİRİŞLƏR / BANNER
# ============================================================
def check_and_show_notifications(card_id):
    try:
        notifs = run_query(
            "SELECT id, message FROM notifications WHERE card_id=:cid AND (is_read IS NULL OR is_read=FALSE) ORDER BY created_at DESC LIMIT 1",
            {"cid": card_id}
        )
        if not notifs.empty:
            msg = notifs.iloc[0]['message']
            notif_id = notifs.iloc[0]['id']
            st.markdown(f'<div class="promo-banner">🎉 {msg}</div>', unsafe_allow_html=True)
            if st.button("✓ Oxudum", key="dismiss_notif", use_container_width=True):
                run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id": notif_id})
                st.rerun()
    except Exception:
        pass


# ============================================================
# AI BARİSTA
# ============================================================
def render_ai_barista():
    st.markdown("""
    <div style="text-align:center; padding: 15px 16px 5px;">
        <div style="font-size: 40px;">🤖</div>
        <div style="font-family: 'Jura'; font-weight: 800; color: #D4AF37; font-size: 18px; margin-top: 5px;">AI BARİSTA</div>
        <div style="color: #666; font-size: 13px; margin-top: 5px;">Əhvalınızı yazın, sizə ideal kofe seçim!</div>
    </div>
    """, unsafe_allow_html=True)

    if 'barista_chat' not in st.session_state:
        st.session_state.barista_chat = []

    # Chat history
    for msg in st.session_state.barista_chat:
        css = "chat-user" if msg['role'] == 'user' else "chat-ai"
        st.markdown(f'<div class="chat-bubble {css}">{msg["text"]}</div>', unsafe_allow_html=True)

    # Input
    col1, col2 = st.columns([5, 1])
    with col1:
        user_msg = st.text_input("Mesaj", placeholder="Yuxuluyam, mənə güclü nəsə...", label_visibility="collapsed", key="barista_input")
    with col2:
        send = st.button("📤", key="barista_send")

    if send and user_msg.strip():
        st.session_state.barista_chat.append({'role': 'user', 'text': user_msg})

        model, _ = get_ai_model()
        if model:
            try:
                menu_df = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE")
                menu_text = ", ".join([f"{r['item_name']} ({r['price']} ₼)" for _, r in menu_df.iterrows()]) if not menu_df.empty else "Menyu boşdur"

                prompt = f"""Sən 'Emalatkhana' kofe şopunun gənc, mehriban və zarafatcıl AI Baristasısan.
Menyumuz: {menu_text}

Müştəri deyir: '{user_msg}'

YALNIZ menyudan 1-2 məhsul təklif et. Qısa (2-3 cümlə), səmimi, emoji ilə cavab ver. Qiymətləri yaz. 
Sonda 'Kassaya yaxınlaşıb sifariş verə bilərsiniz! ☕' əlavə et."""

                response = model.generate_content(prompt)
                ai_text = response.text
            except Exception as e:
                ai_text = "Bağışla, bir az başım qarışdı ☕ Bir daha yaz!"
                logger.error(f"AI Barista error: {e}")
        else:
            ai_text = "AI bağlantısı yoxdur 🔌 Zəhmət olmasa kassada soruşun!"

        st.session_state.barista_chat.append({'role': 'ai', 'text': ai_text})
        st.rerun()

    if st.session_state.barista_chat:
        if st.button("🗑️ Söhbəti Təmizlə", use_container_width=True, key="clear_chat"):
            st.session_state.barista_chat = []
            st.rerun()


# ============================================================
# KOFE FALI (Şəkil + AI Vision)
# ============================================================
def render_fortune_teller():
    st.markdown("""
    <div style="text-align:center; padding: 15px 16px 5px;">
        <div style="font-size: 48px;">🔮</div>
        <div style="font-family: 'Jura'; font-weight: 800; color: #D4AF37; font-size: 20px; margin-top: 8px;">KOFE FALI</div>
        <div style="color: #666; font-size: 13px; margin-top: 5px;">Kofenizin fincanını çəkin, falınıza baxaq!</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="fortune-zone">
        <div style="font-size: 60px; margin-bottom: 15px;">☕📸</div>
        <div style="color: #888; font-weight: 700;">Fincanın dibinin şəklini çəkin</div>
        <div style="color: #555; font-size: 12px; margin-top: 8px;">Daha yaxşı nəticə üçün yaxından, işıqlı mühitdə çəkin</div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader("Şəkil seçin", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed", key="fortune_upload")

    if uploaded:
        st.image(uploaded, use_container_width=True)

        if st.button("🔮 Falıma Bax!", type="primary", use_container_width=True, key="fortune_btn"):
            with st.spinner("Falçı fincanı oxuyur... 🔮✨"):
                model, all_models = get_ai_model()
                if not model:
                    st.error("AI falçı yuxudadır 😴")
                    return

                try:
                    # Vision model seç
                    vision_model_name = None
                    if all_models:
                        for m in all_models:
                            if 'vision' in m.lower() or 'flash' in m.lower():
                                vision_model_name = m
                                break
                        if not vision_model_name:
                            vision_model_name = all_models[0]

                    vision_model = genai.GenerativeModel(vision_model_name)

                    if Image:
                        img = Image.open(uploaded)

                        prompt = """Sən məşhur Azərbaycan falçısısan. Bu şəkildə kofe fincanının dibini görürsən.
Fincanın dibindəki formaları, xətləri, şəkilləri 'görürsən' kimi yorum et.
Müsbət, ümidverici və əyləncəli fal de. 4-5 cümlə yaz.
Mövzular: sevgi, iş/karyera, pul, səyahət, sağlamlıq (birini seç).
Azərbaycan dilində, emoji ilə, sirli üslubda yaz.
Sonda bir xoşbəxt cümlə əlavə et."""

                        response = vision_model.generate_content([prompt, img])
                    else:
                        prompt = """Sən Azərbaycan falçısısan. Bir müştəri fincanını gətirib.
Ümumi, müsbət və əyləncəli kofe falı de. 4-5 cümlə.
Azərbaycan dilində, emoji ilə, sirli üslubda."""
                        response = model.generate_content(prompt)

                    st.markdown(f"""
                    <div class="fortune-result">
                        <div style="text-align:center; font-size: 28px; margin-bottom: 15px;">🔮 ✨</div>
                        <div style="font-family: 'Jura'; font-weight: 800; color: #D4AF37; text-align:center; margin-bottom: 15px; font-size: 16px;">SİZİN FALINIZ</div>
                        <div style="color: #DDD; line-height: 1.7; font-size: 15px;">{response.text}</div>
                        <div style="text-align:center; margin-top: 20px; font-size: 12px; color: #555;">
                            ☕ Emalatkhana · Falınız xeyirli olsun!
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Fal xətası: {e}")
                    logger.error(f"Fortune teller error: {e}", exc_info=True)


# ============================================================
# ƏSAS FUNKSİYA
# ============================================================
def render_customer_app(customer_id=None):
    inject_customer_css()

    if not customer_id:
        st.error("⚠️ QR Kod oxunmadı.")
        return

    # Müştəri data
    c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
    if c_df.empty:
        st.error("⚠️ Müştəri tapılmadı.")
        return

    cust = c_df.iloc[0].to_dict()
    stars = cust.get('stars', 0)
    c_type = str(cust.get('type', 'standard'))

    # Salamlama
    hour = get_baku_now().hour
    if 5 <= hour < 12:
        greeting = "Sabahınız xeyir ☕"
    elif 12 <= hour < 18:
        greeting = "Günortanız xeyir ☀️"
    else:
        greeting = "Axşamınız xeyir 🌙"

    # HERO
    st.markdown(f"""
    <div class="ek-hero">
        <div class="ek-brand">EMALATKHANA</div>
        <div class="ek-greeting">{greeting}</div>
    </div>
    """, unsafe_allow_html=True)

    # Bildirişlər
    check_and_show_notifications(customer_id)

    # Loyalty Card
    render_loyalty_card(stars, c_type)

    # QR Button
    st.markdown("<div style='padding: 0 16px;'>", unsafe_allow_html=True)
    if st.button("📱 MƏNİM QR KODUM", type="primary", use_container_width=True, key="show_qr"):
        show_qr_dialog(customer_id)
    st.markdown("</div>", unsafe_allow_html=True)

    # TAB Navigation
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Menyu", "📜 Tarixçə", "🤖 Barista", "🔮 Fal"])

    with tab1:
        render_menu_section()

    with tab2:
        render_history_section(customer_id)

    with tab3:
        render_ai_barista()

    with tab4:
        render_fortune_teller()

    # Footer
    st.markdown("""
    <div style="text-align:center; padding: 30px 0 20px; color: #333;">
        <div style="font-family: 'Jura'; font-weight: 800; font-size: 12px; letter-spacing: 2px; color: #444;">EMALATKHANA</div>
        <div style="font-size: 11px; color: #333; margin-top: 4px;">Crafted with ☕ & ❤️</div>
    </div>
    """, unsafe_allow_html=True)
