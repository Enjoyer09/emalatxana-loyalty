import streamlit as st
import pandas as pd
import time
import base64
from io import BytesIO
from database import run_query, run_action, get_setting, set_setting, conn
from auth import admin_confirm_dialog
from utils import hash_password, image_to_base64, BONUS_RECIPIENTS, DEFAULT_TERMS, ALLOWED_TABLES

def render_settings_page():
    st.subheader("⚙️ Ayarlar")
    with st.expander("🧾 Çek Dizaynı və Logo", expanded=True):
        st.info("Logonu seçən kimi avtomatik yadda saxlanılır.")
        c1, c2 = st.columns([1, 2])
        with c1:
            lg = st.file_uploader("Logo Yüklə", key="logo_uploader")
            if lg:
                b64 = image_to_base64(lg); curr = get_setting("receipt_logo_base64")
                if b64 != curr: set_setting("receipt_logo_base64", b64); st.success("Yükləndi!"); time.sleep(1); st.rerun()
            curr_logo = get_setting("receipt_logo_base64")
            if curr_logo: st.image(BytesIO(base64.b64decode(curr_logo)), width=100, caption="Cari Logo")
        with c2:
            rn = st.text_input("Mağaza", value=get_setting("receipt_store_name", "Emalatkhana"))
            ra = st.text_input("Ünvan", value=get_setting("receipt_address", "Baku"))
            rh = st.text_input("Başlıq", value=get_setting("receipt_header", "Xoş Gəlmisiniz!"))
            rf = st.text_input("Son", value=get_setting("receipt_footer", "Təşəkkürlər!"))
            if st.button("💾 Yadda Saxla"): 
                set_setting("receipt_store_name", rn); set_setting("receipt_address", ra); set_setting("receipt_header", rh); set_setting("receipt_footer", rf); st.success("OK")

    st.divider(); st.markdown("### 🛠️ Menecer")
    # ... (Qalan kodları bayaqki son admin.py versiyasından kopyala, eynidir)
    # Əgər qısa istəyirsənsə:
    col_mp1, col_mp2, col_mp3, col_mp4 = st.columns(4)
    perm_menu = col_mp1.checkbox("✅ Menyu", value=(get_setting("manager_perm_menu", "FALSE") == "TRUE"))
    if col_mp1.button("Save Menu"): set_setting("manager_perm_menu", "TRUE" if perm_menu else "FALSE"); st.rerun()
    # (Bura qədər yetərlidir, digər funksiyalar: render_database_page, render_logs_page, render_notes_page də mütləq olmalıdır)
    # Sənə tam versiyanı bayaq vermişdim, onu bura qoy.
