import streamlit as st
import pandas as pd
import random
import qrcode
from io import BytesIO
import zipfile
from PIL import Image, ImageDraw, ImageFont
import time
from sqlalchemy import text
import os
import bcrypt

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Emalatxana",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =====================================================
# DATABASE CONNECTION
# =====================================================
db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
if not db_url:
    st.error("Database URL tapılmadı")
    st.stop()

db_url = db_url.strip().strip('"').strip("'")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

conn = st.connection("neon", type="sql", url=db_url)

# =====================================================
# SCHEMA (SAFE)
# =====================================================
def ensure_schema():
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                card_id TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        s.commit()

ensure_schema()

# =====================================================
# SECURITY
# =====================================================
def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(p, h):
    if h.startswith("$2"):
        return bcrypt.checkpw(p.encode(), h.encode())
    return p == h

# =====================================================
# DB HELPERS
# =====================================================
def run_query(sql, params=None):
    try:
        return conn.query(sql, params=params, ttl=0)
    except:
        return pd.DataFrame()

def run_action(sql, params=None):
    try:
        with conn.session as s:
            s.execute(text(sql), params or {})
            s.commit()
        return True
    except:
        return False

# =====================================================
# QR (CACHED / OFFLINE)
# =====================================================
@st.cache_data(show_spinner=False)
def generate_qr(card_id):
    link = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    w, h = img.size
    box = draw.textbbox((0, 0), card_id, font=font)
    bw, bh = box[2] - box[0] + 20, box[3] - box[1] + 10
    x0, y0 = (w - bw) // 2, (h - bh) // 2
    draw.rectangle([x0, y0, x0 + bw, y0 + bh], fill="white")
    draw.text((x0 + 10, y0 + 5), card_id, fill="black", font=font)

    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

# =====================================================
# SCAN LOGIC (ATOMIC)
# =====================================================
def process_scan():
    card_id = st.session_state.scanner_input
    staff = st.session_state.get("current_user", "staff")

    if not card_id:
        return

    try:
        with conn.session.begin():
            row = conn.session.execute(
                text("SELECT * FROM customers WHERE card_id=:c FOR UPDATE"),
                {"c": card_id}
            ).mappings().fetchone()

            if not row:
                st.error("Kart tapılmadı")
                return

            stars = row["stars"] + 1
            action = "Star Added"
            msg = f"⭐ {stars}/10"

            if stars >= 10:
                stars = 0
                action = "Free Coffee"
                msg = "🎁 PULSUZ KOFE!"

            conn.session.execute(
                text("""
                    UPDATE customers
                    SET stars=:s, last_visit=NOW()
                    WHERE card_id=:c
                """),
                {"s": stars, "c": card_id}
            )

            conn.session.execute(
                text("""
                    INSERT INTO logs (staff_name, card_id, action_type)
                    VALUES (:u, :c, :a)
                """),
                {"u": staff, "c": card_id, "a": action}
            )

        st.session_state["last_result"] = {"msg": msg}

    except Exception as e:
        st.error(f"Sistem xətası: {e}")

    st.session_state.scanner_input = ""

# =====================================================
# ROUTING
# =====================================================
query = st.query_params

# =====================================================
# CUSTOMER VIEW
# =====================================================
if "id" in query:
    cid = query["id"]

    st.image("emalatxana.png", width=150)

    notes = run_query("""
        SELECT * FROM notifications
        WHERE card_id=:c AND is_read=FALSE
        ORDER BY created_at DESC
    """, {"c": cid})

    for _, n in notes.iterrows():
        st.info(n["message"])
        run_action("UPDATE notifications SET is_read=TRUE WHERE id=:i", {"i": n["id"]})

    df = run_query("SELECT * FROM customers WHERE card_id=:c", {"c": cid})
    if df.empty:
        st.error("Kart tapılmadı")
        st.stop()

    stars = int(df.iloc[0]["stars"])

    st.markdown(f"### ⭐ {stars}/10")
    st.progress(stars / 10)

    st.download_button(
        "📥 Kartı Yüklə",
        generate_qr(cid),
        f"{cid}.png",
        "image/png",
        use_container_width=True
    )

    st.stop()

# =====================================================
# LOGIN
# =====================================================
if "logged" not in st.session_state:
    st.session_state.logged = False

if not st.session_state.logged:
    st.image("emalatxana.png", width=150)
    u = st.text_input("İstifadəçi")
    p = st.text_input("Şifrə", type="password")

    if st.button("Daxil ol"):
        df = run_query("SELECT * FROM users WHERE username=:u", {"u": u})
        if not df.empty and verify_password(p, df.iloc[0]["password"]):
            st.session_state.logged = True
            st.session_state.current_user = u
            st.session_state.role = df.iloc[0]["role"]
            st.rerun()
        else:
            st.error("Yanlış məlumat")

    st.stop()

# =====================================================
# ADMIN / STAFF PANEL
# =====================================================
st.sidebar.write(f"👤 {st.session_state.current_user}")
if st.sidebar.button("Çıxış"):
    st.session_state.logged = False
    st.rerun()

tabs = st.tabs(["📠 Terminal", "📊 Analitika", "📋 Menyu", "🔔 Bildiriş", "🖨️ QR"])

# ---------------- TERMINAL ----------------
with tabs[0]:
    st.text_input("Barkod", key="scanner_input", on_change=process_scan)
    if "last_result" in st.session_state:
        st.success(st.session_state["last_result"]["msg"])

# ---------------- ANALYTICS ----------------
with tabs[1]:
    df = run_query("""
        SELECT action_type, COUNT(*) c
        FROM logs GROUP BY action_type
    """)
    if not df.empty:
        st.bar_chart(df.set_index("action_type"))

# ---------------- MENU ----------------
with tabs[2]:
    with st.form("menu"):
        n = st.text_input("Ad")
        p = st.text_input("Qiymət")
        if st.form_submit_button("Əlavə et"):
            run_action(
                "INSERT INTO menu (item_name, price) VALUES (:n,:p)",
                {"n": n, "p": p}
            )
            st.rerun()

# ---------------- NOTIFICATION ----------------
with tabs[3]:
    with st.form("notify"):
        cid = st.text_input("Kart ID")
        msg = st.text_area("Mesaj")
        if st.form_submit_button("Göndər"):
            run_action(
                "INSERT INTO notifications (card_id, message) VALUES (:c,:m)",
                {"c": cid, "m": msg}
            )
            st.success("Göndərildi")

# ---------------- QR ----------------
with tabs[4]:
    if st.button("Yeni Kart"):
        cid = str(random.randint(10000000, 99999999))
        run_action(
            "INSERT INTO customers (card_id, stars) VALUES (:c,0)",
            {"c": cid}
        )
        st.image(generate_qr(cid), width=250)
