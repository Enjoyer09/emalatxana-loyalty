import streamlit as st
import pandas as pd
from database import run_query

def render_customer_app(customer_id=None):
    # 📱 1. MOBİL "APP" DİZAYNI VƏ LOYALTY CSS
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {padding: 1rem 0.5rem; max-width: 100%; padding-bottom: 100px;}
        
        /* TABS (Mobil tətbiq menyusu kimi) */
        div[data-testid="stTabs"] button {
            font-size: 16px !important;
            font-weight: bold !important;
            font-family: 'Nunito', sans-serif !important;
            color: #888 !important;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #ffd700 !important;
            border-bottom-color: #ffd700 !important;
        }
        
        /* Dashboard Kartları */
        .dash-card {
            background: linear-gradient(145deg, #2a2d32, #1e2226);
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.3);
            border: 1px solid #3a4149;
            margin-bottom: 20px;
        }
        
        .stars-big { font-size: 48px; font-weight: 900; color: #ffd700; text-shadow: 0 0 15px rgba(255, 215, 0, 0.4); font-family: 'Jura', sans-serif;}
        
        /* Progress Bar */
        .progress-bg {
            background: #111;
            border-radius: 20px;
            width: 100%;
            height: 25px;
            margin-top: 15px;
            overflow: hidden;
            border: 1px solid #333;
            position: relative;
        }
        .progress-fill {
            background: linear-gradient(90deg, #b38f00, #ffd700);
            height: 100%;
            border-radius: 20px;
            transition: width 0.5s ease-in-out;
        }
        .progress-text {
            position: absolute;
            width: 100%;
            text-align: center;
            top: 2px;
            font-size: 13px;
            font-weight: bold;
            color: #fff;
            text-shadow: 1px 1px 2px #000;
        }

        /* Məhsul Kartı Dizaynı */
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] {
            background-color: #ffffff;
            border-radius: 15px;
            padding: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.04);
            margin-bottom: 10px;
        }
        
        /* Uçan Səbət (Floating Cart) */
        .floating-cart {
            position: fixed;
            bottom: 20px;
            left: 5%;
            width: 90%;
            background-color: #1e2226;
            color: #ffd700;
            padding: 15px 20px;
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.8);
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 9999;
            font-family: sans-serif;
            font-weight: bold;
            border: 1px solid #ffd700;
        }
        </style>
    """, unsafe_allow_html=True)

    # 🛒 Səbət yaddaşı
    if 'cust_cart' not in st.session_state:
        st.session_state.cust_cart = {}

    # 👤 MÜŞTƏRİ MƏLUMATLARINI BAZADAN ÇƏKİRİK
    cust_data = None
    if customer_id:
        c_df = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": customer_id})
        if not c_df.empty:
            cust_data = c_df.iloc[0].to_dict()

    st.markdown(f"<h2 style='text-align: center; color: #ffd700; margin-bottom: 0;'>Füzuli Menu</h2>", unsafe_allow_html=True)
    
    # ƏGƏR MÜŞTƏRİ TAPILDISA, 3 TAB GÖSTƏRİRİK
    if cust_data:
        stars = cust_data.get('stars', 0)
        c_type = str(cust_data.get('type', 'Standard')).upper()
        
        # Sadiqlik məntiqi (Hər 10 ulduza 1 pulsuz kofe)
        free_coffees = int(stars // 10)
        stars_towards_next = int(stars % 10)
        progress_pct = (stars_towards_next / 10.0) * 100

        tab_home, tab_qr, tab_menu = st.tabs(["⭐ Hesabım", "📱 QR Kod", "📋 Menyu"])
        
        # ==========================================
        # TAB 1: DASHBOARD (Hesabım)
        # ==========================================
        with tab_home:
            st.markdown(f"""
                <div class="dash-card">
                    <p style='color:#aaa; font-size:18px; margin:0;'>Mövcud Ulduzlarım</p>
                    <div class="stars-big">{stars} ⭐</div>
                    <p style='color:#ffd700; font-weight:bold; margin-top:5px;'>Status: {c_type}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if free_coffees > 0:
                st.success(f"🎉 Təbriklər! Sizin **{free_coffees} ədəd HƏDİYYƏ** kofeniz var!")
            
            st.markdown(f"""
                <div style='background:#1e2226; padding:15px; border-radius:15px; border:1px solid #3a4149;'>
                    <h4 style='text-align:center; color:#fff; margin:0;'>Növbəti hədiyyəyə doğru:</h4>
                    <div class="progress-bg">
                        <div class="progress-fill" style="width: {progress_pct}%;"></div>
                        <div class="progress-text">{stars_towards_next} / 10 Ulduz</div>
                    </div>
                    <p style='text-align:center; color:#aaa; font-size:12px; margin-top:8px;'>Hər 10 ulduz 1 pulsuz kofe deməkdir!</p>
                </div>
            """, unsafe_allow_html=True)
        
        # ==========================================
        # TAB 2: QR KOD (Müştərinin Kartı)
        # ==========================================
        with tab_qr:
            st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
            st.markdown("<p style='color:#aaa; margin-bottom:15px;'>Kassada ödəniş edərkən bu QR kodu ofisianta göstərin ki, ulduzlarınız hesaba yazılsın.</p>", unsafe_allow_html=True)
            
            # Xarici API vasitəsilə sürətli QR generasiya edirik ki, ekranda şəkil kimi görünsün və "Save" edilə bilsin
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=id={customer_id}&color=1e2226&bgcolor=ffffff"
            st.markdown(f"<div style='text-align:center;'><img src='{qr_url}' style='border-radius:20px; border: 5px solid #fff; box-shadow: 0 5px 15px rgba(0,0,0,0.5); width:200px; height:200px;'/></div>", unsafe_allow_html=True)
            
            st.markdown(f"<h3 style='text-align:center; color:#ffd700; margin-top:15px;'>{customer_id}</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; font-size:12px; color:#aaa;'>* QR Kodu telefonunuzda saxlamaq üçün üzərinə basılı tutub 'Save Image' seçin.</p>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    else:
        # Əgər ID səhvdirsə və ya yoxdursa, yalnız menyunu göstəririk
        st.warning("Müştəri profili tapılmadı, lakin menyuya baxa bilərsiniz.")
        tab_menu = st.container()

    # ==========================================
    # TAB 3: SİFARİŞ VƏ MENYU
    # ==========================================
    menu_container = tab_menu if cust_data else st.container()
    
    with menu_container:
        menu_df = run_query("SELECT id, item_name, price, category FROM menu WHERE is_active=TRUE")
        if menu_df.empty:
            st.warning("Menyu hazırda yenilənir...")
            return

        cats = ["HAMISI"] + sorted(menu_df['category'].dropna().unique().tolist())
        selected_cat = st.radio("Kateqoriyalar", cats, horizontal=True, label_visibility="collapsed")
        
        if selected_cat != "HAMISI":
            menu_df = menu_df[menu_df['category'] == selected_cat]

        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

        for _, item in menu_df.iterrows():
            i_id = str(item['id'])
            i_name = item['item_name']
            i_price = float(item['price'])
            
            c1, c2 = st.columns([3, 1.5], vertical_alignment="center")
            
            with c1:
                st.markdown(f"<b style='font-size: 16px; color:#333;'>{i_name}</b><br><span style='color: #888; font-size:14px;'>{i_price:.2f} ₼</span>", unsafe_allow_html=True)
                
            with c2:
                qty = st.session_state.cust_cart.get(i_id, {}).get('qty', 0)
                if qty == 0:
                    if st.button("Əlavə et ➕", key=f"add_{i_id}", use_container_width=True):
                        st.session_state.cust_cart[i_id] = {'name': i_name, 'price': i_price, 'qty': 1}
                        st.rerun()
                else:
                    b1, b2, b3 = st.columns([1,1,1])
                    if b1.button("➖", key=f"dec_{i_id}"):
                        st.session_state.cust_cart[i_id]['qty'] -= 1
                        if st.session_state.cust_cart[i_id]['qty'] == 0:
                            del st.session_state.cust_cart[i_id]
                        st.rerun()
                    b2.markdown(f"<div style='text-align:center; padding-top:5px; font-weight:bold; color:#1e2226;'>{qty}</div>", unsafe_allow_html=True)
                    if b3.button("➕", key=f"inc_{i_id}"):
                        st.session_state.cust_cart[i_id]['qty'] += 1
                        st.rerun()

        # UÇAN SƏBƏT HESABLARI
        total_qty = sum([v['qty'] for v in st.session_state.cust_cart.values()])
        total_price = sum([v['qty'] * v['price'] for v in st.session_state.cust_cart.values()])

        if total_qty > 0:
            st.markdown(f"""
                <div class="floating-cart">
                    <div>🛒 {total_qty} məhsul</div>
                    <div style="font-size: 18px;">{total_price:.2f} ₼</div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("Sifarişi Göndər 🚀", type="primary", use_container_width=True):
                # Növbəti mərhələdə Sifarişi birbaşa kassanın (POS) ekranına atacağıq!
                st.success("✅ Sifarişiniz qəbul edildi!")
                st.session_state.cust_cart = {}
                st.rerun()
