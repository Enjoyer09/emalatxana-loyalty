# modules/customer_menu.py — FINAL GLOSSY LUXURY v10.0
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
# GLOSSY LUXURY CSS
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;700;800&family=Nunito:wght@400;600;700;800;900&display=swap');

    :root {
        --bg: linear-gradient(180deg, #FFF9F3 0%, #FFF2E8 50%, #FFE9D8 100%);
        --glass: rgba(255,255,255,0.72);
        --glass-strong: rgba(255,255,255,0.85);
        --glass-border: rgba(255,210,170,0.50);
        --glass-shadow: 0 8px 32px rgba(180,100,40,0.08);
        --glass-blur: blur(16px);
        --card-solid: #FFFFFF;
        --orange: #F27D2D;
        --orange-light: #FF9F58;
        --orange-glow: rgba(242,125,45,0.18);
        --orange-soft: #FFF5ED;
        --brown: #6B3415;
        --brown-light: #8A4E28;
        --text: #2B1D14;
        --text-soft: #A0806A;
        --text-muted: #C4A48E;
        --shadow-orange: 0 6px 20px rgba(242,125,45,0.16);
        --radius: 24px;
        --radius-sm: 18px;
    }

    .stApp {
        background: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Nunito', sans-serif !important;
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; padding-bottom: 40px !important; }
    section.main > div:first-child { padding-top: 0 !important; }

    /* ===== HERO ===== */
    .hero {
        background:
            radial-gradient(circle at 80% 15%, rgba(255,255,255,0.25) 0%, transparent 30%),
            radial-gradient(circle at 15% 80%, rgba(255,255,255,0.15) 0%, transparent 25%),
            linear-gradient(155deg, #FFAB6B 0%, #F27D2D 42%, #D96517 100%);
        padding: 30px 18px 54px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .hero::after {
        content: '';
        position: absolute;
        bottom: -22px; left: 0; right: 0;
        height: 46px;
        background: #FFF9F3;
        border-radius: 50% 50% 0 0 / 100% 100% 0 0;
    }
    .hero-icon { font-size: 44px; position: relative; z-index: 2; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.12)); }
    .hero-brand {
        font-family: 'Jura', sans-serif;
        font-size: 25px; font-weight: 800;
        color: white; letter-spacing: 4px;
        text-transform: uppercase;
        position: relative; z-index: 2;
        text-shadow: 0 3px 12px rgba(0,0,0,0.15);
    }
    .hero-sub { color: rgba(255,255,255,0.90); font-size: 13px; margin-top: 6px; font-weight: 700; position: relative; z-index: 2; }

    /* ===== GLASS CARD ===== */
    .glass {
        background: var(--glass-strong);
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius);
        box-shadow: var(--glass-shadow);
        position: relative;
        overflow: hidden;
    }
    .glass::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 50%;
        background: linear-gradient(180deg, rgba(255,255,255,0.35) 0%, transparent 100%);
        border-radius: var(--radius) var(--radius) 0 0;
        pointer-events: none;
    }

    /* ===== LOYALTY CARD ===== */
    .loyalty-card {
        margin: -8px 14px 14px;
        padding: 20px 16px;
        z-index: 5;
    }
    .loyalty-card::after {
        content: '☕';
        position: absolute;
        right: 8px; bottom: -8px;
        font-size: 85px; opacity: 0.04;
    }
    .loyalty-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; position: relative; z-index: 2; }
    .loyalty-title { font-family: 'Jura', sans-serif; font-size: 17px; font-weight: 800; color: var(--brown); letter-spacing: 1px; }
    .tier-badge {
        background: linear-gradient(135deg, var(--orange), var(--orange-light));
        color: white; padding: 6px 14px; border-radius: 20px;
        font-size: 10px; font-weight: 900; letter-spacing: 1px;
        box-shadow: var(--shadow-orange);
    }
    .loyalty-tagline { color: var(--text-soft); font-size: 12px; margin-bottom: 16px; font-weight: 700; position: relative; z-index: 2; }

    /* ===== STAMPS ===== */
    .stamp-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; max-width: 290px; margin: 0 auto 14px; position: relative; z-index: 2; }
    .s {
        width: 50px; height: 50px; border-radius: 50%; margin: 0 auto;
        display: flex; align-items: center; justify-content: center;
        font-weight: 900; font-size: 13px; transition: all 0.3s ease;
    }
    .s-off {
        background: linear-gradient(145deg, #FFF9F4, #FFEEDD);
        border: 2px solid #FFD8BE; color: #D9B49A;
    }
    .s-on {
        background: linear-gradient(145deg, var(--orange), var(--orange-light));
        border: 2px solid var(--orange); color: white;
        box-shadow: 0 4px 12px var(--orange-glow);
    }
    .s-gift {
        background: linear-gradient(145deg, var(--brown), var(--brown-light));
        border: 2px solid var(--brown); color: #FFE8D5;
        box-shadow: 0 4px 14px rgba(107,52,21,0.20);
        animation: pop 1.8s infinite;
    }
    @keyframes pop { 0%,100% { transform: scale(1); } 50% { transform: scale(1.10); } }
    .stamp-info { text-align: center; color: var(--text-soft); font-size: 12px; font-weight: 700; position: relative; z-index: 2; }

    /* ===== FREE BANNER ===== */
    .free-banner {
        margin: 0 14px 12px;
        background: linear-gradient(135deg, var(--orange), #FFB166);
        color: white; border-radius: 20px; padding: 16px;
        text-align: center; font-weight: 900; font-size: 15px;
        box-shadow: var(--shadow-orange);
        animation: glow 3s infinite;
    }
    @keyframes glow {
        0%,100% { box-shadow: 0 6px 20px rgba(242,125,45,0.16); }
        50% { box-shadow: 0 8px 30px rgba(242,125,45,0.28); }
    }

    /* ===== INFO BANNERS ===== */
    .info-bar { margin: 0 14px 12px; border-radius: var(--radius-sm); padding: 12px 16px; text-align: center; font-size: 13px; font-weight: 800; }
    .info-bar.hh { background: linear-gradient(90deg, #FFD86F, #FFB84F); color: #5A3500; }
    .info-bar.msg { background: var(--glass); backdrop-filter: var(--glass-blur); border: 1px solid var(--glass-border); color: #8A5632; }

    /* ===== REWARDS ===== */
    .rw {
        margin: 0 14px 10px;
        padding: 14px 16px;
        display: flex; align-items: center; gap: 14px;
    }
    .rw-ico {
        width: 50px; height: 50px; border-radius: var(--radius-sm);
        display: flex; align-items: center; justify-content: center;
        font-size: 24px; flex-shrink: 0; background: var(--orange-soft);
    }
    .rw-t { font-size: 14px; font-weight: 800; color: var(--brown); }
    .rw-d { font-size: 12px; color: var(--text-soft); margin-top: 2px; }
    .rw-r { margin-left: auto; font-size: 16px; font-weight: 900; color: var(--orange); }

    /* ===== MENU ===== */
    .cat-title {
        font-family: 'Jura', sans-serif;
        font-size: 15px; font-weight: 800; color: var(--brown);
        margin: 16px 14px 8px; text-transform: uppercase; letter-spacing: 1px;
    }
    .mg { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; padding: 0 14px; margin-bottom: 8px; }
    .mc {
        padding: 16px 12px; text-align: center;
        min-height: 160px; display: flex; flex-direction: column; justify-content: center;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .mc:active { transform: scale(0.97); }
    .mc-e { font-size: 34px; margin-bottom: 6px; }
    .mc-n { font-size: 13px; font-weight: 800; color: var(--text); line-height: 1.35; margin-bottom: 4px; }
    .mc-p { font-size: 18px; font-weight: 900; color: var(--orange); }
    .mc-b {
        font-size: 10px; font-weight: 800; color: var(--orange);
        background: var(--orange-soft); padding: 3px 10px;
        border-radius: 12px; margin-top: 6px;
        display: inline-block; align-self: center;
    }

    /* ===== HISTORY ===== */
    .hc {
        margin: 0 14px 10px; padding: 14px 16px;
        border-left: 4px solid var(--orange);
    }
    .hc-d { font-size: 11px; color: var(--text-muted); font-weight: 700; }
    .hc-i { font-size: 13px; color: #5B4A40; line-height: 1.5; margin-top: 4px; }
    .hc-t { font-size: 16px; color: var(--brown); font-weight: 900; margin-top: 6px; }
    .hc-s {
        display: inline-block; margin-top: 6px;
        background: var(--orange-soft); color: var(--orange);
        padding: 3px 10px; border-radius: 12px;
        font-size: 10px; font-weight: 800;
    }

    /* ===== CHAT ===== */
    .cb { padding: 14px 18px; border-radius: 22px; margin-bottom: 8px; max-width: 88%; font-size: 14px; line-height: 1.55; }
    .cb-u {
        background: linear-gradient(135deg, var(--orange), var(--orange-light));
        color: white; margin-left: auto; border-bottom-right-radius: 5px;
        font-weight: 700; box-shadow: var(--shadow-orange);
    }
    .cb-a {
        color: var(--brown); margin-right: auto;
        border-bottom-left-radius: 5px;
    }

    /* ===== FORTUNE ===== */
    .fz {
        border: 2px dashed #FFD3AE; border-radius: var(--radius);
        margin: 14px; padding: 32px 20px; text-align: center;
    }
    .fr {
        border: 2px solid var(--orange); border-radius: var(--radius);
        padding: 22px; margin: 14px;
        box-shadow: var(--shadow-orange);
    }

    /* ===== STREAMLIT OVERRIDES ===== */
    h1, h2, h3, h4 { color: var(--text) !important; }

    div[data-baseweb="input"] > div {
        background: var(--glass-strong) !important;
        backdrop-filter: var(--glass-blur) !important;
        border: 2px solid var(--glass-border) !important;
        border-radius: var(--radius-sm) !important;
        box-shadow: none !important;
    }
    div[data-baseweb="input"] input {
        color: var(--text) !important; font-weight: 600 !important;
        -webkit-text-fill-color: var(--text) !important;
    }
    div[data-baseweb="input"] input::placeholder {
        color: var(--text-muted) !important;
        -webkit-text-fill-color: var(--text-muted) !important;
    }

    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, var(--orange), var(--orange-light)) !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        box-shadow: var(--shadow-orange) !important;
        min-height: 52px !important;
        position: relative;
        overflow: hidden;
    }
    button[kind="primary"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 50%;
        background: linear-gradient(180deg, rgba(255,255,255,0.22) 0%, transparent 100%);
        border-radius: var(--radius-sm) var(--radius-sm) 0 0;
        pointer-events: none;
    }
    button[kind="primary"]:active { transform: scale(0.97) !important; }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p {
        color: white !important; font-weight: 900 !important; font-size: 15px !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background: var(--glass) !important;
        backdrop-filter: var(--glass-blur) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: var(--radius-sm) !important;
        box-shadow: var(--glass-shadow) !important;
        min-height: 52px !important;
        position: relative;
        overflow: hidden;
    }
    button[kind="secondary"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 50%;
        background: linear-gradient(180deg, rgba(255,255,255,0.30) 0%, transparent 100%);
        border-radius: var(--radius-sm) var(--radius-sm) 0 0;
        pointer-events: none;
    }
    button[kind="secondary"] p {
        color: var(--brown) !important; font-weight: 800 !important; font-size: 14px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
        border: none !important; box-shadow: none !important; padding: 0 !important;
    }

    div[role="radiogroup"] > label {
        background: var(--glass) !important;
        backdrop-filter: var(--glass-blur) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 14px !important;
        padding: 6px 12px !important;
        min-height: auto !important;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p { color: var(--text-soft) !important; font-size: 12px !important; font-weight: 700 !important; }
    div[role="radiogroup"] label:has(input:checked) {
        background: var(--orange) !important; border-color: var(--orange) !important;
    }
    div[role="radiogroup"] label:has(input:checked) p { color: white !important; }

    div[role="dialog"] > div {
        background: #FFF9F3 !important;
        border: 2px solid var(--orange) !important;
        border-radius: 26px !important;
    }

    .stFileUploader > div {
        background: var(--glass) !important;
        backdrop-filter: var(--glass-blur) !important;
        border: 2px dashed #FFD3AE !important;
        border-radius: 20px !important;
    }

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
# STAMP CARD
# ============================================================
def render_stamp_card(stars, cust_type):
    tier_map = {"standard": "QONAQ", "golden": "GOLD", "platinum": "PLATINUM",
                "elite": "ELITE", "thermos": "THERMOS", "telebe": "TƏLƏBƏ", "ikram": "İKRAM"}
    tier = tier_map.get(str(cust_type).lower(), "QONAQ")
    current = int(stars or 0)
    filled = current % 10
    remaining = 10 - filled

    stamps = ""
    for i in range(10):
        num = i + 1
        if i == 9:
            if filled >= 10: stamps += '<div class="s s-gift">🎁</div>'
            elif filled == 9: stamps += '<div class="s s-off" style="border-color:#E46C24;color:#E46C24;">🎁</div>'
            else: stamps += '<div class="s s-off">🎁</div>'
        elif i < filled: stamps += f'<div class="s s-on">{num}</div>'
        else: stamps += f'<div class="s s-off">{num}</div>'

    st.markdown(f"""
    <div class="glass loyalty-card">
        <div class="loyalty-top">
            <div class="loyalty-title">EMALATKHANA CLUB</div>
            <div class="tier-badge">{tier}</div>
        </div>
        <div class="loyalty-tagline">Hər kofe = 1 stamp · 10 stamp = 1 hədiyyə ☕</div>
        <div class="stamp-grid">{stamps}</div>
        <div class="stamp-info">{filled}/10 stamp · {remaining} stamp qaldı</div>
    </div>
    """, unsafe_allow_html=True)


def render_free_banner(free_count):
    if free_count > 0:
        st.markdown(f'<div class="free-banner">🎉 {free_count} PULSUZ KOFENİZ HAZIRDIR!</div>', unsafe_allow_html=True)


def render_rewards(stars, free_count):
    remaining = 10 - (int(stars or 0) % 10)
    pct = int(((10 - remaining) / 10) * 100)

    st.markdown(f"""
    <div class="glass rw">
        <div class="rw-ico">☕</div>
        <div><div class="rw-t">Pulsuz Kofe</div><div class="rw-d">10 stamp = 1 hədiyyə</div></div>
        <div class="rw-r">{pct}%</div>
    </div>
    """, unsafe_allow_html=True)

    if free_count > 0:
        st.markdown(f"""
        <div class="glass rw">
            <div class="rw-ico">🎁</div>
            <div><div class="rw-t">Hazır Hədiyyə</div><div class="rw-d">{free_count} pulsuz kofe gözləyir</div></div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# QR DIALOG
# ============================================================
@st.dialog("📱 QR Kodunuz")
def show_qr_dialog(cid):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={cid}&color=F27D2D&bgcolor=FFF9F3"
    st.markdown(f"""
    <div style="text-align:center; padding: 18px;">
        <img src="{qr_url}" style="width:200px; height:200px; border-radius:22px; border:4px solid #F27D2D; box-shadow: 0 10px 30px rgba(242,125,45,0.18);"/>
        <h3 style="margin-top:16px; font-weight:900; color:#F27D2D; letter-spacing:3px;">{cid}</h3>
        <p style="color:#A08C7C; font-size:12px; margin-top:6px;">Kassada göstərin → Stamp qazanın ☕</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# BANNERS
# ============================================================
def check_notifications(card_id):
    try:
        n = run_query("SELECT id, message FROM notifications WHERE card_id=:c AND (is_read IS NULL OR is_read=FALSE) ORDER BY created_at DESC LIMIT 1", {"c": card_id})
        if not n.empty:
            st.markdown(f'<div class="info-bar msg">🎉 {n.iloc[0]["message"]}</div>', unsafe_allow_html=True)
            if st.button("✓ Oxudum", key="notif_x", use_container_width=True):
                run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id": n.iloc[0]['id']})
                st.rerun()
    except: pass


def check_happy_hour():
    try:
        from utils import get_active_happy_hour
        hh = get_active_happy_hour()
        if hh:
            st.markdown(f'<div class="info-bar hh">⏰ HAPPY HOUR! {hh["discount_percent"]}% ENDİRİM · {hh["name"]} · {hh["end_time"][:5]}-ə qədər!</div>', unsafe_allow_html=True)
    except: pass


# ============================================================
# QUICK ACTIONS (Funksional — tab əvəzinə)
# ============================================================
def render_quick_actions():
    if 'cust_screen' not in st.session_state:
        st.session_state.cust_screen = 'menu'

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("☕\nMenyu", key="qa_menu", use_container_width=True,
                      type="primary" if st.session_state.cust_screen == 'menu' else "secondary"):
            st.session_state.cust_screen = 'menu'
            st.rerun()
    with c2:
        if st.button("📜\nTarixçə", key="qa_hist", use_container_width=True,
                      type="primary" if st.session_state.cust_screen == 'history' else "secondary"):
            st.session_state.cust_screen = 'history'
            st.rerun()
    with c3:
        if st.button("🤖\nBarista", key="qa_bar", use_container_width=True,
                      type="primary" if st.session_state.cust_screen == 'barista' else "secondary"):
            st.session_state.cust_screen = 'barista'
            st.rerun()
    with c4:
        if st.button("🔮\nFal", key="qa_fal", use_container_width=True,
                      type="primary" if st.session_state.cust_screen == 'fortune' else "secondary"):
            st.session_state.cust_screen = 'fortune'
            st.rerun()


# ============================================================
# MENU
# ============================================================
def render_coffee_menu():
    menu_df = run_query("SELECT item_name, price, category, is_coffee FROM menu WHERE is_active=TRUE ORDER BY category, item_name")
    if menu_df.empty:
        st.info("Menyu yenilənir...")
        return

    emoji_map = {"latte":"☕","espresso":"⚡","americano":"🫗","cappuccino":"🥛","mocha":"🍫","macchiato":"🎨","flat":"☕","raf":"🧁","turkish":"🫖","cold":"🧊","ice":"🧊","frappe":"🥤","matcha":"🍵","hot":"🔥","chocolate":"🍫","tea":"🍵","kruasan":"🥐","croissant":"🥐","cookie":"🍪"}

    def emoji(name):
        for k, e in emoji_map.items():
            if k in name.lower(): return e
        return "☕"

    cats = menu_df['category'].dropna().unique().tolist()
    sel = st.radio("Kat", ["☕ Hamısı"] + sorted(cats), horizontal=True, label_visibility="collapsed", key="cm_c")
    filtered = menu_df if "Hamısı" in sel else menu_df[menu_df['category'] == sel.replace("☕ ", "")]

    st.markdown("<p style='text-align:center; color:#C4A48E; font-size:12px; margin:5px 0 10px;'>Sifarişlərinizi kassada verin</p>", unsafe_allow_html=True)

    if "Hamısı" in sel:
        for cat in sorted(filtered['category'].dropna().unique().tolist()):
            ci = filtered[filtered['category'] == cat].to_dict('records')
            st.markdown(f'<div class="cat-title">{cat}</div>', unsafe_allow_html=True)
            for idx in range(0, len(ci), 2):
                h = '<div class="mg">'
                for j in range(2):
                    if idx+j < len(ci):
                        it = ci[idx+j]
                        h += f'<div class="glass mc"><div class="mc-e">{emoji(it["item_name"])}</div><div class="mc-n">{it["item_name"]}</div><div class="mc-p">{float(it["price"]):.2f} ₼</div>{"<div class=mc-b>+1 Stamp ☕</div>" if it["is_coffee"] else ""}</div>'
                    else: h += '<div></div>'
                h += '</div>'
                st.markdown(h, unsafe_allow_html=True)
    else:
        items = filtered.to_dict('records')
        for idx in range(0, len(items), 2):
            h = '<div class="mg">'
            for j in range(2):
                if idx+j < len(items):
                    it = items[idx+j]
                    h += f'<div class="glass mc"><div class="mc-e">{emoji(it["item_name"])}</div><div class="mc-n">{it["item_name"]}</div><div class="mc-p">{float(it["price"]):.2f} ₼</div>{"<div class=mc-b>+1 Stamp ☕</div>" if it["is_coffee"] else ""}</div>'
                else: h += '<div></div>'
            h += '</div>'
            st.markdown(h, unsafe_allow_html=True)


# ============================================================
# HISTORY
# ============================================================
def render_history(card_id):
    sales = run_query("SELECT items, total, created_at, payment_method FROM sales WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) AND (status IS NULL OR status='COMPLETED') ORDER BY created_at DESC LIMIT 15", {"cid": card_id})
    if sales.empty:
        st.markdown('<div style="text-align:center; padding:30px; color:#C4A48E;"><div style="font-size:40px;">📋</div><div style="font-weight:700; margin-top:10px;">Hələ sifariş yoxdur</div></div>', unsafe_allow_html=True)
        return

    for _, row in sales.iterrows():
        try: ds = row['created_at'].strftime("%d.%m.%Y · %H:%M")
        except: ds = "-"
        try:
            items = json.loads(row['items'])
            istr = " · ".join([f"{i['item_name']} ×{i['qty']}" for i in items])
            cc = sum([i['qty'] for i in items if i.get('is_coffee')])
        except: istr = str(row['items'])[:50]; cc = 0
        pm = "💵" if row.get('payment_method') in ['Nəğd', 'Cash'] else "💳"
        sh = f'<div class="hc-s">+{cc} stamp ☕</div>' if cc > 0 else ""
        st.markdown(f'<div class="glass hc"><div class="hc-d">{ds} {pm}</div><div class="hc-i">{istr}</div><div class="hc-t">{float(row["total"]):.2f} ₼</div>{sh}</div>', unsafe_allow_html=True)


# ============================================================
# AI BARISTA
# ============================================================
def render_ai_barista():
    st.markdown('<div style="text-align:center; padding:12px 16px 5px;"><div style="font-size:36px;">🤖☕</div><div style="font-weight:900; color:#6B3415; font-size:17px; margin-top:5px;">AI Barista</div><div style="color:#A0806A; font-size:12px; margin-top:3px;">Əhvalınızı yazın, kofe seçək</div></div>', unsafe_allow_html=True)

    if 'barista_chat' not in st.session_state:
        st.session_state.barista_chat = []

    for m in st.session_state.barista_chat:
        css = "cb-u" if m['role'] == 'user' else "cb-a"
        bg_class = f"cb {css}" if m['role'] == 'user' else f"glass cb {css}"
        st.markdown(f'<div class="{bg_class}">{m["text"]}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c1:
        um = st.text_input("", placeholder="Məs: Yuxuluyam, şirin güclü nəsə...", label_visibility="collapsed", key="b_i")
    with c2:
        go = st.button("📤", key="b_s")

    if go and um.strip():
        st.session_state.barista_chat.append({'role': 'user', 'text': um})
        model, _ = get_ai_model()
        if model:
            try:
                mdf = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE AND is_coffee=TRUE")
                mt = ", ".join([f"{r['item_name']} ({r['price']}₼)" for _, r in mdf.iterrows()]) if not mdf.empty else ""
                r = model.generate_content(f"Sən premium kofe shop baristasısan. Menyu: {mt}. Müştəri: '{um}'. 1-2 kofe təklif et. Qısa, emoji ilə.")
                ai = r.text
            except: ai = "Bağışla, bir az yoruldum ☕"
        else: ai = "AI bağlantısı yoxdur 🔌"
        st.session_state.barista_chat.append({'role': 'ai', 'text': ai})
        st.rerun()

    if st.session_state.barista_chat:
        if st.button("🗑️ Təmizlə", use_container_width=True, key="clr"):
            st.session_state.barista_chat = []
            st.rerun()


# ============================================================
# FORTUNE
# ============================================================
def render_fortune():
    st.markdown('<div style="text-align:center; padding:12px 16px 5px;"><div style="font-size:40px;">🔮☕</div><div style="font-weight:900; color:#6B3415; font-size:17px; margin-top:5px;">Kofe Falı</div><div style="color:#A0806A; font-size:12px; margin-top:3px;">Fincanınızın şəklini çəkin!</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="glass fz"><div style="font-size:50px;">📸</div><div style="color:#A0806A; font-weight:700; margin-top:10px;">Fincanın dibinin şəkli</div></div>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Şəkil", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed", key="fu")
    if uploaded:
        st.image(uploaded, use_container_width=True)
        if st.button("🔮 Falıma Bax!", type="primary", use_container_width=True, key="fb"):
            with st.spinner("Falçı oxuyur... 🔮"):
                model, all_m = get_ai_model()
                if not model: st.error("Falçı yuxudadır 😴"); return
                try:
                    vm = next((m for m in (all_m or []) if 'vision' in m.lower() or 'flash' in m.lower()), (all_m or ['gemini-pro'])[0])
                    vmodel = genai.GenerativeModel(vm)
                    prompt = "Sən Azərbaycan falçısısan. Kofe fincanına baxırsan. Müsbət, əyləncəli fal de. 4-5 cümlə, Azərbaycan dilində, emoji ilə."
                    resp = vmodel.generate_content([prompt, Image.open(uploaded)] if Image else prompt)
                    st.markdown(f'<div class="glass fr"><div style="text-align:center; font-size:24px; margin-bottom:12px;">🔮✨</div><div style="text-align:center; font-weight:900; color:#6B3415; margin-bottom:12px;">SİZİN FALINIZ</div><div style="color:#5B4A40; line-height:1.7; font-size:14px;">{resp.text}</div><div style="text-align:center; margin-top:15px; font-size:11px; color:#C4A48E;">☕ Falınız xeyirli olsun!</div></div>', unsafe_allow_html=True)
                except Exception as e: st.error(f"Fal xətası: {e}")


# ============================================================
# MAIN
# ============================================================
def render_customer_app(customer_id=None):
    inject_customer_css()

    if not customer_id:
        st.error("QR Kod oxunmadı."); return

    c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
    if c_df.empty:
        st.error("Müştəri tapılmadı."); return

    cust = c_df.iloc[0].to_dict()
    stars = int(cust.get('stars', 0))
    c_type = str(cust.get('type', 'standard'))
    free_count = stars // 10

    hour = get_baku_now().hour
    greet = "Sabahınız xeyir ☕" if 5 <= hour < 12 else "Günortanız xeyir ☀️" if hour < 18 else "Axşamınız xeyir 🌙"

    st.markdown(f"""
    <div class="hero">
        <div class="hero-icon">☕</div>
        <div class="hero-brand">EMALATKHANA</div>
        <div class="hero-sub">{greet}</div>
    </div>
    """, unsafe_allow_html=True)

    check_happy_hour()
    check_notifications(customer_id)
    render_stamp_card(stars, c_type)
    render_free_banner(free_count)
    render_rewards(stars, free_count)
    render_quick_actions()

    st.markdown('<div style="padding:0 14px 14px;">', unsafe_allow_html=True)
    if st.button("📱 QR KODUMU GÖSTƏR", type="primary", use_container_width=True, key="qr_s"):
        show_qr_dialog(customer_id)
    st.markdown('</div>', unsafe_allow_html=True)

    screen = st.session_state.get('cust_screen', 'menu')
    if screen == 'menu': render_coffee_menu()
    elif screen == 'history': render_history(customer_id)
    elif screen == 'barista': render_ai_barista()
    elif screen == 'fortune': render_fortune()

    st.markdown("""
    <div style="text-align:center; padding:24px 0 14px;">
        <div style="font-family:'Jura'; font-weight:900; font-size:11px; letter-spacing:3px; color:#B5856D;">EMALATKHANA</div>
        <div style="font-size:10px; color:#C9A48F; margin-top:4px;">Every coffee tells a story ☕</div>
    </div>
    """, unsafe_allow_html=True)
