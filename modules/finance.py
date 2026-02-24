import streamlit as st
from database import run_query, run_action
from utils import get_baku_now
import pandas as pd

def render_finance_page():
    st.subheader("💰 Maliyyə və Kassa İdarəetməsi")
    st.info("💡 **İzah:** Bu bölmə yalnız kassaya girən və ya çıxan əlavə pulları qeyd etmək üçündür. Satış pulları buraya avtomatik düşür, onlara toxunmağa ehtiyac yoxdur.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style='background: #1e2226; padding: 20px; border-radius: 10px; border: 2px solid #4CAF50;'>
            <h3 style='color: #4CAF50; margin-top:0;'>📥 KASSAYA PUL QOY (Mədaxil)</h3>
            <p style='color: #aaa; font-size: 14px;'>Məsələn: Təsisçi kassaya xırda pul (smen pulu) qoydu və ya kənardan əlavə gəlir gəldi.</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("finance_in_form", clear_on_submit=True):
            amt_in = st.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0)
            cat_in = st.selectbox("Səbəb / Kateqoriya", ["Kassaya Xırda Pul", "Təsisçi İnvestisiyası", "Digər Gəlir"])
            src_in = st.selectbox("Hansı Hesaba?", ["Kassa (Nağd)", "Bank Kartı"])
            desc_in = st.text_input("Əlavə Qeyd (İstəyə bağlı)")
            if st.form_submit_button("✅ Pul Qəbul Et"):
                if amt_in > 0:
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', :c, :a, :s, :d, :u)", 
                               {"c":cat_in, "a":amt_in, "s":src_in, "d":desc_in, "u":st.session_state.user})
                    st.success(f"{amt_in} ₼ mədaxil edildi!")
                    st.rerun()
                else:
                    st.error("Məbləğ sıfırdan böyük olmalıdır.")

    with col2:
        st.markdown("""
        <div style='background: #1e2226; padding: 20px; border-radius: 10px; border: 2px solid #e57373;'>
            <h3 style='color: #e57373; margin-top:0;'>📤 KASSADAN XƏRC ÇIX (Məxaric)</h3>
            <p style='color: #aaa; font-size: 14px;'>Məsələn: İşçiyə avans verildi, obyektin icarəsi ödənildi, su və ya təsərrüfat malı alındı.</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("finance_out_form", clear_on_submit=True):
            amt_out = st.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0)
            cat_out = st.selectbox("Səbəb / Kateqoriya", ["Maaş / Avans", "İcarə Haqqı", "Kommunal (İşıq/Su)", "Təchizat / Mal Alışı", "Təmir", "Vergi", "Digər Xərc"])
            src_out = st.selectbox("Hansı Hesabdan?", ["Kassa (Nağd)", "Bank Kartı"])
            desc_out = st.text_input("Kimin üçün / Nə üçün? (Mütləq yazın)")
            if st.form_submit_button("❌ Xərc Çıx"):
                if amt_out > 0 and desc_out:
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', :c, :a, :s, :d, :u)", 
                               {"c":cat_out, "a":amt_out, "s":src_out, "d":desc_out, "u":st.session_state.user})
                    st.success(f"{amt_out} ₼ məxaric edildi!")
                    st.rerun()
                else:
                    st.error("Məbləğ və Səbəb mütləq doldurulmalıdır!")
                    
    st.divider()
    st.markdown("### 📜 Son Əməliyyatlar (Tarixçə)")
    df = run_query("SELECT created_at as Tarix, type as Növ, category as Kateqoriya, amount as Məbləğ, source as Hesab, description as Qeyd, created_by as İcraçı FROM finance ORDER BY created_at DESC LIMIT 50")
    if not df.empty:
        df['Növ'] = df['Növ'].apply(lambda x: '🟢 Mədaxil' if x == 'in' else '🔴 Məxaric')
        st.dataframe(df, use_container_width=True, hide_index=True)
