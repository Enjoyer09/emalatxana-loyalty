import streamlit as st
import pandas as pd
import random
import qrcode
from io import BytesIO
import zipfile
from PIL import Image, ImageDraw, ImageFont
import time
from sqlalchemy import text, exc
import os
import bcrypt
import requests
import datetime
import secrets
import threading
import base64

# ==========================================
# === IRONWAVES POS - VERSION 2.0 (ALPHA) ===
# === MODULE: INVENTORY & RECIPES ===
# ==========================================

# --- CONFIG ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store" 
APP_URL = f"https://{DOMAIN}"
DEFAULT_SENDER_EMAIL = "info@ironwaves.store" 

st.set_page_config(page_title="Ironwaves V2", page_icon="🧪", layout="wide", initial_sidebar_state="expanded")

# --- STYLES ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;700;900&display=swap');
    .stApp { font-family: 'Oswald', sans-serif !important; background-color: #f0f2f6; }
    div.stButton > button[kind="primary"] { background-color: #6200EA !important; border:none; }
    .metric-card { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- DB CONNECTION ---
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url: st.error("DB URL not found!"); st.stop()
    if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    conn = st.connection("neon", type="sql", url=db_url, pool_pre_ping=True)
except Exception as e: st.error(f"DB Error: {e}"); st.stop()

# --- HELPERS ---
def run_query(q, p=None): return conn.query(q, params=p, ttl=0)
def run_action(q, p=None): 
    with conn.session as s: s.execute(text(q), p if p else {}); s.commit()

# --- V2: ANBAR FUNKSİYALARI ---
def render_inventory_management():
    st.markdown("### 📦 Ağıllı Anbar İdarəetməsi (V2)")
    
    inv_tabs = st.tabs(["📋 Xammal Siyahısı", "➕ Yeni Xammal", "🥣 Reseptlər", "💰 Mədaxil (Alış)"])
    
    # 1. XAMMAL SİYAHISI
    with inv_tabs[0]:
        df_inv = run_query("SELECT * FROM inventory ORDER BY name")
        if not df_inv.empty:
            for index, row in df_inv.iterrows():
                # Stok yoxlanışı
                status_color = "red" if row['stock_level'] <= row['alert_limit'] else "green"
                status_icon = "⚠️ BİTİR!" if row['stock_level'] <= row['alert_limit'] else "OK"
                
                with st.expander(f"{status_icon} {row['name']} | Qalıq: {row['stock_level']} {row['unit']}"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Qalıq", f"{row['stock_level']} {row['unit']}")
                    c2.metric("Maya Dəyəri", f"{row['cost_per_unit']} ₼ / {row['unit']}")
                    c3.metric("Limit", f"{row['alert_limit']}")
                    
                    if st.button(f"🗑️ Sil ({row['name']})", key=f"del_inv_{row['id']}"):
                        run_action("DELETE FROM inventory WHERE id=:id", {"id":row['id']})
                        st.rerun()
        else:
            st.info("Anbar boşdur. 'Yeni Xammal' bölməsindən əlavə edin.")

    # 2. YENİ XAMMAL
    with inv_tabs[1]:
        with st.form("add_inv"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Xammal Adı (Məs: Süd 3.2%)")
            unit = c2.selectbox("Ölçü Vahidi", ["kq", "litr", "ədəd", "qr", "ml"])
            alert = st.number_input("Xəbərdarlıq Limiti (Bu rəqəmdən az olanda xəbər ver)", min_value=0.0)
            
            if st.form_submit_button("Anbara Əlavə Et"):
                run_action("INSERT INTO inventory (name, unit, alert_limit) VALUES (:n, :u, :a)", 
                           {"n":name, "u":unit, "a":alert})
                st.success(f"{name} anbara əlavə olundu!"); st.rerun()

    # 3. RESEPTLƏR (Kofeni Xammala bağlamaq)
    with inv_tabs[2]:
        st.info("Burada Menyu məhsulunu seçib, onun içində nə olduğunu yazacağıq.")
        
        # Menyu və Xammalları gətiririk
        menu_items = run_query("SELECT id, item_name FROM menu ORDER BY item_name")
        inv_items = run_query("SELECT id, name, unit FROM inventory ORDER BY name")
        
        if not menu_items.empty and not inv_items.empty:
            c1, c2, c3 = st.columns([2, 2, 1])
            sel_menu = c1.selectbox("Menyu Məhsulu", menu_items['item_name'].tolist())
            sel_inv = c2.selectbox("İstifadə olunan Xammal", inv_items['name'].tolist())
            
            # Seçimlərin ID-lərini tapırıq
            m_id = menu_items[menu_items['item_name']==sel_menu].iloc[0]['id']
            i_row = inv_items[inv_items['name']==sel_inv].iloc[0]
            i_id = i_row['id']; i_unit = i_row['unit']
            
            qty = c3.number_input(f"Miqdar ({i_unit})", min_value=0.0, step=0.001, format="%.3f")
            
            if st.button("🔗 Reseptə Əlavə Et"):
                run_action("INSERT INTO recipes (menu_item_id, item_name_cached, inventory_item_id, quantity_required) VALUES (:mid, :mname, :iid, :q)",
                           {"mid":int(m_id), "mname":sel_menu, "iid":int(i_id), "q":qty})
                st.success("Bağlantı quruldu!")
            
            st.divider()
            st.markdown("#### 📜 Mövcud Reseptlər")
            recipes = run_query("""
                SELECT r.id, r.item_name_cached, i.name as inv_name, r.quantity_required, i.unit 
                FROM recipes r 
                JOIN inventory i ON r.inventory_item_id = i.id
                ORDER BY r.item_name_cached
            """)
            st.dataframe(recipes, use_container_width=True)
            
        else:
            st.warning("Əvvəlcə Anbara xammal əlavə edin.")

    # 4. MƏDAXİL (MAL ALIŞI)
    with inv_tabs[3]:
        st.markdown("Bazardan mal alanda buraya daxil edin ki, stok artsın.")
        inv_items = run_query("SELECT id, name, unit FROM inventory ORDER BY name")
        
        if not inv_items.empty:
            with st.form("stock_in"):
                s_item = st.selectbox("Məhsul", inv_items['name'].tolist())
                s_qty = st.number_input("Nə qədər aldınız?", min_value=0.0)
                s_price = st.number_input("Cəmi nə qədər pul verdiniz? (AZN)", min_value=0.0)
                
                if st.form_submit_button("Stoku Artır"):
                    i_data = inv_items[inv_items['name']==s_item].iloc[0]
                    # Yeni maya dəyərini hesablamaq (Weighted Average Cost) - sadə versiya
                    unit_cost = s_price / s_qty if s_qty > 0 else 0
                    
                    run_action("""
                        UPDATE inventory 
                        SET stock_level = stock_level + :qty, 
                            cost_per_unit = :cost 
                        WHERE id = :id
                    """, {"qty":s_qty, "cost":unit_cost, "id":int(i_data['id'])})
                    
                    run_action("INSERT INTO expenses (description, amount, category, created_by) VALUES (:d, :a, 'Məhsul Alışı', 'Admin')",
                               {"d":f"{s_item} alışı ({s_qty} {i_data['unit']})", "a":s_price})
                    
                    st.success("Anbar yeniləndi və Xərc yazıldı!")
        else:
            st.warning("Xammal yoxdur.")

# --- MAIN APP LAYOUT (ONLY V2 PARTS) ---
st.title("🧪 Ironwaves POS v2.0 (Alpha)")
st.info("Bu sadəcə V2 test versiyasıdır. Real satışlar üçün 'app.py' istifadə edin.")

# Parol qorunması (Sadəcə Admin)
pwd = st.text_input("Giriş üçün Admin Şifrəsi", type="password")
if pwd == "demo" or pwd == "admin": # Test üçün sadə şifrə
    render_inventory_management()
else:
    st.warning("Test mühitinə giriş üçün şifrə tələb olunur.")
