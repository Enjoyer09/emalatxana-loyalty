# modules/customer_menu.py — FINAL PATCHED v6.1
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
# PREMIUM CSS
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;700;800&family=Nunito:wght@400;600;700;800;900&display=swap');

    .stApp {
        background: linear-gradient(180deg, #F7F1EA 0%, #F2EAE1 100%) !important;
        color: #2D241F !important;
        font-family: 'Nunito', sans-serif !important;
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section.main > div:first-child { padding-top: 0 !important; }

    .hero-wrap {
        background: radial-gradient(circle at top left, rgba(255,255,255,0.08) 0%, transparent 35%),
                    linear-gradient(160deg, #2E1F17 0%, #4A3023 55%, #7A523A 100%);
        padding: 30px 20px 50px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .hero-wrap::after {
        content: '';
        position: absolute;
        bottom: -22px;
        left: 0;
        right: 0;
        height: 44px;
        background: #F7F1EA;
        border-radius: 50% 50% 0 0 / 100% 100% 0 0;
    }
    .hero-icon {
        font-size: 40px;
        margin-bottom: 6px;
    }
    .hero-brand {
        font-family: 'Jura', sans-serif;
        font-weight: 800;
        font-size: 24px;
        color: #F5E2C8;
        letter-spacing: 3px;
        text-transform: uppercase;
    }
    .hero-sub {
        color: rgba(245,226,200,0.75);
        font-size: 13px;
        margin-top: 6px;
        font-weight: 600;
    }

    .club-card {
        background: linear-gradient(145deg, #FFFFFF 0%, #FCFAF8 100%);
        border: 1px solid #E8DDD1;
        border-radius: 28px;
        margin: 0 16px 16px;
        margin-top: -15px;
        padding: 22px 18px;
        box-shadow: 0 12px 35px rgba(50,30,20,0.08);
        position: relative;
        overflow: hidden;
    }
    .club-card::before {
        content: '☕';
        position: absolute;
        right: -5px;
        top: -5px;
        font-size: 90px;
        opacity: 0.05;
    }
    .cc-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .cc-title {
        font-family: 'Jura', sans-serif;
        font-size: 17px;
        font-weight: 800;
        color: #3A271D;
        letter-spacing: 1px;
    }
    .cc-tier {
        background: linear-gradient(135deg, #3A271D, #5C3A28);
        color: #F6E8D7;
        padding: 5px 12px;
        border-radius: 16px;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: 1px;
    }
    .cc-desc {
        color: #9A8B7F;
        font-size: 12px;
        margin-bottom: 16px;
        font-weight: 600;
    }

    .stamp-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 8px;
        max-width: 290px;
        margin: 0 auto 14px;
    }
    .stamp {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        font-size: 13px;
        transition: all 0.3s ease;
    }
    .stamp-empty {
        background: #F5F0EB;
        border: 2px solid #D9CEC1;
        color: #C8B9AA;
    }
    .stamp-filled {
        background: linear-gradient(145deg, #3A271D, #56392A);
        border: 2px solid #3A271D;
        color: #F5E2C8;
        box-shadow: 0 3px 10px rgba(58,39,29,0.25);
    }
    .stamp-gift {
        background: linear-gradient(145deg, #E88D48, #D87431);
        border: 2px solid #E88D48;
        color: white;
        box-shadow: 0 4px 14px rgba(232,141,72,0.35);
        animation: pulseGift 1.8s infinite;
    }
    @keyframes pulseGift {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.08); }
    }
    .cc-footer {
        text-align: center;
        color: #A09184;
        font-size: 12px;
        font-weight: 700;
    }

    .free-coffee-banner {
        margin: 0 16px 14px;
        padding: 14px 16px;
        border-radius: 18px;
        background: linear-gradient(135deg, #E88D48, #F0A55E);
        color: white;
        text-align: center;
        font-weight: 900;
        font-size: 15px;
        box-shadow: 0 6px 20px rgba(232,141,72,0.28);
    }

    .smart-banner {
        margin: 0 16px 12px;
        padding: 12px 16px;
        border-radius: 16px;
        text-align: center;
        font-size: 13px;
        font-weight: 800;
    }
    .smart-banner.hh {
        background: linear-gradient(90deg, #FF6B35, #F7C948);
        color: #241A12;
    }
    .smart-banner.notif {
        background: linear-gradient(90deg, #7A523A, #A36A47);
        color: #FFF7F0;
    }

    .reward-box {
        background: #FFF;
        border: 1px solid #E8DDD1;
        border-radius: 18px;
        margin: 0 16px 10px;
        padding: 14px 16px;
        display: flex;
        align-items: center;
        gap: 14px;
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
    }
    .reward-icon.coffee { background: #F4E8DB; }
    .reward-icon.gift { background: #FFF1E4; }
    .reward-title { font-weight: 800; font-size: 14px; color: #3A271D; }
    .reward-desc { font-size: 12px; color: #A09184; margin-top: 2px; }
    .reward-right { margin-left: auto; font-weight: 900; color: #3A271D; font-size: 16px; }

    .menu-cat-title {
        font-size: 13px;
        font-weight: 900;
        color: #3A271D;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 14px 16px 8px;
        padding-bottom: 4px;
        border-bottom: 2px solid #EDE8E3;
    }

    .coffee-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        padding: 0 16px;
        margin-bottom: 8px;
    }
    .coffee-card {
        background: #FFF;
        border: 1px solid #E8DDD1;
        border-radius: 18px;
        padding: 14px 12px;
        text-align: center;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .coffee-emoji {
        font-size: 32px;
        margin-bottom: 6px;
    }
    .coffee-name {
        font-size: 13px;
        font-weight: 800;
        color: #2D241F;
        line-height: 1.35;
        margin-bottom: 4px;
    }
    .coffee-price {
        font-size: 17px;
        font-weight: 900;
        color: #3A271D;
    }
    .coffee-badge {
        font-size: 10px;
        font-weight: 700;
        color: #D4763A;
        background: #FFF3E8;
        padding: 2px 8px;
        border-radius: 10px;
        margin-top: 6px;
        display: inline-block;
        align-self: center;
    }

    .history-card {
        background: #FFF;
        border: 1px solid #E8DDD1;
        border-radius: 16px;
        margin: 0 16px 8px;
        padding: 14px;
        border-left: 4px solid #3A271D;
    }
    .history-date {
        font-size: 11px;
        color: #B0A195;
        font-weight: 700;
    }
    .history-items {
        font-size: 13px;
        color: #5A4C42;
        line-height: 1.45;
        margin-top: 4px;
    }
    .history-total {
        font-size: 15px;
        color: #3A271D;
        font-weight: 900;
        margin-top: 6px;
    }
    .history-stamp {
        display: inline-block;
        margin-top: 6px;
        background: #F4E8DB;
        color: #3A271D;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 10px;
        font-weight: 800;
    }

    .chat-bubble {
        padding: 12px 16px;
        border-radius: 18px;
        margin-bottom: 8px;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.5;
    }
    .chat-user {
        background: #3A271D;
        color: #F5E2C8;
        margin-left: auto;
        border-bottom-right-radius: 4px;
        font-weight: 700;
    }
    .chat-ai {
        background: #FFF;
        border: 1px solid #E8DDD1;
        color: #3A271D;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }

    .fortune-zone {
        border: 2px dashed #D9CEC1;
        border-radius: 22px;
        background: #FFF;
        margin: 16px;
        padding: 30px 20px;
        text-align: center;
    }
    .fortune-result {
        background: #FFF;
        border: 2px solid #E88D48;
        border-radius: 20px;
        padding: 20px;
        margin: 16px;
    }

    h1, h2, h3, h4 { color: #2D241F !important; }
    div[data-baseweb="input"] > div {
        background: #FFF !important;
        border: 2px solid #E8DDD1 !important;
        border-radius: 14px !important;
        box-shadow: none !important;
    }
    div[data-baseweb="input"] input {
        color: #2D241F !important;
        font-weight: 600 !important;
        -webkit-text-fill-color: #2D241F !important;
    }
    div[data-baseweb="input"] input::placeholder {
        color: #C5B7AA !important;
        -webkit-text-fill-color: #C5B7AA !important;
    }

    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #3A271D, #5C3A28) !important;
        border: none !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 15px rgba(58,39,29,0.2) !important;
        min-height: auto !important;
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p {
        color: #F5E2C8 !important;
        font-weight: 900 !important;
        font-size: 15px !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background: #FFF !important;
        border: 1px solid #E8DDD1 !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
        min-height: auto !important;
    }
    button[kind="secondary"] p {
        color: #3A271D !important;
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
        background: #FFF;
        border-radius: 14px;
        padding: 4px;
        margin: 0 16px 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #E8DDD1;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 11px !important;
        color: #999 !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        padding: 8px 4px !important;
    }
    .stTabs [aria-selected="true"] {
        background: #3A271D !important;
        color: #F5E2C8 !important;
        font-weight: 900 !important;
    }

    div[role="radiogroup"] > label {
        background: #FFF !important;
        border: 1px solid #E8DDD1 !important;
        border-radius: 10px !important;
        padding: 6px 12px !important;
        box-shadow: none !important;
        min-height: auto !important;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p {
        color: #88796E !important;
        font-size: 12px !important;
        font-weight: 700 !important;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: #3A271D !important;
        border-color: #3A271D !important;
        transform: none !important;
        box-shadow: none !important;
    }
    div[role="radiogroup"] label:has(input:checked) p {
        color: #F5E2C8 !important;
    }

    div[role="dialog"] > div {
        background: #F7F1EA !important;
        border: 2px solid #3A271D !important;
        border-radius: 22px !important;
    }

    .stFileUploader > div {
        background: #FFF !important;
        border: 2px dashed #D9CEC1 !important;
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
        "standard": "QONAQ", "golden": "GOLD", "platinum": "PLATINUM",
        "elite": "ELITE", "thermos": "THERMOS", "telebe": "TƏLƏBƏ", "ikram": "İKRAM"
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
                stamps_html += '<div class="stamp stamp-gift">🎁</div>'
            elif filled == 9:
                stamps_html += '<div class="stamp stamp-empty" style="border-color:#E88D48;color:#E88D48;">🎁</div>'
            else:
                stamps_html += '<div class="stamp stamp-empty">🎁</div>'
        elif i < filled:
            stamps_html += f'<div class="stamp stamp-filled">{num}</div>'
        else:
            stamps_html += f'<div class="stamp stamp-empty">{num}</div>'

    free_html = ""
    if free_count > 0:
        free_html = f'<div class="free-coffee-banner">🎉 {free_count} PULSUZ KOFENİZ HAZIRDIR! Kassada istifadə edin</div>'

    st.markdown(f"""
    <div class="club-card">
        <div class="cc-top">
            <div class="cc-title">EMALATKHANA CLUB</div>
            <div class="cc-tier">{tier}</div>
        </div>
        <div class="cc-desc">Hər kofe alışında 1 stamp qazan! ☕</div>
        <div class="stamp-grid">{stamps_html}</div>
        <div class="cc-footer">{filled}/10 stamp · Pulsuz kofeyə {remaining} qaldı</div>
    </div>
    {free_html}
    """, unsafe_allow_html=True)


def render_rewards(stars, free_count):
    remaining = 10 - (int(stars or 0) % 10)
    pct = int(((10 - remaining) / 10) * 100)

    st.markdown(f"""
    <div class="reward-box">
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
        <div class="reward-box" style="border-left:4px solid #E88D48;">
            <div class="reward-icon gift">🎁</div>
            <div>
                <div class="reward-title">Hədiyyəniz Hazırdır!</div>
                <div class="reward-desc">{free_count} pulsuz kofe kassada gözləyir</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


@st.dialog("📱 QR Kodunuz")
def show_qr_dialog(cid):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={cid}&color=3C2415&bgcolor=F5F0EB"
    st.markdown(f"""
    <div style="text-align:center; padding: 15px;">
        <img src="{qr_url}" style="width:180px; height:180px; border-radius:18px; border:4px solid #3C2415; box-shadow: 0 8px 25px rgba(60,36,21,0.15);"/>
        <h3 style="margin-top:15px; font-weight:900; color:#3C2415; letter-spacing:2px;">{cid}</h3>
        <p style="color:#999; font-size:12px;">Kassada göstərin → Stamp qazanın ☕</p>
    </div>
    """, unsafe_allow_html=True)


def check_notifications(card_id):
    try:
        n = run_query(
            "SELECT id, message FROM notifications WHERE card_id=:c AND (is_read IS NULL OR is_read=FALSE) ORDER BY created_at DESC LIMIT 1",
            {"c": card_id}
        )
        if not n.empty:
            st.markdown(f'<div class="smart-banner notif">🎉 {n.iloc[0]["message"]}</div>', unsafe_allow_html=True)
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
            <div class="smart-banner hh">
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

    st.markdown("<p style='text-align:center; color:#AAA; font-size:12px; margin: 5px 0 10px;'>Sifarişlərinizi kassada verin</p>", unsafe_allow_html=True)

    if "Hamısı" in sel:
        for cat in sorted(filtered['category'].dropna().unique().tolist()):
            cat_items = filtered[filtered['category'] == cat]
            st.markdown(f'<div class="menu-cat-title">{cat}</div>', unsafe_allow_html=True)
            items = cat_items.to_dict('records')
            for idx in range(0, len(items), 2):
                html = '<div class="coffee-grid">'
                for j in range(2):
                    if idx + j < len(items):
                        item = items[idx + j]
                        emoji = get_emoji(item['item_name'])
                        stamp = '<div class="coffee-badge">+1 Stamp ☕</div>' if item['is_coffee'] else ''
                        html += f'''
                        <div class="coffee-card">
                            <div class="coffee-emoji">{emoji}</div>
                            <div class="coffee-name">{item['item_name']}</div>
                            <div class="coffee-price">{float(item['price']):.2f} ₼</div>
                            {stamp}
                        </div>'''
                    else:
                        html += '<div></div>'
                html += '</div>'
                st.markdown(html, unsafe_allow_html=True)
    else:
        for _, item in filtered.iterrows():
            stamp = '<span style="color:#E88D48; margin-right:6px;">⭐</span>' if item['is_coffee'] else ""
            st.markdown(f"""
            <div class="ml-item">
                <div>
                    <div class="ml-name">{item['item_name']}</div>
                    <div class="ml-cat">{item['category'] or ''}</div>
                </div>
                <div style="display:flex; align-items:center;">
                    {stamp}
                    <div class="ml-price">{float(item['price']):.2f} ₼</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_history(card_id):
    sales = run_query(
        "SELECT items, total, created_at, payment_method FROM sales "
        "WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) AND (status IS NULL OR status='COMPLETED') "
        "ORDER BY created_at DESC LIMIT 15",
        {"cid": card_id}
    )
    if sales.empty:
        st.markdown("""
        <div style="text-align:center; padding:30px 20px; color:#BBB;">
            <div style="font-size:40px;">📋</div>
            <div style="font-weight:700; color:#999; margin-top:10px;">Hələ sifariş yoxdur</div>
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
        </div>""", unsafe_allow_html=True)


def render_ai_barista():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:36px;">🤖☕</div>
        <div style="font-weight:900; color:#3A271D; font-size:17px; margin-top:5px;">AI Barista</div>
        <div style="color:#AAA; font-size:12px; margin-top:3px;">Nə içmək istədiyinizi yazın!</div>
    </div>""", unsafe_allow_html=True)

    if 'barista_chat' not in st.session_state:
        st.session_state.barista_chat = []

    for m in st.session_state.barista_chat:
        css = "chat-user" if m['role'] == 'user' else "chat-ai"
        st.markdown(f'<div class="chat-bubble {css}">{m["text"]}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c1:
        um = st.text_input("", placeholder="Yuxuluyam, güclü nəsə...", label_visibility="collapsed", key="b_i")
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
        <div style="font-weight:900; color:#3A271D; font-size:17px; margin-top:5px;">Kofe Falı</div>
        <div style="color:#AAA; font-size:12px; margin-top:3px;">Fincanınızın şəklini çəkin!</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="fortune-zone">
        <div style="font-size:50px;">📸</div>
        <div style="color:#AAA; font-weight:700; margin-top:10px;">Fincanın dibinin şəkli</div>
        <div style="color:#CCC; font-size:11px; margin-top:5px;">Yaxından, işıqlı mühitdə çəkin</div>
    </div>""", unsafe_allow_html=True)

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
                        <div style="text-align:center; font-weight:900; color:#3A271D; margin-bottom:12px; font-size:16px;">SİZİN FALINIZ</div>
                        <div style="color:#555; line-height:1.7; font-size:14px;">{resp.text}</div>
                        <div style="text-align:center; margin-top:15px; font-size:11px; color:#CCC;">☕ Falınız xeyirli olsun!</div>
                    </div>""", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Fal xətası: {e}")


# ============================================================
# MAIN EXPORT FUNCTION
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
    <div class="hero-wrap">
        <div class="hero-icon">☕</div>
        <div class="hero-brand">EMALATKHANA</div>
        <div class="hero-sub">{greet}</div>
    </div>""", unsafe_allow_html=True)

    check_happy_hour()
    check_notifications(customer_id)
    render_stamp_card(stars, c_type)
    render_rewards(stars, free_count)

    st.markdown('<div style="padding:0 16px 14px;">', unsafe_allow_html=True)
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
    <div style="text-align:center; padding:25px 0 15px;">
        <div style="font-family:'Jura'; font-weight:900; font-size:11px; letter-spacing:2px; color:#7A6658;">EMALATKHANA</div>
        <div style="font-size:10px; color:#A69285; margin-top:3px;">Hər kofe bir stamp, hər 10 stamp bir hədiyyə!</div>
    </div>""", unsafe_allow_html=True)
