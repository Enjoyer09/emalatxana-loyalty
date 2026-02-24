import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
from database import run_query, get_setting, set_setting
from utils import get_logical_date
import io
from gtts import gTTS

def render_ai_page():
    st.subheader("🤖 AI Menecer və Səsli Məsləhətçi")
    
    st.info("Bu səhifədə həm ümumi hesabat ala, həm də datalarla bağlı öz xüsusi sualınızı verə bilərsiniz.")
    
    api_key = get_setting("gemini_api_key", "")
    with st.expander("⚙️ AI Ayarları (API Key)", expanded=True if not api_key else False):
        new_key = st.text_input("Google AI Studio-dan aldığınız API Key-i bura yapışdırın:", value=api_key, type="password")
        if st.button("Açarı Yadda Saxla"):
            set_setting("gemini_api_key", new_key)
            st.success("Açar uğurla yadda saxlanıldı!")
            st.rerun()
            
    if not api_key:
        st.warning("⚠️ AI Meneceri işə salmaq üçün yuxarıdakı xanaya API açarını daxil edin.")
        return

    try:
        genai.configure(api_key=api_key)
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if not valid_models:
            st.error("Hesabınızda aktiv model tapılmadı.")
            return
        chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0])
        model = genai.GenerativeModel(chosen_model) 
    except Exception as e:
        st.error(f"Sistem konfiqurasiyasında xəta: {e}")
        return
    
    st.markdown("### 📈 Nəyi Analiz Edək?")
    c1, c2 = st.columns(2)
    d1 = c1.date_input("Başlanğıc Tarixi", get_logical_date() - datetime.timedelta(days=7))
    d2 = c2.date_input("Bitiş Tarixi", get_logical_date())
    
    user_question = st.text_area("Xüsusi sualınız var? (İstəyə bağlı)", placeholder="Məsələn: Səncə bu aralıqda nağd satış niyə bu qədər çoxdur?")

    if st.button("🧠 AI Analizini Başlat", type="primary", use_container_width=True):
        with st.spinner("🤖 AI satış datalarınızı oxuyur və cavab hazırlayır..."):
            ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
            ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
            
            sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
            
            if sales.empty:
                st.error("Seçilmiş tarixlərdə satış yoxdur. Analiz edəcək məlumat tapılmadı.")
                return
            
            total_revenue = sales['total'].sum()
            cash_rev = sales[sales['payment_method']=='Cash']['total'].sum()
            card_rev = sales[sales['payment_method']=='Card']['total'].sum()
            
            item_counts = {}
            for items_str in sales['items']:
                if not isinstance(items_str, str) or items_str == "Table Order": continue
                parts = items_str.split(", ")
                for p in parts:
                    if " x" in p:
                        try:
                            name_part, qty_part = p.rsplit(" x", 1)
                            qty = int(qty_part.split()[0])
                            item_counts[name_part] = item_counts.get(name_part, 0) + qty
                        except: pass
            
            top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
            top_items_str = ", ".join([f"{k} ({v} ədəd)" for k, v in top_items[:15]])
            least_items_str = ", ".join([f"{k} ({v} ədəd)" for k, v in top_items[-5:]]) if len(top_items) > 5 else "Məlumat azdır"

            if user_question.strip():
                task_instruction = f"Müdirin sənə xüsusi sualı var: '{user_question}'. Zəhmət olmasa yuxarıdakı datalara əsasən MƏHZ bu suala peşəkar və ətraflı cavab ver."
            else:
                task_instruction = "Müdir xüsusi sual verməyib. Ona bu aralıq üçün qısa ümumi biznes vəziyyətini, menyudan çıxarılmalı məhsulları və gəliri artırmaq üçün 2 kampaniya təklifi ver."

            prompt = f"""
            Sən 'Füzuli' adlı kofe şopunun baş meneceri və biznes analitikisən. 
            DİQQƏT: YALNIZ bu kofe biznesi, satışlar və idarəetmə barədə danış!
            
            Məlumatlar ({d1} - {d2}):
            - Ümumi Dövriyyə: {total_revenue:.2f} AZN
            - Nağd Satış: {cash_rev:.2f} AZN
            - Kartla Satış: {card_rev:.2f} AZN
            - Ümumi çek sayı: {len(sales)}
            - Ən çox satılanlar: {top_items_str}
            - Ən zəif satılanlar: {least_items_str}
            
            Tapşırıq:
            {task_instruction}
            
            Məsləhətini Azərbaycan dilində yaz.
            """

            try:
                response = model.generate_content(prompt)
                st.success("✅ AI Analizi Tamamlandı!")
                
                with st.spinner("🔊 Səs yaradılır..."):
                    try:
                        tts = gTTS(text=response.text, lang='tr')
                        fp = io.BytesIO()
                        tts.write_to_fp(fp)
                        st.audio(fp, format='audio/mp3')
                        st.info("▶️ Yuxarıdakı pleyerdən hesabatı səsli dinləyə bilərsiniz.")
                    except Exception as audio_e:
                        st.warning(f"Mətn yaradıldı, lakin səsə çevrilərkən xəta oldu: {audio_e}")

                st.markdown(f"""
                <div style="background: #1e2226; padding: 20px; border-left: 5px solid #ffd700; border-radius: 10px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);">
                    {response.text}
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Xəta baş verdi. Detal: {e}")
