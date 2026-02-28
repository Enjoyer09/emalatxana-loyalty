import streamlit as st
import pandas as pd
from database import run_query
import datetime
from utils import get_baku_now

def render_customer_app(customer_id=None):
    # 📱 1. PREMIUM UI/UX DİZAYN (Glassmorphism, Yumşaq Kölgələr, Animasiyalar)
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;800;900&family=Nunito:wght@400;700;900&display=swap');
        
        /* Ana Səhifəni Təmizləyirik */
        .stApp { background: #f8f9fa !important; color: #2b2d42 !important; font-family: 'Nunito', sans-serif !important;}
        #MainMenu, header, footer {visibility: hidden;}
        .block-container {padding: 0 !important; max-width: 100%; padding-bottom: 80px !important;}
        
        /* Dinamik Salamlaşma Paneli (Hero Section) */
        .hero-section {
            background: linear-gradient(135deg, #c8102e 0%, #8b0000 100%);
            padding: 40px 20px 50px 20px;
            border-bottom-left-radius: 35px;
            border-bottom-right-radius: 35px;
            color: white;
            box-shadow: 0 10px 30px rgba(200, 16, 46, 0.3);
            position: relative;
            overflow: hidden;
        }
        /* Arxa plandakı bəzək qrafikası */
        .hero-section::after {
            content: ''; position: absolute; top: -50px; right: -50px; width: 150px; height: 150px;
            background: rgba(255,255,255,0.1); border-radius: 50%;
        }
        
        /* Şüşə Effekti (Glassmorphism) Kartlar */
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 20px;
            margin: -30px 20px 20px 20px; /* Hero panelin üstünə minir */
            box-shadow: 0 8px 25px rgba(0,0,0,0.06);
            border: 1px solid rgba(255,255,255,0.5);
            position: relative;
            z-index: 10;
        }
        
        /* Normal Kartlar */
        .ui-card {
            background: #ffffff; border-radius: 20px; padding: 20px; margin: 15px 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #edf2f7;
        }

        /* Hədiyyə Bileti (Ticket) Dizaynı */
        .reward-ticket {
            background: linear-gradient(135deg, #ffd700, #ffb300);
            border-radius: 15px; padding: 15px; margin-bottom: 15px;
            display: flex; align-items: center; justify-content: space-between;
            color: #000; box-shadow: 0 5px 15px rgba(255, 215, 0, 0.3);
            border-left: 8px dashed #fff;
            position: relative;
        }
        
        /* Səviyyə Barı */
        .level-bar-bg { background: #e2e8f0; height: 8px; border-radius: 10px; width: 100%; margin-top: 10px; overflow: hidden; }
        .level-bar-fill { background: linear-gradient(90deg, #c8102e, #ff4b4b); height: 100%; border-radius: 10px; transition: 1s ease-out; }
        
        /* Sürüşən Tablar */
        div[data-testid="stTabs"] { padding: 0 10px; margin-top: 10px; }
        div[data-testid="stTabs"] button { font-size: 15px !important; font-weight: 800 !important; color: #a0aec0 !important; }
        div[data-testid="stTabs"] button[aria-selected="true"] { color: #c8102e !important; border-bottom: 3px solid #c8102e !important; }
        
        /* Tarixçə Siyahısı */
        .history-item { border-bottom: 1px solid #f0f0f0; padding: 10px 0; display: flex; justify-content: space-between; }
        .history-item:last-child { border-bottom: none; }
        </style>
    """, unsafe_allow_html=True)

    if not customer_id:
        st.error("⚠️ Səhv QR Kod oxutdunuz.")
        return

    # 🗄️ BAZADAN MƏLUMATLARI ÇƏKİRİK
    c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
    if c_df.empty:
        st.error("⚠️ Müştəri tapılmadı.")
        return
        
    cust_data = c_df.iloc[0].to_dict()
    stars = cust_data.get('stars', 0)
    c_type = str(cust_data.get('type', 'Standard')).upper()
    
    # Sifariş Tarixçəsini Çəkirik (Son 3 ziyarət)
    history_df = run_query("SELECT created_at, items, total FROM sales WHERE customer_card_id=:id ORDER BY created_at DESC LIMIT 3", {"id": customer_id})

    # 🧠 FUNKSİONALLIQ VƏ RİYAZİYYAT
    # Salamlaşma məntiqi
    hour = get_baku_now().hour
    if 5 <= hour < 12: greeting = "Sabahın xeyir! 🌅"
    elif 12 <= hour < 18: greeting = "Günorta vaxtı! ☀️"
    else: greeting = "Axşamın xeyir! 🌙"

    # Hədiyyə kofe məntiqi
    free_coffees = int(stars // 10)
    current_progress = int(stars % 10)
    remaining = 10 - current_progress
    circle_dasharray = f"{current_progress * 10}, 100"

    # Gamification: Növbəti Səviyyəyə (Statusa) Keçid
    next_level_stars = 50 if c_type == 'STANDARD' else 150 if c_type == 'GOLDEN' else 300 if c_type == 'PLATINUM' else 0
    next_level_name = "GOLDEN 🥇" if c_type == 'STANDARD' else "PLATINUM 🥈" if c_type == 'GOLDEN' else "ELITE 💎" if c_type == 'PLATINUM' else "MAX SƏVİYYƏ"
    level_progress = min((stars / next_level_stars) * 100, 100) if next_level_stars > 0 else 100

    # 🔴 HERO SECTION (Salamlaşma və Əsas Xal)
    st.markdown(f"""
    <div class="hero-section">
        <h4 style="margin:0; font-family:'Nunito'; font-weight:400; color:#ffb3b3;">{greeting}</h4>
        <h2 style="margin:5px 0 0 0; font-family:'Jura'; font-size:28px; font-weight:900;">Dəyərli Qonağımız</h2>
    </div>
    """, unsafe_allow_html=True)

    # ⚪ GLASSMORPHISM ƏSAS KART (Ulduzlar və Progress)
    st.markdown(f"""
    <div class="glass-card" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <p style="margin:0; color:#718096; font-size:13px; font-weight:700;">TOPLANAN ULDUZLAR</p>
            <h1 style="margin:0; font-family:'Jura'; color:#c8102e; font-size:42px; font-weight:900;">{stars} <span style="font-size:20px;">⭐</span></h1>
            <p style="margin:0; font-size:13px; color:#4a5568; margin-top:5px;">
                🎁 <b>{remaining}</b> kofedən sonra 1 hədiyyə!
            </p>
        </div>
        
        <div style="position:relative; width:80px; height:80px;">
            <svg viewBox="0 0 36 36" style="width:80px; height:80px; transform: rotate(-90deg);">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#edf2f7" stroke-width="3"/>
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#c8102e" stroke-width="3" stroke-dasharray="{circle_dasharray}" />
            </svg>
            <div style="position:absolute; top:22px; left:0; width:100%; text-align:center;">
                <span style="font-size:20px; font-weight:900; color:#c8102e;">{current_progress}</span><span style="font-size:12px; font-weight:bold; color:#a0aec0;">/10</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 📑 TABS (Alt Menyular)
    tab_rewards, tab_qr, tab_history = st.tabs(["🎁 Hədiyyələr", "📱 Kartım", "🕒 Tarixçə"])

    # ==========================================
    # TAB 1: HƏDİYYƏLƏR VƏ STATUS
    # ==========================================
    with tab_rewards:
        # Gamification: Status Bar
        st.markdown(f"""
        <div class="ui-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                <div>
                    <span style="font-size:12px; color:#a0aec0; font-weight:bold;">MÖVCUD STATUS</span><br>
                    <b style="font-size:18px; color:#2d3748;">{c_type}</b>
                </div>
                <div style="text-align:right;">
                    <span style="font-size:12px; color:#a0aec0; font-weight:bold;">NÖVBƏTİ SƏVİYYƏ</span><br>
                    <b style="font-size:14px; color:#c8102e;">{next_level_name}</b>
                </div>
            </div>
            <div class="level-bar-bg">
                <div class="level-bar-fill" style="width: {level_progress}%;"></div>
            </div>
            <p style="margin:5px 0 0 0; text-align:center; font-size:11px; color:#718096;">Daha {int(next_level_stars - stars)} ulduz toplayaraq səviyyə atlayın!</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<h4 style='margin-left:20px; color:#2d3748; font-weight:800; font-size:18px;'>Sizin Kuponlar</h4>", unsafe_allow_html=True)
        
        if free_coffees > 0:
            for i in range(free_coffees):
                st.markdown(f"""
                <div style="margin: 0 20px;">
                    <div class="reward-ticket">
                        <div>
                            <h3 style="margin:0; font-weight:900; color:#000;">1x PULSUZ KOFE ☕</h3>
                            <p style="margin:0; font-size:12px; color:#333;">İstənilən ölçüdə və çeşiddə.</p>
                        </div>
                        <div style="background:#fff; padding:5px 10px; border-radius:10px; font-weight:bold; font-size:12px;">AKTİV</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="text-align:center; padding:30px 20px; color:#a0aec0;">
                <div style="font-size:40px; margin-bottom:10px;">😔</div>
                <b>Hələlik hədiyyə yoxdur.</b><br>
                <span style="font-size:13px;">Kofe içməyə davam edin, hədiyyələr yoldadır!</span>
            </div>
            """, unsafe_allow_html=True)

    # ==========================================
    # TAB 2: QR KARTIM
    # ==========================================
    with tab_qr:
        st.markdown(f"""
        <div class="ui-card" style="text-align:center; padding:40px 20px;">
            <h3 style="margin-top:0; color:#2d3748; font-weight:900;">Rəqəmsal Kartınız</h3>
            <p style="color:#718096; font-size:14px; margin-bottom:30px;">Kassada ofisianta göstərin ki, ulduzlar hesaba yazılsın.</p>
        """, unsafe_allow_html=True)
        
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=c8102e&bgcolor=ffffff"
        st.markdown(f"<img src='{qr_url}' style='width:220px; height:220px; box-shadow: 0 10px 25px rgba(200, 16, 46, 0.2); border-radius:15px; border: 5px solid #fff;'/>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <h3 style="margin-top:25px; letter-spacing:3px; color:#2d3748; font-family:'Jura';">{customer_id}</h3>
            <div style="margin-top:20px; padding:12px; background:#f8f9fa; border-radius:12px; border:1px dashed #cbd5e0; text-align:left;">
                <span style="font-size:12px; color:#4a5568;">💡 <b>İpucu:</b> Şəklin üzərinə basılı tutaraq "Save Image" (Yadda saxla) seçin və internetsiz olanda Qalereyadan istifadə edin.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # TAB 3: SİFARİŞ TARİXÇƏSİ
    # ==========================================
    with tab_history:
        st.markdown("<div class='ui-card'>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin:0 0 15px 0; color:#2d3748; font-weight:800; font-size:18px;'>Son Ziyarətlər</h4>", unsafe_allow_html=True)
        
        if not history_df.empty:
            for _, row in history_df.iterrows():
                date_str = row['created_at'].strftime("%d %b, %H:%M") if pd.notna(row['created_at']) else "Bilinmir"
                items_str = str(row['items']).split(",")[0] + "..." if len(str(row['items'])) > 15 else str(row['items'])
                total_val = float(row['total'])
                
                st.markdown(f"""
                <div class="history-item">
                    <div>
                        <b style="color:#2d3748; font-size:15px;">{date_str}</b><br>
                        <span style="color:#a0aec0; font-size:13px;">{items_str}</span>
                    </div>
                    <div style="text-align:right;">
                        <b style="color:#c8102e; font-size:15px;">{total_val:.2f} ₼</b><br>
                        <span style="color:#48bb78; font-size:12px; font-weight:bold;">+ Ulduz əlavə edildi</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<p style='text-align:center; color:#a0aec0; margin:20px 0;'>Hələ ki, heç bir sifarişiniz yoxdur. Sizi gözləyirik! ☕</p>", unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)
