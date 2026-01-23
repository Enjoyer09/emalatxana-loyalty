import streamlit as st
import os, time, base64, datetime
import pandas as pd
from io import BytesIO
from sqlalchemy import text
from reportlab.lib.pagesizes import A7
from reportlab.pdfgen import canvas
import requests

# =========================================================
# CONFIG
# =========================================================
APP_NAME = "Emalatxana Coffee"
SENDER_EMAIL = "info@ironwaves.store"
SENDER_NAME = "Emalatxana Coffee"

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DB_URL = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")

# =========================================================
# STREAMLIT
# =========================================================
st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# KIOSK + IDLE RESET
# =========================================================
st.markdown("""
<script>
let idle=0;
setInterval(()=>{
  idle++;
  if(idle>240){window.location.reload();}
},1000);
document.onclick=document.onmousemove=document.onkeydown=()=>{idle=0;}
document.addEventListener("contextmenu",e=>e.preventDefault());
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){e.preventDefault();e.stopPropagation();}
});
</script>
""", unsafe_allow_html=True)

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
.pos{display:grid;grid-template-columns:2fr 1fr;gap:20px}
.products{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
button{min-height:90px;font-size:22px!important;border-radius:18px!important}
.coffee{background:#E8F5E9!important}
.drink{background:#E3F2FD!important}
.dessert{background:#FFF3E0!important}
.receipt{font-family:Courier New;background:#fff;border:2px dashed #999;padding:15px}
.row{display:flex;justify-content:space-between}
</style>
""", unsafe_allow_html=True)

# =========================================================
# DATABASE
# =========================================================
conn = st.connection("neon", type="sql", url=DB_URL)

def q(sql, params=None):
    return conn.query(sql, params=params, ttl=0)

def exec(sql, params=None):
    with conn.session as s:
        s.execute(text(sql), params)
        s.commit()

# =========================================================
# PDF RECEIPT
# =========================================================
def generate_pdf(cart, total):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A7)
    y = 190
    c.setFont("Courier", 10)
    c.drawCentredString(100, y, APP_NAME); y-=15
    c.drawCentredString(100, y, "QƏBZ"); y-=20
    for i in cart:
        c.drawString(10, y, f"{i['name']} x{i['qty']}")
        c.drawRightString(190, y, f"{i['price']*i['qty']:.2f} ₼")
        y-=12
    y-=10
    c.drawString(10, y, f"YEKUN: {total:.2f} ₼")
    c.showPage(); c.save()
    buf.seek(0)
    return buf

# =========================================================
# EMAIL (RESEND)
# =========================================================
def send_receipt(email, pdf_bytes):
    if not email or not RESEND_API_KEY:
        return
    payload = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [email],
        "subject": "🧾 Sizin qəbziniz",
        "html": "<p>Alışınız üçün təşəkkür edirik ☕</p>",
        "attachments": [{
            "filename": "receipt.pdf",
            "content": base64.b64encode(pdf_bytes).decode()
        }]
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    requests.post("https://api.resend.com/emails", json=payload, headers=headers)

# =========================================================
# STATE
# =========================================================
if "cart" not in st.session_state:
    st.session_state.cart = []

def add_to_cart(item):
    for c in st.session_state.cart:
        if c["id"] == item["id"]:
            c["qty"] += 1
            return
    st.session_state.cart.append({
        "id": item["id"],
        "name": item["item_name"],
        "price": float(item["price"]),
        "qty": 1,
        "is_coffee": item["is_coffee"]
    })

# =========================================================
# UI
# =========================================================
st.markdown("<div class='pos'>", unsafe_allow_html=True)

# ================= PRODUCTS =================
with st.container():
    st.markdown("### ☕ Məhsullar")
    st.markdown("<div class='products'>", unsafe_allow_html=True)

    menu = q("SELECT * FROM menu WHERE is_active=TRUE ORDER BY category, item_name")

    for _, m in menu.iterrows():
        cls = "coffee" if m["category"]=="Qəhvə" else "drink" if m["category"]=="İçkilər" else "dessert"
        if st.button(f"{m['item_name']}\n{m['price']} ₼", key=m["id"], use_container_width=True):
            add_to_cart(m)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ================= RECEIPT =================
with st.container():
    st.markdown("<div class='receipt'>", unsafe_allow_html=True)
    st.markdown(f"<b>{APP_NAME}</b>", unsafe_allow_html=True)

    total = 0
    coffee_count = 0

    for i, item in enumerate(st.session_state.cart):
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        c1.write(f"{item['name']} ({item['qty']})")
        c2.write(f"{item['price']*item['qty']:.2f}")
        if c3.button("➖", key=f"m{i}"):
            item["qty"]-=1
            if item["qty"]<=0: st.session_state.cart.pop(i)
            st.rerun()
        if c4.button("➕", key=f"p{i}"):
            item["qty"]+=1
            st.rerun()

        total += item["price"]*item["qty"]
        if item["is_coffee"]:
            coffee_count += item["qty"]

    st.markdown(f"<hr><b>YEKUN: {total:.2f} ₼</b>", unsafe_allow_html=True)

    email = st.text_input("📧 Qəbz üçün Email (istəyə görə)")

    if st.button("✅ SATIŞI TAMAMLA", use_container_width=True):
        exec(
            "INSERT INTO sales (items,total,payment_method,created_at) VALUES (:i,:t,'POS',NOW())",
            {"i":", ".join([c["name"] for c in st.session_state.cart]), "t": total}
        )

        pdf = generate_pdf(st.session_state.cart, total)
        send_receipt(email, pdf.getvalue())

        st.session_state.cart = []
        st.success("Satış tamamlandı")
        time.sleep(1)
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
