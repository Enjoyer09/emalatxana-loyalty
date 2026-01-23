import streamlit as st
import pandas as pd
import os, io, zipfile, datetime, secrets
import bcrypt, requests, qrcode
from PIL import Image
from sqlalchemy import text

# =========================================================
# CONFIG
# =========================================================
SHOP_NAME_DEFAULT = "Coffee Shop"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

st.set_page_config(
    page_title="Coffee POS & Loyalty",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# GLOBAL CSS
# =========================================================
st.markdown("""
<style>
#MainMenu, header, footer { display: none !important; }

.pos-grid button { height: 90px; font-weight: bold; font-size: 16px; }
.coffee { background:#E8F5E9 !important; }
.drink { background:#EDE7F6 !important; }
.dessert { background:#FCE4EC !important; }

.pulse {
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.08); }
  100% { transform: scale(1); }
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# DATABASE
# =========================================================
conn = st.connection("neon", type="sql")

def q(sql, params=None):
    return conn.query(sql, params=params, ttl=0)

def exec_sql(sql, params=None):
    with conn.session as s:
        s.execute(text(sql), params)
        s.commit()

# =========================================================
# SCHEMA
# =========================================================
def ensure_schema():
    exec_sql("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        role TEXT
    );

    CREATE TABLE IF NOT EXISTS customers (
        card_id TEXT PRIMARY KEY,
        stars INTEGER DEFAULT 0,
        type TEXT,
        email TEXT,
        birth_date DATE,
        is_active BOOLEAN DEFAULT FALSE,
        secret_token TEXT,
        last_feedback_star INTEGER
    );

    CREATE TABLE IF NOT EXISTS menu (
        id SERIAL PRIMARY KEY,
        item_name TEXT,
        price NUMERIC,
        category TEXT,
        is_coffee BOOLEAN,
        is_active BOOLEAN DEFAULT TRUE
    );

    CREATE TABLE IF NOT EXISTS sales (
        id SERIAL PRIMARY KEY,
        items TEXT,
        total NUMERIC,
        payment_method TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS customer_coupons (
        id SERIAL PRIMARY KEY,
        card_id TEXT,
        coupon_type TEXT,
        is_used BOOLEAN DEFAULT FALSE
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        card_id TEXT,
        message TEXT,
        is_read BOOLEAN DEFAULT FALSE
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        card_id TEXT,
        rating INTEGER,
        message TEXT
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

ensure_schema()

# =========================================================
# HELPERS
# =========================================================
def get_setting(key, default=""):
    df = q("SELECT value FROM settings WHERE key=:k", {"k": key})
    return df.iloc[0]["value"] if not df.empty else default

def set_setting(key, value):
    exec_sql(
        "INSERT INTO settings(key,value) VALUES(:k,:v) "
        "ON CONFLICT(key) DO UPDATE SET value=:v",
        {"k": key, "v": value}
    )

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw, hashed):
    if not hashed.startswith("$2"):
        return pw == hashed
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def generate_qr(data):
    qr = qrcode.make(data)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

def send_email(to, subject, body):
    if not RESEND_API_KEY:
        return
    requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": f"{get_setting('shop_name', SHOP_NAME_DEFAULT)} <info@yourdomain.com>",
            "to": [to],
            "subject": subject,
            "html": body
        }
    )

# =========================================================
# SESSION STATE
# =========================================================
for k, v in {
    "logged_in": False,
    "role": None,
    "cart": [],
    "current_customer": None
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# ROLE 1 — CUSTOMER (QR)
# =========================================================
params = st.query_params
if "id" in params:
    cid = params["id"]
    token = params.get("t")

    df = q("SELECT * FROM customers WHERE card_id=:c", {"c": cid})
    if df.empty:
        st.error("Invalid card")
        st.stop()

    user = df.iloc[0]
    if user["secret_token"] and token != user["secret_token"]:
        st.error("Unauthorized")
        st.stop()

    st.title(get_setting("shop_name", SHOP_NAME_DEFAULT))

    # Activation
    if not user["is_active"]:
        with st.form("activate"):
            st.markdown("### Terms & Conditions")
            st.text_area("Rules", "1 coffee = 1 star\n10 stars = free coffee", height=120)
            agree = st.checkbox("I Agree")
            email = st.text_input("Email")
            if st.form_submit_button("Activate") and agree:
                exec_sql(
                    "UPDATE customers SET is_active=TRUE,email=:e WHERE card_id=:c",
                    {"e": email, "c": cid}
                )
                st.rerun()

    stars = int(user["stars"])
    cols = st.columns(10)
    for i in range(10):
        cols[i].write("☕" if i < stars else "⚪")

    coupons = q(
        "SELECT * FROM customer_coupons WHERE card_id=:c AND is_used=FALSE",
        {"c": cid}
    )
    if not coupons.empty:
        st.markdown(
            f"<div class='pulse'>🎁 {coupons.iloc[0]['coupon_type']}</div>",
            unsafe_allow_html=True
        )

    # Feedback
    if user["last_feedback_star"] is None:
        with st.form("feedback"):
            rating = st.slider("Rating", 1, 5)
            msg = st.text_input("Message")
            if st.form_submit_button("Send"):
                exec_sql(
                    "INSERT INTO feedback(card_id,rating,message) VALUES(:c,:r,:m)",
                    {"c": cid, "r": int(rating), "m": msg}
                )
                exec_sql(
                    "UPDATE customers SET last_feedback_star=:r WHERE card_id=:c",
                    {"r": int(rating), "c": cid}
                )
                st.success("Thanks!")

    st.download_button(
        "Download QR",
        generate_qr(f"?id={cid}&t={user['secret_token']}"),
        f"{cid}.png"
    )
    st.stop()

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.logged_in:
    st.title("Staff Login")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            df = q("SELECT * FROM users WHERE username=:u", {"u": u})
            if not df.empty and verify_pw(p, df.iloc[0]["password"]):
                st.session_state.logged_in = True
                st.session_state.role = df.iloc[0]["role"]
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# =========================================================
# ROLE 2 — STAFF POS
# =========================================================
def render_pos():
    left, right = st.columns([1.3, 1])

    with left:
        st.subheader("Cart")
        cid = st.text_input("Customer QR")
        if cid:
            df = q("SELECT * FROM customers WHERE card_id=:c", {"c": cid})
            if not df.empty:
                st.session_state.current_customer = df.iloc[0]

        for i, item in enumerate(st.session_state.cart):
            st.write(f"{item['item_name']} - {item['price']}")

        total = sum(float(x["price"]) for x in st.session_state.cart)
        st.metric("Total", f"{total:.2f}")

        pay = st.radio("Payment", ["Cash", "Card"])
        if st.button("Pay"):
            exec_sql(
                "INSERT INTO sales(items,total,payment_method) VALUES(:i,:t,:p)",
                {
                    "i": ", ".join(x["item_name"] for x in st.session_state.cart),
                    "t": total,
                    "p": pay
                }
            )
            st.session_state.cart = []
            st.success("Paid")
            st.rerun()

    with right:
        st.subheader("Menu")
        menu = q("SELECT * FROM menu WHERE is_active=TRUE")
        cols = st.columns(3)
        for i, m in menu.iterrows():
            cls = "coffee" if m["category"]=="Coffee" else "drink" if m["category"]=="Drink" else "dessert"
            if cols[i % 3].button(
                f"{m['item_name']}\n{m['price']}",
                key=f"m{m['id']}",
                use_container_width=True
            ):
                st.session_state.cart.append(m.to_dict())
                st.rerun()

# =========================================================
# ROLE 3 — ADMIN
# =========================================================
if st.session_state.role == "admin":
    tabs = st.tabs(["POS", "Analytics", "CRM", "Menu", "Settings", "Users", "QR"])
    with tabs[0]: render_pos()

    with tabs[1]:
        sales = q("SELECT * FROM sales")
        st.bar_chart(sales["total"])

    with tabs[2]:
        users = q("SELECT * FROM customers WHERE email IS NOT NULL")
        selected = st.data_editor(users, use_container_width=True)
        if st.button("Send Email"):
            for _, r in selected.iterrows():
                send_email(r["email"], "Promo", "Hello!")

    with tabs[3]:
        with st.form("menu"):
            n = st.text_input("Name")
            p = st.number_input("Price")
            c = st.selectbox("Category", ["Coffee", "Drink", "Dessert"])
            ic = st.checkbox("Is Coffee")
            if st.form_submit_button("Add"):
                exec_sql(
                    "INSERT INTO menu(item_name,price,category,is_coffee) VALUES(:n,:p,:c,:i)",
                    {"n": n, "p": float(p), "c": c, "i": ic}
                )

    with tabs[4]:
        name = st.text_input("Shop Name", get_setting("shop_name", SHOP_NAME_DEFAULT))
        if st.button("Save"):
            set_setting("shop_name", name)

    with tabs[5]:
        with st.form("user"):
            u = st.text_input("Username")
            p = st.text_input("Password")
            r = st.selectbox("Role", ["staff", "admin"])
            if st.form_submit_button("Add"):
                exec_sql(
                    "INSERT INTO users VALUES(:u,:p,:r)",
                    {"u": u, "p": hash_pw(p), "r": r}
                )

    with tabs[6]:
        count = st.number_input("How many cards", 1, 100)
        if st.button("Generate"):
            z = io.BytesIO()
            with zipfile.ZipFile(z, "w") as zipf:
                for _ in range(count):
                    cid = secrets.token_hex(4)
                    token = secrets.token_hex(8)
                    exec_sql(
                        "INSERT INTO customers(card_id,secret_token) VALUES(:c,:t)",
                        {"c": cid, "t": token}
                    )
                    zipf.writestr(f"{cid}.png", generate_qr(f"?id={cid}&t={token}"))
            st.download_button("Download ZIP", z.getvalue(), "cards.zip")

else:
    render_pos()
