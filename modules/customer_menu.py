# modules/customer_menu.py — TIM HORTONS STYLE v4.0 (Warm & Compact)
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
# TİM HORTONS STİLİ CSS (Warm Red + Cream + Compact)
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

    /* ===== BASE ===== */
    .stApp { 
        background: #FAF6F1 !important; 
        color: #2D2926 !important; 
        font-family: 'Nunito', sans-serif !important; 
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section.main > div:first-child { padding-top: 0 !important; }

    /* ===== HERO ===== */
    .th-hero {
        background: linear-gradient(160deg, #C8102E 0%, #A50D22 100%);
        padding: 28px 20px 22px;
        text-align: center;
        position: relative;
    }
    .th-hero::after {
        content: '';
        position: absolute;
        bottom: -15px;
        left: 0;
        right: 0;
        height: 30px;
        background: #FAF6F1;
        border-radius: 50% 50% 0 0;
    }
    .th-logo {
        font-weight: 900;
        font-size: 22px;
        color: #FFFFFF;
        letter-spacing: 2px;
    }
    .th-greeting {
        font-size: 13px;
        color: rgba(255,255,255,0.8);
        margin-top: 4px;
    }

    /* ===== LOYALTY CARD (Compact) ===== */
    .th-card {
        background: #FFFFFF;
        border-radius: 20px;
        padding: 18px 16px;
        margin: 5px 16px 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        border: 1px solid #F0ECE6;
    }
    .th-card-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
    }
    .th-card-title {
        font-weight: 900;
        font-size: 15px;
        color: #C8102E;
    }
    .th-tier-badge {
        background: #C8102E;
        color: #FFF;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.5px;
    }
    .th-stars-row {
        display: flex;
        justify-content: center;
        gap: 4px;
        margin-bottom: 10px;
    }
    .th-star {
        width: 26px;
        height: 26px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
    }
    .th-star-empty {
        background: #F5F0EA;
        color: #D1C7B8;
    }
    .th-star-filled {
        background: #C8102E;
        color: #FFF;
        box-shadow: 0 2px 6px rgba(200,16,46,0.3);
    }
    .th-card-info {
        text-align: center;
        font-size: 12px;
        color: #999;
        font-weight: 600;
    }
    .th-free-alert {
        text-align: center;
        margin-top: 10px;
        padding: 8px;
        background: linear-gradient(90deg, #C8102E, #E8243C);
        color: #FFF;
        border-radius: 12px;
        font-weight: 900;
        font-size: 13px;
        animation: bounce 2s infinite;
    }
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
    }

    /* ===== QR BUTTON ===== */
    .qr-btn-wrap { padding: 0 16px; margin-bottom: 12px; }

    /* ===== MENYU (Compact Grid) ===== */
    .menu-cat-title {
        font-size: 13px;
        font-weight: 900;
        color: #C8102E;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin: 12px 16px 6px;
        padding-bottom: 4px;
        border-bottom: 2px solid #F0ECE6;
    }
    .menu-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        padding: 0 16px;
        margin-bottom: 8px;
    }
    .mg-item {
        background: #FFFFFF;
        border: 1px solid #F0ECE6;
        border-radius: 14px;
        padding: 12px;
        transition: all 0.15s;
    }
    .mg-item:active { transform: scale(0.98); }
    .mg-name {
        font-weight: 800;
        font-size: 13px;
        color: #2D2926;
        line-height: 1.3;
        margin-bottom: 4px;
    }
    .mg-price {
        font-weight: 900;
        font-size: 16px;
        color: #C8102E;
    }
    .mg-star {
        font-size: 9px;
        color: #C8102E;
        background: #FFF0F0;
        padding: 2px 6px;
        border-radius: 8px;
        margin-top: 4px;
        display: inline-block;
        font-weight: 700;
    }

    /* ===== MENYU LİST (Alternativ) ===== */
    .ml-item {
        background: #FFFFFF;
        border: 1px solid #F0ECE6;
        border-radius: 14px;
        padding: 12px 14px;
        margin: 0 16px 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .ml-left { flex: 1; }
    .ml-name { font-weight: 800; font-size: 14px; color: #2D2926; }
    .ml-cat { font-size: 11px; color: #AAA; margin-top: 2px; }
    .ml-price { font-weight: 900; font-size: 17px; color: #C8102E; white-space: nowrap; margin-left: 10px; }

    /* ===== TARİXÇƏ ===== */
    .hist-item {
        background: #FFFFFF;
        border: 1px solid #F0ECE6;
        border-radius: 14px;
        padding: 14px;
        margin: 0 16px 8px;
        border-left: 4px solid #C8102E;
    }
    .hist-date { font-size: 11px; color: #AAA; margin-bottom: 4px; font-weight: 600; }
    .hist-items { font-size: 13px; color: #555; line-height: 1.4; }
    .hist-total { font-size: 16px; font-weight: 900; color: #C8102E; margin-top: 6px; }

    /* ===== BANNER ===== */
    .th-banner {
        background: linear-gradient(90deg, #C8102E, #E8243C);
        color: #FFF;
        padding: 14px 18px;
        border-radius: 14px;
        margin: 8px 16px;
        text-align: center;
        font-weight: 800;
        font-size: 14px;
        box-shadow: 0 4px 15px rgba(200,16,46,0.25);
        animation: slideDown 0.5s ease-out;
    }
    @keyframes slideDown { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

    /* ===== CHAT ===== */
    .cb { padding: 12px 16px; border-radius: 18px; margin-bottom: 8px; max-width: 85%; font-size: 14px; line-height: 1.5; }
    .cb-user { background: #C8102E; color: #FFF; margin-left: auto; border-bottom-right-radius: 4px; font-weight: 700; }
    .cb-ai { background: #FFF; color: #333; margin-right: auto; border-bottom-left-radius: 4px; border: 1px solid #EEE; }

    /* ===== FORTUNE ===== */
    .fort-zone {
        border: 2px dashed #DDD;
        border-radius: 20px;
        padding: 30px 20px;
        text-align: center;
        margin: 15px 16px;
        background: #FFF;
    }
    .fort-result {
        background: #FFF;
        border: 2px solid #C8102E;
        border-radius: 20px;
        padding: 20px;
        margin: 15px 16px;
    }

    /* ===== STREAMLIT OVERRİDES ===== */
    h1, h2, h3, h4 { color: #2D2926 !important; }
    
    div[data-baseweb="input"] > div { 
        background: #FFF !important; 
        border: 2px solid #E8E2DA !important; 
        border-radius: 14px !important;
        box-shadow: none !important;
    }
    div[data-baseweb="input"] input { 
        color: #2D2926 !important; 
        font-weight: 600 !important;
        -webkit-text-fill-color: #2D2926 !important;
    }
    div[data-baseweb="input"] input::placeholder { color: #BBB !important; -webkit-text-fill-color: #BBB !important; }
    
    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: #C8102E !important;
        border: none !important;
        border-radius: 14px !important;
        color: #FFF !important;
        font-weight: 900 !important;
        box-shadow: 0 4px 15px rgba(200,16,46,0.3) !important;
        min-height: auto !important;
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p { color: #FFF !important; font-weight: 900 !important; font-size: 15px !important; }
    
    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background: #FFF !important;
        border: 1px solid #E8E2DA !important;
        border-radius: 14px !important;
        color: #333 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        min-height: auto !important;
    }
    button[kind="secondary"] p { color: #333 !important; font-weight: 700 !important; font-size: 14px !important; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 0; 
        background: #FFF; 
        border-radius: 14px; 
        padding: 4px; 
        margin: 0 16px 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #F0ECE6;
    }
    .stTabs [data-baseweb="tab"] { 
        border-radius: 11px !important; 
        color: #999 !important; 
        font-weight: 700 !important;
        font-size: 12px !important;
        padding: 8px 4px !important;
    }
    .stTabs [aria-selected="true"] { 
        background: #C8102E !important; 
        color: #FFF !important; 
        font-weight: 900 !important;
    }

    /* Radio */
    div[role="radiogroup"] > label {
        background: #FFF !important;
        border: 1px solid #F0ECE6 !important;
        border-radius: 10px !important;
        padding: 6px 14px !important;
        box-shadow: none !important;
        min-height: auto !important;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p { color: #666 !important; font-size: 12px !important; font-weight: 700 !important; }
    div[role="radiogroup"] label:has(input:checked) {
        background: #C8102E !important;
        border-color: #C8102E !important;
        transform: none !important;
        box-shadow: 0 2px 8px rgba(200,16,46,0.2) !important;
    }
    div[role="radiogroup"] label:has(input:checked) p { color: #FFF !important; }

    /* Dialog */
    div[role="dialog"] > div {
        background: #FAF6F1 !important;
        border: 2px solid #C8102E !important;
        border-radius: 20px !important;
    }

    /* File uploader */
    .stFileUploader > div { 
        background: #FFF !important; 
        border: 2px dashed #DDD !important; 
        border-radius: 14px !important; 
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 0px; }
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
        valid = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not valid:
            return None, None
        chosen = next((m for m in valid if 'flash' in m.lower()), valid[0])
        return genai.GenerativeModel(chosen), valid
    except:
        return None, None


# ============================================================
# LOYALTY CARD (Compact)
# ============================================================
def render_loyalty_card(stars, cust_type):
    tier_map = {
        "standard": "QONAQ", "golden": "GOLD", "platinum": "PLATINUM",
        "elite": "ELITE", "thermos": "THERMOS", "telebe": "TƏLƏBƏ", "ikram": "İKRAM"
    }
    tier = tier_map.get(str(cust_type).lower(), "QONAQ")
    current = int(stars or 0)
    filled = current % 10
    free_count = current // 10
    remaining = 10 - filled

    stars_html = ""
    for i in range(10):
        if i < filled:
            stars_html += '<div class="th-star th-star-filled">★</div>'
        else:
            stars_html += '<div class="th-star th-star-empty">☆</div>'

    free_html = ""
    if free_count > 0:
        free_html = f'<div class="th-free-alert">🎁 {free_count} PULSUZ KOFENİZ VAR!</div>'

    st.markdown(f"""
    <div class="th-card">
        <div class="th-card-top">
            <div class="th-card-title">☕ EMALATKHANA CLUB</div>
            <div class="th-tier-badge">💎 {tier}</div>
        </div>
        <div class="th-stars-row">{stars_html}</div>
        <div class="th-card-info">Pulsuz kofeyə <b>{remaining}</b> ulduz qalıb</div>
        {free_html}
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# QR DİALOQ
# ============================================================
@st.dialog("📱 QR Kodunuz")
def show_qr_dialog(cid):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={cid}&color=C8102E&bgcolor=FAF6F1"
    st.markdown(f"""
    <div style="text-align:center; padding: 15px;">
        <img src="{qr_url}" style="width:180px; height:180px; border-radius:18px; border:4px solid #C8102E; box-shadow: 0 8px 25px rgba(200,16,46,0.2);"/>
        <h3 style="margin-top:15px; font-weight:900; color:#C8102E; letter-spacing:2px;">{cid}</h3>
        <p style="color:#999; font-size:12px;">Kassada göstərin və ulduz qazanın!</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# MENYU (Compact Grid)
# ============================================================
def render_menu_section():
    menu_df = run_query("SELECT item_name, price, category, is_coffee FROM menu WHERE is_active=TRUE ORDER BY category, item_name")
    if menu_df.empty:
        st.info("Menyu yenilənir...")
        return

    cats = menu_df['category'].dropna().unique().tolist()
    all_cats = ["Hamısı"] + sorted(cats)
    sel = st.radio("Kat", all_cats, horizontal=True, label_visibility="collapsed", key="cm_cat")

    filtered = menu_df if sel == "Hamısı" else menu_df[menu_df['category'] == sel]

    if sel == "Hamısı":
        # Kateqoriyalara bölünmüş grid
        for cat in sorted(filtered['category'].dropna().unique().tolist()):
            cat_items = filtered[filtered['category'] == cat]
            st.markdown(f'<div class="menu-cat-title">{cat}</div>', unsafe_allow_html=True)

            items_html = '<div class="menu-grid">'
            for _, item in cat_items.iterrows():
                star = '<div class="mg-star">⭐ +1 Ulduz</div>' if item['is_coffee'] else ""
                items_html += f'''
                <div class="mg-item">
                    <div class="mg-name">{item['item_name']}</div>
                    <div class="mg-price">{float(item['price']):.2f} ₼</div>
                    {star}
                </div>'''
            items_html += '</div>'
            st.markdown(items_html, unsafe_allow_html=True)
    else:
        # Seçilmiş kateqoriya — list view
        for _, item in filtered.iterrows():
            star = '<div class="mg-star" style="margin:0 0 0 8px;">⭐</div>' if item['is_coffee'] else ""
            st.markdown(f"""
            <div class="ml-item">
                <div class="ml-left">
                    <div class="ml-name">{item['item_name']}</div>
                </div>
                <div style="display:flex; align-items:center;">
                    {star}
                    <div class="ml-price">{float(item['price']):.2f} ₼</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ============================================================
# TARİXÇƏ
# ============================================================
def render_history_section(card_id):
    sales = run_query(
        "SELECT items, total, created_at, payment_method FROM sales "
        "WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) "
        "ORDER BY created_at DESC LIMIT 15",
        {"cid": card_id}
    )
    if sales.empty:
        st.markdown("""
        <div style="text-align:center; padding: 30px 20px; color:#BBB;">
            <div style="font-size:40px; margin-bottom:10px;">📋</div>
            <div style="font-weight:700; font-size:15px; color:#999;">Hələ sifariş yoxdur</div>
            <div style="font-size:12px; margin-top:5px;">İlk sifarişinizi verin!</div>
        </div>""", unsafe_allow_html=True)
        return

    for _, row in sales.iterrows():
        try:
            ds = row['created_at'].strftime("%d.%m.%Y · %H:%M")
        except:
            ds = "-"
        try:
            items = json.loads(row['items'])
            istr = " · ".join([f"{i['item_name']} ×{i['qty']}" for i in items])
        except:
            istr = str(row['items'])[:50]
        pm = "💵" if row.get('payment_method') in ['Nəğd', 'Cash'] else "💳"

        st.markdown(f"""
        <div class="hist-item">
            <div class="hist-date">{ds} {pm}</div>
            <div class="hist-items">{istr}</div>
            <div class="hist-total">{float(row['total']):.2f} ₼</div>
        </div>""", unsafe_allow_html=True)


# ============================================================
# BİLDİRİŞLƏR
# ============================================================
def check_notifications(card_id):
    try:
        n = run_query(
            "SELECT id, message FROM notifications WHERE card_id=:c AND (is_read IS NULL OR is_read=FALSE) ORDER BY created_at DESC LIMIT 1",
            {"c": card_id}
        )
        if not n.empty:
            st.markdown(f'<div class="th-banner">🎉 {n.iloc[0]["message"]}</div>', unsafe_allow_html=True)
            if st.button("✓ Oxudum", key="notif_dismiss"):
                run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id": n.iloc[0]['id']})
                st.rerun()
    except:
        pass


# ============================================================
# AI BARİSTA
# ============================================================
def render_ai_barista():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:36px;">🤖☕</div>
        <div style="font-weight:900; color:#C8102E; font-size:17px; margin-top:5px;">AI Barista</div>
        <div style="color:#999; font-size:12px; margin-top:3px;">Nə istədiyinizi yazın, sizə ideal içki seçim!</div>
    </div>""", unsafe_allow_html=True)

    if 'barista_chat' not in st.session_state:
        st.session_state.barista_chat = []

    for msg in st.session_state.barista_chat:
        css = "cb-user" if msg['role'] == 'user' else "cb-ai"
        st.markdown(f'<div class="cb {css}">{msg["text"]}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c1:
        um = st.text_input("Mesaj", placeholder="Yuxuluyam, güclü nəsə...", label_visibility="collapsed", key="b_inp")
    with c2:
        go = st.button("📤", key="b_send")

    if go and um.strip():
        st.session_state.barista_chat.append({'role': 'user', 'text': um})
        model, _ = get_ai_model()
        if model:
            try:
                mdf = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE")
                mt = ", ".join([f"{r['item_name']} ({r['price']}₼)" for _, r in mdf.iterrows()]) if not mdf.empty else ""
                p = f"""Sən 'Emalatkhana' kofe şopunun gənc, səmimi AI Baristasısan.
Menyu: {mt}
Müştəri: '{um}'
Menyudan 1-2 məhsul təklif et. Qısa (2-3 cümlə), emoji ilə. Qiymət yaz. Sonda 'Kassaya buyurun! ☕'"""
                r = model.generate_content(p)
                ai = r.text
            except:
                ai = "Bağışla, bir az yoruldum ☕ Bir daha yaz!"
        else:
            ai = "AI bağlantısı yoxdur 🔌"
        st.session_state.barista_chat.append({'role': 'ai', 'text': ai})
        st.rerun()

    if st.session_state.barista_chat:
        if st.button("🗑️ Söhbəti Təmizlə", use_container_width=True, key="clr_chat"):
            st.session_state.barista_chat = []
            st.rerun()


# ============================================================
# KOFE FALI
# ============================================================
def render_fortune():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:40px;">🔮☕</div>
        <div style="font-weight:900; color:#C8102E; font-size:17px; margin-top:5px;">Kofe Falı</div>
        <div style="color:#999; font-size:12px; margin-top:3px;">Fincanınızın şəklini çəkin!</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="fort-zone">
        <div style="font-size:50px;">📸</div>
        <div style="color:#AAA; font-weight:700; margin-top:10px;">Fincanın dibinin şəkli</div>
        <div style="color:#CCC; font-size:11px; margin-top:5px;">Yaxından, işıqlı mühitdə çəkin</div>
    </div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader("Şəkil", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed", key="fort_up")

    if uploaded:
        st.image(uploaded, use_container_width=True)
        if st.button("🔮 Falıma Bax!", type="primary", use_container_width=True, key="fort_btn"):
            with st.spinner("Falçı fincanı oxuyur... 🔮"):
                model, all_m = get_ai_model()
                if not model:
                    st.error("Falçı yuxudadır 😴")
                    return
                try:
                    vm = None
                    if all_m:
                        for m in all_m:
                            if 'vision' in m.lower() or 'flash' in m.lower():
                                vm = m
                                break
                        if not vm:
                            vm = all_m[0]
                    vmodel = genai.GenerativeModel(vm)
                    
                    prompt = """Sən məşhur Azərbaycan falçısısan. Kofe fincanının dibini görürsən.
Müsbət, əyləncəli fal de (4-5 cümlə). Sevgi, iş, pul, səyahətdən birini seç.
Azərbaycan dilində, emoji ilə, sirli üslubda."""

                    if Image:
                        img = Image.open(uploaded)
                        resp = vmodel.generate_content([prompt, img])
                    else:
                        resp = model.generate_content(prompt)

                    st.markdown(f"""
                    <div class="fort-result">
                        <div style="text-align:center; font-size:24px; margin-bottom:12px;">🔮✨</div>
                        <div style="text-align:center; font-weight:900; color:#C8102E; margin-bottom:12px;">SİZİN FALINIZ</div>
                        <div style="color:#555; line-height:1.7; font-size:14px;">{resp.text}</div>
                        <div style="text-align:center; margin-top:15px; font-size:11px; color:#CCC;">☕ Falınız xeyirli olsun!</div>
                    </div>""", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Xəta: {e}")


# ============================================================
# ƏSAS FUNKSİYA
# ============================================================
def render_customer_app(customer_id=None):
    inject_customer_css()

    if not customer_id:
        st.error("QR Kod oxunmadı.")
        return

    c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
    if c_df.empty:
        st.error("Müştəri tapılmadı.")
        return

    cust = c_df.iloc[0].to_dict()
    stars = cust.get('stars', 0)
    c_type = str(cust.get('type', 'standard'))

    hour = get_baku_now().hour
    if 5 <= hour < 12:
        greet = "Sabahınız xeyir ☕"
    elif 12 <= hour < 18:
        greet = "Günortanız xeyir ☀️"
    else:
        greet = "Axşamınız xeyir 🌙"

    # HERO
    st.markdown(f"""
    <div class="th-hero">
        <div class="th-logo">☕ EMALATKHANA</div>
        <div class="th-greeting">{greet}</div>
    </div>""", unsafe_allow_html=True)

    # Notifications
    check_notifications(customer_id)

    # Loyalty
    render_loyalty_card(stars, c_type)

    # QR Button
    st.markdown('<div class="qr-btn-wrap">', unsafe_allow_html=True)
    if st.button("📱 QR KODUMU GÖSTƏR", type="primary", use_container_width=True, key="qr_show"):
        show_qr_dialog(customer_id)
    st.markdown('</div>', unsafe_allow_html=True)

    # Tabs
    t1, t2, t3, t4 = st.tabs(["📋 Menyu", "📜 Tarixçə", "🤖 Barista", "🔮 Fal"])

    with t1:
        render_menu_section()
    with t2:
        render_history_section(customer_id)
    with t3:
        render_ai_barista()
    with t4:
        render_fortune()

    # Footer
    st.markdown("""
    <div style="text-align:center; padding:25px 0 15px;">
        <div style="font-weight:900; font-size:11px; letter-spacing:2px; color:#CCC;">EMALATKHANA</div>
        <div style="font-size:10px; color:#DDD; margin-top:3px;">Crafted with ☕ & ❤️</div>
    </div>""", unsafe_allow_html=True)
