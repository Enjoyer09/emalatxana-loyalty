import streamlit as st
import pandas as pd
from database import run_query, run_action

def render_finance_page():
    st.subheader("💰 Maliyyə və Xərclərin İdarəedilməsi")
    
    # Üç əsas bölmə yaradırıq
    t1, t2, t3 = st.tabs(["💸 Məxaric (Xərc / Çıxarış)", "💵 Mədaxil (Kassaya Pul Qoyuluşu)", "📋 Maliyyə Tarixçəsi"])
    
    # ==========================================
    # 1. MƏXARİC (KASSADAN VƏ YA KARTDAN ÇIXAN PUL)
    # ==========================================
    with t1:
        st.markdown("### 💸 Yeni Xərc və ya Çıxarış")
        with st.form("expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                category = st.selectbox("Xərcin Kateqoriyası", [
                    "Maaş / Avans", 
                    "Kommunal", 
                    "Təchizat / Xammal", 
                    "İcarə", 
                    "Təmir / İnventar", 
                    "Vergi / Rüsum", 
                    "İnkassasiya (Növbə Bağlanışı)", 
                    "Digər"
                ])
                amount = st.number_input("Məbləğ (₼)", min_value=0.01, step=0.5, format="%.2f")
            
            with c2:
                # SƏN İSTƏYƏN "BANK KARTI" BURADADIR
                source = st.selectbox("Mənbə (Pul hardan çıxır?)", [
                    "Kassa", 
                    "Bank Kartı", 
                    "Şəxsi Cib", 
                    "Təsisçi", 
                    "Digər"
                ])
                description = st.text_input("Açıqlama (Məsələn: Ay işçisinə avans)")
                
            submit_expense = st.form_submit_button("Xərci Təsdiqlə", type="primary", use_container_width=True)
            
            if submit_expense:
                if amount > 0:
                    run_action("""
                        INSERT INTO finance (type, category, amount, source, description, created_by) 
                        VALUES ('out', :c, :a, :s, :d, :u)
                    """, {
                        "c": category, "a": float(amount), "s": source, "d": description, "u": str(st.session_state.user)
                    })
                    st.success(f"✅ {amount} ₼ məbləğində xərc uğurla qeydə alındı!")
                    st.rerun()
                else:
                    st.warning("Məbləğ 0-dan böyük olmalıdır.")

    # ==========================================
    # 2. MƏDAXİL (KASSAYA XIRDA PUL QOYULUŞU)
    # ==========================================
    with t2:
        st.markdown("### 💵 Yeni Mədaxil (Kassaya və ya Karta Pul Mədaxili)")
        st.info("💡 Məsələn: Səhər kassaya xırda pul kimi 100 AZN qoyursunuzsa, buradan qeyd edin.")
        
        with st.form("income_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                category_in = st.selectbox("Mədaxil Kateqoriyası", [
                    "Kassaya Xırda Pul Qoyuluşu", 
                    "Təsisçi İnvestisiyası", 
                    "Sponsorluq / Reklam", 
                    "Digər Mədaxil"
                ])
                amount_in = st.number_input("Məbləğ (₼)", min_value=0.01, step=0.5, format="%.2f", key="inc_amount")
            
            with c2:
                # SƏN İSTƏYƏN "BANK KARTI" BURADADIR
                source_in = st.selectbox("Hədəf (Pul hara daxil olur?)", [
                    "Kassa", 
                    "Bank Kartı", 
                    "Digər"
                ])
                description_in = st.text_input("Açıqlama", placeholder="Məsələn: Səhər kassası üçün 100 AZN xırda")
                
            submit_income = st.form_submit_button("Mədaxili Təsdiqlə", type="primary", use_container_width=True)
            
            if submit_income:
                if amount_in > 0:
                    run_action("""
                        INSERT INTO finance (type, category, amount, source, description, created_by) 
                        VALUES ('in', :c, :a, :s, :d, :u)
                    """, {
                        "c": category_in, "a": float(amount_in), "s": source_in, "d": description_in, "u": str(st.session_state.user)
                    })
                    st.success(f"✅ {amount_in} ₼ məbləğində mədaxil uğurla qeydə alındı!")
                    st.rerun()
                else:
                    st.warning("Məbləğ 0-dan böyük olmalıdır.")

    # ==========================================
    # 3. MALİYYƏ TARİXÇƏSİ
    # ==========================================
    with t3:
        st.markdown("### 📋 Son Əməliyyatlar")
        df_finance = run_query("SELECT id, type, category, amount, source, description, created_by, created_at FROM finance ORDER BY created_at DESC LIMIT 100")
        
        if not df_finance.empty:
            # Type sütununu Azərbaycan dilinə tərcümə edək ki, cədvəldə qəşəng görünsün
            df_finance['type'] = df_finance['type'].apply(lambda x: "🟢 MƏDAXİL" if x == 'in' else "🔴 MƏXARİC")
            df_finance['created_at'] = pd.to_datetime(df_finance['created_at']).dt.strftime('%d/%m/%Y %H:%M')
            
            # Sütun adlarını səliqəyə salaq
            df_finance = df_finance.rename(columns={
                "id": "ID",
                "type": "Növ",
                "category": "Kateqoriya",
                "amount": "Məbləğ (₼)",
                "source": "Mənbə / Hədəf",
                "description": "Açıqlama",
                "created_by": "İcra Edən",
                "created_at": "Tarix"
            })
            
            st.dataframe(df_finance, hide_index=True, use_container_width=True)
        else:
            st.info("Hələ heç bir maliyyə əməliyyatı yoxdur.")
