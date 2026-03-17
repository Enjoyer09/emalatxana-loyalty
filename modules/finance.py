# modules/finance.py
import streamlit as st
import pandas as pd
import datetime, time, io, os
import plotly.express as px
import google.generativeai as genai
try:
    from gtts import gTTS
except ImportError:
    pass
from database import run_query, run_action, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range, get_baku_now, log_system

def render_finance_page():
    st.subheader("💰 Maliyyə Mərkəzi (Nəzarət & Düzəliş)")
    
    is_t_active = st.session_state.get('test_mode', False)
    if is_t_active:
        st.warning("⚠️ Hazırda TEST rejimindəsiniz. Aşağıdakı balans və cədvəldə TEST əməliyyatları nəzərə alınır.")

    with st.expander("🔓 Səhər Kassanı Aç (Opening Balance)", expanded=False):
        with st.form("open_register_form", clear_on_submit=True):
            c_open1, c_open2 = st.columns([3, 1])
            open_amt = c_open1.number_input("Səhər kassada olan məbləğ (Açılış balansı - AZN)", min_value=0.0, step=1.0)
            if c_open2.form_submit_button("✅ Kassanı Bu Məbləğlə Aç"): 
                set_setting("cash_limit", str(open_amt))
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Kassa Açılışı', :a, 'Kassa', 'Səhər açılış balansı', :u, :t, :tst)", 
                           {"a": open_amt, "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active})
                try: log_system(st.session_state.user, f"Kassa açılışı edildi: {open_amt} ₼")
                except: pass
                st.success(f"Gün {open_amt} AZN ilə başladı (Sistemə yazıldı)!"); time.sleep(1.5); st.rerun()

    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
    log_date = get_logical_date(); shift_start, shift_end = get_shift_range(log_date)
    
    test_filter = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
    if "Növbə" in view_mode: 
        cond = f"AND created_at >= :d AND created_at < :e {test_filter}"; params = {"d":shift_start, "e":shift_end}
    else:
        last_z = get_setting("last_z_report_time")
        last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else get_baku_now() - datetime.timedelta(days=365)
        cond = f"AND created_at > :d {test_filter}"; params = {"d":last_z_dt}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {cond}", params).iloc[0]['s'] or 0.0
    e_cash = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_cash = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {cond}", params).iloc[0]['i'] or 0.0
    start_lim = float(get_setting("cash_limit", "0.0" if "Növbə" in view_mode else "100.0"))
    disp_cash = start_lim + float(s_cash) + float(i_cash) - float(e_cash)
    
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {cond}", params).iloc[0]['s'] or 0.0
    e_card = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_card = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Kart)') {cond}", params).iloc[0]['i'] or 0.0
    disp_card_view = float(s_card) + float(i_card) - float(e_card)
    
    debt_out = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Nisyə / Borc' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    debt_in = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Nisyə / Borc' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    disp_debt = float(debt_out) - float(debt_in)
    
    st.divider(); m1, m2, m3 = st.columns(3)
    m1.metric("🏪 Kassa (Cibdə Olan)", f"{disp_cash:.2f} ₼")
    m2.metric(f"💳 Bank Kartı ({'Növbə' if 'Növbə' in view_mode else 'Seçilmiş'})", f"{disp_card_view:.2f} ₼")
    m3.metric("📝 Ödəniləcək Borc (Nisyə)", f"{disp_debt:.2f} ₼", delta="Bizim Borcumuz" if disp_debt > 0 else "Borc Yoxdur", delta_color="inverse")

    st.markdown("---")
    
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Maliyyə Audit (Şübhəli Tranzaksiyalar və İtkilər)"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin (Ayarlar bölməsindən).")
            else:
                if st.button("🔍 Maliyyə Məlumatlarını Skan Et", use_container_width=True):
                    with st.spinner("AI şübhəli maliyyə çıxarışlarını incələyir..."):
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            recent_fin = run_query("SELECT id, type, category, amount, source, created_by, description FROM finance ORDER BY created_at DESC LIMIT 50")
                            if not recent_fin.empty:
                                fin_str = "\n".join([f"ID: {r['id']} | Növ: {r['type']} | Kat: {r['category']} | Məbləğ: {r['amount']} | Mənbə: {r['source']} | Qeyd: {r['description']}" for _, r in recent_fin.iterrows()])
                                prompt = f"Sən biznes auditorusan. Son 50 maliyyə əməliyyatında itkiləri, çox yüksək və məntiqsiz xərcləri və şübhəli çıxarışları tap və hesabat ver:\n\n{fin_str}"
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background: #1e2226; padding: 15px; border-left: 5px solid #dc3545;'>{response.text}</div>", unsafe_allow_html=True)
                            else: st.info("Kifayət qədər data yoxdur.")
                        except Exception as e: st.error(e)

        with st.expander("💳 Bank Kartından Çıxarış (Sıfırlama / Təhvil)", expanded=False):
            st.info("Kartınızda yığılan məbləği çıxarış edərək sistemdəki kart balansını real balansa uyğunlaşdıra / sıfırlaya bilərsiniz.")
            with st.form("card_withdraw_form"):
                c_amt, c_rsn = st.columns(2)
                cw_amt = c_amt.number_input("Çıxarılan Məbləğ (AZN)", max_value=float(disp_card_view) if float(disp_card_view) > 0 else 10000.0, value=float(disp_card_view) if float(disp_card_view) > 0 else 0.0, step=1.0)
                cw_reason = c_rsn.selectbox("Məxaric Səbəbi / Kateqoriya", ["Təsisçi Çıxarışı", "Aylıq Xərclərin Ödənişi", "Digər Banka Transfer", "Kredit/Borc Ödənişi", "Təchizatçı Ödənişi", "Digər"])
                cw_desc = st.text_input("Açıqlama / Qeyd", "Kartdan çıxarış")
                
                if st.form_submit_button("Kartdan Çıxarış Et (Balansı Azalt)", type="primary"):
                    if cw_amt > 0:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', :c, :a, 'Bank Kartı', :d, :u, :t, :tst)",
                                   {"c": cw_reason, "a": cw_amt, "d": cw_desc, "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active})
                        st.success(f"{cw_amt} AZN kartdan çıxarıldı! Kart balansı uğurla azaldıldı.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Məbləğ 0-dan böyük olmalıdır.")

        with st.expander("⚖️ Balans Korreksiyası (Sinxronizasiya)", expanded=False):
            st.warning("Məcburi balans bərabərləşdirmə (Dövr ərzində yaranmış kəsir və ya artığı tənzimləyin).")
            with st.form("sync_balance"):
                new_cash = st.number_input("Kassada olmalı olan HƏQİQİ nağd məbləğ (AZN):", value=float(disp_cash), step=1.0)
                new_card = st.number_input("Kartda olmalı olan HƏQİQİ məbləğ (AZN):", value=float(disp_card_view), step=1.0)
                if st.form_submit_button("Balansları İndi Bərabərləşdir"):
                    u = st.session_state.user
                    now = get_baku_now()
                    
                    cash_diff = new_cash - disp_cash
                    if abs(cash_diff) > 0.01:
                        c_type = 'in' if cash_diff > 0 else 'out'
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, 'Sistem Korreksiyası', :a, 'Kassa', 'Məcburi Balans Sinxronizasiyası', :u, :time, FALSE)", 
                                   {"t": c_type, "a": abs(cash_diff), "u": u, "time": now})
                    
                    card_diff = new_card - disp_card_view
                    if abs(card_diff) > 0.01:
                        c_type = 'in' if card_diff > 0 else 'out'
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, 'Sistem Korreksiyası', :a, 'Bank Kartı', 'Məcburi Balans Sinxronizasiyası', :u, :time, FALSE)", 
                                   {"t": c_type, "a": abs(card_diff), "u": u, "time": now})
                    
                    st.success("✅ Sistem uğurla real pulla sinxronlaşdırıldı!")
                    time.sleep(1.5)
                    st.rerun()

    with st.expander("➕ Yeni Əməliyyat / Daxili Transfer", expanded=False):
        t_op, t_tr = st.tabs(["Standart Əməliyyat", "Daxili Transfer 🔄"])
        with t_op:
            with st.form("new_fin_trx", clear_on_submit=True):
                st.info("💡 Əgər xərci kartla etmisinizsə, mənbə olaraq mütləq 'Bank Kartı' seçin.")
                c1, c2, c3 = st.columns(3)
                f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"])
                f_source = c2.selectbox("Mənbə (Ödəmə Şəkli)", ["Kassa", "Bank Kartı", "Seyf", "Nisyə / Borc"]) 
                f_subj = c3.selectbox("Subyekt", SUBJECTS)
                
                c4, c5 = st.columns(2)
                f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kassa Açılışı", "Kommunal", "Kirayə", "Maaş/Avans", "Digər", "İnkassasiya (Rəhbərə verilən)"])
                f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
                f_desc = st.text_input("Qeyd")
                
                if st.form_submit_button("Təsdiqlə"):
                    db_type = 'out' if "Məxaric" in f_type else 'in'
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)", 
                               {"t":db_type, "c":f_cat, "a":float(f_amt), "s":f_source, "d":f_desc, "u":st.session_state.user, "sb":f_subj, "time":get_baku_now(), "tst":is_t_active})
                    st.success("Yazıldı!"); time.sleep(1); st.rerun()

        with t_tr:
            with st.form("transfer_trx", clear_on_submit=True):
                st.info("Kassadan Karta (və ya tərsi) transferlər, yaxud Borcun Ödənilməsi üçün istifadə edin.")
                c1, c2 = st.columns(2)
                t_dir = c1.selectbox("Transfer Yönü", [
                    "💳 Bank Kartından ➡️ 🏪 Kassaya", 
                    "🏪 Kassadan ➡️ 💳 Bank Kartına",
                    "🏪 Kassadan ➡️ 📝 Borcun Ödənməsinə",
                    "💳 Bank Kartından ➡️ 📝 Borcun Ödənməsinə"
                ])
                t_amt = c2.number_input("Transfer Məbləği (AZN)", min_value=0.01, step=0.01)
                t_desc = st.text_input("Açıqlama", "Transfer / Ödəniş")
                
                st.write("---")
                has_comm = st.checkbox("Bu transfer üçün Bank Komissiyası (Nağdlaşdırma xərci) tutulub?")
                comm_amt = st.number_input("Komissiya Məbləği (AZN)", min_value=0.0, step=0.01, value=0.0) if has_comm else 0.0

                if st.form_submit_button("Transferi Təsdiqlə"):
                    u = st.session_state.user
                    
                    if "Bank Kartından ➡️ 🏪 Kassaya" in t_dir:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Daxili Transfer', :a, 'Bank Kartı', :d, :u, :time, :tst)", {"a":float(t_amt), "d":t_desc + " (Kassaya)", "u":u, "time":get_baku_now(), "tst":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Daxili Transfer', :a, 'Kassa', :d, :u, :time, :tst)", {"a":float(t_amt), "d":t_desc + " (Kartdan)", "u":u, "time":get_baku_now(), "tst":is_t_active})
                        if has_comm and comm_amt > 0:
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Nağdlaşdırma xərci', :u, :time, :tst)", {"a":float(comm_amt), "u":u, "time":get_baku_now(), "tst":is_t_active})
                    
                    elif "Kassadan ➡️ 💳 Bank Kartına" in t_dir:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Daxili Transfer', :a, 'Kassa', :d, :u, :time, :tst)", {"a":float(t_amt), "d":t_desc + " (Karta)", "u":u, "time":get_baku_now(), "tst":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Daxili Transfer', :a, 'Bank Kartı', :d, :u, :time, :tst)", {"a":float(t_amt), "d":t_desc + " (Kassadan)", "u":u, "time":get_baku_now(), "tst":is_t_active})
                        if has_comm and comm_amt > 0:
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Mədaxil/Transfer xərci', :u, :time, :tst)", {"a":float(comm_amt), "u":u, "time":get_baku_now(), "tst":is_t_active})
                    
                    elif "Kassadan ➡️ 📝 Borcun Ödənməsinə" in t_dir:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Borc Ödənişi', :a, 'Kassa', :d, :u, :time, :tst)", {"a":float(t_amt), "d":t_desc, "u":u, "time":get_baku_now(), "tst":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Borc Ödənişi', :a, 'Nisyə / Borc', :d, :u, :time, :tst)", {"a":float(t_amt), "d":"Kassadan ödənildi", "u":u, "time":get_baku_now(), "tst":is_t_active})
                    
                    elif "Bank Kartından ➡️ 📝 Borcun Ödənməsinə" in t_dir:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Borc Ödənişi', :a, 'Bank Kartı', :d, :u, :time, :tst)", {"a":float(t_amt), "d":t_desc, "u":u, "time":get_baku_now(), "tst":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Borc Ödənişi', :a, 'Nisyə / Borc', :d, :u, :time, :tst)", {"a":float(t_amt), "d":"Kartdan ödənildi", "u":u, "time":get_baku_now(), "tst":is_t_active})
                        if has_comm and comm_amt > 0:
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Transfer xərci', :u, :time, :tst)", {"a":float(comm_amt), "u":u, "time":get_baku_now(), "tst":is_t_active})
                    
                    st.success("Transfer İcra Edildi!"); time.sleep(1); st.rerun()

    st.markdown("---")
    st.subheader("✏️ Maliyyə Əməliyyatları (Düzəliş & Silmə)")
    st.info("Səhv yazılmış əməliyyatları seçin, məbləğini/qeydini dəyişib 'Yadda Saxla' basın və ya tamamilə silin.")
    
    today = get_baku_now().date()
    start_of_month = today.replace(day=1)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        date_filter = st.selectbox("Tarix Aralığı", ["Bu Ay", "Bu Gün", "Keçən Ay", "Bütün Zamanlar", "Xüsusi Aralıq"])
    with f_col2:
        type_filter = st.selectbox("Əməliyyat Növü", ["Hamısı", "Məxaric (Çıxış)", "Mədaxil (Giriş)"])
    with f_col3:
        src_filter = st.selectbox("Mənbə", ["Hamısı", "Kassa", "Bank Kartı", "Seyf", "Nisyə / Borc"])

    hide_pos = st.checkbox("🛒 Gündəlik POS satışlarını cədvəldə gizlət", value=True)

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

    query = f"SELECT * FROM finance WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {test_filter}"
    params = {"sd": sd, "ed": ed}
    
    if type_filter == "Məxaric (Çıxış)": query += " AND type='out'"
    elif type_filter == "Mədaxil (Giriş)": query += " AND type='in'"
    if src_filter != "Hamısı":
        query += " AND source=:src"
        params["src"] = src_filter
        
    query += " ORDER BY created_at DESC"
    fin_df = run_query(query, params)
    
    if hide_pos and not fin_df.empty:
        fin_df = fin_df[~fin_df['description'].isin(['POS Satış', 'Masa Satışı', 'Kart Satış Komissiyası', 'Masa Satış Komissiyası'])]
    
    if not fin_df.empty and (type_filter in ["Hamısı", "Məxaric (Çıxış)"]):
        expenses_only = fin_df[fin_df['type'] == 'out']
        if not expenses_only.empty:
            exp_grouped = expenses_only.groupby('category')['amount'].sum().reset_index()
            exp_grouped = exp_grouped[~exp_grouped['category'].isin(['Daxili Transfer', 'Borc Ödənişi', 'Sistem Korreksiyası', 'Təsisçi Çıxarışı', 'Bank Komissiyası'])]
            
            if not exp_grouped.empty:
                st.markdown("**💸 Xərclərin Kateqoriyalar Üzrə Bölgüsü (Seçilmiş Aralıq)**")
                fig = px.pie(exp_grouped, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig, use_container_width=True)

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
                            expenses_str = ", ".join([f"{cat}: {amt:.2f} AZN" for cat, amt in exp_grouped.items() if cat not in ['Daxili Transfer', 'Borc Ödənişi']])
                        
                        prompt = f"""
                        Sən kofe şopunun baş maliyyəçisisən (CFO).
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

    if not fin_df.empty:
        disp_df = fin_df.copy()
        disp_df['Tip'] = disp_df['type'].apply(lambda x: "🟢 Giriş" if x=='in' else "🔴 Çıxış")
        disp_df['Tarix'] = pd.to_datetime(disp_df['created_at']).dt.strftime('%d.%m.%Y %H:%M')
        
        edit_cols = ['id', 'Tarix', 'Tip', 'category', 'amount', 'source', 'description']
        display_df = disp_df[edit_cols].copy()
        display_df.insert(0, "Seç", False)
        
        edited_fin = st.data_editor(
            display_df, hide_index=True,
            column_config={"Seç": st.column_config.CheckboxColumn(required=True), "amount": st.column_config.NumberColumn("Məbləğ (₼)", format="%.2f")},
            disabled=['id', 'Tarix', 'Tip', 'source'], use_container_width=True, key="fin_editor"
        )
        
        sel_fin = edited_fin[edited_fin["Seç"]]
        c_f1, c_f2 = st.columns(2)
        
        if c_f1.button("💾 Seçilənlərə Düzəliş Et", type="primary"):
            for _, r in sel_fin.iterrows():
                run_action("UPDATE finance SET amount=:a, category=:c, description=:d WHERE id=:id", {"a":r['amount'], "c":r['category'], "d":r['description'], "id":r['id']})
            st.success("Yeniləndi!"); time.sleep(1.5); st.rerun()
            
        if not sel_fin.empty and c_f2.button("🗑️ Seçilənləri Sil"):
            for i in sel_fin['id'].tolist():
                run_action("DELETE FROM finance WHERE id=:id", {"id":int(i)})
            st.success("Silindi!"); time.sleep(1.5); st.rerun()
    else:
        st.write("Seçilmiş filtrlərə uyğun əməliyyat yoxdur.")
