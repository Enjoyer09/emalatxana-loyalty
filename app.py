import streamlit as st
import pandas as pd
import os, io, zipfile, secrets
import bcrypt, qrcode
from sqlalchemy import text

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(
    page_title="Emalatxana Coffee POS",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
#MainMenu, header, footer { display:none !important; }
button { font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ======================================================
# DATABASE CONNECTION (RAILWAY SAFE — EXACT PATTERN)
# ======================================================
try:
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
    if not db_url:
        raise ValueError("STREAMLIT_CONNECTIONS_NEON_URL not set")

    if db_url.startswith("postgres://"):
        db_url = db_url.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1
        )

    conn = st.connection("neon", type="sql", url=db_url)

except Exception as e:
    st.error(f"DB Connection Error: {e}")
    st.stop()

# ======================================================
# DB HELPERS
# ======================================================
def q(sql, params=None):
    return conn.query(sql, params=params, ttl=0)

def exec_sql(sql, params=None):
    with conn.session as s:
        s.execute(text(sql), params)
        s.commit()

# ======================================================
# SCHEMA
# ======================================================
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
        type TEXT DEFAULT 'standard',
        email TEXT,
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

# ======================================================
# AUTH HELPERS
# ======================================================
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())

# ======================================================
# BOOTSTRAP ADMIN (CRITICAL)
# ======================================================
admin_check = q("SELECT * FROM users WHERE role='admin'")
if admin_check.empty:
    exec_sql(
        "INSERT INTO users(username,password,role) VALUES(:u,:p,'admin')",
        {
            "u": "admin",
            "p": hash_pw("admin123")
        }
    )

# ======================================================
# SESSION STATE
# ======================================================
for k, v in {
    "logged_in": False,
    "role": None,
    "cart": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ======================================================
# CUSTOMER VIEW (QR)
# ======================================================
params = st.query_params
if "id" in params:
    cid = params["id"]
    token = params.get("t")

    df = q("SELECT * FROM customers WHERE card_id=:c", {"c": cid})
    if df.empty:
        st.error("Invalid card")
        st.stop()

    cust = df.iloc[0]

    if cust["secret_token"] and token != cust["secret_token"]:
        st.error("Unauthorized")
        st.stop()

    st.title("Emalatxana Coffee Loyalty")

    if not cust["is_active"]:
        with st.form("activate"):
            st.text_area("Terms", "10 stars = 1 free coffee", height=120)
            agree = st.checkbox("I Agree")
            email = st.text_input("Email")
            if st.form_submit_button("Activate") and agree:
                exec_sql(
                    "UPDATE customers SET is_active=TRUE,email=:e WHERE card_id=:c",
                    {"e": email, "c": cid}
                )
                st.rerun()

    stars = int(cust["stars"])
    cols = st.columns(10)
    for i in range(10):
        cols[i].write("☕" if i < stars else "⚪")

    if cust["last_feedback_star"] is None:
        with st.form("feedback"):
            r = st.slider("Rating", 1, 5)
            m = st.text_input("Comment")
            if st.form_submit_button("Send"):
                exec_sql(
                    "INSERT INTO feedback(card_id,rating,message) VALUES(:c,:r,:m)",
                    {"c": cid, "r": int(r), "m": m}
                )
                exec_sql(
                    "UPDATE customers SET last_feedback_star=:r WHERE card_id=:c",
                    {"r": int(r), "c": cid}
                )
                st.success("Thanks!")

    qr = qrcode.make(f"?id={cid}&t={cust['secret_token']}")
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    st.download_button("Download QR", buf.getvalue(), f"{cid}.png")

    st.stop()

# ======================================================
# LOGIN
# ======================================================
if not st.session_state.logged_in:
    st.title("Staff / Admin Login")
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

# ======================================================
# POS
# ======================================================
def render_pos():
    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Cart")
        total = 0
        for item in st.session_state.cart:
            st.write(f"{item['item_name']} — {item['price']}₼")
            total += float(item["price"])

        st.metric("Total", f"{total:.2f} ₼")
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
            st.success("Payment successful")
            st.rerun()

    with right:
        st.subheader("Menu")
        menu = q("SELECT * FROM menu WHERE is_active=TRUE")
        cols = st.columns(3)
        for i, m in menu.iterrows():
            if cols[i % 3].button(
                f"{m['item_name']}\n{m['price']}₼",
                key=f"m{m['id']}",
                use_container_width=True
            ):
                st.session_state.cart.append(m.to_dict())
                st.rerun()

# ======================================================
# ADMIN
# ======================================================
if st.session_state.role == "admin":
    tabs = st.tabs(["POS", "Menu", "Users", "QR"])

    with tabs[0]:
        render_pos()

    with tabs[1]:
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
                st.success("Added")

    with tabs[2]:
        with st.form("user"):
            u = st.text_input("Username")
            p = st.text_input("Password")
            r = st.selectbox("Role", ["staff", "admin"])
            if st.form_submit_button("Add"):
                exec_sql(
                    "INSERT INTO users(username,password,role) VALUES(:u,:p,:r)",
                    {"u": u, "p": hash_pw(p), "r": r}
                )
                st.success("User added")

    with tabs[3]:
        count = st.number_input("Cards", 1, 50)
        if st.button("Generate"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for _ in range(count):
                    cid = secrets.token_hex(4)
                    token = secrets.token_hex(8)
                    exec_sql(
                        "INSERT INTO customers(card_id,secret_token) VALUES(:c,:t)",
                        {"c": cid, "t": token}
                    )
                    qr = qrcode.make(f"?id={cid}&t={token}")
                    b = io.BytesIO()
                    qr.save(b, format="PNG")
                    z.writestr(f"{cid}.png", b.getvalue())
            st.download_button("Download ZIP", buf.getvalue(), "cards.zip")

else:
    render_pos()
