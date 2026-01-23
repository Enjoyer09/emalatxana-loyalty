# =========================================================
# EMALATXANA POS & LOYALTY SYSTEM v2.0 (STABLE)
# UX + AUTOMATION + KIOSK EDITION
# =========================================================

import streamlit as st
import pandas as pd
import random, os, time, base64, datetime, secrets, threading
import bcrypt, requests, qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import text
from reportlab.lib.pagesizes import A7
from reportlab.pdfgen import canvas

# =========================================================
# INFRASTRUCTURE
# =========================================================
DB_URL = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store"
APP_URL = f"https://{DOMAIN}"
SENDER_EMAIL = "info@ironwaves.store"

# =========================================================
# STREAMLIT
# =========================================================
st.set_page_config(
    page_title="Emalatxana Coffee",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# KIOSK + IDLE RESET
# =========================================================
st.markdown("""
<script>
let idle=0;
setInterval(()=>{ idle++; if(idle>240){location.reload();}},1000);
document.onclick=document.onmousemove=document.onkeydown=()=>{idle=0};
document.addEventListener("contextmenu",e=>e.preventDefault());
document.addEventListener("keydown",e=>{
 if(e.key==="Escape"){e.preventDefault();e.stopPropagation();}
});
</script>
""", unsafe_allow_html=True)

# =========================================================
# CSS – REAL POS UI
# =========================================================
st.markdown("""
<style>
#MainMenu, header, footer {display:none}
.pos{display:grid;grid-template-columns:2fr 1fr;gap:20px}
.products{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:900px){.products{grid-template-columns:repeat(2,1fr)}}

.pos-card{
 position:relative;border-radius:22px;padding:18px 10px 14px;
 text-align:center;font-weight:700;cursor:pointer;
 box-shadow:0 6px 0 rgba(0,0,0,.15);
}
.pos-card:active{transform:translateY(6px);box-shadow:none}

.coffee{background:#E8F5E9;color:#1B5E20}
.drink{background:#E3F2FD;color:#0D47A1}
.dessert{background:#FFF3E0;color:#E65100}

.pos-icon{font-size:34px;margin-bottom:6px}
.pos-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pos-price{font-size:16px;margin-top:4px}

.qty-badge{
 position:absolute;top:8px;right:8px;
 background:#D32F2F;color:#fff;
 min-width:28px;height:28px;
 border-radius:999px;
 display:flex;align-items:center;justify-content:center;
}

.receipt{
 font-family:Courier New;background:#fff;
 border:2px dashed #999;padding:15px
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# DB CONNECTION
# =========================================================
conn = st.connection("neon", type="sql", url=DB_URL)

def q(sql, p=None):
    return conn.query(sql, params=p, ttl=0)

def exec_sql(sql, p=None):
    with conn.session as s:
        s.execute(text(sql), p)
        s.commit()

# =========================================================
# STATE
# =========================================================
if "cart" not in st.session_state:
    st.session_state.cart = []
if "current_customer" not in st.session_state:
    st.session_state.current_customer = None

# =========================================================
# HELPERS
# =========================================================
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

def get_qty(pid):
    for c in st.session_state.cart:
        if c["id"] == pid:
            return c["qty"]
    return 0

def best_coupon(cart, coupons):
    # avtomatik ən sərfəli kupon
    if not coupons: return None
    types = [c["coupon_type"] for c in coupons]
    if "birthday_gift" in types: return "birthday_gift"
    if "free_cookie" in types: return "free_cookie"
    if "50_percent" in types: return "50_percent"
    return None

def generate_pdf(cart, total):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A7)
    y = 190
    c.setFont("Courier", 10)
    c.drawCentredString(100, y, "EMALATXANA COFFEE"); y-=20
    for i in cart:
        c.drawString(10, y, f"{i['name']} x{i['qty']}")
        c.drawRightString(190, y, f"{i['price']*i['qty']:.2f} ₼")
        y-=12
    y-=10
    c.drawString(10, y, f"YEKUN: {total:.2f} ₼")
    c.showPage(); c.save()
    buf.seek(0)
    return buf

def send_email(email, pdf):
    if not email or not RESEND_API_KEY: return
    requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": f"Emalatxana Coffee <{SENDER_EMAIL}>",
            "to": [email],
            "subject": "🧾 Qəbziniz",
            "html": "<p>Alış üçün təşəkkür edirik ☕</p>",
            "attachments": [{
                "filename": "receipt.pdf",
                "content": base64.b64encode(pdf).decode()
            }]
        }
    )

# =========================================================
# ICONS
# =========================================================
EMOJI = {"Qəhvə":"☕","İçkilər":"🥤","Desert":"🍰"}

# =========================================================
# UI
# =========================================================
st.markdown("<div class='pos'>", unsafe_allow_html=True)

# ================= PRODUCTS =================
with st.container():
    st.markdown("### Məhsullar")
    st.markdown("<div class='products'>", unsafe_allow_html=True)

    menu = q("SELECT * FROM menu WHERE is_active=TRUE ORDER BY category,item_name")

    for _, m in menu.iterrows():
        cls = "coffee" if m["category"]=="Qəhvə" else "drink" if m["category"]=="İçkilər" else "dessert"
        qty = get_qty(m["id"])
        badge = f"<div class='qty-badge'>{qty}</div>" if qty>0 else ""

        st.markdown(f"""
        <div class="pos-card {cls}">
          {badge}
          <div class="pos-icon">{EMOJI.get(m['category'])}</div>
          <div class="pos-name">{m['item_name']}</div>
          <div class="pos-price">{m['price']} ₼</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(" ", key=f"add_{m['id']}", use_container_width=True):
            add_to_cart(m); st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ================= RECEIPT =================
with st.container():
    st.markdown("<div class='receipt'>", unsafe_allow_html=True)
    st.markdown("**EMALATXANA COFFEE**")

    total, coffee_count = 0, 0
    for i, item in enumerate(st.session_state.cart):
        c1,c2,c3,c4 = st.columns([3,1,1,1])
        c1.write(f"{item['name']} ({item['qty']})")
        c2.write(f"{item['price']*item['qty']:.2f}")
        if c3.button("➖", key=f"m{i}"):
            item["qty"]-=1
            if item["qty"]<=0: st.session_state.cart.pop(i)
            st.rerun()
        if c4.button("➕", key=f"p{i}"):
            item["qty"]+=1; st.rerun()
        total += item["price"]*item["qty"]
        if item["is_coffee"]: coffee_count += item["qty"]

    st.markdown(f"<hr><b>YEKUN: {total:.2f} ₼</b>", unsafe_allow_html=True)

    email = st.text_input("📧 Qəbz üçün email (istəyə görə)")

    if st.button("✅ SATIŞI TAMAMLA", use_container_width=True):
        exec_sql(
            "INSERT INTO sales (items,total,payment_method,created_at) VALUES (:i,:t,'POS',NOW())",
            {"i":", ".join([c['name'] for c in st.session_state.cart]), "t": total}
        )
        pdf = generate_pdf(st.session_state.cart, total)
        send_email(email, pdf.getvalue())
        st.session_state.cart = []
        st.success("Satış tamamlandı")
        time.sleep(1); st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
