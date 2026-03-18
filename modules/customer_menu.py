# `modules/customer_menu.py` — TIM HORTONS STYLE PREMIUM REDESIGN 🍩☕

Tamamilə yenidən dizayn edilmiş, **mobil tətbiq hissiyyatı**, **qızılı/tünd theme**, **10-ulduz loyalty tracker**, **AI Barista chat**, **Kofe Falı**, **Tarixçə** və **Bildiriş banneri** ilə hazırlanmış versiya:

```python
# modules/customer_menu.py — TIM HORTONS STYLE REDESIGN v3.0
import streamlit as st
import pandas as pd
import json
import logging
import io
from datetime import datetime
from PIL import Image

from database import run_query, get_setting
from utils import get_baku_now, safe_decimal

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# ============================================================
📱 MOBİL TƏTBİQ CSS (Premium Dark/Gold Theme)
# ============================================================
def inject_app_css():
    st.markdown("""
    <style>
        /* Əsas Layout */
        .stApp { background-color: #0B0B0F !important; color: #E8E8E8 !important; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif !important; }
        header, #MainMenu, footer, div[data-testid="stStatusWidget"] { visibility: hidden !important; height: 0 !important; }
        .block-container { padding: 0 !important; max-width: 100% !important; }
        section.main > div:first-child { padding-top: 0 !important; }
        
        /* Hero Header */
        .app-header {
            background: linear-gradient(160deg, #1A1A20 0%, #0F0F14 100%);
            padding: 40px 20px 60px 20px;
            border-bottom-left-radius: 28px;
            border-bottom-right-radius: 28px;
            position: relative;
            overflow: hidden;
        }
        .app-header::before {
            content: ''; position: absolute; top: -50%; right: -20%; width: 200px; height: 200px;
            background: radial-gradient(circle, rgba(212,175,55,0.15) 0%, transparent 70%);
            border-radius: 50%;
        }
        .greeting { font-size: 14px; color: #888; letter-spacing: 0.5px; margin-bottom: 6px; }
        .brand-title { font-size: 26px; font-weight: 900; color: #D4AF37; margin: 0; letter-spacing: 1px; }
        
        /* Loyalty Card */
        .loyalty-card {
            background: linear-gradient(145deg, #15151A 0%, #0D0D11 100%);
            border: 1px solid #2A2A32;
            border-radius: 22px;
            padding: 24px;
            margin: -40px 16px 20px 16px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.4);
            position: relative;
            z-index: 2;
        }
        .tier-badge {
            display: inline-block; padding: 6px 12px; border-radius: 20px;
            font-size: 11px; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase;
            background: rgba(212,175,55,0.15); color: #D4AF37; border: 1px solid rgba(212,175,55,0.3);
            margin-bottom: 14px;
        }
        .progress-label { font-size: 13px; color: #999; margin-bottom: 12px; }
        .progress-track { display: flex; justify-content: space-between; gap: 6px; margin-bottom: 8px; }
        .progress-dot {
            width: 28px; height: 28px; border-radius: 50%;
            background: #1E1E24; border: 2px solid #333;
            display: flex; align-items: center; justify-content: center;
            font-size: 14px; transition: all 0.3s ease;
        }
        .progress-dot.filled { background: #D4AF37; border-color: #D4AF37; color: #000; box-shadow: 0 0 12px rgba(212,175,55,0.4); }
        .free-reward { 
            margin-top: 14px; padding: 10px; border-radius: 12px; 
            background: linear-gradient(90deg, rgba(212,175,55,0.1) 0%, rgba(212,175,55,0.05) 100%);
            border: 1px dashed #D4AF37; text-align: center; font-size: 13px; font-weight: 700; color: #D4AF37;
        }
        
        /* Feature Grid */
        .feature-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; padding: 0 16px; margin-bottom: 20px; }
        .feature-card {
            background: #15151A; border: 1px solid #25252D; border-radius: 18px;
            padding: 18px; text-align: center; cursor: pointer; transition: all 0.2s;
        }
        .feature-card:active { transform: scale(0.98); background: #1A1A20; }
        .feature-icon { font-size: 28px; margin-bottom: 8px; }
        .feature-title { font-size: 14px; font-weight: 700; color: #E8E8E8; }
        
        /* Notification Banner */
        .notif-banner {
            background: linear-gradient(90deg, #D4AF37 0%, #F0C850 100%);
            color: #000; padding: 14px 16px; margin: 0 16px 16px 16px;
            border-radius: 14px; font-size: 13px; font-weight: 700;
            box-shadow: 0 6px 18px rgba(212,175,55,0.25);
            display: flex; align-items: center; justify-content: space-between;
            animation: slideDown 0.5s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        
        /* Dialog Overrides */
        div[role="dialog"] > div { background: #0F0F14 !important; border: 1px solid #2A2A32 !important; border-radius: 20px !important; }
        div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 { color: #D4AF37 !important; }
        div[role="dialog"] p, div[role="dialog"] span { color: #CCC !important; }
        
        /* Chat Bubbles */
        .chat-container { padding: 10px 16px 80px 16px; }
        .chat-bubble { padding: 12px 16px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; font-size: 14px; line-height: 1.5; }
        .chat-user { background: #D4AF37; color: #000; margin-left: auto; border-bottom-right-radius: 4px; }
        .chat-ai { background: #1E1E24; color: #E8E8E8; margin-right: auto; border-bottom-left-radius: 4px; border: 1px solid #2A2A32; }
        
        /* History Items */
        .history-item { background: #15151A; border-left: 3px solid #D4AF37; padding: 14px; border-radius: 0 12px 12px 0; margin: 10px 16px; }
        .history-date { font-size: 11px; color: #777; margin-bottom: 4px; }
        .history-items { font-size: 13px; color: #DDD; }
        .history-total { font-size: 12px; font-weight: 800; color: #D4AF37; margin-top: 6px; }
        
        /* Upload Zone */
        .upload-zone { border: 2px dashed #333; border-radius: 16px; padding: 30px; text-align: center; margin: 16px; background: #15151A; }
        .upload-icon { font-size: 40px; margin-bottom: 10px; }
        .upload-text { color: #888; font-size: 13px; }
        
        /* Buttons */
        button[kind="primary"] { background: #D4AF37 !important; color: #000 !important; border: none !important; border-radius: 14px !important; font-weight: 800 !important; }
        button[kind="secondary"] { background: #1E1E24 !important; color: #E8E8E8 !important; border: 1px solid #2A2A32 !important; border-radius: 14px !important; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
📱 DIALOGS
# ============================================================
@st.dialog("📱 Sizin QR Kodunuz", width="small")
def show_qr_dialog(customer_id):
    st.markdown("<p style='text-align:center; color:#888; font-size:13px;'>Kassada oxudun, ulduz qazanın.</p>", unsafe_allow_html=True)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=000000&bgcolor=ffffff"
    st.markdown(f"""
    <div style='text-align:center; margin: 20px 0;'>
        <img src='{qr_url}' style='width:220px; height:220px; border-radius:16px; border: 4px solid #D4AF37; box-shadow: 0 8px 24px rgba(212,175,55,0.2);'/>
        <h3 style='color:#D4AF37; font-weight:900; margin-top:15px; letter-spacing:2px;'>{customer_id}</h3>
    </div>
    """, unsafe_allow_html=True)
    st.info("💡 Şəkli qalereyada saxlayın və ya ekran görüntüsü alın.")

@st.dialog("📋 Emalatkhana Menyusu", width="large")
def show_menu_dialog():
    menu_df = run_query("SELECT item_name, price, category FROM menu WHERE is_active=TRUE ORDER BY category, item_name")
    if menu_df.empty:
        st.warning("Menyu hazırda yenilənir...")
        return
    
    st.markdown("<p style='text-align:center; color:#888; font-size:13px;'>Sifarişlərinizi kassada verə bilərsiniz.</p>", unsafe_allow_html=True)
    
    categories = ["HAMISI"] + sorted(menu_df['category'].dropna().unique().tolist())
    selected_cat = st.radio("Kateqoriya", categories, horizontal=True, label_visibility="collapsed", key="menu_cat_radio")
    
    display_df = menu_df if selected_cat == "HAMISI" else menu_df[menu_df['category'] == selected_cat]
    
    cols = st.columns(2)
    for idx, (_, item) in enumerate(display_df.iterrows()):
        with cols[idx % 2]:
            st.markdown(f"""
            <div style="background:#15151A; padding:14px; margin-bottom:10px; border-radius:14px; border:1px solid #25252D;">
                <div style="color:#E8E8E8; font-weight:700; font-size:14px; margin-bottom:4px;">{item['item_name']}</div>
                <div style="color:#D4AF37; font-weight:900; font-size:15px;">{float(item['price']):.2f} ₼</div>
            </div>
            """, unsafe_allow_html=True)

@st.dialog("🎁 Günün Təklifləri", width="large")
def show_promos_dialog():
    try:
        campaigns = run_query("SELECT title, description, badge, img_url FROM campaigns WHERE is_active=TRUE ORDER BY id DESC")
    except:
        campaigns = pd.DataFrame()
        
    if campaigns.empty:
        st.info("Hazırda aktiv kampaniya yoxdur. Tezliklə yeni təkliflər gələcək! ✨")
        return
        
    for _, camp in campaigns.iterrows():
        bg = camp['img_url'] if camp['img_url'] else "https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&q=80&w=600"
        badge = f"<span style='background:#D4AF37; color:#000; padding:4px 10px; border-radius:8px; font-size:11px; font-weight:800;'>{camp['badge']}</span>" if camp['badge'] else ""
        st.markdown(f"""
        <div style="border-radius:16px; overflow:hidden; border:1px solid #25252D; margin-bottom:16px; background:#15151A;">
            <div style="height:110px; background-image:url('{bg}'); background-size:cover; background-position:center; padding:10px; display:flex; align-items:flex-start;">{badge}</div>
            <div style="padding:14px;">
                <h4 style="margin:0; color:#D4AF37; font-weight:900; font-size:16px;">{camp['title']}</h4>
                <p style="margin:6px 0 0 0; font-size:13px; color:#AAA; line-height:1.5;">{camp['description']}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

@st.dialog("🤖 AI Barista", width="large")
def show_ai_barista_dialog():
    st.markdown("<h4 style='text-align:center; color:#D4AF37; font-weight:900;'>Nə içmək istəyirsiniz?</h4>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#888; font-size:13px;'>Əhvalınızı yazın, mən sizə ən uyğun içkini seçim ☕</p>", unsafe_allow_html=True)
    
    if 'ai_chat_history' not in st.session_state:
        st.session_state.ai_chat_history = []
    
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.ai_chat_history:
            css = "chat-user" if msg['role'] == 'user' else "chat-ai"
            st.markdown(f'<div class="chat-bubble {css}">{msg["text"]}</div>', unsafe_allow_html=True)
    
    col_in, col_btn = st.columns([5, 1])
    with col_in:
        user_input = st.text_input("Mesaj", placeholder="Məs: Yuxuluyam, şirin və soyuq nəsə...", label_visibility="collapsed", key="ai_input")
    with col_btn:
        send = st.button("📤", key="ai_send")
        
    if send and user_input.strip():
        st.session_state.ai_chat_history.append({'role': 'user', 'text': user_input})
        
        api_key = get_setting("gemini_api_key", "")
        if not api_key or not genai:
            reply = "⚠️ AI Barista hazırda offline-dır. Admin panelindən API Key yoxlayın."
        else:
            try:
                menu_df = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE LIMIT 20")
                menu_text = ", ".join([f"{r['item_name']} ({float(r['price']):.1f}₼)" for _, r in menu_df.iterrows()]) if not menu_df.empty else "Menyu boşdur"
                
                prompt = f"""Sən 'Emalatkhana'nın mehriban AI Baristasısan.
Menyumuz: {menu_text}
Müştəri deyir: '{user_input}'
Vəzifə: Yalnız menyudan 1-2 məhsul təklif et. Qiyməti yaz. Qısa, səmimi, emojili cavab ver (max 3 cümlə). Azərbaycan dilində."""
                
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                reply = model.generate_content(prompt).text
            except Exception as e:
                reply = f"Xəta: {e}"
                
        st.session_state.ai_chat_history.append({'role': 'ai', 'text': reply})
        st.rerun()

@st.dialog("🔮 Kofe Falı", width="large")
def show_fortune_dialog():
    st.markdown("<h4 style='text-align:center; color:#D4AF37; font-weight:900;'>Fincanındakı Sirri Aç</h4>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#888; font-size:13px;'>Kofe fincanının dibinin şəklini çək və yüklə. AI falçı yorumlasın 🔮</p>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class="upload-zone">
        <div class="upload-icon">☕</div>
        <div class="upload-text">Şəkil yükləyin (JPG/PNG)</div>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded = st.file_uploader(" ", type=['jpg','jpeg','png'], label_visibility="collapsed")
    
    if uploaded:
        st.image(uploaded, caption="Yüklənən Fincan", use_column_width=True)
        if st.button("🔮 Falı Oxu", type="primary", use_container_width=True):
            with st.spinner("Falçı sehrini işə salır..."):
                api_key = get_setting("gemini_api_key", "")
                if not api_key or not genai:
                    st.error("AI falçı aktiv deyil.")
                else:
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        img = Image.open(uploaded)
                        prompt = """Sən Azərbaycanın məşhur kofe falçısısan. Bu fincan dibindəki formaları sehrli, ümidverici və əyləncəli şəkildə yorumla. Sevgi, iş, şans haqqında qısa fal de. Emoji istifadə et. Azərbaycan dilində."""
                        res = model.generate_content([prompt, img])
                        st.markdown(f"""
                        <div style='background:#15151A; padding:16px; border-radius:14px; border:1px solid #D4AF37; margin-top:15px;'>
                            <div style='text-align:center; font-size:20px; margin-bottom:10px;'>🔮</div>
                            <div style='color:#E8E8E8; line-height:1.6; font-size:14px;'>{res.text}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Fal xətası: {e}")

@st.dialog("📜 Sifariş Tarixçəsi", width="large")
def show_history_dialog(customer_id):
    try:
        sales = run_query(
            "SELECT items, total, created_at FROM sales WHERE customer_card_id=:cid AND (is_test IS NULL OR is_test=FALSE) ORDER BY created_at DESC LIMIT 15",
            {"cid": customer_id}
        )
    except:
        sales = pd.DataFrame()
        
    if sales.empty:
        st.info("Hələ heç bir sifarişiniz yoxdur. İlk kofenizi için, ulduz qazanın! ☕")
        return
        
    for _, row in sales.iterrows():
        date_str = row['created_at'].strftime("%d.%m.%Y %H:%M") if pd.notna(row['created_at']) else "-"
        try:
            items = json.loads(row['items'])
            items_str = ", ".join([f"{i['item_name']} x{i['qty']}" for i in items])
        except:
            items_str = str(row['items'])[:60]
            
        st.markdown(f"""
        <div class="history-item">
            <div class="history-date">{date_str}</div>
            <div class="history-items">{items_str}</div>
            <div class="history-total">{float(row['total']):.2f} ₼</div>
        </div>
        """, unsafe_allow_html=True)

@st.dialog("💬 Rəy Bildir", width="small")
def show_feedback_dialog():
    st.markdown("<h3 style='text-align:center; color:#D4AF37;'>Tezliklə! 🚀</h3>", unsafe_allow_html=True)
    st.write("Rəy sistemi növbəti yenilənmədə aktiv olacaq. Dəstəyiniz üçün təşəkkürlər! ✨")


# ============================================================
🚀 ƏSAS TƏTBİQ RENDER
# ============================================================
def render_customer_app(customer_id=None):
    inject_app_css()
    
    if not customer_id:
        st.error("⚠️ QR Kod oxunmadı.")
        st.stop()
        
    try:
        c_df = run_query("SELECT card_id, stars, type, secret_token FROM customers WHERE card_id=:id", {"id": customer_id})
    except:
        c_df = pd.DataFrame()
        
    if c_df.empty:
        st.error("⚠️ Müştəri tapılmadı.")
        st.stop()
        
    cust = c_df.iloc[0].to_dict()
    stars = int(cust.get('stars', 0) or 0)
    c_type = str(cust.get('type', 'Standard')).upper()
    
    # Loyalty math
    current_progress = stars % 10
    free_coffees = stars // 10
    remaining = 10 - current_progress
    
    # Greeting
    hour = get_baku_now().hour
    if 5 <= hour < 12: greeting = "Sabahınız xeyir! Kofe vaxtıdır ☕"
    elif 12 <= hour < 18: greeting = "Günortanız xeyir! Enerji yığın ☀️"
    else: greeting = "Axşamınız xeyir! Rahatlamaq vaxtıdır 🌙"
    
    # Notification check
    try:
        notif = run_query("SELECT message FROM notifications WHERE card_id=:cid AND is_read IS NULL ORDER BY created_at DESC LIMIT 1", {"cid": customer_id})
        if not notif.empty:
            msg = notif.iloc[0]['message']
            st.markdown(f"""
            <div class="notif-banner">
                <span>🎉 {msg}</span>
                <span style="cursor:pointer;" onclick="window.location.reload()">✖</span>
            </div>
            """, unsafe_allow_html=True)
    except:
        pass
    
    # Header
    st.markdown(f"""
    <div class="app-header">
        <div class="greeting">{greeting}</div>
        <h1 class="brand-title">EMALATKHANA</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Loyalty Card
    tier_colors = {"GOLDEN": "#D4AF37", "PLATINUM": "#C0C0C0", "ELITE": "#9B59B6", "IKRAM": "#E74C3C", "TELEBE": "#3498DB"}
    tier_color = tier_colors.get(c_type, "#888")
    
    dots_html = ""
    for i in range(10):
        cls = "filled" if i < current_progress else ""
        dots_html += f'<div class="progress-dot {cls}">★</div>'
        
    st.markdown(f"""
    <div class="loyalty-card">
        <div class="tier-badge" style="border-color:{tier_color}40; color:{tier_color}; background:{tier_color}15;">💎 {c_type} ÜZV</div>
        <div class="progress-label">Pulsuz kofeyə <b style="color:#D4AF37;">{remaining}</b> ulduz qaldı</div>
        <div class="progress-track">{dots_html}</div>
        {f'<div class="free-reward">🎁 {free_coffees} Pulsuz kofeniz hazırdır! Kassada istifadə edin.</div>' if free_coffees > 0 else ''}
    </div>
    """, unsafe_allow_html=True)
    
    # Feature Grid
    st.markdown("<div class='feature-grid'>", unsafe_allow_html=True)
    
    cols = st.columns(2)
    with cols[0]:
        if st.button("📱 QR Kodum\nMənim Kartım", key="btn_qr", use_container_width=True):
            show_qr_dialog(customer_id)
    with cols[1]:
        if st.button("📋 Menyu\nBax & Seç", key="btn_menu", use_container_width=True):
            show_menu_dialog()
            
    cols = st.columns(2)
    with cols[0]:
        if st.button("🤖 AI Barista\nMənə Seç", key="btn_ai", use_container_width=True):
            show_ai_barista_dialog()
    with cols[1]:
        if st.button("🔮 Kofe Falı\nSirri Aç", key="btn_fal", use_container_width=True):
            show_fortune_dialog()
            
    cols = st.columns(2)
    with cols[0]:
        if st.button("🎁 Təkliflər\nKampaniyalar", key="btn_promo", use_container_width=True):
            show_promos_dialog()
    with cols[1]:
        if st.button("📜 Tarixçə\nSifarişlərim", key="btn_hist", use_container_width=True):
            show_history_dialog(customer_id)
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Bottom spacing
    st.markdown("<div style='height:60px;'></div>", unsafe_allow_html=True)
```

