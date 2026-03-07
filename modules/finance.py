import streamlit as st
import pandas as pd
import datetime, time, io
import plotly.express as px
import google.generativeai as genai
from gtts import gTTS
from database import run_query, run_action, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range, get_baku_now

def render_finance_page():
    st.subheader("💰 Maliyyə Mərkəzi (Dəqiq Bank Uçotu)")
    
    # --- KASSA AÇILIŞI ---
    with st.expander("🔓 Səhər Kassanı Aç"):
        op_bal = st.number_input("Kassada nə qədər pul var? (AZN)", min_value=0.0, step=0.1)
        if st.button("✅ Kassanı Təsdiqlə"): 
            set_setting("cash_limit", str(op_bal))
            st.success(f"Gün {op_bal} ₼ ilə başladı!"); time.sleep(1); st.rerun()

    # --- BALANSLAR ---
    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə", "📅 Ümumi Balans"], horizontal=True)
    log_date = get_logical_date(); shift_start, shift_end = get_shift_range(log_date)
    cond = "AND created_at >= :d AND created_at < :e AND (is_test IS NULL OR is_test = FALSE)" if "Növbə" in view_mode else "AND (is_test IS NULL OR is_test = FALSE)"
    params = {"d":shift_start, "e":shift_end} if "Növbə" in view_mode else {}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {cond}", params).iloc[0]['s'] or 0.0
    e_cash = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_cash = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    disp_cash = float(get_setting("cash_limit", "0.0")) + float(s_cash) + float(i_cash) - float(e_cash)
    
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Card' {cond}", params).iloc[0]['s'] or 0.0
    e_card = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Emalatxana Kartı' AND type='out' {cond}", params).iloc[0]['e'] or 0.0
    i_card = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Emalatxana Kartı' AND type='in' {cond}", params).iloc[0]['i'] or 0.0
    disp_card = float(s_card) + float(i_card) - float(e_card)
    
    st.divider(); m1, m2 = st.columns(2)
    m1.metric("🏪 Kassada (Nəğd)", f"{disp_cash:.2f} ₼")
    m2.metric("💳 Emalatxana Kartı", f"{disp_card:.2f} ₼")

    # --- ƏMƏLİYYATLAR ---
    with st.expander("➕ Yeni Əməliyyat / Daxili Transfer", expanded=True):
        t_op, t_tr = st.tabs(["Standart Əməliyyat", "Daxili Transfer 🔄"])
        with t_op:
            with st.form("new_fin_trx", clear_on_submit=True):
                c1, c2, c3 = st.columns(3); f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"]); f_source = c2.selectbox("Mənbə", ["Kassa", "Emalatxana Kartı", "Laptop Market Kartı", "Seyf", "Investor"]); f_subj = c3.selectbox("Subyekt", SUBJECTS)
                c4, c5 = st.columns(2); f_cat = c4.selectbox("Kateqoriya", ["Market Alış-verişi", "Kartdan Karta Transfer", "Xammal Alışı", "Maaş/Avans", "Təsisçi Çıxarışı", "Digər"]); f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01)
                f_desc = st.text_input("Qeyd")
                if st.form_submit_button("Təsdiqlə"):
                    db_type, user, now, is_t = ('out' if "Məxaric" in f_type else 'in'), st.session_state.user, get_baku_now(), st.session_state.get('test_mode', False)
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)", {"t":db_type, "c":f_cat, "a":f_amt, "s":f_source, "d":f_desc, "u":user, "sb":f_subj, "time":now, "tst":is_t})
                    
                    # YENİ MƏNTİQ: Minimum 0.60 AZN və ya 0.5%
                    if db_type == 'out' and f_source == 'Emalatxana Kartı' and f_cat == 'Kartdan Karta Transfer':
                        comm = max(0.60, f_amt * 0.005)
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, :s, 'Transfer xərci', :u, :time, :tst)", {"a":comm, "s":f_source, "u":user, "time":now, "tst":is_t})
                    st.success("Qeyd olundu!"); time.sleep(1); st.rerun()

        with t_tr:
            with st.form("transfer_trx", clear_on_submit=True):
                t_dir = st.selectbox("Yön", ["💳 Kart ➡️ 🏪 Kassa", "🏪 Kassa ➡️ 💳 Kart"]); t_amt = st.number_input("Məbləğ", min_value=0.01)
                if st.form_submit_button("Transferi İcra Et"):
                    is_t, u, n = st.session_state.get('test_mode', False), st.session_state.user, get_baku_now()
                    if "Kart ➡️ Kassa" in t_dir:
                        comm = max(0.60, t_amt * 0.005)
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('out', 'Transfer', :a, 'Emalatxana Kartı', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Emalatxana Kartı', 'Nağdlaşdırma', :n, :is_t)", {"a":comm, "n":n, "is_t":is_t})
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('in', 'Transfer', :a, 'Kassa', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t})
                    else:
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('out', 'Transfer', :a, 'Kassa', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t})
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('in', 'Transfer', :a, 'Emalatxana Kartı', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t})
                    st.success("Köçürüldü!"); time.sleep(1); st.rerun()

    # --- HESABATLAR VƏ AI ---
    st.markdown("---")
    f_c1, f_c2 = st.columns(2); sd = f_c1.date_input("Başlanğıc", get_baku_now().date().replace(day=1)); ed = f_c2.date_input("Bitiş", get_baku_now().date())
    fin_df = run_query("SELECT * FROM finance WHERE DATE(created_at) BETWEEN :sd AND :ed AND (is_test IS NULL OR is_test = FALSE) ORDER BY created_at DESC", {"sd": sd, "ed": ed})
    
    if not fin_df.empty:
        total_comm = fin_df[fin_df['category'] == 'Bank Komissiyası']['amount'].sum()
        if total_comm > 0: st.warning(f"🏦 Ödənilən cəmi bank komissiyası: **{total_comm:.2f} ₼**")
        
        if st.button("🤖 AI CFO Analizi (Səsli)", type="primary", use_container_width=True):
            api_key = get_setting("gemini_api_key", "")
            if api_key:
                try:
                    genai.configure(api_key=api_key); model = genai.GenerativeModel('gemini-1.5-flash')
                    total_in, total_out = fin_df[fin_df['type'] == 'in']['amount'].sum(), fin_df[fin_df['type'] == 'out']['amount'].sum()
                    prompt = f"Gəlir {total_in} AZN, Xərc {total_out} AZN. Qısa maliyyə analizi ver."
                    resp = model.generate_content(prompt).text; st.info(resp)
                    tts = gTTS(text=resp, lang='tr'); fp = io.BytesIO(); tts.write_to_fp(fp); st.audio(fp)
                except Exception as e: st.error(f"AI Xətası: {e}")
        
        exp_only = fin_df[fin_df['type'] == 'out']
        if not exp_only.empty:
            fig = px.pie(exp_only.groupby('category')['amount'].sum().reset_index(), values='amount', names='category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(fin_df[['created_at', 'type', 'category', 'amount', 'source', 'description']], hide_index=True, use_container_width=True)
