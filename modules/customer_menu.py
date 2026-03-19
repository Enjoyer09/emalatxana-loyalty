# modules/customer_menu.py — PREMIUM ORANGE MOBILE v7.0
import streamlit as st
import pandas as pd
import json
import logging

from database import run_query, run_action, get_setting
from utils import get_baku_now

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
# MOBILE-FIRST PREMIUM ORANGE CSS
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;700;800&family=Nunito:wght@400;600;700;800;900&display=swap');

    /* ===== BASE ===== */
    .stApp {
        background: linear-gradient(180deg, #FFF7F0 0%, #FFF2E8 100%) !important;
        color: #2B211C !important;
        font-family: 'Nunito', sans-serif !important;
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { 
        padding: 0 !important; 
        max-width: 100% !important; 
        padding-bottom: 30px !important;
    }
    section.main > div:first-child { padding-top: 0 !important; }

    /* ===== HERO ===== */
    .mobile-hero {
        background: linear-gradient(160deg, #FF9C5B 0%, #F4823A 45%, #E46C24 100%);
        padding: 26px 18px 44px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .mobile-hero::before {
        content: '';
        position: absolute;
        top: -60px;
        right: -40px;
        width: 180px;
        height: 180px;
        background: rgba(255,255,255,0.12);
        border-radius: 50%;
    }
    .mobile-hero::after {
        content: '';
        position: absolute;
        bottom: -18px;
        left: 0;
        right: 0;
        height: 38px;
        background: #FFF7F0;
        border-radius: 50% 50% 0 0 / 100% 100% 0 0;
    }
    .mh-icon {
        font-size: 38px;
        margin-bottom: 4px;
        position: relative;
        z-index: 2;
    }
    .mh-brand {
        font-family: 'Jura', sans-serif;
        font-size: 23px;
        font-weight: 800;
        letter-spacing: 3px;
        color: #FFFFFF;
        position: relative;
        z-index: 2;
    }
    .mh-sub {
        font-size: 13px;
        color: rgba(255,255,255,0.88);
        margin-top: 6px;
        font-weight: 700;
        position: relative;
        z-index: 2;
    }

    /* ===== MAIN CARD ===== */
    .main-card {
        background: rgba(255,255,255,0.95);
        border: 1px solid #FFE0C7;
        border-radius: 26px;
        margin: -10px 14px 14px;
        padding: 18px 16px;
        box-shadow: 0 10px 30px rgba(228,108,36,0.10);
        position: relative;
        z-index: 5;
        backdrop-filter: blur(8px);
    }

    /* ===== LOYALTY HEADER ===== */
    .loyalty-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .loyalty-title {
        font-family: 'Jura', sans-serif;
        font-size: 17px;
        font-weight: 800;
        color: #7A3514;
        letter-spacing: 1px;
    }
    .tier-pill {
        background: linear-gradient(135deg, #FF9C5B, #E46C24);
        color: white;
        padding: 5px 12px;
        border-radius: 16px;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: 1px;
    }
    .loyalty-sub {
        color: #B58D75;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 14px;
    }

    /* ===== STAMP GRID ===== */
    .stamp-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 8px;
        max-width: 280px;
        margin: 0 auto 14px;
    }
    .stamp-box {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 900;
    }
    .stamp-off {
        background: #FFF3E8;
        border: 2px solid #FFD6B8;
        color: #D8B39A;
    }
    .stamp-on {
        background: linear-gradient(145deg, #FF9C5B, #E46C24);
        border: 2px solid #E46C24;
        color: white;
        box-shadow: 0 4px 10px rgba(228,108,36,0.25);
    }
    .stamp-gift {
        background: linear-gradient(145deg, #7A3514, #5A240C);
        border: 2px solid #7A3514;
        color: #FFF3E8;
        box-shadow: 0 4px 14px rgba(122,53,20,0.25);
        animation: pulseGift 1.8s infinite;
    }
    @keyframes pulseGift {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.08); }
    }
    .stamp-footer {
        text-align: center;
        color: #B58D75;
        font-size: 12px;
        font-weight: 700;
    }

    /* ===== FREE REWARD ALERT ===== */
    .free-reward {
        margin: 0 14px 12px;
        background: linear-gradient(135deg, #FF9C5B, #E46C24);
        color: white;
        border-radius: 18px;
        padding: 14px;
        text-align: center;
        font-weight: 900;
        font-size: 15px;
        box-shadow: 0 8px 20px rgba(228,108,36,0.18);
    }

    /* ===== BANNERS ===== */
    .smart-banner {
        margin: 0 14px 12px;
        border-radius: 16px;
        padding: 12px 14px;
        text-align: center;
        font-size: 13px;
        font-weight: 800;
    }
    .banner-hh {
        background: linear-gradient(90deg, #FFD36A, #FFB347);
        color: #4A2A00;
        box-shadow: 0 4px 12px rgba(255,179,71,0.18);
    }
    .banner-msg {
        background: linear-gradient(90deg, #FFF0E2, #FFE0C7);
        color: #8A4B1C;
        border: 1px solid #FFD3AE;
    }

    /* ===== REWARD CARDS ===== */
    .reward-card {
        background: #FFFFFF;
        border: 1px solid #FFE0C7;
        border-radius: 18px;
        margin: 0 14px 10px;
        padding: 14px;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.03);
    }
    .reward-icon {
        width: 46px;
        height: 46px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        flex-shrink: 0;
        background: #FFF3E8;
    }
    .reward-title {
        font-size: 14px;
        font-weight: 800;
        color: #7A3514;
    }
    .reward-desc {
        font-size: 12px;
        color: #B58D75;
        margin-top: 2px;
    }
    .reward-right {
        margin-left: auto;
        font-size: 15px;
        font-weight: 900;
        color: #E46C24;
    }

    /* ===== SECTION TITLE ===== */
    .section-title {
        font-family: 'Jura', sans-serif;
        font-size: 15px;
        font-weight: 800;
        color: #7A3514;
        margin: 16px 14px 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* ===== MENU GRID ===== */
    .menu-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        padding: 0 14px;
        margin-bottom: 8px;
    }
    .menu-card {
        background: #FFFFFF;
        border: 1px solid #FFE0C7;
        border-radius: 20px;
        padding: 14px 12px;
        text-align: center;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }
    .menu-emoji {
        font-size: 32px;
        margin-bottom: 6px;
    }
    .menu-name {
        font-size: 13px;
        font-weight: 800;
        color: #2B211C;
        line-height: 1.35;
        margin-bottom: 4px;
    }
    .menu-price {
        font-size: 18px;
        font-weight: 900;
        color: #E46C24;
    }
    .menu-badge {
        font-size: 10px;
        font-weight: 800;
        color: #A75316;
        background: #FFF3E8;
        padding: 3px 8px;
        border-radius: 12px;
        margin-top: 6px;
        display: inline-block;
        align-self: center;
    }

    /* ===== HISTORY ===== */
    .history-card {
        background: #FFFFFF;
        border: 1px solid #FFE0C7;
        border-radius: 18px;
        margin: 0 14px 8px;
        padding: 14px;
        border-left: 4px solid #E46C24;
    }
    .history-date {
        font-size: 11px;
        color: #BA977E;
        font-weight: 700;
    }
    .history-items {
        font-size: 13px;
        color: #5B4A40;
        line-height: 1.45;
        margin-top: 4px;
    }
    .history-total {
        font-size: 15px;
        color: #7A3514;
        font-weight: 900;
        margin-top: 6px;
    }
    .history-stamp {
        display: inline-block;
        margin-top: 6px;
        background: #FFF3E8;
        color: #A75316;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 10px;
        font-weight: 800;
    }

    /* ===== CHAT ===== */
    .chat-bubble {
        padding: 12px 16px;
        border-radius: 18px;
        margin-bottom: 8px;
        max-width: 88%;
        font-size: 14px;
        line-height: 1.5;
    }
    .chat-user {
        background: linear-gradient(135deg, #E46C24, #F28A46);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 5px;
        font-weight: 700;
    }
    .chat-ai {
        background: #FFFFFF;
        border: 1px solid #FFE0C7;
        color: #3A2B24;
        margin-right: auto;
        border-bottom-left-radius: 5px;
    }

    /* ===== FORTUNE ===== */
    .fortune-zone {
        border: 2px dashed #FFD3AE;
        border-radius: 22px;
        background: #FFFFFF;
        margin: 14px;
        padding: 30px 20px;
        text-align: center;
    }
    .fortune-result {
        background: #FFFFFF;
        border: 2px solid #F28A46;
        border-radius: 22px;
        padding: 20px;
        margin: 14px;
        box-shadow: 0 6px 16px rgba(242,138,70,0.08);
    }

    /* ===== STREAMLIT OVERRIDES ===== */
    h1, h2, h3, h4 { color: #2B211C !important; }

    div[data-baseweb="input"] > div {
        background: #FFFFFF !important;
        border: 2px solid #FFE0C7 !important;
        border-radius: 16px !important;
        box-shadow: none !important;
    }
    div[data-baseweb="input"] input {
        color: #2B211C !important;
        font-weight: 600 !important;
        -webkit-text-fill-color: #2B211C !important;
    }
    div[data-baseweb="input"] input::placeholder {
        color: #D2B29A !important;
        -webkit-text-fill-color: #D2B29A !important;
    }

    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #E46C24, #F28A46) !important;
        border: none !important;
        border-radius: 16px !important;
        box-shadow: 0 6px 16px rgba(228,108,36,0.18) !important;
        min-height: 50px !important;
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p {
        color: white !important;
        font-weight: 900 !important;
        font-size: 15px !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background: #FFFFFF !important;
        border: 1px solid #FFE0C7 !important;
        border-radius: 16px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
        min-height: 48px !important;
    }
    button[kind="secondary"] p {
        color: #7A3514 !important;
        font-weight: 700 !important;
        font-size: 14px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #FFFFFF;
        border-radius: 16px;
        padding: 4px;
        margin: 0 14px 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #FFE0C7;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px !important;
        color: #A08C7C !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        padding: 8px 6px !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #E46C24, #F28A46) !important;
        color: white !important;
        font-weight: 900 !important;
    }

    div[role="radiogroup"] > label {
        background: #FFFFFF !important;
        border: 1px solid #FFE0C7 !important;
        border-radius: 10px !important;
        padding: 6px 12px !important;
        box-shadow: none !important;
        min-height: auto !important;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p {
        color: #A08C7C !important;
        font-size: 12px !important;
        font-weight: 700 !important;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: #E46C24 !important;
        border-color: #E46C24 !important;
        transform: none !important;
        box-shadow: none !important;
    }
    div[role="radiogroup"] label:has(input:checked) p {
        color: white !important;
    }

    div[role="dialog"] > div {
        background: #FFF7F0 !important;
        border: 2px solid #E46C24 !important;
        border-radius: 24px !important;
    }

    .stFileUploader > div {
        background: #FFFFFF !important;
        border: 2px dashed #FFD3AE !important;
        border-radius: 16px !important;
    }

    ::-webkit-scrollbar { width: 0px; }
    </style>
    """, unsafe_allow_html=True)
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


def render_stamp_card(stars, cust_type):
    tier_map = {
        "standard": "QONAQ",
        "golden": "GOLD",
        "platinum": "PLATINUM",
        "elite": "ELITE",
        "thermos": "THERMOS",
        "telebe": "TƏLƏBƏ",
        "ikram": "İKRAM"
    }
    tier = tier_map.get(str(cust_type).lower(), "QONAQ")
    current = int(stars or 0)
    filled = current % 10
    free_count = current // 10
    remaining = 10 - filled

    stamps_html = ""
    for i in range(10):
        num = i + 1
        if i == 9:
            if filled >= 10:
                stamps_html += '<div class="stamp-box stamp-gift">🎁</div>'
            elif filled == 9:
                stamps_html += '<div class="stamp-box stamp-off" style="border-color:#E46C24;color:#E46C24;">🎁</div>'
            else:
                stamps_html += '<div class="stamp-box stamp-off">🎁</div>'
        elif i < filled:
            stamps_html += f'<div class="stamp-box stamp-on">{num}</div>'
        else:
            stamps_html += f'<div class="stamp-box stamp-off">{num}</div>'

    st.markdown(f"""
    <div class="main-card">
        <div class="loyalty-top">
            <div class="loyalty-title">EMALATKHANA CLUB</div>
            <div class="tier-pill">{tier}</div>
        </div>
        <div class="loyalty-sub">Hər kofe alışında 1 stamp qazan! ☕</div>
        <div class="stamp-grid">{stamps_html}</div>
        <div class="stamp-footer">{filled}/10 stamp · Pulsuz kofeyə {remaining} qaldı</div>
    </div>
    """, unsafe_allow_html=True)


def render_free_banner(free_count):
    if free_count > 0:
        st.markdown(f"""
        <div class="free-reward">
            🎉 {free_count} PULSUZ KOFENİZ HAZIRDIR! Kassada istifadə edin
        </div>
        """, unsafe_allow_html=True)


def render_rewards(stars, free_count):
    remaining = 10 - (int(stars or 0) % 10)
    pct = int(((10 - remaining) / 10) * 100)

    st.markdown(f"""
    <div class="reward-card">
        <div class="reward-icon coffee">☕</div>
        <div>
            <div class="reward-title">Pulsuz Kofe</div>
            <div class="reward-desc">10 stamp topla, 1 pulsuz kofe qazan</div>
        </div>
        <div class="reward-right">{pct}%</div>
    </div>
    """, unsafe_allow_html=True)

    if free_count > 0:
        st.markdown(f"""
        <div class="reward-card">
            <div class="reward-icon gift">🎁</div>
            <div>
                <div class="reward-title">Hazır Hədiyyə</div>
                <div class="reward-desc">{free_count} pulsuz kofe gözləyir</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


@st.dialog("📱 QR Kodunuz")
def show_qr_dialog(cid):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={cid}&color=E46C24&bgcolor=FFF7F0"
    st.markdown(f"""
    <div style="text-align:center; padding: 15px;">
        <img src="{qr_url}" style="width:190px; height:190px; border-radius:18px; border:4px solid #E46C24; box-shadow: 0 8px 25px rgba(228,108,36,0.18);"/>
        <h3 style="margin-top:15px; font-weight:900; color:#E46C24; letter-spacing:2px;">{cid}</h3>
        <p style="color:#A08C7C; font-size:12px;">Kassada göstərin → Stamp qazanın ☕</p>
    </div>
    """, unsafe_allow_html=True)


def check_notifications(card_id):
    try:
        n = run_query(
            "SELECT id, message FROM notifications WHERE card_id=:c AND (is_read IS NULL OR is_read=FALSE) ORDER BY created_at DESC LIMIT 1",
            {"c": card_id}
        )
        if not n.empty:
            st.markdown(f'<div class="smart-banner banner-msg">🎉 {n.iloc[0]["message"]}</div>', unsafe_allow_html=True)
            if st.button("✓ Oxudum", key="notif_x", use_container_width=True):
                run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id": n.iloc[0]['id']})
                st.rerun()
    except:
        pass


def check_happy_hour():
    try:
        from utils import get_active_happy_hour
        hh = get_active_happy_hour()
        if hh:
            hh_end = hh['end_time'][:5]
            st.markdown(f"""
            <div class="smart-banner banner-hh">
                ⏰ HAPPY HOUR! {hh['discount_percent']}% ENDİRİM · {hh['name']} · {hh_end}-ə qədər!
            </div>
            """, unsafe_allow_html=True)
    except:
        pass


def render_coffee_menu():
    menu_df = run_query("SELECT item_name, price, category, is_coffee FROM menu WHERE is_active=TRUE ORDER BY category, item_name")
    if menu_df.empty:
        st.info("Menyu yenilənir...")
        return

    emoji_map = {
        "latte": "☕", "espresso": "⚡", "americano": "🫗", "cappuccino": "🥛",
        "mocha": "🍫", "macchiato": "🎨", "flat": "☕", "raf": "🧁",
        "turkish": "🫖", "cold": "🧊", "ice": "🧊", "frappe": "🥤",
        "matcha": "🍵", "hot": "🔥", "chocolate": "🍫", "tea": "🍵",
        "kombo": "🎁", "combo": "🎁", "kruasan": "🥐", "croissant": "🥐",
        "keks": "🧁", "tort": "🎂", "su": "💧", "water": "💧",
    }

    def get_emoji(name):
        name_lower = name.lower()
        for key, emoji in emoji_map.items():
            if key in name_lower:
                return emoji
        return "☕"

    cats = menu_df['category'].dropna().unique().tolist()
    all_cats = ["☕ Hamısı"] + sorted(cats)
    sel = st.radio("Kateqoriya", all_cats, horizontal=True, label_visibility="collapsed", key="cm_cat")

    filtered = menu_df if "Hamısı" in sel else menu_df[menu_df['category'] == sel.replace("☕ ", "")]

    st.markdown("<p style='text-align:center; color:#AA8F7C; font-size:12px; margin: 5px 0 10px;'>Sifarişlərinizi kassada verin</p>", unsafe_allow_html=True)

    if "Hamısı" in sel:
        for cat in sorted(filtered['category'].dropna().unique().tolist()):
            cat_items = filtered[filtered['category'] == cat]
            st.markdown(f'<div class="section-title">{cat}</div>', unsafe_allow_html=True)
            items = cat_items.to_dict('records')
            for idx in range(0, len(items), 2):
                html = '<div class="menu-grid">'
                for j in range(2):
                    if idx + j < len(items):
                        item = items[idx + j]
                        emoji = get_emoji(item['item_name'])
                        stamp = '<div class="menu-badge">+1 Stamp ☕</div>' if item['is_coffee'] else ''
                        html += f'''
                        <div class="menu-card">
                            <div class="menu-emoji">{emoji}</div>
                            <div class="menu-name">{item['item_name']}</div>
                            <div class="menu-price">{float(item['price']):.2f} ₼</div>
                            {stamp}
                        </div>'''
                    else:
                        html += '<div></div>'
                html += '</div>'
                st.markdown(html, unsafe_allow_html=True)
    else:
        items = filtered.to_dict('records')
        for idx in range(0, len(items), 2):
            html = '<div class="menu-grid">'
            for j in range(2):
                if idx + j < len(items):
                    item = items[idx + j]
                    emoji = get_emoji(item['item_name'])
                    stamp = '<div class="menu-badge">+1 Stamp ☕</div>' if item['is_coffee'] else ''
                    html += f'''
                    <div class="menu-card">
                        <div class="menu-emoji">{emoji}</div>
                        <div class="menu-name">{item['item_name']}</div>
                        <div class="menu-price">{float(item['price']):.2f} ₼</div>
                        {stamp}
                    </div>'''
                else:
                    html += '<div></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)


def render_history(card_id):
    sales = run_query(
        "SELECT items, total, created_at, payment_method FROM sales "
        "WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) AND (status IS NULL OR status='COMPLETED') "
        "ORDER BY created_at DESC LIMIT 15",
        {"cid": card_id}
    )
    if sales.empty:
        st.markdown("""
        <div style="text-align:center; padding:30px 20px; color:#B8A091;">
            <div style="font-size:40px;">📋</div>
            <div style="font-weight:700; margin-top:10px;">Hələ sifariş yoxdur</div>
            <div style="font-size:12px; margin-top:5px;">İlk sifarişinizi verin!</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for _, row in sales.iterrows():
        try:
            ds = row['created_at'].strftime("%d.%m.%Y · %H:%M")
        except:
            ds = "-"
        try:
            items = json.loads(row['items'])
            istr = " · ".join([f"{i['item_name']} ×{i['qty']}" for i in items])
            coffee_count = sum([i['qty'] for i in items if i.get('is_coffee')])
        except:
            istr = str(row['items'])[:50]
            coffee_count = 0
        pm = "💵" if row.get('payment_method') in ['Nəğd', 'Cash'] else "💳"
        stamp_html = f'<div class="history-stamp">+{coffee_count} stamp ☕</div>' if coffee_count > 0 else ""

        st.markdown(f"""
        <div class="history-card">
            <div class="history-date">{ds} {pm}</div>
            <div class="history-items">{istr}</div>
            <div class="history-total">{float(row['total']):.2f} ₼</div>
            {stamp_html}
        </div>
        """, unsafe_allow_html=True)


def render_ai_barista():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:36px;">🤖☕</div>
        <div style="font-weight:900; color:#7A3514; font-size:17px; margin-top:5px;">AI Barista</div>
        <div style="color:#B58D75; font-size:12px; margin-top:3px;">Əhvalınızı yazın, sizə uyğun kofe təklif edim</div>
    </div>
    """, unsafe_allow_html=True)

    if 'barista_chat' not in st.session_state:
        st.session_state.barista_chat = []

    for m in st.session_state.barista_chat:
        css = "chat-user" if m['role'] == 'user' else "chat-ai"
        st.markdown(f'<div class="chat-bubble {css}">{m["text"]}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c1:
        um = st.text_input("", placeholder="Məsələn: yuxuluyam, şirin nəsə istəyirəm...", label_visibility="collapsed", key="b_i")
    with c2:
        go = st.button("📤", key="b_s")

    if go and um.strip():
        st.session_state.barista_chat.append({'role': 'user', 'text': um})
        model, _ = get_ai_model()
        if model:
            try:
                mdf = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE AND is_coffee=TRUE")
                mt = ", ".join([f"{r['item_name']} ({r['price']}₼)" for _, r in mdf.iterrows()]) if not mdf.empty else ""
                p = f"""Sən 'Emalatkhana' kofe şopunun gənc, mehriban baristasısan.
Kofe menyumuz: {mt}
Müştəri deyir: '{um}'
Menyudan 1-2 kofe təklif et. Qısa (2-3 cümlə), emoji ilə. Qiymət yaz. Sonda 'Kassaya buyurun! ☕'"""
                r = model.generate_content(p)
                ai = r.text
            except:
                ai = "Bağışla, bir az yoruldum ☕ Bir daha yaz!"
        else:
            ai = "AI bağlantısı yoxdur 🔌"

        st.session_state.barista_chat.append({'role': 'ai', 'text': ai})
        st.rerun()

    if st.session_state.barista_chat:
        if st.button("🗑️ Söhbəti Təmizlə", use_container_width=True, key="clr_c"):
            st.session_state.barista_chat = []
            st.rerun()


def render_fortune():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:40px;">🔮☕</div>
        <div style="font-weight:900; color:#7A3514; font-size:17px; margin-top:5px;">Kofe Falı</div>
        <div style="color:#B58D75; font-size:12px; margin-top:3px;">Fincanınızın şəklini çəkin!</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="fortune-zone">
        <div style="font-size:50px;">📸</div>
        <div style="color:#B58D75; font-weight:700; margin-top:10px;">Fincanın dibinin şəkli</div>
        <div style="color:#C5A892; font-size:11px; margin-top:5px;">Yaxından, işıqlı mühitdə çəkin</div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader("Şəkil", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed", key="fu")

    if uploaded:
        st.image(uploaded, use_container_width=True)
        if st.button("🔮 Falıma Bax!", type="primary", use_container_width=True, key="fb"):
            with st.spinner("Falçı oxuyur... 🔮"):
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
                    <div class="fortune-result">
                        <div style="text-align:center; font-size:24px; margin-bottom:12px;">🔮✨</div>
                        <div style="text-align:center; font-weight:900; color:#7A3514; margin-bottom:12px; font-size:16px;">SİZİN FALINIZ</div>
                        <div style="color:#5B4A40; line-height:1.7; font-size:14px;">{resp.text}</div>
                        <div style="text-align:center; margin-top:15px; font-size:11px; color:#BA977E;">☕ Falınız xeyirli olsun!</div>
                    </div>
                    """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Fal xətası: {e}")


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
    stars = int(cust.get('stars', 0))
    c_type = str(cust.get('type', 'standard'))
    free_count = stars // 10

    hour = get_baku_now().hour
    if 5 <= hour < 12:
        greet = "Sabahınız xeyir ☕"
    elif 12 <= hour < 18:
        greet = "Günortanız xeyir ☀️"
    else:
        greet = "Axşamınız xeyir 🌙"

    st.markdown(f"""
    <div class="mobile-hero">
        <div class="mh-icon">☕</div>
        <div class="mh-brand">EMALATKHANA</div>
        <div class="mh-sub">{greet}</div>
    </div>
    """, unsafe_allow_html=True)

    check_happy_hour()
    check_notifications(customer_id)
    render_stamp_card(stars, c_type)
    render_free_banner(free_count)
    render_rewards(stars, free_count)

    st.markdown('<div style="padding:0 14px 14px;">', unsafe_allow_html=True)
    if st.button("📱 QR KODUMU GÖSTƏR", type="primary", use_container_width=True, key="qr_s"):
        show_qr_dialog(customer_id)
    st.markdown('</div>', unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs(["☕ Menyu", "📜 Tarixçə", "🤖 Barista", "🔮 Fal"])

    with t1:
        render_coffee_menu()
    with t2:
        render_history(customer_id)
    with t3:
        render_ai_barista()
    with t4:
        render_fortune()

    st.markdown("""
    <div style="text-align:center; padding:24px 0 14px;">
        <div style="font-family:'Jura'; font-weight:900; font-size:11px; letter-spacing:2px; color:#A57C63;">EMALATKHANA</div>
        <div style="font-size:10px; color:#C0A28D; margin-top:3px;">Hər kofe bir stamp, hər 10 stamp bir hədiyyə!</div>
    </div>
    """, unsafe_allow_html=True)    
