import streamlit as st
import pandas as pd
from database import run_query

def render_customer_app(customer_id=None):
    # 📱 1. TIM HORTONS TİPLİ AÇIQ RƏNGLİ DİZAYN (Ana dark temanı əzirik)
    st.markdown("""
        <style>
        /* Proqramın ana qaranlıq temasını yalnız bu səhifə üçün açıq rəngə çeviririk */
        .stApp { background: #f4f6f8 !important; color: #333333 !important; }
        #MainMenu, header, footer {visibility: hidden;}
        .block-container {padding: 0 !important; max-width: 100%;}
        
        /* Bütün standart mətnləri tünd edirik */
        h1, h2, h3, h4, p, span, label, div { font-family: 'Nunito', sans-serif; text-shadow: none !important; color: #333333 !important;}
        
        /* Üst Qırmızı Panel (Tim Hortons stili) */
        .red-header {
            background-color: #c8102e;
            color: #ffffff !important;
            padding: 40px 20px 30px 20px;
            border-bottom-left-radius: 25px;
            border-bottom-right-radius: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 15px rgba(200, 16, 46, 0.4);
            margin-top: -50px; /* Yuxarıdakı boşluğu silmək üçün */
        }
        .red-header h2, .red-header p, .red-header div, .red-header span {
            color: #ffffff !important;
        }
        
        /* Kampaniya Kartları */
        .promo-card {
            background-color: #ffffff;
            border-radius: 15px;
            padding: 15px;
            margin: 15px 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            border: 1px solid #eee;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .promo-img {
            width: 80px;
            height: 80px;
            border-radius: 10px;
            background: #ffebee;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 40px;
        }
        
        /* Tabs Dizaynı */
        div[data-testid="stTabs"] { padding: 0 10px; }
        div[data-testid="stTabs"] button {
            font-size: 14px !important;
            font-weight: 800 !important;
            color: #888 !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #c8102e !important;
            border-bottom: 3px solid #c8102e !important;
        }
        
        /* QR Kod Kartı */
        .qr-card {
            background-color: #ffffff;
            border-radius: 20px;
            padding: 30px;
            margin: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

    # 👤 MÜŞTƏRİ MƏLUMATLARINI BAZADAN ÇƏKİRİK
    cust_data = None
    if customer_id:
        c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
        if not c_df.empty:
            cust_data = c_df.iloc[0].to_dict()

    if cust_data:
        stars = cust_data.get('stars', 0)
        c_type = str(cust_data.get('type', 'Standard')).upper()
        
        # Riyaziyyat: 10 ulduza 1 kofe
        free_coffees = int(stars // 10)
        current_progress = int(stars % 10)
        remaining = 10 - current_progress
        stroke_dasharray = f"{current_progress * 10}, 100" # 100 üzərindən faiz

        # 🔴 QIRMIZI HEADER (Tims Rewards stili)
        st.markdown(f"""
        <div class="red-header">
            <div>
                <h2 style="margin:0; font-weight:900; font-size:24px;">Füzuli Rewards</h2>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">
                    Növbəti hədiyyəyə <b>{remaining}</b> kofe qaldı!
                </p>
                <div style="background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 10px; display:inline-block; margin-top:10px; font-size:12px; font-weight:bold;">
                    Status: {c_type}
                </div>
            </div>
            
            <div style="position:relative; width:80px; height:80px;">
                <svg viewBox="0 0 36 36" style="width:80px; height:80px;">
                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e05260" stroke-width="2.5"/>
                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-dasharray="{stroke_dasharray}" />
                </svg>
                <div style="position:absolute; top:20px; left:0; width:100%; text-align:center;">
                    <span style="font-size:20px; font-weight:900; line-height:1;">{current_progress}</span><br>
                    <span style="font-size:10px; font-weight:bold; opacity:0.8;">/10 Kofe</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 🟢 HƏDİYYƏ VARSA BİLDİRİŞ (Ağ fonda)
        if free_coffees > 0:
            st.markdown(f"""
            <div style="background:#4caf50; color:white; margin:15px 20px; padding:15px; border-radius:12px; font-weight:bold; box-shadow:0 4px 10px rgba(76, 175, 80, 0.3);">
                🎉 Təbriklər! Sizin istifadə edilməmiş <b>{free_coffees} Hədiyyə Kofeniz</b> var! Kassirə yaxınlaşın.
            </div>
            """, unsafe_allow_html=True)

        # 📑 TABLAR VƏ KONTENT
        st.markdown("<br>", unsafe_allow_html=True)
        t_home, t_card = st.tabs(["🏠 Təkliflər (Home)", "💳 Füzuli Kart (QR)"])
        
        # --- TAB 1: GÜNÜN TƏKLİFLƏRİ ---
        with t_home:
            st.markdown("<h4 style='margin-left: 20px; margin-top:10px; color:#c8102e !important; font-weight:900;'>🔥 Günün Təklifləri</h4>", unsafe_allow_html=True)
            
            # Promo 1
            st.markdown("""
            <div class="promo-card">
                <div class="promo-img">🥐</div>
                <div>
                    <h4 style="margin:0; font-weight:800; color:#111 !important;">Səhər Kombosu</h4>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#666 !important;">İstənilən Kofe + Kruasan = Yalnız 6 AZN. (12:00-a qədər)</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Promo 2
            st.markdown("""
            <div class="promo-card">
                <div class="promo-img" style="background:#e3f2fd;">☕</div>
                <div>
                    <h4 style="margin:0; font-weight:800; color:#111 !important;">Soyuq Günlər Üçün</h4>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#666 !important;">Yeni Karamel Makiyatomuzu yoxladınızmı? Şirin və isidici.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Promo 3
            st.markdown("""
            <div class="promo-card">
                <div class="promo-img" style="background:#fff3e0;">🎁</div>
                <div>
                    <h4 style="margin:0; font-weight:800; color:#111 !important;">Dostunu Gətir</h4>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#666 !important;">Kartındakı QR kodu dostunla paylaş, hər ikiniz +2 ulduz qazanın!</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # --- TAB 2: QR KOD (SAVE EDİLƏ BİLƏN) ---
        with t_card:
            st.markdown("""
            <div class="qr-card">
                <h3 style="margin-top:0; color:#c8102e !important; font-weight:900;">Sizin Rəqəmsal Kartınız</h3>
                <p style="color:#666 !important; font-size:14px; margin-bottom:20px;">
                    Sifariş verərkən bu kodu ofisianta və ya kassirə göstərin.
                </p>
            """, unsafe_allow_html=True)
            
            # Xarici API vasitəsilə təmiz Şəkil (img) kimi QR Kod generasiya edirik. 
            # Rəngi Füzulinin Qırmızısı edirik (#c8102e)
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=c8102e&bgcolor=ffffff"
            st.markdown(f"<img src='{qr_url}' style='width:200px; height:200px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); border-radius:10px;'/>", unsafe_allow_html=True)
            
            st.markdown(f"""
                <h4 style="margin-top:20px; letter-spacing: 2px; color:#333 !important;">{customer_id}</h4>
                <div style="margin-top:20px; padding:10px; background:#f9f9f9; border-radius:10px; border:1px dashed #ccc;">
                    <span style="font-size:12px; color:#888 !important;">💡 <b>İpucu:</b> QR kodun üzərinə basılı tutaraq "Save Image" (Şəkli yadda saxla) seçin. Beləcə internetsiz vaxtlarda da Qalereyadan istifadə edə bilərsiniz.</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.error("⚠️ Səhv QR Kod oxutdunuz və ya Müştəri tapılmadı.")
