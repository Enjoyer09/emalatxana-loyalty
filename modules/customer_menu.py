# modules/customer_menu.py — DIGITAL STAMP CARD v5.0
import streamlit as st
import pandas as pd
import json
import logging
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
# CSS — DİGİTAL STAMP CARD STİLİ
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

    .stApp { 
        background: #F5F0EB !important; 
        color: #2D2926 !important; 
        font-family: 'Nunito', sans-serif !important; 
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section.main > div:first-child { padding-top: 0 !important; }

    /* ===== HERO ===== */
    .app-hero {
        background: linear-gradient(160deg, #3C2415 0%, #5C3A28 50%, #8B5E3C 100%);
        padding: 30px 20px 45px;
        text-align: center;
        position: relative;
    }
    .app-hero::after {
        content: '';
        position: absolute;
        bottom: -20px;
        left: 0; right: 0;
        height: 40px;
        background: #F5F0EB;
        border-radius: 50% 50% 0 0 / 100% 100% 0 0;
    }
    .app-logo { font-weight: 900; font-size: 24px; color: #F5E6D3; letter-spacing: 3px; }
    .app-logo-icon { font-size: 36px; margin-bottom: 5px; }
    .app-greet { font-size: 13px; color: rgba(245,230,211,0.7); margin-top: 5px; }

    /* ===== STAMP CARD ===== */
    .stamp-card {
        background: #FFFFFF;
        border-radius: 24px;
        padding: 24px 20px;
        margin: 0px 16px 16px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.08);
        border: 1px solid #EDE8E3;
    }
    .sc-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .sc-title {
        font-weight: 900;
        font-size: 18px;
        color: #3C2415;
        letter-spacing: 0.5px;
    }
    .sc-tier {
        background: linear-gradient(135deg, #3C2415, #5C3A28);
        color: #F5E6D3;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 800;
    }
    .sc-subtitle {
        font-size: 13px;
        color: #999;
        margin-bottom: 20px;
    }

    /* ===== STAMPS GRID (Şəkildəki kimi) ===== */
    .stamps-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 10px;
        margin: 0 auto 15px;
        max-width: 300px;
    }
    .stamp-circle {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 900;
        margin: 0 auto;
        position: relative;
    }
    .stamp-empty {
        background: #F5F0EB;
        border: 2.5px solid #DDD5CC;
        color: #C4B8AA;
    }
    .stamp-filled {
        background: #3C2415;
        border: 2.5px solid #3C2415;
        color: #F5E6D3;
        box-shadow: 0 3px 10px rgba(60,36,21,0.3);
    }
    .stamp-gift {
        background: linear-gradient(135deg, #E88D48, #D4763A);
        border: 2.5px solid #E88D48;
        color: #FFF;
        box-shadow: 0 3px 12px rgba(232,141,72,0.4);
        animation: giftPulse 2s infinite;
    }
    @keyframes giftPulse {
        0%, 100% { transform: scale(1); box-shadow: 0 3px 12px rgba(232,141,72,0.4); }
        50% { transform: scale(1.08); box-shadow: 0 5px 18px rgba(232,141,72,0.6); }
    }

    .sc-footer-text {
        text-align: center;
        font-size: 12px;
        color: #AAA;
        font-weight: 600;
    }

    /* ===== FREE COFFEE ALERT ===== */
    .free-alert {
        background: linear-gradient(135deg, #E88D48, #D4763A);
        color: #FFF;
        padding: 14px;
        border-radius: 16px;
        margin: 0 16px 16px;
        text-align: center;
        font-weight: 900;
        font-size: 15px;
        box-shadow: 0 6px 20px rgba(232,141,72,0.35);
    }

    /* ===== REWARDS SECTION ===== */
    .reward-card {
        background: #FFF;
        border: 1px solid #EDE8E3;
        border-radius: 16px;
        padding: 14px 16px;
        margin: 0 16px 10px;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .rw-icon {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        flex-shrink: 0;
    }
    .rw-icon-coffee { background: #F0E4D7; }
    .rw-icon-gift { background: #E8F5E9; }
    .rw-icon-star { background: #FFF3E0; }
    .rw-title { font-weight: 800; font-size: 14px; color: #2D2926; }
    .rw-desc { font-size: 12px; color: #999; margin-top: 2px; }
    .rw-right { margin-left: auto; text-align: right; }
    .rw-points { font-weight: 900; font-size: 14px; color: #3C2415; }

    /* ===== NAV BUTTONS ===== */
    .nav-section { padding: 0 16px; margin-bottom: 12px; }

    /* ===== MENYU (Compact + Yalnız Kofe) ===== */
    .coffee-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        padding: 0 16px;
    }
    .cg-item {
        background: #FFF;
        border: 1px solid #EDE8E3;
        border-radius: 16px;
        padding: 14px;
        text-align: center;
        transition: all 0.15s;
    }
    .cg-item:active { transform: scale(0.97); }
    .cg-emoji { font-size: 32px; margin-bottom: 6px; }
    .cg-name { font-weight: 800; font-size: 13px; color: #2D2926; line-height: 1.3; margin-bottom: 4px; }
    .cg-price { font-weight: 900; font-size: 17px; color: #3C2415; }
    .cg-stamp { font-size: 10px; color: #E88D48; font-weight: 700; margin-top: 4px; }

    /* Menyu kateqoriya başlığı */
    .menu-head {
        font-size: 16px;
        font-weight: 900;
        color: #3C2415;
        margin: 15px 16px 8px;
        padding-bottom: 6px;
        border-bottom: 2px solid #EDE8E3;
    }

    /* ===== TARİXÇƏ ===== */
    .h-item {
        background: #FFF;
        border: 1px solid #EDE8E3;
        border-radius: 14px;
        padding: 14px;
        margin: 0 16px 8px;
    }
    .h-date { font-size: 11px; color: #BBB; font-weight: 600; }
    .h-items { font-size: 13px; color: #555; margin-top: 4px; line-height: 1.4; }
    .h-total { font-size: 15px; font-weight: 900; color: #3C2415; margin-top: 6px; }
    .h-stamp-earned { 
        display: inline-block;
        background: #F0E4D7;
        color: #3C2415;
        padding: 2px 8px;
        border-radius: 8px;
        font-size: 10px;
        font-weight: 800;
        margin-top: 4px;
    }

    /* ===== BANNER ===== */
    .promo-bar {
        background: linear-gradient(90deg, #E88D48, #F0A060);
        color: #FFF;
        padding: 12px 16px;
        border-radius: 14px;
        margin: 8px 16px;
        text-align: center;
        font-weight: 800;
        font-size: 13px;
        box-shadow: 0 4px 15px rgba(232,141,72,0.3);
        animation: slideIn 0.5s ease-out;
    }
    @keyframes slideIn { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

    /* ===== CHAT ===== */
    .msg { padding: 12px 16px; border-radius: 18px; margin-bottom: 8px; max-width: 85%; font-size: 14px; line-height: 1.5; }
    .msg-u { background: #3C2415; color: #F5E6D3; margin-left: auto; border-bottom-right-radius: 4px; font-weight: 700; }
    .msg-a { background: #FFF; color: #333; margin-right: auto; border-bottom-left-radius: 4px; border: 1px solid #EDE8E3; }

    /* ===== FORTUNE ===== */
    .fz { border: 2px dashed #DDD5CC; border-radius: 20px; padding: 30px 20px; text-align: center; margin: 15px 16px; background: #FFF; }
    .fr { background: #FFF; border: 2px solid #E88D48; border-radius: 20px; padding: 20px; margin: 15px 16px; }

    /* ===== STREAMLIT ===== */
    h1,h2,h3,h4 { color: #2D2926 !important; }
    div[data-baseweb="input"] > div { background: #FFF !important; border: 2px solid #EDE8E3 !important; border-radius: 14px !important; box-shadow: none !important; }
    div[data-baseweb="input"] input { color: #2D2926 !important; font-weight: 600 !important; -webkit-text-fill-color: #2D2926 !important; }
    div[data-baseweb="input"] input::placeholder { color: #CCC !important; -webkit-text-fill-color: #CCC !important; }
    
    button[kind="primary"] { background: linear-gradient(135deg, #3C2415, #5C3A28) !important; border: none !important; border-radius: 14px !important; box-shadow: 0 4px 15px rgba(60,36,21,0.25) !important; min-height: auto !important; }
    button[kind="primary"] p { color: #F5E6D3 !important; font-weight: 900 !important; font-size: 15px !important; }
    button[kind="secondary"] { background: #FFF !important; border: 1px solid #EDE8E3 !important; border-radius: 14px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important; min-height: auto !important; }
    button[kind="secondary"] p { color: #333 !important; font-weight: 700 !important; font-size: 14px !important; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 0; background: #FFF; border-radius: 14px; padding: 4px; margin: 0 16px 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #EDE8E3; }
    .stTabs [data-baseweb="tab"] { border-radius: 11px !important; color: #999 !important; font-weight: 700 !important; font-size: 12px !important; padding: 8px 4px !important; }
    .stTabs [aria-selected="true"] { background: #3C2415 !important; color: #F5E6D3 !important; font-weight: 900 !important; }

    div[role="radiogroup"] > label { background: #FFF !important; border: 1px solid #EDE8E3 !important; border-radius: 10px !important; padding: 6px 12px !important; box-shadow: none !important; min-height: auto !important; }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p { color: #888 !important; font-size: 12px !important; font-weight: 700 !important; }
    div[role="radiogroup"] label:has(input:checked) { background: #3C2415 !important; border-color: #3C2415 !important; transform: none !important; box-shadow: none !important; }
    div[role="radiogroup"] label:has(input:checked) p { color: #F5E6D3 !important; }

    div[role="dialog"] > div { background: #F5F0EB !important; border: 2px solid #3C2415 !important; border-radius: 20px !important; }
    .stFileUploader > div { background: #FFF !important; border: 2px dashed #DDD5CC !important; border-radius: 14px !important; }
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
# STAMP CARD (Şəkildəki kimi 5x2 grid)
# ============================================================
def render_stamp_card(stars, cust_type):
    tier_map = {
        "standard": "QONAQ", "golden": "GOLD", "platinum": "PLATINUM",
        "elite": "ELITE", "thermos": "THERMOS", "telebe": "TƏLƏBƏ", "ikram": "İKRAM"
    }
    tier = tier_map.get(str(cust_type).lower(), "QONAQ")
    current = int(stars or 0)
    filled = current % 10
    free_count = current // 10

    # 10 stamp — 5x2 grid (şəkildəki kimi 1-10 nömrəli)
    stamps_html = ""
    for i in range(10):
        num = i + 1
        if i == 9:
            # 10-cu stamp = hədiyyə ikonu
            if filled >= 10:
                stamps_html += '<div class="stamp-circle stamp-gift">🎁</div>'
            elif filled == 9:
                stamps_html += '<div class="stamp-circle stamp-empty" style="border-color:#E88D48; color:#E88D48;">🎁</div>'
            else:
                stamps_html += '<div class="stamp-circle stamp-empty">🎁</div>'
        elif i < filled:
            stamps_html += f'<div class="stamp-circle stamp-filled">{num}</div>'
        else:
            stamps_html += f'<div class="stamp-circle stamp-empty">{num}</div>'

    # Free alert
    free_html = ""
    if free_count > 0:
        free_html = f'<div class="free-alert">🎉 {free_count} PULSUZ KOFENİZ HAZIRDIR! Kassada istifadə edin</div>'

    st.markdown(f"""
    <div class="stamp-card">
        <div class="sc-header">
            <div class="sc-title">YOUR STAMPS</div>
            <div class="sc-tier">{tier}</div>
        </div>
        <div class="sc-subtitle">Hər kofe alışında 1 stamp qazan!</div>
        <div class="stamps-grid">{stamps_html}</div>
        <div class="sc-footer-text">☕ {filled}/10 stamp · Pulsuz kofeyə {10 - filled} qaldı</div>
    </div>
    {free_html}
    """, unsafe_allow_html=True)


# ============================================================
# REWARDS SECTİON (Şəkildəki kimi)
# ============================================================
def render_rewards_section(stars, free_count):
    remaining = 10 - (int(stars or 0) % 10)
    pct = int(((10 - remaining) / 10) * 100)

    st.markdown(f"""
    <div class="reward-card">
        <div class="rw-icon rw-icon-coffee">☕</div>
        <div>
            <div class="rw-title">Pulsuz Kofe</div>
            <div class="rw-desc">10 stamp topla, 1 pulsuz kofe qazan</div>
        </div>
        <div class="rw-right">
            <div class="rw-points">{pct}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if free_count > 0:
        st.markdown(f"""
        <div class="reward-card" style="border-left: 4px solid #E88D48;">
            <div class="rw-icon rw-icon-gift">🎁</div>
            <div>
                <div class="rw-title">Hədiyyəniz Hazırdır!</div>
                <div class="rw-desc">{free_count} pulsuz kofe kassada gözləyir</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# QR DİALOQ
# ============================================================
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


# ============================================================
# MENYU (Yalnız Kofelər — Compact Grid)
# ============================================================
def render_coffee_menu():
    menu_df = run_query("SELECT item_name, price, category, is_coffee FROM menu WHERE is_active=TRUE ORDER BY category, item_name")
    if menu_df.empty:
        st.info("Menyu yenilənir...")
        return

    # Kofe emojisi map
    emoji_map = {
        "latte": "☕", "espresso": "⚡", "americano": "🫗", "cappuccino": "🥛",
        "mocha": "🍫", "macchiato": "🎨", "flat": "☕", "raf": "🧁",
        "turkish": "🫖", "cold": "🧊", "ice": "🧊", "frappe": "🥤",
        "matcha": "🍵", "hot": "🔥", "chocolate": "🍫", "tea": "🍵",
        "kombo": "🎁", "combo": "🎁"
    }

    def get_emoji(name):
        name_lower = name.lower()
        for key, emoji in emoji_map.items():
            if key in name_lower:
                return emoji
        return "☕"

    # Kateqoriya filteri
    cats = menu_df['category'].dropna().unique().tolist()
    all_cats = ["☕ Hamısı"] + sorted(cats)
    sel = st.radio("Kat", all_cats, horizontal=True, label_visibility="collapsed", key="cm_cat")

    filtered = menu_df if "Hamısı" in sel else menu_df[menu_df['category'] == sel.replace("☕ ", "")]

    # Grid render
    items = filtered.to_dict('records')
    for idx in range(0, len(items), 2):
        html = '<div class="coffee-grid">'
        for j in range(2):
            if idx + j < len(items):
                item = items[idx + j]
                emoji = get_emoji(item['item_name'])
                stamp_txt = '<div class="cg-stamp">+1 Stamp ☕</div>' if item['is_coffee'] else ''
                html += f'''
                <div class="cg-item">
                    <div class="cg-emoji">{emoji}</div>
                    <div class="cg-name">{item['item_name']}</div>
                    <div class="cg-price">{float(item['price']):.2f} ₼</div>
                    {stamp_txt}
                </div>'''
            else:
                html += '<div></div>'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)


# ============================================================
# TARİXÇƏ
# ============================================================
def render_history(card_id):
    sales = run_query(
        "SELECT items, total, created_at, payment_method FROM sales "
        "WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) "
        "ORDER BY created_at DESC LIMIT 15",
        {"cid": card_id}
    )
    if sales.empty:
        st.markdown("""
        <div style="text-align:center; padding:30px 20px; color:#BBB;">
            <div style="font-size:40px;">📋</div>
            <div style="font-weight:700; color:#999; margin-top:10px;">Hələ sifariş yoxdur</div>
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
        stamp_html = f'<div class="h-stamp-earned">+{coffee_count} stamp ☕</div>' if coffee_count > 0 else ""

        st.markdown(f"""
        <div class="h-item">
            <div class="h-date">{ds} {pm}</div>
            <div class="h-items">{istr}</div>
            <div class="h-total">{float(row['total']):.2f} ₼</div>
            {stamp_html}
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
            st.markdown(f'<div class="promo-bar">🎉 {n.iloc[0]["message"]}</div>', unsafe_allow_html=True)
            if st.button("✓ Oxudum", key="notif_x"):
                run_action("UPDATE notifications SET is_read=TRUE WHERE id=:id", {"id": n.iloc[0]['id']})
                st.rerun()
    except:
        pass


# ============================================================
# AI BARİSTA
# ============================================================
def render_barista():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:36px;">🤖☕</div>
        <div style="font-weight:900; color:#3C2415; font-size:17px; margin-top:5px;">AI Barista</div>
        <div style="color:#AAA; font-size:12px; margin-top:3px;">Əhvalınızı yazın, sizə ideal kofe seçim!</div>
    </div>""", unsafe_allow_html=True)

    if 'barista_chat' not in st.session_state:
        st.session_state.barista_chat = []

    for m in st.session_state.barista_chat:
        css = "msg-u" if m['role'] == 'user' else "msg-a"
        st.markdown(f'<div class="msg {css}">{m["text"]}</div>', unsafe_allow_html=True)

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
                p = f"""Sən 'Emalatkhana' kofe şopunun gənc, səmimi baristasısan.
Kofe menyumuz: {mt}
Müştəri: '{um}'
1-2 kofe təklif et. Qısa (2-3 cümlə), emoji ilə. Qiymət yaz. Sonda 'Kassaya buyurun! ☕'"""
                r = model.generate_content(p)
                ai = r.text
            except:
                ai = "Bağışla, bir az yoruldum ☕"
        else:
            ai = "AI bağlantısı yoxdur 🔌"
        st.session_state.barista_chat.append({'role': 'ai', 'text': ai})
        st.rerun()

    if st.session_state.barista_chat:
        if st.button("🗑️ Təmizlə", use_container_width=True, key="clr"):
            st.session_state.barista_chat = []
            st.rerun()


# ============================================================
# KOFE FALI
# ============================================================
def render_fortune():
    st.markdown("""
    <div style="text-align:center; padding:12px 16px 5px;">
        <div style="font-size:40px;">🔮☕</div>
        <div style="font-weight:900; color:#3C2415; font-size:17px; margin-top:5px;">Kofe Falı</div>
        <div style="color:#AAA; font-size:12px; margin-top:3px;">Fincanınızın şəklini çəkin!</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="fz">
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
                                vm = m; break
                        if not vm: vm = all_m[0]
                    vmodel = genai.GenerativeModel(vm)
                    prompt = """Sən Azərbaycan falçısısan. Kofe fincanının dibini görürsən.
Müsbət, əyləncəli fal de (4-5 cümlə). Sevgi, iş, pul, səyahətdən birini seç.
Azərbaycan dilində, emoji ilə, sirli üslubda."""
                    if Image:
                        img = Image.open(uploaded)
                        resp = vmodel.generate_content([prompt, img])
                    else:
                        resp = model.generate_content(prompt)
                    st.markdown(f"""
                    <div class="fr">
                        <div style="text-align:center; font-size:24px; margin-bottom:12px;">🔮✨</div>
                        <div style="text-align:center; font-weight:900; color:#3C2415; margin-bottom:12px;">SİZİN FALINIZ</div>
                        <div style="color:#555; line-height:1.7; font-size:14px;">{resp.text}</div>
                        <div style="text-align:center; margin-top:15px; font-size:11px; color:#CCC;">☕ Falınız xeyirli olsun!</div>
                    </div>""", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Xəta: {e}")


# ============================================================
# ƏSAS
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
    if 5 <= hour < 12: greet = "Sabahınız xeyir ☕"
    elif 12 <= hour < 18: greet = "Günortanız xeyir ☀️"
    else: greet = "Axşamınız xeyir 🌙"

    # HERO
    st.markdown(f"""
    <div class="app-hero">
        <div class="app-logo-icon">☕</div>
        <div class="app-logo">EMALATKHANA</div>
        <div class="app-greet">{greet}</div>
    </div>""", unsafe_allow_html=True)

    # Notifications
    check_notifications(customer_id)

    # STAMP CARD
    render_stamp_card(stars, c_type)

    # REWARDS
    render_rewards_section(stars, free_count)

    # QR Button
    st.markdown('<div class="nav-section">', unsafe_allow_html=True)
    if st.button("📱 QR KODUMU GÖSTƏR", type="primary", use_container_width=True, key="qr_s"):
        show_qr_dialog(customer_id)
    st.markdown('</div>', unsafe_allow_html=True)

    # TABS
    t1, t2, t3, t4 = st.tabs(["☕ Menyu", "📜 Tarixçə", "🤖 Barista", "🔮 Fal"])

    with t1:
        render_coffee_menu()
    with t2:
        render_history(customer_id)
    with t3:
        render_barista()
    with t4:
        render_fortune()

    # Footer
    st.markdown("""
    <div style="text-align:center; padding:25px 0 15px;">
        <div style="font-weight:900; font-size:11px; letter-spacing:2px; color:#CCC;">☕ EMALATKHANA</div>
        <div style="font-size:10px; color:#DDD; margin-top:3px;">Hər kofe bir stamp, hər 10 stamp bir hədiyyə!</div>
    </div>""", unsafe_allow_html=True)
