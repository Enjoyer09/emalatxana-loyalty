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
    
    # 3 TAB YARADILDI
    tab_biz, tab_sec, tab_audit = st.tabs(["📊 Biznes Analizi", "🕵️‍♂️ Sistem Təhlükəsizliyi", "🧪 Anbar və Resept Auditi"])
    
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
                    st.error("Seçilmiş tarixlərdə satış yoxdur.")
                else:
                    total_revenue = sales['total'].sum()
                    cash_rev = sales[sales['payment_method'].isin(['Cash','Nəğd'])]['total'].sum()
                    card_rev = sales[sales['payment_method'].isin(['Card','Kart'])]['total'].sum()
                    
                    item_counts = {}
                    for items_str in sales['items']:
                        if not isinstance(items_str, str) or items_str == "Table Order": continue
                        try:
                            import json
                            parsed = json.loads(items_str)
                            for i in parsed: item_counts[i['item_name']] = item_counts.get(i['item_name'], 0) + i['qty']
                        except:
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

                    if user_question.strip():
                        task_instruction = f"Müdirin sənə xüsusi sualı var: '{user_question}'. Zəhmət olmasa yuxarıdakı datalara əsasən MƏHZ bu suala peşəkar cavab ver."
                    else:
                        task_instruction = "Müdir xüsusi sual verməyib. Qısa biznes vəziyyətini analiz et."

                    prompt = f"Məlumatlar:\nDövriyyə: {total_revenue} AZN\nƏn çox satılanlar: {top_items_str}\n\nTapşırıq: {task_instruction}"

                    try:
                        response = model.generate_content(prompt)
                        st.success("✅ Analiz Tamamlandı!")
                        st.markdown(f"<div style='background: #1e2226; padding: 20px; border-left: 5px solid #ffd700; border-radius: 10px;'>{response.text}</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Xəta: {e}")

    with tab_sec:
        st.markdown("### 🕵️‍♂️ Sistem Loqları və Anomaliya Ovu")
        c3, c4 = st.columns(2)
        audit_d1 = c3.date_input("Başlanğıc Tarixi", get_logical_date(), key="audit_d1")
        audit_d2 = c4.date_input("Bitiş Tarixi", get_logical_date(), key="audit_d2")
        
        audit_q = st.text_area("Müfəttişə sualın var?", placeholder="Məsələn: Bu gün kimsə çeki silibmi?", key="audit_q")
        
        if st.button("🚨 Təhlükəsizlik Auditi Başlat", type="primary", use_container_width=True, key="audit_btn"):
            with st.spinner("🕵️‍♂️ Müfəttiş loqları oxuyur..."):
                t_s = datetime.datetime.combine(audit_d1, datetime.time(0,0))
                t_e = datetime.datetime.combine(audit_d2, datetime.time(23,59))
                
                logs_df = pd.DataFrame()
                try: logs_df = run_query("SELECT \"user\", action, created_at FROM logs WHERE created_at BETWEEN :s AND :e ORDER BY created_at DESC LIMIT 200", {"s":t_s, "e":t_e})
                except: pass 
                
                logs_str = "Loq yoxdur." if logs_df.empty else "\n".join([f"[{r['created_at']}] {r['user']}: {r['action']}" for _, r in logs_df.iterrows()])
                
                sys_prompt = f"LOQLAR:\n{logs_str[:3000]}\nSUAL: {audit_q if audit_q.strip() else 'Şübhəli əməliyyatları axtar.'}"
                
                try:
                    audit_res = model.generate_content(sys_prompt)
                    st.markdown(f"<div style='background: #1e1e1e; padding: 20px; border-left: 5px solid #28a745; border-radius: 10px;'>{audit_res.text}</div>", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Müfəttiş xəta verdi: {e}")

    # ==========================================
    # YENİ MODUL: ANBAR VƏ RESEPT AUDİTİ
    # ==========================================
    with tab_audit:
        st.markdown("### 🧪 Qramaj və Qiymət Auditi")
        st.info("Müfəttiş bütün menyunu, reseptlərin tərkibini və anbar qiymətlərini incələyəcək. Həddindən artıq istifadə olunan qramajları (məs: 1 stəkana 5kq süd) və xətalı maya dəyərlərini aşkar edəcək.")
        
        if st.button("🔍 Bütün Reseptləri Skan Et", type="primary", use_container_width=True):
            with st.spinner("Bütün qramajlar və anbar qiymətləri analiz edilir..."):
                recipes = run_query("SELECT menu_item_name, ingredient_name, quantity_required FROM recipes")
                ingredients = run_query("SELECT name, unit, unit_cost, stock_qty FROM ingredients")
                
                if recipes.empty or ingredients.empty:
                    st.warning("Resept və ya anbar məlumatları kifayət deyil.")
                else:
                    rec_str = "\n".join([f"- Məhsul: {r['menu_item_name']} | Xammal: {r['ingredient_name']} | Miqdar: {r['quantity_required']}" for _, r in recipes.iterrows()])
                    ing_str = "\n".join([f"- {r['name']} | Vahid: {r['unit']} | Alış Qiyməti: {r['unit_cost']} ₼" for _, r in ingredients.iterrows()])
                    
                    prompt = f"""
                    Sən Baş Auditor və Baristasan. Aşağıdakı məlumatlar kofe şopun bazasındandır.
                    Səndən istədiyim:
                    1. Reseptlərdəki 'Miqdar' dəyərlərini məntiq süzgəcindən keçir. (Məsələn, 1 porsiya kofeyə 15 qram (0.015 KG) kofe gedər, əgər 15 KG yazılıbsa bu XƏTADIR!)
                    2. Xammalların 'Alış Qiyməti'ni yoxla. (Məsələn, 1 ədəd stəkan 0.05 AZN olar, əgər 50 AZN yazılıbsa XƏTADIR!)
                    3. Alış qiyməti '0' olanları xüsusi olaraq qeyd et ki, təcili düzəltsinlər.
                    
                    YALNIZ ŞÜBHƏLİ GÖRDÜYÜN VƏ XƏTALI OLANLARI SİYAHI ŞƏKLİNDƏ YAZ. (Əgər hər şey qaydasındadırsa, qısa 'Hər şey mükəmməldir' de).
                    
                    -- RESEPTLƏR (Qramajlar) --
                    {rec_str}
                    
                    -- ANBAR XAMMALLARI --
                    {ing_str}
                    """
                    
                    try:
                        audit_res = model.generate_content(prompt)
                        st.success("Skan tamamlandı!")
                        st.markdown(f"<div style='background: #1e1e1e; padding: 20px; border-left: 5px solid #dc3545; border-radius: 10px;'><h4 style='color:#dc3545;'>🔴 AŞKARLANAN RİSKLƏR</h4>{audit_res.text}</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Xəta: {e}")
