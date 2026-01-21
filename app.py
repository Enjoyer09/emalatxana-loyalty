import streamlit as st
import pandas as pd
import os, time, random
import bcrypt
import stripe
import qrcode
from io import BytesIO
from sqlalchemy import text
from PIL import Image, ImageDraw, ImageFont

# =====================================================
# CONFIG
# =====================================================
st.set_page_config("Emalatxana", "☕", layout="centered")

DB_URL = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
STRIPE_KEY = os.environ.get("STRIPE_SECRET")

stripe.api_key = STRIPE_KEY
conn = st.connection("neon", type="sql", url=DB_URL)

# =====================================================
# SECURITY
# =====================================================
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(p: str, h: str) -> bool:
    if h.startswith("$2"):
        return bcrypt.checkpw(p.encode(), h.encode())
    return p == h

ROLE_PERMS = {
    "admin": {"scan", "analytics", "users", "export", "qr", "sync"},
    "staff": {"scan"},
    "manager": {"scan", "analytics", "export"}
}

def can(role, perm):
    return perm in ROLE_PERMS.get(role, set())

# =====================================================
# DB HELPERS
# =====================================================
def q(sql, params=None):
    return conn.query(sql, params=params, ttl=0)

def exec(sql, params=None):
    with conn.session as s:
        s.execute(text(sql), params or {})
        s.commit()

# =====================================================
# QR GENERATOR (CACHED)
# =====================================================
@st.cache_data(show_spinner=False)
def generate_qr(card_id):
    link = f"https://emalatxana-loyalty-production.up.railway.app/?id={card_id}"
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    d = ImageDraw.Draw(img)
    w, h = img.size
    font = ImageFont.load_default()
    box = d.textbbox((0, 0), card_id, font=font)
    bw, bh = box[2]-box[0]+20, box[3]-box[1]+10
    x0, y0 = (w-bw)//2, (h-bh)//2
    d.rectangle([x0, y0, x0+bw, y0+bh], fill="white")
    d.text((x0+10, y0+5), card_id, fill="black", font=font)
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

# =====================================================
# SCAN LOGIC (ATOMIC)
# =====================================================
def process_scan(card_id, staff):
    with conn.session.begin():
        row = conn.session.execute(
            text("SELECT * FROM customers WHERE card_id=:c FOR UPDATE"),
            {"c": card_id}
        ).mappings().fetchone()

        if not row:
            raise Exception("Kart tapılmadı")

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
    return msg

# =====================================================
# OFFLINE MODE
# =====================================================
def save_offline(card_id, staff):
    exec("""
        INSERT INTO offline_scans (card_id, staff_name)
        VALUES (:c, :s)
    """, {"c": card_id, "s": staff})

def sync_offline():
    df = q("SELECT * FROM offline_scans WHERE synced=FALSE")
    for _, r in df.iterrows():
        try:
            process_scan(r["card_id"], r["staff_name"])
            exec("UPDATE offline_scans SET synced=TRUE WHERE id=:i", {"i": r["id"]})
        except:
            pass

# =====================================================
# PAYMENTS
# =====================================================
def create_payment(card_id, amount):
    intent = stripe.PaymentIntent.create(
        amount=int(amount * 100),
        currency="usd",
        metadata={"card_id": card_id}
    )
    exec("""
        INSERT INTO payments (card_id, amount, currency, status, provider)
        VALUES (:c,:a,'usd','pending','stripe')
    """, {"c": card_id, "a": amount})
    return intent.client_secret

# =====================================================
# AUTH UI
# =====================================================
if "logged" not in st.session_state:
    st.session_state.logged = False

if not st.session_state.logged:
    st.title("🔐 Giriş")
    u = st.text_input("İstifadəçi")
    p = st.text_input("Şifrə", type="password")
    if st.button("Daxil ol"):
        df = q("SELECT * FROM users WHERE username=:u", {"u": u})
        if not df.empty and verify_password(p, df.iloc[0]["password"]):
            st.session_state.logged = True
            st.session_state.user = u
            st.session_state.role = df.iloc[0]["role"]
            st.rerun()
        else:
            st.error("Yanlış məlumat")
    st.stop()

# =====================================================
# MAIN APP
# =====================================================
role = st.session_state.role
user = st.session_state.user

st.sidebar.write(f"👤 {user} ({role})")
if st.sidebar.button("Çıxış"):
    st.session_state.logged = False
    st.rerun()

tabs = st.tabs(["📠 Scan", "📊 Analitika", "🧾 Export", "🖨️ QR", "⚙️ Sistem"])

# -----------------------------------------------------
# SCAN
# -----------------------------------------------------
with tabs[0]:
    if can(role, "scan"):
        card = st.text_input("Kart ID")
        if st.button("Scan"):
            try:
                msg = process_scan(card, user)
                st.success(msg)
            except:
                save_offline(card, user)
                st.warning("📴 Offline qeyd edildi")
    else:
        st.warning("İcazə yoxdur")

# -----------------------------------------------------
# ANALYTICS
# -----------------------------------------------------
with tabs[1]:
    if can(role, "analytics"):
        df = q("SELECT action_type, COUNT(*) c FROM logs GROUP BY action_type")
        st.bar_chart(df.set_index("action_type"))
    else:
        st.stop()

# -----------------------------------------------------
# EXPORT
# -----------------------------------------------------
with tabs[2]:
    if can(role, "export"):
        df = q("SELECT * FROM logs ORDER BY created_at DESC")
        csv = df.to_csv(index=False).encode()
        st.download_button("CSV", csv, "logs.csv", "text/csv")

# -----------------------------------------------------
# QR
# -----------------------------------------------------
with tabs[3]:
    if can(role, "qr"):
        cid = st.text_input("Yeni kart ID")
        if st.button("Yarat"):
            exec("""
                INSERT INTO customers (card_id, stars)
                VALUES (:c,0)
            """, {"c": cid})
            st.image(generate_qr(cid), width=250)

# -----------------------------------------------------
# SYSTEM
# -----------------------------------------------------
with tabs[4]:
    if can(role, "sync"):
        if st.button("📴 Offline Sync"):
            sync_offline()
            st.success("Hazır")
