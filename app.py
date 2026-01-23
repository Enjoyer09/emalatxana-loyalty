# =========================================================
# EMALATXANA POS & LOYALTY SYSTEM — FINAL STABLE
# =========================================================

import streamlit as st
import pandas as pd
import random, os, time, base64, datetime, secrets
import bcrypt, requests, qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import text
from reportlab.lib.pagesizes import A7
from reportlab.pdfgen import canvas

# ================= CONFIG =================
DB_URL = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DOMAIN = "emalatxana.ironwaves.store"
APP_URL = f"https://{DOMAIN}"
SHOP_NAME = "Emalatxana Coffee"
SENDER_EMAIL = "info@ironwaves.store"

# ================= STREAMLIT =================
st.set_page_config("Emalatxana POS", "☕", layout="wide", initial_sidebar_state="collapsed")

# ================= KIOSK =================
st.markdown("""
<script>
let idle=0;
setInterval(()=>{idle++; if(idle>300){location.reload();}},1000);
document.onclick=document.onmousemove=document.onkeydown=()=>{idle=0};
document.addEventListener("keydown",e=>{if(e.key==="Escape"){e.preventDefault();}});
</script>
""", unsafe_allow_html=True)

# ================= CSS =================
st.markdown("""
<style>
#MainMenu,header,footer{display:none}
.pos{display:grid;grid-template-columns:2fr 1fr;gap:20px}
.products{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:900px){.products{grid-template-columns:repeat(2,1fr)}}

.pos-card{
 position:relative;border-radius:18px;padding:16px 10px;
 text-align:center;font-weight:700;cursor:pointer;
 background:#fff;box-shadow:0 6px 0 rgba(0,0,0,.15)
}
.pos-card:active{transform:translateY(6px);box-shadow:none}
.pos-icon{font-size:32px}
.pos-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pos-price{font-size:16px}

.qty-badge{
 position:absolute;top:6px;right:6px;
 background:#D32F2F;color:#fff;
 min-width:26px;height:26px;border-radius:999px;
 display:flex;align-items:center;justify-content:center
}

.receipt{font-family:Courier New;background:#fff;border:2px dashed #999;padding:15px}

.progress-ring{
 width:160px;height:160px;border-radius:50%;
 background:conic-gradient(#2E7D32 calc(var(--p)*1%),#E0E0E0 0);
 display:flex;align-items:center;justify-content:center;margin:auto
}
.progress-inner{
 width:120px;height:120px;background:#fff;border-radius:50%;
 display:flex;flex-direction:column;align-items:center;justify-content:center
}
.free-coffee{
 background:#E8F5E9;border:3px solid #2E7D32;border-radius:20px;
 padding:20px;text-align:center;font-size:22px
}
</style>
""", unsafe_allow_html=True)

# ================= DB =================
conn = st.connection("neon", type="sql", url=DB_URL)
def q(sql,p=None): return conn.query(sql,params=p,ttl=0)
def exec_sql(sql,p=None):
    with conn.session as s: s.execute(text(sql),p); s.commit()

# ================= STATE =================
if "cart" not in st.session_state: st.session_state.cart=[]
if "logged_in" not in st.session_state: st.session_state.logged_in=False
if "role" not in st.session_state: st.session_state.role=None

# ================= HELPERS =================
def verify(p,h): return bcrypt.checkpw(p.encode(),h.encode())
def add_to_cart(item):
    for c in st.session_state.cart:
        if c["id"]==item["id"]:
            c["qty"]+=1; return
    st.session_state.cart.append({
        "id":item["id"],"name":item["item_name"],
        "price":float(item["price"]),"qty":1,
        "is_coffee":item["is_coffee"]
    })

def generate_pdf(cart,total):
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A7); y=190
    c.setFont("Courier",10)
    c.drawCentredString(100,y,SHOP_NAME); y-=20
    for i in cart:
        c.drawString(10,y,f"{i['name']} x{i['qty']}")
        c.drawRightString(190,y,f"{i['price']*i['qty']:.2f} ₼"); y-=12
    y-=10; c.drawString(10,y,f"YEKUN: {total:.2f} ₼")
    c.showPage(); c.save(); buf.seek(0); return buf

