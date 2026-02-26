import streamlit as st
import pandas as pd
import datetime
import time
import io
import plotly.express as px
import google.generativeai as genai
from gtts import gTTS
from database import run_query, run_action, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range, get_baku_now
from auth import admin_confirm_dialog

def render_finance_page():
    st.subheader("💰 Maliyyə Mərkəzi (AI CFO Paneli)")
    
    # === 1. KASSA AÇILIŞI VƏ ÜMUMİ BALANSLAR ===
    with st.expander("🔓 Səhər Kassanı Aç (Opening Balance)"):
        op_bal = st.number_input("Kassada nə qədər pul var? (AZN)", min_value=0.0, step=0.1)
        if st.button("✅ Kassanı Bu Məbləğlə Aç"): 
            set_setting("cash_limit", str(op_bal)); st.success(f"Gün {op_bal} AZN ilə başladı!"); time.sleep(1); st.rerun()

    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
    log_date = get_logical_date(); shift_start, shift_end = get_shift_range(log_date)
    
    if "Növbə" in view_mode: 
        cond = "AND created_at >= :d AND created_at < :e"; params = {"d":shift_start, "e":shift_end}
    else:
        last_z = get_setting("last_z_report_time")
        # BURADA DA BAKU VAXTINI NƏZƏRƏ ALIRIQ
        last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else get_baku_now() - datetime.timedelta(days=365)
        cond = "AND created_at > :d"; params = {"d":last_z_dt}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {cond}", params).iloc[0]['s'] or 0.0
    e_cash = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_cash = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    start_lim = float(get_setting("cash_limit", "0.0" if "Növbə" in view_mode else "100.0"))
    disp_cash = start_lim + float(s_cash) + float(i_cash) - float(e_cash)
    
    s_card_shift = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Card' {cond}", params).iloc[0]['s'] or 0.0
    e_card_shift = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_card_shift = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    disp_card_view = float(s_card_shift) + float(i_card_shift) - float(e_card_shift)
    
    s_card_all = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card'").iloc[0]['s'] or 0.0
    e_card_all = run_query("SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out'").iloc[0]['e'] or 0.0
    i_card_all = run_query("SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in'").iloc[0]['i'] or 0.0
    disp_card_all = float(s_card_all) + float(i_card_all) - float(e_card_all)
    
    st.divider(); m1, m2 = st.columns(2)
    m1.metric("🏪 Kassa (Cibdə)", f"{disp_cash:.2f} ₼")
    m2.metric(f"💳 Bank Kartı ({'Növbə' if 'Növbə' in view_mode else 'Seçilmiş'})", f"{disp_card_view:.2f} ₼", delta=f"Bazada Ümumi: {disp_card_all:.2f} ₼", delta_color="off")

    st.markdown("---")
    
    # === 2. YENİ ƏMƏLİYYAT VƏ DAXİLİ TRANSFER ===
    with st.expander("➕ Yeni Əməliyyat / Daxili Transfer", expanded=False):
        t_op, t_tr = st.tabs(["Standart Əməliyyat", "Daxili Transfer 🔄"])
        with t_op:
            with st.form("new_fin_trx", clear_on_submit=True):
                c1, c2, c3 = st.columns(3); f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"]); f_source = c2.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Investor"]); f_subj = c3.selectbox("Subyekt", SUBJECTS)
                c4, c5 = st.columns(2); f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kommunal", "Kirayə", "Maaş/Avans", "Borc", "Digər", "Tips / Çayvoy"]); f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
                f_desc = st.text_input("Qeyd")
                if st.form_submit_button("Təsdiqlə"):
                    db_type = 'out' if "Məxaric" in f_type else 'in'
                    # BURADA BÜTÜN ƏMƏLİYYATLARA ZORLA get_baku_now() VERİRİK!
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at) VALUES (:t, :c, :a, :s, :d, :u, :sb, :time)", {"t":db_type, "c":f_cat, "a":f_amt, "s":f_source, "d":f_desc, "u":st.session_state.user, "sb":f_subj, "time":get_baku_now()})
                    if db_type == 'out': 
                        run_action("INSERT INTO expenses (amount, reason, spender, source, created_at) VALUES (:a, :r, :s, :src, :time)", {"a":f_amt, "r":f"{f_subj} - {f_desc}", "s":st.session_state.user, "src":f_source, "time":get_baku_now()})
                    st.success("Yazıldı!"); time.sleep(1); st.rerun()

        with t_tr:
            with st.form("transfer_trx", clear_on_submit=True):
                st.info("💡 Kartdakı pulu nağdlaşdırıb kassaya qoymaq və ya əksini etmək üçün istifadə edin.")
                c1, c2 = st.columns(2)
                t_dir = c1.selectbox("Transfer Yönü", ["💳 Bank Kartından ➡️ 🏪 Kassaya", "🏪 Kassadan ➡️ 💳 Bank Kartına"])
                t_amt = c2.number_input("Transfer Məbləği (AZN)", min_value=0.01, step=0.01)
                t_desc = st.text_input("Açıqlama", "Nağdlaşdırma / Kəsirin bərpası")
                if st.form_submit_button("Transferi Təsdiqlə"):
                    user_u = st.session_state.user
                    # TRANSFERLƏRDƏ DƏ BAKU VAXTI!
                    if "Bank Kartından" in t_dir:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('out', 'Daxili Transfer', :a, 'Bank Kartı', :d, :u, :time)", {"a":t_amt, "d":t_desc + " (Kassaya)", "u":user_u, "time":get_baku_now()})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('in', 'Daxili Transfer', :a, 'Kassa', :d, :u, :time)", {"a":t_amt, "d":t_desc + " (Kartdan)", "u":user_u, "time":get_baku_now()})
                    else:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('out', 'Daxili Transfer', :a, 'Kassa', :d, :u, :time)", {"a":t_amt, "d":t_desc + " (Karta)", "u":user_u, "time":get_baku_now()})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('in', 'Daxili Transfer', :a, 'Bank Kartı', :d, :u, :time)", {"a":t_amt, "d":t_desc + " (Kassadan)", "u":user_u, "time":get_baku_now()})
                    st.success("Transfer Uğurla İcra Edildi!"); time.sleep(1); st.rerun()

    # === 3. AĞILLI FİLTRLƏR VƏ CFO ANALİZATORU ===
    st.markdown("---")
    st.subheader("🔍 Ağıllı Maliyyə Cədvəli və Hesabatlar")
    
    today = get_baku_now().date()
    start_of_month = today.replace(day=1)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        date_filter = st.selectbox("Tarix Aralığı", ["Bu Ay", "Bu Gün", "Keçən Ay", "Bütün Zamanlar", "Xüsusi Aralıq"])
    with f_col2:
        type_filter = st.selectbox("Əməliyyat Növü", ["Hamısı", "Məxaric (Çıxış)", "Mədaxil (Giriş)"])
    with f_col3:
        src_filter = st.selectbox("Mənbə", ["Hamısı", "Kassa", "Bank Kartı", "Seyf", "Investor"])

    # Tarix məntiqi
    if date_filter == "Bu Ay":
        sd, ed = start_of_month, today
    elif date_filter == "Bu Gün":
        sd, ed = today, today
    elif date_filter == "Keçən Ay":
        first_day_last_month = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - datetime.timedelta(days=1)
        sd, ed = first_day_last_month, last_day_last_month
    elif date_filter == "Xüsusi Aralıq":
        d_range = st.date_input("Tarix Seçin", [today, today])
        if len(d_range) == 2: sd, ed = d_range
        else: sd, ed = today, today
    else:
        sd, ed = datetime.date(2000, 1, 1), today

    # Dinamik Query Quraşdırılması
    query = "SELECT * FROM finance WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed"
    params = {"sd": sd, "ed": ed}
    
    if type_filter == "Məxaric (Çıxış)": query += " AND type='out'"
    elif type_filter == "Mədaxil (Giriş)": query += " AND type='in'"
    if src_filter != "Hamısı":
        query += " AND source=:src"
        params["src"] = src_filter
        
    query += " ORDER BY created_at DESC"
    fin_df = run_query(query, params)
    
    # --- Vizual Qrafik (Pie Chart) ---
    if not fin_df.empty and (type_filter in ["Hamısı", "Məxaric (Çıxış)"]):
        expenses_only = fin_df[fin_df['type'] == 'out']
        if not expenses_only.empty:
            exp_grouped = expenses_only.groupby('category')['amount'].sum().reset_index()
            exp_grouped = exp_grouped[exp_grouped['category'] != 'Daxili Transfer'] 
            
            if not exp_grouped.empty:
                st.markdown("**💸 Xərclərin Kateqoriyalar Üzrə Bölgüsü (Seçilmiş Aralıq)**")
                fig = px.pie(exp_grouped, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig, use_container_width=True)

    # === 4. BİRBAŞA AI İNTEQRASİYASI (SƏNİN YAZDIĞIN KOD) ===
    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        if not fin_df.empty:
            csv = fin_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel/CSV kimi Yüklə", data=csv, file_name=f"Maliyye_{sd}_{ed}.csv", mime="text/csv", use_container_width=True)
            
    with action_col2:
        api_key = get_setting("gemini_api_key", "")
        if st.button("🤖 AI Maliyyə Analizi Çıxar", type="primary", use_container_width=True):
            if fin_df.empty:
                st.warning("Analiz üçün bu aralıqda kifayət qədər məlumat yoxdur.")
            elif not api_key:
                st.error("⚠️ AI API Açarı (Gemini Key) tapılmadı! Zəhmət olmasa 'Ayarlar' və ya 'AI Menecer' tabından API açarınızı daxil edin.")
            else:
                try:
                    genai.configure(api_key=api_key)
                    valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0])
                    model = genai.GenerativeModel(chosen_model) 
                    
                    with st.spinner("🤖 AI maliyyə datalarınızı oxuyur və səsli cavab hazırlayır..."):
                        total_in = fin_df[fin_df['type'] == 'in']['amount'].sum()
                        total_out = fin_df[fin_df['type'] == 'out']['amount'].sum()
                        
                        expenses_str = ""
                        expenses_only = fin_df[fin_df['type'] == 'out']
                        if not expenses_only.empty:
                            exp_grouped = expenses_only.groupby('category')['amount'].sum().sort_values(ascending=False)
                            expenses_str = ", ".join([f"{cat}: {amt:.2f} AZN" for cat, amt in exp_grouped.items() if cat != 'Daxili Transfer'])
                        
                        prompt = f"""
                        Sən 'Füzuli' adlı kofe şopunun baş maliyyəçisisən (CFO).
                        Aşağıdakı datalar seçilmiş {sd} - {ed} tarixləri arasındakı maliyyə göstəriciləridir.
                        
                        - Ümumi Mədaxil (Gəlir): {total_in:.2f} AZN
                        - Ümumi Məxaric (Xərc): {total_out:.2f} AZN
                        - Xərc kateqoriyaları: {expenses_str}
                        
                        Müdirə qısa, dəqiq və professional maliyyə analizi ver. Vəziyyəti dəyərləndir və 2 cümləlik tövsiyə ver. Cümlələri uzun uzadı deyil, konkret və aydın yaz ki, mən onu səsləndirəcəyəm.
                        Məsləhətini Azərbaycan dilində yaz.
                        """
                        
                        response = model.generate_content(prompt)
                        st.success("✅ AI Analizi Tamamlandı!")
                        
                        try:
                            tts = gTTS(text=response.text, lang='tr')
                            fp = io.BytesIO()
                            tts.write_to_fp(fp)
                            st.audio(fp, format='audio/mp3')
                        except Exception as audio_e:
                            st.warning(f"Səs generasiyasında xəta oldu (Amma mətn hazırdır): {audio_e}")

                        st.markdown(f"""
                        <div style="background: #1e2226; padding: 20px; border-left: 5px solid #ffd700; border-radius: 10px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);">
                            {response.text}
                        </div>
                        """, unsafe_allow_html=True)
                        
                except Exception as e:
                    st.error(f"AI Analiz xətası: {e}")

    # --- Cədvəl ---
    if not fin_df.empty:
        disp_df = fin_df.copy()
        disp_df['type'] = disp_df['type'].apply(lambda x: "🟢 Giriş" if x=='in' else "🔴 Çıxış")
        disp_df['created_at'] = pd.to_datetime(disp_df['created_at']).dt.strftime('%d.%m.%Y %H:%M')
        st.dataframe(disp_df[['id', 'created_at', 'type', 'category', 'amount', 'source', 'subject', 'description', 'created_by']], hide_index=True, use_container_width=True)
    else:
        st.info("Seçilmiş filtrlərə uyğun məlumat tapılmadı.")