---

## 🎨 Nə Dəyişdi? (Tim Hortons Premium UX)

| Xüsusiyyət | Köhnə | Yeni |
|---|---|---|
| **Theme** | Açıq/krem | 🌑 Tünd + Qızılı (Premium Mobile) |
| **Loyalty UI** | SVG circle | ⭐ 10 nöqtəli progress tracker + pulsuz kofe sayğacı |
| **Naviqasiya** | Sadə buttonlar | 📱 2x3 Feature Grid (mobil app kimi) |
| **AI Barista** | Tək input/output | 💬 Chat bubble interfeysi + history |
| **Kofe Falı** | Yox idi | 🔮 Şəkil upload + Gemini Vision + sehrli UI |
| **Tarixçə** | Yox idi | 📜 Timeline stilində sifarişlər |
| **Bildiriş** | Yox idi | 🎉 Animasiyalı top banner |
| **Dialoglar** | Standart | 📱 Mobil-optimizə, tünd theme, rounded cards |
| **Performance** | Hər render-də query | ✅ Try/except + empty check + limit |

---

## 📲 İstifadə:
1. Faylı `modules/customer_menu.py` kimi yadda saxla
2. QR skan edəndə avtomatik `/?id=XXXX` ilə açılır
3. Bütün funksiyalar **mobil tətbiq hissiyyatı** ilə işləyir
4. AI üçün `gemini_api_key` settings-də olmalıdır

Test et, nəticəni bildir! ☕✨
