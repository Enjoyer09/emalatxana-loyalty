import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
from database import run_query, get_setting, set_setting
from utils import get_logical_date, get_baku_now
import io
try:
    from gtts import gTTS
except ImportError:
    pass

def render_ai_page():
    st.subheader("🤖 AI Menecer və Baş Müfəttiş")
    
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
    
    # Səhifəni 2 Taba (Bölməyə) ayırırıq: Biri Biznes/Satış üçündür, digəri Təhlükəsizlik (Audit) üçün
    tab_biz, tab_sec = st.tabs(["📊 Biznes və Satış Analizi", "🕵️‍♂️ Təhlükəsizlik və Sistem Auditi"])
    
    # ==========================================
    # 1. BİZNES VƏ SATIŞ ANALİZİ (Köhnə kodun inkişaf etmiş forması)
    # ==========================================
    with tab_biz:
        st.markdown("### 📈 Nəyi Analiz Edək?")
        c1, c2 = st.columns(2)
        d1 = c1.date_input("Başlanğıc Tarixi", get_logical_date() - datetime.timedelta(days=7), key="biz_d1")
        d2 = c2.date_input("Bitiş Tarixi", get_logical_date(), key="biz_d2")
        
        user_question = st.text_area("Xüsusi sualınız var? (İstəyə bağlı)", placeholder="Məsələn: Səncə bu aralıqda nağd satış niyə bu qədər çoxdur?", key="biz_q")

        if st.button("🧠 Biznes Analizini Başlat", type="primary", use_container_width=True, key="biz_btn"):
            with st.spinner("🤖 AI satış datalarınızı oxuyur və cavab hazırlayır..."):
                ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
                ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
                
                sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
                
                if sales.empty:
                    st.error("Seçilmiş tarixlərdə satış yoxdur. Analiz edəcək məlumat tapılmadı.")
                else:
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
                        st.success("✅ Biznes Analizi Tamamlandı!")
                        
                        try:
                            tts = gTTS(text=response.text, lang='tr')
                            fp = io.BytesIO()
                            tts.write_to_fp(fp)
                            st.audio(fp, format='audio/mp3')
                            st.info("▶️ Yuxarıdakı pleyerdən hesabatı səsli dinləyə bilərsiniz.")
                        except:
                            pass

                        st.markdown(f"""
                        <div style="background: #1e2226; padding: 20px; border-left: 5px solid #ffd700; border-radius: 10px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);">
                            {response.text}
                        </div>
                        """, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"Xəta baş verdi. Detal: {e}")

    # ==========================================
    # 2. TƏHLÜKƏSİZLİK VƏ SİSTEM AUDİTİ (YENİ NÜVƏ SƏVİYYƏSİ)
    # ==========================================
    with tab_sec:
        st.markdown("### 🕵️‍♂️ Sistem Loqları və Anomaliya Ovu")
        st.info("AI Baş Müfəttiş arxa plandakı bütün hərəkətləri (silinmələr, dəyişikliklər, kassa hərəkətləri) oxuyur və sənə şübhəli vəziyyətləri məruzə edir.")
        
        c3, c4 = st.columns(2)
        audit_d1 = c3.date_input("Başlanğıc Tarixi", get_logical_date(), key="audit_d1")
        audit_d2 = c4.date_input("Bitiş Tarixi", get_logical_date(), key="audit_d2")
        
        audit_q = st.text_area("Müfəttişə sualın var?", placeholder="Məsələn: Bu gün kimsə çeki silibmi? Və ya Səbinə xanım sistemdə nə edib?", key="audit_q")
        
        if st.button("🚨 Təhlükəsizlik Auditi Başlat", type="primary", use_container_width=True, key="audit_btn"):
            with st.spinner("🕵️‍♂️ Müfəttiş sistemin altını-üstünə gətirir, loqları oxuyur..."):
                t_s = datetime.datetime.combine(audit_d1, datetime.time(0,0))
                t_e = datetime.datetime.combine(audit_d2, datetime.time(23,59))
                
                # 1. Bütün Loqları (gələcəkdə yaradacağımız logs cədvəlindən) çəkirik
                # Hələlik logs cədvəli boş və ya yoxdursa, digər kritik hərəkətləri oxuyuruq
                logs_df = pd.DataFrame()
                try:
                    logs_df = run_query("SELECT user, action, created_at FROM logs WHERE created_at BETWEEN :s AND :e ORDER BY created_at DESC LIMIT 200", {"s":t_s, "e":t_e})
                except:
                    pass # Logs cədvəli hələ yoxdursa və ya boşdursa, xəta verməsin
                
                # 2. Endirimli satışları çəkirik (Şübhəli ola bilər)
                disc_sales = run_query("SELECT cashier, items, discount_amount, total, note, created_at FROM sales WHERE discount_amount > 0 AND created_at BETWEEN :s AND :e", {"s":t_s, "e":t_e})
                
                # 3. Kassadan çıxışları (pul qaçırmaq ehtimalı) çəkirik
                cash_outs = run_query("SELECT category, amount, description, created_by, created_at FROM finance WHERE type='out' AND source='Kassa' AND created_at BETWEEN :s AND :e", {"s":t_s, "e":t_e})
                
                # Məlumatları mətnə çeviririk ki, Gemini oxuya bilsin
                logs_str = "Hələlik sistem səviyyəli klik loqları yoxdur." if logs_df.empty else "\n".join([f"[{r['created_at']}] {r['user']}: {r['action']}" for _, r in logs_df.iterrows()])
                disc_str = "Bu aralıqda endirimli satış yoxdur." if disc_sales.empty else "\n".join([f"[{r['created_at']}] {r['cashier']} | Total: {r['total']}AZN | Endirim: {r['discount_amount']}AZN | Səbəb: {r['note']}" for _, r in disc_sales.iterrows()])
                outs_str = "Bu aralıqda kassadan pul çıxışı yoxdur." if cash_outs.empty else "\n".join([f"[{r['created_at']}] {r['created_by']} | {r['amount']}AZN çıxardı | Səbəb: {r['category']} - {r['description']}" for _, r in cash_outs.iterrows()])
                
                sys_prompt = f"""
                Sən 'Füzuli' kofe şopunun 'AI Baş Müfəttişisən' (Security & Audit Manager). Sənin işin verilmiş sistem loqlarını və əməliyyatları oxuyaraq anomaliyaları, şübhəli hərəkətləri (oğurluq, səlahiyyətdən sui-istifadə, qayda pozuntusu) tapmaq və rəhbərə dəqiq hərbi məruzə formatında hesabat verməkdir.
                
                TARİX ARALIĞI: {audit_d1} - {audit_d2}
                
                --- SİSTEM LOQLARI (HƏRƏKƏTLƏR) ---
                {logs_str[:2500]} 
                
                --- ENDİRİMLİ SATIŞLAR (ŞÜBHƏLİ OLA BİLƏR) ---
                {disc_str[:1500]}
                
                --- KASSADAN PUL ÇIXIŞLARI (MƏXARİC) ---
                {outs_str[:1500]}
                
                RƏHBƏRİN SUALI/TƏLƏBİ: {audit_q if audit_q.strip() else 'Mövcud məlumatları incələ və əgər hər hansı bir silinmə, böyük endirim və ya şübhəli hərəkət varsa, mənə məruzə et. Hər şey normaldırsa, sadəcə qısa bir asayiş hesabatı ver.'}
                
                DİQQƏT: Cavabın çox konkret, peşəkar və Azərbaycan dilində olmalıdır. Lazımsız cümlələr qurma. Şübhəli bir şey tapmasan, uydurma, sadəcə "Hər şey qaydasındadır" de.
                """
                
                try:
                    audit_res = model.generate_content(sys_prompt)
                    st.success("🚨 Audit Tamamlandı!")
                    
                    st.markdown(f"""
                    <div style="background: #1e1e1e; padding: 20px; border-left: 5px solid #ff4b4b; border-radius: 10px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);">
                        <h4 style="color:#ff4b4b; margin-top:0;">📋 MÜFƏTTİŞİN MƏRUZƏSİ</h4>
                        {audit_res.text}
                    </div>
                    """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Müfəttiş xəta verdi: {e}")
