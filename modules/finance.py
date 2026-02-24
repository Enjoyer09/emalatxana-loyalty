import streamlit as st
import pandas as pd
import time
from database import run_query, run_action

def render_finance_page():
    st.subheader("💰 Maliyyə və Xərclərin İdarəedilməsi")
    
    # Üç əsas bölmə yaradırıq
    t1, t2, t3 = st.tabs(["💸 Məxaric (Kənara Ödənişlər)", "🔄 Mədaxil və Transfer", "📋 Maliyyə Tarixçəsi"])
    
    # ==========================================
    # 1. MƏXARİC (KASSADAN VƏ YA KARTDAN ÇIXAN XƏRCLƏR)
    # ==========================================
    with t1:
        st.markdown("### 💸 Yeni Xərc və ya Kənara Ödəniş")
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
                    "Digər"
                ])
                amount = st.number_input("Məbləğ (₼)", min_value=0.01, step=0.5, format="%.2f")
            
            with c2:
                source = st.selectbox("Mənbə (Pul hardan çıxır?)", [
                    "Kassa", 
                    "Bank Kartı", 
                    "Şəxsi Cib", 
                    "Təsisçi"
                ])
                description = st.text_input("Açıqlama (Məsələn: Ustaya ödəniş)")
                
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
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Məbləğ 0-dan böyük olmalıdır.")

    # ==========================================
    # 2. MƏDAXİL VƏ DAXİLİ TRANSFER (SƏNİN İSTƏDİYİN MƏNTİQ)
    # ==========================================
    with t2:
        st.markdown("### 🔄 Mədaxil və ya Daxili Transfer")
        st.info("💡 **DİQQƏT:** Əgər kartdan nağdlaşdırıb kassa kəsirini düzəldirsinizsə, Mənbəni 'Bank Kartı', Hədəfi 'Kassa' seçin. Sistem avtomatik transfer edəcək.")
        
        with st.form("income_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                source_from = st.selectbox("Pul Haradan Gəlir? (Mənbə)", [
                    "Kənar Şəxs / Təsisçi (Xalis Mədaxil)", 
                    "Bank Kartı (Daxili Transfer)", 
                    "Kassa (Daxili Transfer)"
                ])
                target_to = st.selectbox("Pul Hara Daxil Olur? (Hədəf)", [
                    "Kassa", 
                    "Bank Kartı"
                ])
                
            with c2:
                amount_in = st.number_input("Məbləğ (₼)", min_value=0.01, step=0.5, format="%.2f", key="inc_amount")
                description_in = st.text_input("Açıqlama", placeholder="Məsələn: Kassa kəsirini bağlamaq üçün nağdlaşdırma")
                
            submit_income = st.form_submit_button("Əməliyyatı Təsdiqlə", type="primary", use_container_width=True)
            
            if submit_income:
                if amount_in > 0:
                    user_str = str(st.session_state.user)
                    
                    # Ssenari 1: Bank Kartından çıxarıb Kassaya qoymaq (Kəsir düzəltmək)
                    if source_from == "Bank Kartı (Daxili Transfer)" and target_to == "Kassa":
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Transfer (Çıxarış)', :a, 'Bank Kartı', :d, :u)", {"a": float(amount_in), "d": f"{description_in} (Kassaya transfer)", "u": user_str})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Transfer (Mədaxil)', :a, 'Kassa', :d, :u)", {"a": float(amount_in), "d": f"{description_in} (Kartdan transfer)", "u": user_str})
                        st.success(f"✅ {amount_in} ₼ Bank Kartından çıxıldı və Kassaya mədaxil edildi!")
                        
                    # Ssenari 2: Kassadan çıxarıb Bank Kartına qoymaq (İnkassasiya edib bankomata vurmaq)
                    elif source_from == "Kassa (Daxili Transfer)" and target_to == "Bank Kartı":
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Transfer (Çıxarış)', :a, 'Kassa', :d, :u)", {"a": float(amount_in), "d": f"{description_in} (Karta transfer)", "u": user_str})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Transfer (Mədaxil)', :a, 'Bank Kartı', :d, :u)", {"a": float(amount_in), "d": f"{description_in} (Kassadan transfer)", "u": user_str})
                        st.success(f"✅ {amount_in} ₼ Kassadan çıxıldı və Bank Kartına mədaxil edildi!")
                        
                    # Ssenari 3: Çöldən (Kənardan) gələn təmiz mədaxil
                    elif source_from == "Kənar Şəxs / Təsisçi (Xalis Mədaxil)":
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Kənar Mədaxil', :a, :t, :d, :u)", {"a": float(amount_in), "t": target_to, "d": description_in, "u": user_str})
                        st.success(f"✅ {amount_in} ₼ məbləğ {target_to} hədəfinə uğurla mədaxil edildi!")
                        
                    # Məntiqsiz seçim (Eyni yerdən eyni yerə)
                    else:
                        st.warning("⚠️ Mənbə və Hədəf eyni ola bilməz (Məsələn: Kassadan Kassaya)!")
                        st.stop()
                    
                    time.sleep(1.5)
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
            df_finance['type'] = df_finance['type'].apply(lambda x: "🟢 MƏDAXİL" if x == 'in' else "🔴 MƏXARİC")
            df_finance['created_at'] = pd.to_datetime(df_finance['created_at']).dt.strftime('%d/%m/%Y %H:%M')
            
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
