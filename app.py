# =========================================================
# EMALATXANA POS & LOYALTY — genişləndirilmiş versiya
# =========================================================
import streamlit as st
import pandas as pd
import os, time
import bcrypt
from datetime import datetime
from sqlalchemy import text
from io import BytesIO
from reportlab.lib.pagesizes import A7
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ================= CONFIG =================
DB_URL = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
SHOP_NAME = "Emalatxana Coffee"

st.set_page_config(page_title="Emalatxana POS", page_icon="☕", layout="wide", initial_sidebar_state="collapsed")

# ================= CSS (əvvəlki ilə eynidir, yalnız bəzi əlavələr) =================
st.markdown("""
<style>
    section[data-testid="stSidebar"] {width: 280px !important;}
    .cart-item {padding:10px; border-bottom:1px solid #eee; display:flex; justify-content:space-between;}
    .total {font-size:1.4em; font-weight:bold; margin:16px 0;}
    .category-btn {height:60px; font-size:1.1em;}
    .qty-btn {min-width:50px; height:50px; font-size:1.2em;}
</style>
""", unsafe_allow_html=True)

# ================= DB =================
conn = st.connection("neon", type="sql", url=DB_URL)
def q(sql, p=None): return conn.query(sql, params=p, ttl=0)
def exec_sql(sql, p=None):
    with conn.session as s: s.execute(text(sql), p or {}); s.commit()

# ================= SESSION =================
for k, v in {
    "logged_in": False, "role": None, "user_id": None,
    "pin_input": "", "failed_attempts": 0, "last_attempt": None,
    "cart": [], "customer_card": None, "payment_method": "Nağd"
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ================= LOYALTY SCREEN (əvvəlki kimi) =================
qp = st.query_params
if "id" in qp:
    # ... (əvvəlki loyalty kart kodu buraya gəlir – dəyişməz qalır)
    st.stop()

# ================= PIN LOGIN (əvvəlki ilə eyni, yalnız kiçik optimallaşdırma) =================
# ... (əvvəlki PIN bloku buraya gəlir)

# ================= MAIN POS =================
if st.session_state.logged_in:

    # ================= SIDEBAR =================
    with st.sidebar:
        st.success(f"Kassir aktiv • {datetime.now().strftime('%H:%M')}")
        st.markdown("**Ödəniş növü**")
        st.session_state.payment_method = st.radio(
            "Ödəniş", ["Nağd", "Kart", "Mobil"], horizontal=True
        )

        if st.button("Çıxış", type="primary", use_container_width=True):
            for k in list(st.session_state):
                if k not in ["failed_attempts", "last_attempt"]:
                    del st.session_state[k]
            st.rerun()

    # ================= MAIN LAYOUT =================
    st.title("☕ Emalatxana POS")

    tab1, tab2 = st.tabs(["Satış", "Son əməliyyatlar"])

    with tab1:
        col_left, col_right = st.columns([5, 2])

        with col_left:
            # ── Məhsul kateqoriyaları ────────────────
            categories = ["İsti içkilər", "Soyuq içkilər", "Desert", "Digər"]
            cat = st.radio("Kateqoriya", categories, horizontal=True)

            # Sadə məhsul bazası (realda DB-dən gələcək)
            menu = {
                "İsti içkilər": [
                    {"name":"Americano", "price":3.50},
                    {"name":"Latte",     "price":4.20},
                    {"name":"Cappuccino","price":4.00},
                    {"name":"Espresso",  "price":2.80},
                ],
                "Soyuq içkilər": [
                    {"name":"Iced Latte", "price":4.80},
                    {"name":"Cold Brew",  "price":4.50},
                ],
                "Desert": [
                    {"name":"Cheesecake", "price":5.50},
                    {"name":"Brownie",    "price":4.00},
                ],
            }

            products = menu.get(cat, [])

            cols = st.columns(3)
            for i, p in enumerate(products):
                with cols[i%3]:
                    if st.button(f"{p['name']}\n{p['price']:.2f} ₼", key=f"add_{p['name']}_{cat}", use_container_width=True):
                        st.session_state.cart.append({**p, "qty":1})
                        st.rerun()

        with col_right:
            st.subheader("Səbət")

            if not st.session_state.cart:
                st.info("Henüz məhsul əlavə edilməyib")
            else:
                total = 0
                for i, item in enumerate(st.session_state.cart):
                    colA, colB, colC = st.columns([5,2,1])
                    with colA: st.write(item["name"])
                    with colB:
                        qty = st.number_input("Miqdar", 1, 20, item["qty"], key=f"qty_{i}", label_visibility="collapsed")
                        if qty != item["qty"]:
                            st.session_state.cart[i]["qty"] = qty
                            st.rerun()
                    with colC:
                        if st.button("🗑", key=f"del_{i}", help="Sil"):
                            del st.session_state.cart[i]
                            st.rerun()

                    total += item["price"] * item["qty"]

                st.markdown(f"<div class='total'>Cəmi: {total:.2f} ₼</div>", unsafe_allow_html=True)

                # Müştəri kartı oxuma sahəsi
                card_id = st.text_input("Müştəri kartı № (loyalty üçün)", "")
                if card_id and card_id != st.session_state.get("customer_card"):
                    df = q("SELECT * FROM customers WHERE card_id = :c", {"c":card_id})
                    if not df.empty:
                        st.session_state.customer_card = card_id
                        st.success(f"Müştəri tapıldı – {df.iloc[0]['name']}")
                    else:
                        st.warning("Kart tapılmadı")

                # Ödəniş düyməsi
                if st.button(f"ÖDƏNİŞ → {total:.2f} ₼", type="primary", use_container_width=True):
                    if total <= 0:
                        st.error("Səbət boşdur")
                    else:
                        sale_data = {
                            "cashier_id": st.session_state.user_id,
                            "total": total,
                            "payment_method": st.session_state.payment_method,
                            "customer_card": st.session_state.customer_card,
                            "created_at": datetime.now(),
                            "items": str([{"n":i["name"],"q":i["qty"],"p":i["price"]} for i in st.session_state.cart])
                        }

                        # Satışı yazırıq
                        exec_sql("""
                            INSERT INTO sales 
                            (cashier_id, total, payment_method, customer_card, items, created_at)
                            VALUES (:cashier_id, :total, :payment_method, :customer_card, :items, :created_at)
                        """, sale_data)

                        # Əgər müştəri kartı varsa → ulduz əlavə et
                        if st.session_state.customer_card:
                            exec_sql("""
                                UPDATE customers 
                                SET stars = stars + 1 
                                WHERE card_id = :card
                            """, {"card": st.session_state.customer_card})

                        st.success("Ödəniş qəbul edildi! ☑")
                        st.balloons()

                        # Səbəti sıfırlayırıq
                        st.session_state.cart = []
                        st.session_state.customer_card = None
                        st.rerun()

    with tab2:
        st.subheader("Son satışlar (son 48 saat)")
        recent = q("""
            SELECT s.*, u.username 
            FROM sales s
            LEFT JOIN users u ON s.cashier_id = u.id
            WHERE s.created_at > NOW() - INTERVAL '48 hours'
            ORDER BY s.created_at DESC
            LIMIT 12
        """)
        st.dataframe(recent[["created_at","total","payment_method","username"]])
