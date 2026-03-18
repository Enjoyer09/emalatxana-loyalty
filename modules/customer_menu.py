# modules/customer_menu.py — TIM HORTONS STYLE REDESIGN v2.0
import streamlit as st
import pandas as pd
import json
import base64
import logging
import io
import time
from datetime import datetime
from PIL import Image

from database import run_query, run_action, get_setting
from utils import BRAND_NAME, safe_decimal, get_baku_now

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# ============================================================
# MOBİL TƏTBİQ CSS (Qızılı/Tünd Theme)
# ============================================================
def inject_mobile_css():
    st.markdown("""
    <style>
        /* Əsas Fon */
        .stApp { background-color: #121212 !important; color: #E0E0E0 !important; font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif; }
        
        /* Header Gizlət */
        header, #MainMenu, footer, div[data-testid="stStatusWidget"] { visibility: hidden; height: 0; }
        
        /* Konteynerlər */
        .block-container { padding: 0 !important; max-width: 100% !important; }
        section.main > div:first-child { padding-top: 0 !important; }
        
        /* Loyalty Kartı */
        .loyalty-card {
            background: linear-gradient(135deg, #D4AF37 0%, #AA8626 100%);
            border-radius: 20px;
            padding: 25px;
            margin: 15px;
            box-shadow: 0 10px 30px rgba(212, 175, 55, 0.3);
            color: #000;
            text-align: center;
        }
        .loyalty-title { font-size: 14px; font-weight: 600; letter-spacing: 1px; opacity: 0.8; margin-bottom: 10px; }
        .loyalty-tier { font-size: 28px; font-weight: 900; text-transform: uppercase; margin-bottom: 20px; text-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        
        /* Progress Bar */
        .progress-container { display: flex; justify-content: center; gap: 8px; margin: 20px 0; }
        .star-box { width: 28px; height: 28px; background: rgba(0,0,0,0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; border: 2px solid rgba(0,0,0,0.1); }
        .star-filled { background: #000; border-color: #000; color: #D4AF37; }
        
        /* Menyu Grid */
        .menu-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; padding: 15px; }
        .menu-item { background: #1E1E1E; border-radius: 16px; padding: 15px; border: 1px solid #333; transition: all 0.2s; }
        .menu-item:active { transform: scale(0.98); background: #252525; }
        .menu-name { font-weight: 700; font-size: 15px; color: #FFF; margin-bottom: 5px; }
        .menu-price { font-weight: 800; font-size: 18px; color: #D4AF37; }
        .menu-star { font-size: 12px; color: #888; margin-top: 5px; }
        
        /* Tab Navigation (Bottom) */
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: #1E1E1E; border-top: 1px solid #333; display: flex; justify-content: space-around; padding: 12px 0; z-index: 999; }
        .nav-item { text-align: center; color: #666; font-size: 12px; cursor: pointer; }
        .nav-item.active { color: #D4AF37; }
        .nav-icon { font-size: 24px; margin-bottom: 4px; }
        
        /* Popup/Banner */
        .popup-banner { background: linear-gradient(90deg, #D4AF37, #F0C850); color: #000; padding: 15px; border-radius: 15px; margin: 15px; text-align: center; font-weight: 700; box-shadow: 0 5px 15px rgba(0,0,0,0.3); animation: slideDown 0.5s; }
        @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        
        /* Chat Interface */
        .chat-container { padding: 15px; padding-bottom: 80px; }
        .chat-bubble { padding: 12px 16px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; font-size: 15px; line-height: 1.4; }
        .chat-user { background: #D4AF37; color: #000; margin-left: auto; border-bottom-right-radius: 4px; }
        .chat-ai { background: #2C2C2C; color: #FFF; margin-right: auto; border-bottom-left-radius: 4px; }
        
        /* Input Fix */
        .stTextInput > div > div { background: #2C2C2C !important; border: 1px solid #444 !important; border-radius: 25px !important; }
        .stTextInput input { color: #FFF !important; }
        
        /* History List */
        .history-item { background: #1E1E1E; padding: 15px; border-radius: 12px; margin: 10px 15px; border-left: 4px solid #D4AF37; }
        
        /* Fortune Teller */
        .upload-zone { border: 2px dashed #444; border-radius: 20px; padding: 40px; text-align: center; margin: 20px; background: #1E1E1E; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# LOYALTY KARTI KOMPONENTİ
# ============================================================
def render_loyalty_card(stars, cust_type):
    # Tier adı
    tier_map = {
        "standard": "☕ Qonaq",
        "golden": "🥇 Gold", 
        "platinum": "🥈 Platinum",
        "elite": "💎 Elite",
        "thermos": "🥤 Thermos",
        "telebe": "🎓 Tələbə",
        "ikram": "🎁 İkram"
    }
    tier_name = tier_map.get(cust_type, "☕ Qonaq")
    
    # Progress (10-ulduz sistem)
    current_stars = int(stars or 0)
    filled = current_stars % 10
    free_coffees = current_stars // 10
    
    stars_html = ""
    for i in range(10):
        css_class = "star-filled" if i < filled else ""
        icon = "★" if i < filled else "☆"
        stars_html += f'<div class="star-box {css_class}">{icon}</div>'
    
    st.markdown(f"""
    <div class="loyalty-card">
        <div class="loyalty-title">SƏNİN KARTIN</div>
        <div class="loyalty-tier">{tier_name}</div>
        <div style="font-size: 13px; margin-bottom: 15px;">Hər 10 ulduzda 1 PULSUZ kofe! ☕</div>
        <div class="progress-container">{stars_html}</div>
        <div style="font-size: 12px; opacity: 0.7;">{filled}/10 Ulduz</div>
        {f'<div style="margin-top: 10px; font-weight: 900; color: #000;">🎁 {free_coffees} Pulsuz kofen hazırdır!</div>' if free_coffees > 0 else ''}
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# MENYU KOMPONENTİ
# ============================================================
def render_mobile_menu():
    menu_df = run_query("SELECT item_name, price, category, is_coffee FROM menu WHERE is_active=TRUE ORDER BY category, item_name")
    
    if menu_df.empty:
        st.info("Menyu boşdur")
        return
    
    # Kategoriyalar
    categories = menu_df['category'].unique().tolist()
    
    # Tab-lar kimi kategoriyalar
    tabs = st.tabs(["☕ Hamısı"] + [f"📂 {c[:10]}" for c in categories[:5]])
    
    with tabs[0]:
        render_menu_grid(menu_df)
    
    for i, cat in enumerate(categories[:5]):
        with tabs[i+1]:
            cat_df = menu_df[menu_df['category'] == cat]
            render_menu_grid(cat_df)


def render_menu_grid(df):
    for idx in range(0, len(df), 2):
        cols = st.columns(2)
        for j in range(2):
            if idx + j < len(df):
                row = df.iloc[idx + j]
                with cols[j]:
                    star_text = "⭐ Ulduz qazan!" if row['is_coffee'] else ""
                    st.markdown(f"""
                    <div class="menu-item">
                        <div class="menu-name">{row['item_name']}</div>
                        <div class="menu-price">{float(row['price']):.2f} ₼</div>
                        <div class="menu-star">{star_text}</div>
                    </div>
                    """, unsafe_allow_html=True)


# ============================================================
# TARİXÇƏ KOMPONENTİ
# ============================================================
def render_history(card_id):
    sales = run_query(
        "SELECT items, total, created_at FROM sales WHERE customer_card_id=:cid ORDER BY created_at DESC LIMIT 20",
        {"cid": card_id}
    )
    
    if sales.empty:
        st.info("Sifariş tarixçəniz yoxdur")
        return
    
    for _, row in sales.iterrows():
        date_str = row['created_at'].strftime("%d.%m.%Y %H:%M") if pd.notna(row['created_at']) else "-"
        
        # Items parse
        try:
            items = json.loads(row['items'])
            items_str = ", ".join([f"{i['item_name']} x{i['qty']}" for i in items])
        except:
            items_str = str(row['items'])[:50]
        
        st.markdown(f"""
        <div class="history-item">
            <div style="color:#888; font-size:12px; margin-bottom:5px;">{date_str}</div>
            <div style="color:#FFF; font-size:14px;">{items_str}</div>
            <div style="color:#D4AF37; font-weight:800; margin-top:5px;">{float(row['total']):.2f} ₼</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# KUPON/BANNER KOMPONENTİ
# ============================================================
def check_notifications(card_id):
    notifs = run_query(
        "SELECT message FROM notifications WHERE card_id=:cid AND is_read IS NULL ORDER BY created_at DESC LIMIT 1",
        {"cid": card_id}
    )
    
    if not notifs.empty:
        msg = notifs.iloc[0]['message']
        st.markdown(f'<div class="popup-banner">🎉 {msg}</div>', unsafe_allow_html=True)
        
        # Mark as read
        if st.button("Tamam", key="dismiss_notif"):
            run_action("UPDATE notifications SET is_read=TRUE WHERE card_id=:cid", {"cid": card_id})
            st.rerun()


# ============================================================
# AI BARİSTA CHAT
# ============================================================
def render_ai_chat():
    st.markdown("<div style='padding: 15px; text-align: center; color: #888;'>AI Barista ilə söhbət</div>", unsafe_allow_html=True)
    
    # Chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display messages
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            role = msg['role']
            text = msg['text']
            css = "chat-user" if role == 'user' else "chat-ai"
            st.markdown(f'<div class="chat-bubble {css}">{text}</div>', unsafe_allow_html=True)
    
    # Input
    col_input, col_send = st.columns([5, 1])
    with col_input:
        user_msg = st.text_input("Mesaj", placeholder="Sənə nə verim?", label_visibility="collapsed", key="chat_input")
    with col_send:
        send_btn = st.button("📤", key="send_chat")
    
    if send_btn and user_msg.strip():
        # Add user message
        st.session_state.chat_history.append({'role': 'user', 'text': user_msg})
        
        # AI Response
        api_key = get_setting("gemini_api_key", "")
        if api_key and genai:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                
                prompt = f"""Sən 'Emalatkhana' kofe şopunun gənc, mehriban və zarafatcıl baristasan. 
                Müştəri sənə deyir: '{user_msg}'
                Qısa, səmimi cavab ver (max 2 cümlə). Azərbaycan dilində. Emoji istifadə et."""
                
                response = model.generate_content(prompt)
                ai_text = response.text
            except Exception as e:
                ai_text = "Uff, bir az yorğunam, dəqiqə gözlə ☕"
        else:
            ai_text = "AI bağlantısı yoxdur 🔌"
        
        st.session_state.chat_history.append({'role': 'ai', 'text': ai_text})
        st.rerun()


# ============================================================
# KOFE FALI (FORTUNE TELLER)
# ============================================================
def render_fortune_teller():
    st.markdown("<div style='padding: 15px; text-align: center;'><h3 style='color:#D4AF37;'>🔮 Kofe Falı</h3></div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class="upload-zone">
        <div style="font-size: 48px; margin-bottom: 10px;">☕</div>
        <div style="color: #888;">Kofenin şəklini çək və yüklə!</div>
        <div style="color: #666; font-size: 12px; margin-top: 10px;">Fal üçün stəkanın dibinin şəkli olmalıdır</div>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Şəkil yüklə", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed")
    
    if uploaded_file:
        # Preview
        st.image(uploaded_file, caption="Kofe Falı", use_column_width=True)
        
        if st.button("🔮 Falı Oxu", type="primary", use_container_width=True):
            with st.spinner("Falçı bacarıq içindədir... 🔮"):
                api_key = get_setting("gemini_api_key", "")
                if not api_key or not genai:
                    st.error("AI falçı hazır deyil 😅")
                else:
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-pro-vision')
                        
                        # Image to PIL
                        image = Image.open(uploaded_file)
                        
                        prompt = """Sən məşhur Azərbaycan kofe falçısısan. Bu şəkildə kofə fincanının dibindəki formaları görürsən.
                        Bunu sehrli, sirli və əyləncəli şəkildə yorumla. Müştərinin gələcəyi, sevgi həyatı, işi və ya şansı haqqında 
                        qısa, ümumi və müsbət fal de. Azərbaycan dilində. Emoji istifadə et."""
                        
                        response = model.generate_content([prompt, image])
                        
                        st.markdown(f"""
                        <div style='background: #1E1E1E; padding: 20px; border-radius: 15px; margin-top: 20px; border: 1px solid #D4AF37;'>
                            <div style='text-align: center; font-size: 24px; margin-bottom: 15px;'>🔮</div>
                            <div style='color: #E0E0E0; line-height: 1.6;'>{response.text}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"Fal xətası: {e}")


# ============================================================
# ƏSAS FUNKSİYA
# ============================================================
def render_customer_app(card_id):
    """Müştəri mobil tətbiqi əsas giriş nöqtəsi"""
    
    inject_mobile_css()
    
    # Token yoxlaması (URL-dən)
    params = st.query_params
    token = params.get("t", [None])[0] if isinstance(params.get("t"), list) else params.get("t")
    
    # Müştəri məlumatlarını çək
    cust = run_query(
        "SELECT card_id, stars, type, secret_token FROM customers WHERE card_id=:cid",
        {"cid": card_id}
    )
    
    if cust.empty:
        st.error("❌ Müştəri tapılmadı!")
        st.stop()
    
    customer = cust.iloc[0]
    
    # Token verify (əgər varsa)
    if token and str(customer.get('secret_token', '')) != str(token):
        st.error("❌ Keçərsiz QR kod!")
        st.stop()
    
    # Bildirişləri yoxla
    check_notifications(card_id)
    
    # LOYALTY KARTI
    render_loyalty_card(customer['stars'], customer['type'])
    
    # TAB NAVİQASİYA
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Menyu", 
        "📜 Tarixçə", 
        "🤖 Barista",
        "🔮 Fal"
    ])
    
    with tab1:
        st.markdown("<div style='padding: 10px;'></div>", unsafe_allow_html=True)
        render_mobile_menu()
    
    with tab2:
        st.markdown("<div style='padding: 10px;'></div>", unsafe_allow_html=True)
        render_history(card_id)
    
    with tab3:
        render_ai_chat()
    
    with tab4:
        render_fortune_teller()
    
    # BOTTOM SPACE (for fixed nav fix)
    st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
