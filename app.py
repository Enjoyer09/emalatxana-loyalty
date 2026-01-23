# =========================================================
# EMALATXANA POS & LOYALTY SYSTEM — FINAL CLEAN VERSION
# =========================================================

import streamlit as st
import pandas as pd
import os, time, base64, datetime
import bcrypt, requests
from sqlalchemy import text
from io import BytesIO
from reportlab.lib.pagesizes import A7
from reportlab.pdfgen import canvas

# ================= CONFIG =================
DB_URL = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SHOP_NAME = "Emalatxana Coffee"
SENDER_EMAIL = "info@ironwaves.store"

# ================= STREAMLIT =================
st.set_page_config("Emalatxana POS", "☕", layout="wide", initial_sidebar_state="collapsed")

# ================= CSS =================
st.markdown("""
<style>
#MainMenu,header,footer{display:none}
.center{max-width:420px;margin:40px auto;text-align:center}
.card{
 background:white;border-radius:20px;padding:24px;
 box-shadow:0 10px 30px rgba(0,0,0,.1)
}
.progress{
 width:180px;height:180px;border-radius:50%;
 background:conic-gradient(#2E7D32 calc(var(--p)*1%),#E0E0E0 0);
 display:flex;align-items:center;justify-content:center;margin:20px auto
}
.progress-inner{
 width:130px;height:130px;background:#fff;border-radius:50%;
 display:flex;flex-direction:column;align-items:center;justify-content:center
}
.free{
 background:#E8F5E9;border:3px solid #2E7D32;
 border-radius:18px;padding:20px;font-size:22px
}
.pin-wrap{max-width:360px;margin:60px auto;text-align:center}
.pin-dots{display:flex;justify-content:center;gap:14px;margin-bottom:20px}
.pin-dot{width:18px;height:18px;border-radius:50%;background:#ccc}
.pin-dot.active{background:#2E7D32}
.keypad{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.keypad button{
 height:70px;font-size:24px;font-weight:bold;
 border-radius:16px;border:none;background:#F5F5F5
}
.keypad button:active{background:#E0E0E0}
</style>
""", unsafe_allow_html=True)

# ================= DB =================
conn = st.connection("neon", type="sql", url=DB_URL)
def q(sql,p=None): return conn.query(sql,params=p,ttl=0)
def exec_sql(sql,p=None):
    with conn.session as s: s.execute(text(sql),p); s.commit()

# ================= STATE =================
if "logged_in" not in st.session_state: st.session_state.logged_in=False
if "role" not in st.session_state: st.session_state.role=None
if "pin_input" not in st.session_state: st.session_state.pin_input=""
if "cart" not in st.session_state: st.session_state.cart=[]

# =========================================================
# CUSTOMER SCREEN (REDESIGNED)
# =========================================================
qp = st.query_params
if "id" in qp:
    cid = qp["id"]
    df = q("SELECT * FROM customers WHERE card_id=:i",{"i":cid})
    if df.empty:
        st.error("Kart tapılmadı")
        st.stop()

    u = df.iloc[0]
    stars = u["stars"]
    goal = 9
    pct = int((stars/goal)*100)

    st.markdown("<div class='center'>", unsafe_allow_html=True)
    st.markdown(f"<h2>{SHOP_NAME} Loyalty</h2>", unsafe_allow_html=True)

    if stars >= goal:
        st.markdown("<div class='card free'>🎉 BU KOFE BİZDƏN ☕<br><small>Sadiqliyiniz üçün təşəkkürlər</small></div>", unsafe_allow_html=True)
        st.balloons()
    else:
        st.markdown(f"""
        <div class="card">
          <div class="progress" style="--p:{pct}">
            <div class="progress-inner">
              <div style="font-size:36px">{stars}/{goal}</div>
              <div style="color:#777">{goal-stars} qaldı ☕</div>
            </div>
          </div>
          <p style="color:#555">Hər kofe səni hədiyyəyə yaxınlaşdırır</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# =========================================================
# PIN LOGIN (STAFF)
# =========================================================
if not st.session_state.logged_in:
    st.markdown("<div class='pin-wrap'>", unsafe_allow_html=True)
    st.markdown("<h2>🔢 Kassir Girişi</h2>", unsafe_allow_html=True)

    dots=""
    for i in range(4):
        cls="pin-dot active" if i<len(st.session_state.pin_input) else "pin-dot"
        dots+=f"<div class='{cls}'></div>"
    st.markdown(f"<div class='pin-dots'>{dots}</div>", unsafe_allow_html=True)

    st.markdown("<div class='keypad'>", unsafe_allow_html=True)

    def press(k):
        if k=="⌫":
            st.session_state.pin_input=st.session_state.pin_input[:-1]
        elif k=="OK":
            if len(st.session_state.pin_input)==4:
                users=q("SELECT * FROM users WHERE role='staff' AND pin IS NOT NULL")
                for _,u in users.iterrows():
                    if bcrypt.checkpw(st.session_state.pin_input.encode(),u["pin"].encode()):
                        st.session_state.logged_in=True
                        st.session_state.role="staff"
                        st.session_state.pin_input=""
                        st.rerun()
                st.session_state.pin_input=""
                st.error("Yanlış PIN")
        else:
            if len(st.session_state.pin_input)<4:
                st.session_state.pin_input+=k

    for k in ["1","2","3","4","5","6","7","8","9","⌫","0","OK"]:
        if st.button(k, key=f"pin{k}"):
            press(k)

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# =========================================================
# POS (minimal, işlək)
# =========================================================
st.success("POS aktivdir – kassir daxil oldu ✔")
