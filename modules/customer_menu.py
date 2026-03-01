import streamlit as st
import pandas as pd
from database import run_query
import datetime

def render_customer_app(customer_id=None):
    # 📱 1. EMALATKHANA STİLİ DİZAYN (CSS)
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;800;900&display=swap');
.stApp { background: #f8f9fa !important; font-family: 'Nunito', sans-serif !important; color: #111 !important; }
#MainMenu, header, footer { display: none !important; }
.block-container { padding: 0 !important; max-width: 100%; padding-bottom: 90px !important; }
.tims-header {
background-color: #c8102e; color: #ffffff; padding: 40px 20px 30px 20px;
display: flex; justify-content: space-between; align-items: center;
border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;
box-shadow: 0 10px 20px rgba(200, 16, 46, 0.2); position: relative;
}
.tims-promo {
background: #ffffff; border-radius: 15px; overflow: hidden;
box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin: 15px 20px; border: 1px solid #edf2f7;
}
.tims-promo-img {
height: 140px; width: 100%; background-size: cover; background-position: center; background-color: #f0f0f0;
display: flex; align-items: flex-end; justify-content: flex-end; padding: 10px;
}
.tims-promo-content { padding: 15px; }
.tims-promo-title { font-size: 18px; font-weight: 800; color: #2d3748; margin: 0; }
.tims-promo-desc { font-size: 14px; color: #718096; margin: 5px 0 0 0; }
div[data-testid="stTabs"] { padding: 0 10px; margin-top: 15px; }
div[data-testid="stTabs"] button { font-size: 15px !important; font-weight: 800 !important; color: #a0aec0 !important; padding-bottom: 10px !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #c8102e !important; border-bottom: 3px solid #c8102e !important; }
.tims-floating-cart {
position: fixed; bottom: 20px; left: 5%; width: 90%;
background-color: #c8102e; color: #ffffff; padding: 15px 20px;
border-radius: 50px; box-shadow: 0 10px 25px rgba(200, 16, 46, 0.4);
display: flex; justify-content: space-between; align-items: center;
z-index: 9999; font-weight: 800; border: 2px solid #fff;
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
    # 🔴 1. EMALATKHANA REWARDS HERO SECTION
    # Diqqət: HTML-i təmizlədik ki, ekranda yazı kimi çıxmasın!
    # ==========================================
    st.markdown(f"""
<div class="tims-header">
<div style="flex: 1;">
<p style="margin:0; font-size:14px; font-weight:900; color:rgba(255,255,255,0.9);">Emalatkhana Rewards</p>
<h2 style="margin:5px 0 0 0; font-size:16px; font-weight:400; line-height:1.4;">Növbəti hədiyyə üçün <br><b>{remaining} sifariş</b> qaldı!</h2>
<div style="margin-top:10px; display:inline-block; border: 1px solid rgba(255,255,255,0.5); padding: 4px 12px; border-radius: 20px; font-size:12px; font-weight:800;">{stars} ÜMUMİ XAL</div>
</div>
<div style="position:relative; width:90px; height:90px; margin-left:10px;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" style="width:90px; height:90px; transform: rotate(-90deg);">
<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="2.5"/>
<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="{svg_fill}, 100" />
</svg>
<div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center;">
<span style="font-size:26px; font-weight:900; line-height:1; color:#ffffff;">{current_progress}</span>
<span style="font-size:10px; font-weight:bold; color:rgba(255,255,255,0.8); margin-top:-2px;">/ 10</span>
</div>
</div>
</div>
    """, unsafe_allow_html=True)

    if free_coffees > 0:
        st.markdown(f"""
<div style="margin: 15px 20px; background: #fff3f3; border: 1px solid #ffcccc; border-left: 5px solid #c8102e; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
<h4 style="margin:0; color:#c8102e; font-weight:900;">Təbriklər! 🎁</h4>
<p style="margin:5px 0 0 0; font-size:14px; color:#4a5568;">Sizin <b>{free_coffees} ədəd Pulsuz Kofe</b> hədiyyəniz var. Kassada istifadə edə bilərsiniz!</p>
</div>
        """, unsafe_allow_html=True)

    # ==========================================
    # 2. TABS
    # ==========================================
    t_home, t_qr, t_menu = st.tabs(["🏠 Təkliflər", "📱 Scan & Pay", "☕ Menyu"])

    # --- TAB 1: KAMPANİYALAR (Dinamik) ---
    with t_home:
        st.markdown("<h3 style='margin: 10px 0 0 20px; font-weight:900; color:#111; font-size:20px;'>Günün Təklifləri</h3>", unsafe_allow_html=True)
        
        try:
            campaigns = run_query("SELECT * FROM campaigns WHERE is_active=TRUE ORDER BY id DESC")
            if not campaigns.empty:
                for _, camp in campaigns.iterrows():
                    bg_img = camp['img_url'] if camp['img_url'] else "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&q=80&w=600"
                    badge_html = f"<div style='background:#c8102e; color:#fff; padding:5px 10px; border-radius:8px; font-weight:bold; font-size:12px;'>{camp['badge']}</div>" if camp['badge'] else ""
                    
                    st.markdown(f"""
<div class="tims-promo">
<div class="tims-promo-img" style="background-image: url('{bg_img}');">
{badge_html}
</div>
<div class="tims-promo-content">
<h4 class="tims-promo-title">{camp['title']}</h4>
<p class="tims-promo-desc">{camp['description']}</p>
</div>
</div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Hazırda aktiv kampaniya yoxdur. Yeniliklər üçün izləmədə qalın!")
        except Exception as e:
            st.info("Kampaniyalar yüklənir...")

    # --- TAB 2: QR KOD ---
    with t_qr:
        st.markdown("""
<div style="background:#ffffff; margin:20px; border-radius:20px; padding:30px 20px; text-align:center; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid #edf2f7;">
<h3 style="margin-top:0; color:#111; font-weight:900; font-size:22px;">Scan & Pay</h3>
<p style="color:#718096; font-size:14px; margin-bottom:25px;">Kassada sifariş verərkən ulduz qazanmaq üçün bu kodu oxudun.</p>
        """, unsafe_allow_html=True)
        
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=c8102e&bgcolor=ffffff"
        st.markdown(f"<img src='{qr_url}' style='width:200px; height:200px; box-shadow: 0 5px 15px rgba(200,16,46,0.15); border-radius:15px; border: 4px solid #fff;'/>", unsafe_allow_html=True)
        
        st.markdown(f"""
<h4 style="margin-top:20px; font-weight:800; color:#c8102e; letter-spacing: 2px;">{customer_id}</h4>
<p style="margin-top:20px; font-size:12px; color:#a0aec0; background:#f8f9fa; padding:10px; border-radius:10px;">
Şəklin üzərinə basılı tutaraq "Save Image" seçin və Qalereyada saxlayın.
</p>
</div>
        """, unsafe_allow_html=True)

    # --- TAB 3: MENYU VƏ SƏBƏT ---
    if 'cust_cart' not in st.session_state: st.session_state.cust_cart = {}

    with t_menu:
        menu_df = run_query("SELECT id, item_name, price, category FROM menu WHERE is_active=TRUE")
        if menu_df.empty:
            st.warning("Menyu hazırda yenilənir...")
        else:
            cats = ["HAMISI"] + sorted(menu_df['category'].dropna().unique().tolist())
            selected_cat = st.radio("Kateqoriyalar", cats, horizontal=True, label_visibility="collapsed")
            if selected_cat != "HAMISI": menu_df = menu_df[menu_df['category'] == selected_cat]

            st.markdown("<hr style='margin: 10px 0; border-color:#edf2f7;'>", unsafe_allow_html=True)

            for _, item in menu_df.iterrows():
                i_id = str(item['id'])
                i_name = item['item_name']
                i_price = float(item['price'])
                
                c1, c2 = st.columns([3, 1.5], vertical_alignment="center")
                with c1:
                    st.markdown(f"<div style='padding:10px 0;'><b style='font-size: 16px; color:#111; font-weight:800;'>{i_name}</b><br><span style='color: #c8102e; font-size:14px; font-weight:800;'>{i_price:.2f} ₼</span></div>", unsafe_allow_html=True)
                with c2:
                    qty = st.session_state.cust_cart.get(i_id, {}).get('qty', 0)
                    if qty == 0:
                        if st.button("➕", key=f"add_{i_id}", use_container_width=True):
                            st.session_state.cust_cart[i_id] = {'name': i_name, 'price': i_price, 'qty': 1}; st.rerun()
                    else:
                        b1, b2, b3 = st.columns([1,1,1])
                        if b1.button("➖", key=f"dec_{i_id}"):
                            st.session_state.cust_cart[i_id]['qty'] -= 1
                            if st.session_state.cust_cart[i_id]['qty'] == 0: del st.session_state.cust_cart[i_id]
                            st.rerun()
                        b2.markdown(f"<div style='text-align:center; padding-top:5px; font-weight:900; color:#111;'>{qty}</div>", unsafe_allow_html=True)
                        if b3.button("➕", key=f"inc_{i_id}"):
                            st.session_state.cust_cart[i_id]['qty'] += 1; st.rerun()

            total_qty = sum([v['qty'] for v in st.session_state.cust_cart.values()])
            total_price = sum([v['qty'] * v['price'] for v in st.session_state.cust_cart.values()])

            if total_qty > 0:
                st.markdown(f"""
<div class="tims-floating-cart">
<div style="font-size:16px;">Səbət ({total_qty})</div>
<div style="font-size: 18px;">{total_price:.2f} ₼</div>
</div>
                """, unsafe_allow_html=True)
                
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("Sifarişi Təsdiqlə 🚀", type="primary", use_container_width=True):
                    st.success("✅ Sifarişiniz qəbul edildi!")
                    st.session_state.cust_cart = {}
                    st.rerun()
