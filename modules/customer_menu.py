import streamlit as st
import pandas as pd
from database import run_query

def render_customer_app(customer_id=None):
    # 📱 1. MOBİL "APP" DİZAYNI ÜÇÜN XÜSUSİ CSS (Uçan Səbət, Şıq Kartlar)
    st.markdown("""
        <style>
        /* Streamlit-in standart menyu və lazımsız boşluqlarını gizlədirik */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {padding: 1rem 0.5rem; max-width: 100%; padding-bottom: 100px;}
        
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
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 9999;
            font-family: sans-serif;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    # 🛒 Səbət yaddaşını hazırlayırıq
    if 'cust_cart' not in st.session_state:
        st.session_state.cust_cart = {}

    st.markdown(f"<h2 style='text-align: center; color: #1e2226;'>☕ Füzuli Menu</h2>", unsafe_allow_html=True)

    # 🗄️ Bazadan aktiv menyunu çəkirik
    menu_df = run_query("SELECT id, item_name, price, category FROM menu WHERE is_active=TRUE")
    
    if menu_df.empty:
        st.warning("Menyu hazırda yenilənir...")
        return

    # 🏷️ KATEQORİYALAR (Üfüqi menyu kimi)
    cats = ["HAMISI"] + sorted(menu_df['category'].dropna().unique().tolist())
    selected_cat = st.radio("Kateqoriyalar", cats, horizontal=True, label_visibility="collapsed")
    
    if selected_cat != "HAMISI":
        menu_df = menu_df[menu_df['category'] == selected_cat]

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

    # ☕ MƏHSUL KARTLARI (Şıq və yığcam)
    for _, item in menu_df.iterrows():
        i_id = str(item['id'])
        i_name = item['item_name']
        i_price = float(item['price'])
        
        c1, c2 = st.columns([3, 1.5], vertical_alignment="center")
        
        with c1:
            st.markdown(f"<b style='font-size: 16px; color:#333;'>{i_name}</b><br><span style='color: #888; font-size:14px;'>{i_price:.2f} ₼</span>", unsafe_allow_html=True)
            
        with c2:
            # Artırıb/Azaltma məntiqi
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
                b2.markdown(f"<div style='text-align:center; padding-top:5px; font-weight:bold;'>{qty}</div>", unsafe_allow_html=True)
                if b3.button("➕", key=f"inc_{i_id}"):
                    st.session_state.cust_cart[i_id]['qty'] += 1
                    st.rerun()

    # 🛍️ UÇAN SƏBƏT HESABLARI
    total_qty = sum([v['qty'] for v in st.session_state.cust_cart.values()])
    total_price = sum([v['qty'] * v['price'] for v in st.session_state.cust_cart.values()])

    if total_qty > 0:
        # Səbət düyməsi və dizaynı
        st.markdown(f"""
            <div class="floating-cart">
                <div>🛒 {total_qty} məhsul</div>
                <div style="font-size: 18px;">{total_price:.2f} ₼</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Streamlitin görünməz düyməsini Uçan Səbətin üstünə qoyuruq ki, kliklənə bilsin
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Sifarişi Təsdiqlə (Ofisianta Göndər) 🚀", type="primary", use_container_width=True):
            # BURADA SİFARİŞİ BAZAYA YAZMA MƏNTİQİ OLACAQ (Növbəti addım)
            st.success("✅ Sifarişiniz qəbul edildi! Barista hazırlayır...")
            st.session_state.cust_cart = {} # Səbəti sıfırla