def send_email(to,pdf):
    if not to or not RESEND_API_KEY: return
    requests.post("https://api.resend.com/emails",
        headers={"Authorization":f"Bearer {RESEND_API_KEY}","Content-Type":"application/json"},
        json={
          "from":f"{SHOP_NAME} <{SENDER_EMAIL}>",
          "to":[to],"subject":"🧾 Qəbziniz",
          "html":"<p>Təşəkkür edirik ☕</p>",
          "attachments":[{"filename":"receipt.pdf","content":base64.b64encode(pdf).decode()}]
        })

# ================= CUSTOMER =================
qp = st.query_params
if "id" in qp:
    cid=qp["id"]
    df=q("SELECT * FROM customers WHERE card_id=:i",{"i":cid})
    if df.empty: st.error("Kart tapılmadı"); st.stop()
    u=df.iloc[0]; stars=u["stars"]; goal=9; pct=int(stars/goal*100)
    st.markdown(f"## {SHOP_NAME} Loyalty")
    if stars>=goal:
        st.markdown("<div class='free-coffee'>🎉 BU KOFE BİZDƏN ☕</div>",unsafe_allow_html=True)
        st.balloons()
    else:
        st.markdown(f"""
        <div class="progress-ring" style="--p:{pct}">
          <div class="progress-inner">
            <div style="font-size:32px">{stars}/{goal}</div>
            <div>{goal-stars} qaldı ☕</div>
          </div>
        </div>
        """,unsafe_allow_html=True)
    st.stop()

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.markdown("## Giriş")
    with st.form("login"):
        u=st.text_input("User"); p=st.text_input("Pass",type="password")
        if st.form_submit_button("GİR"):
            df=q("SELECT * FROM users WHERE username=:u",{"u":u})
            if not df.empty and verify(p,df.iloc[0]["password"]):
                st.session_state.logged_in=True
                st.session_state.role=df.iloc[0]["role"]
                st.rerun()
            else: st.error("Səhv")
    st.stop()

# ================= POS =================
st.markdown("<div class='pos'>",unsafe_allow_html=True)

with st.container():
    st.markdown("### Məhsullar")
    st.markdown("<div class='products'>",unsafe_allow_html=True)
    menu=q("SELECT * FROM menu WHERE is_active=TRUE")
    EMOJI={"Qəhvə":"☕","İçkilər":"🥤","Desert":"🍰"}
    for _,m in menu.iterrows():
        qty=sum(c["qty"] for c in st.session_state.cart if c["id"]==m["id"])
        badge=f"<div class='qty-badge'>{qty}</div>" if qty>0 else ""
        st.markdown(f"""
        <div class="pos-card">
          {badge}
          <div class="pos-icon">{EMOJI.get(m['category'])}</div>
          <div class="pos-name">{m['item_name']}</div>
          <div class="pos-price">{m['price']} ₼</div>
        </div>
        """,unsafe_allow_html=True)
        if st.button(" ",key=f"a{m['id']}"):
            add_to_cart(m); st.rerun()
    st.markdown("</div>",unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='receipt'>",unsafe_allow_html=True)
    total=0
    for i,it in enumerate(st.session_state.cart):
        c1,c2,c3,c4=st.columns([3,1,1,1])
        c1.write(f"{it['name']} ({it['qty']})")
        c2.write(f"{it['price']*it['qty']:.2f}")
        if c3.button("➖",key=f"m{i}"):
            it["qty"]-=1
            if it["qty"]<=0: st.session_state.cart.pop(i)
            st.rerun()
        if c4.button("➕",key=f"p{i}"):
            it["qty"]+=1; st.rerun()
        total+=it["price"]*it["qty"]
    st.markdown(f"### YEKUN: {total:.2f} ₼")
    email=st.text_input("📧 Email (istəyə görə)")
    if st.button("SATIŞI TAMAMLA"):
        exec_sql("INSERT INTO sales(items,total,payment_method) VALUES(:i,:t,'POS')",
                 {"i":",".join([c["name"] for c in st.session_state.cart]),"t":total})
        pdf=generate_pdf(st.session_state.cart,total)
        send_email(email,pdf.getvalue())
        st.session_state.cart=[]
        st.success("Uğurlu!"); time.sleep(1); st.rerun()
    st.markdown("</div>",unsafe_allow_html=True)

st.markdown("</div>",unsafe_allow_html=True)
