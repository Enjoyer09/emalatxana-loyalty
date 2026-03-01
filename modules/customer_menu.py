import streamlit as st
import pandas as pd
from database import run_query

def render_customer_app(customer_id=None):
    # 📱 1. EMALATKHANA LOQO RƏNGLƏRİ (CSS) - BOŞ SƏTİRLƏR SİLİNDİ
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;800;900&display=swap');
.stApp { background: #FAF5EF !important; font-family: 'Nunito', sans-serif !important; color: #2A4B2D !important; }
#MainMenu, header, footer { display: none !important; }
.block-container { padding: 0 !important; max-width: 100%; padding-bottom: 50px !important; }
.ema-header {
background-color: #E88D48; padding: 40px 20px 30px 20px;
display: flex; justify-content: space-between; align-items: center;
border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;
box-shadow: 0 10px 20px rgba(232, 141, 72, 0.3); position: relative;
}
.ema-promo {
background: #ffffff; border-radius: 15px; overflow: hidden;
box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin: 15px 20px; border: 1px solid #e2dcd5;
}
.ema-promo-img {
height: 140px; width: 100%; background-size: cover; background-position: center; background-color: #e2dcd5;
display: flex; align-items: flex-end; justify-content: flex-end; padding: 10px;
}
.ema-promo-content { padding: 15px; }
.ema-promo-title { font-size: 18px; font-weight: 900; color: #2A4B2D; margin: 0; }
.ema-promo-desc { font-size: 14px; color: #5a725c; margin: 5px 0 0 0; }
div[data-testid="stTabs"] { padding: 0 10px; margin-top: 15px; }
div[data-testid="stTabs"] button { font-size: 15px !important; font-weight: 800 !important; color: #8a9c8c !important; padding-bottom: 10px !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #2A4B2D !important; border-bottom: 3px solid #2A4B2D !important; }
.menu-item {
background: #ffffff; padding: 15px; margin: 10px 20px; border-radius: 12px;
box-shadow: 0 2px 8px rgba(0,0,0,0.03); border: 1px solid #e2dcd5;
display: flex; justify-content: space-between; align-items: center;
}
</style>
    """, unsafe_allow_html=True)

    if not customer_id:
        st.error("⚠️ QR Kod oxunmadı.")
        return

    c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
    if c_df.empty:
        st.error("⚠️ Müştəri tapılmadı.")
        return
        
    cust_data = c_df.iloc[0].to_dict()
    stars = cust_data.get('stars', 0)
    
    free_coffees = int(stars // 10)
    current_progress = int(stars % 10)
    remaining = 10 - current_progress
    svg_fill = current_progress * 10

    # ==========================================
    # 🔴 1. EMALATKHANA HERO SECTION (Narıncı fon, Yaşıl yazılar)
    # HİÇ BİR BOŞ SƏTİR YOXDUR - XƏTA VERMƏYƏCƏK!
    # ==========================================
    st.markdown(f"""<div class="ema-header"><div style="flex: 1;"><p style="margin:0; font-size:14px; font-weight:900; color:#2A4B2D; opacity:0.9;">EMALATKHANA REWARDS</p><h2 style="margin:5px 0 0 0; font-size:16px; font-weight:700; line-height:1.4; color:#2A4B2D;">Növbəti hədiyyə üçün <br><b style="font-weight:900;">{remaining} sifariş</b> qaldı!</h2><div style="margin-top:10px; display:inline-block; border: 1px solid #2A4B2D; padding: 4px 12px; border-radius: 20px; font-size:12px; font-weight:900; color:#2A4B2D;">{stars} ÜMUMİ XAL</div></div><div style="position:relative; width:90px; height:90px; margin-left:10px;"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" style="width:90px; height:90px; transform: rotate(-90deg);"><path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(42,75,45,0.15)" stroke-width="2.5"/><path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#2A4B2D" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="{svg_fill}, 100" /></svg><div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center;"><span style="font-size:26px; font-weight:900; line-height:1; color:#2A4B2D;">{current_progress}</span><span style="font-size:10px; font-weight:900; color:#2A4B2D; margin-top:-2px;">/ 10</span></div></div></div>""", unsafe_allow_html=True)

    if free_coffees > 0:
        st.markdown(f"""<div style="margin: 15px 20px; background: #E88D48; color: #ffffff; padding: 15px; border-radius: 12px; box-shadow: 0 4px 10px rgba(232, 141, 72, 0.4);"><h4 style="margin:0; font-weight:900; color:#ffffff;">Təbriklər! 🎁</h4><p style="margin:5px 0 0 0; font-size:14px; color:#ffffff; font-weight:700;">Sizin <b>{free_coffees} ədəd Pulsuz Kofe</b> hədiyyəniz var. Kassada sifariş verərkən bildirə bilərsiniz!</p></div>""", unsafe_allow_html=True)

    # ==========================================
    # 2. TABS
    # ==========================================
    t_home, t_qr, t_menu = st.tabs(["🏠 Təkliflər", "📱 QR Kart", "☕ Menyu"])

    # --- TAB 1: KAMPANİYALAR ---
    with t_home:
        st.markdown("<h3 style='margin: 10px 0 0 20px; font-weight:900; color:#2A4B2D; font-size:20px;'>Günün Təklifləri</h3>", unsafe_allow_html=True)
        try:
            campaigns = run_query("SELECT * FROM campaigns WHERE is_active=TRUE ORDER BY id DESC")
            if not campaigns.empty:
                for _, camp in campaigns.iterrows():
                    bg_img = camp['img_url'] if camp['img_url'] else "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&q=80&w=600"
                    badge_html = f"<div style='background:#E88D48; color:#ffffff; padding:5px 10px; border-radius:8px; font-weight:900; font-size:12px;'>{camp['badge']}</div>" if camp['badge'] else ""
                    st.markdown(f"""<div class="ema-promo"><div class="ema-promo-img" style="background-image: url('{bg_img}');">{badge_html}</div><div class="ema-promo-content"><h4 class="ema-promo-title">{camp['title']}</h4><p class="ema-promo-desc">{camp['description']}</p></div></div>""", unsafe_allow_html=True)
            else:
                st.info("Hazırda aktiv kampaniya yoxdur.")
        except:
            pass

    # --- TAB 2: QR KOD (QR rəngi Yaşıl oldu) ---
    with t_qr:
        st.markdown("""<div style="background:#ffffff; margin:20px; border-radius:20px; padding:30px 20px; text-align:center; box-shadow: 0 5px 20px rgba(0,0,0,0.05); border: 1px solid #e2dcd5;"><h3 style="margin-top:0; color:#2A4B2D; font-weight:900; font-size:22px;">Scan & Pay</h3><p style="color:#5a725c; font-size:14px; margin-bottom:25px; font-weight:700;">Sifariş verərkən ulduz qazanmaq üçün bu kodu kassada oxudun.</p>""", unsafe_allow_html=True)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=2A4B2D&bgcolor=ffffff"
        st.markdown(f"<img src='{qr_url}' style='width:200px; height:200px; box-shadow: 0 5px 15px rgba(42,75,45,0.15); border-radius:15px; border: 4px solid #E88D48;'/>", unsafe_allow_html=True)
        st.markdown(f"""<h4 style="margin-top:20px; font-weight:900; color:#2A4B2D; letter-spacing: 2px;">{customer_id}</h4><p style="margin-top:20px; font-size:12px; color:#8a9c8c; background:#FAF5EF; padding:10px; border-radius:10px; border: 1px dashed #E88D48;">💡 Şəklin üzərinə basılı tutaraq "Save Image" seçin və Qalereyada saxlayın.</p></div>""", unsafe_allow_html=True)

    # --- TAB 3: MENYU (Vitrin / Səbətsiz) ---
    with t_menu:
        st.markdown("""<div style="margin: 15px 20px; padding: 10px 15px; background: #2A4B2D; color: #ffffff; border-radius: 10px; text-align:center; font-size:14px; font-weight:700; box-shadow: 0 4px 10px rgba(42,75,45,0.3);">👋 Sifarişlərinizi kassada ofisianta yaxınlaşaraq verə bilərsiniz. Buyurun, menyumuzla tanış olun:</div>""", unsafe_allow_html=True)
        menu_df = run_query("SELECT id, item_name, price, category FROM menu WHERE is_active=TRUE")
        if menu_df.empty:
            st.warning("Menyu hazırda yenilənir...")
        else:
            cats = ["HAMISI"] + sorted(menu_df['category'].dropna().unique().tolist())
            selected_cat = st.radio("Kateqoriyalar", cats, horizontal=True, label_visibility="collapsed")
            if selected_cat != "HAMISI": 
                menu_df = menu_df[menu_df['category'] == selected_cat]

            for _, item in menu_df.iterrows():
                i_name = item['item_name']
                i_price = float(item['price'])
                st.markdown(f"""<div class="menu-item"><div><b style="font-size: 16px; color:#2A4B2D; font-weight:800;">{i_name}</b></div><div><span style="color: #E88D48; font-size:16px; font-weight:900;">{i_price:.2f} ₼</span></div></div>""", unsafe_allow_html=True)
