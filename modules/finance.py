import streamlit as st
import pandas as pd
import datetime, time, io, os
import plotly.express as px
import google.generativeai as genai
from gtts import gTTS
import bcrypt
from database import run_query, run_action, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range, get_baku_now, log_system

def render_finance_page():
    st.subheader("💰 Maliyyə Mərkəzi")
    
    is_t_active = st.session_state.get('test_mode', False)
    if is_t_active:
        st.warning("⚠️ Hazırda TEST rejimindəsiniz. Aşağıdakı balans və cədvəldə TEST əməliyyatları nəzərə alınır.")

    with st.expander("🌅 Kassa Açılışı (Günə Başla)", expanded=False):
        with st.form("open_register_form", clear_on_submit=True):
            c_open1, c_open2 = st.columns([3, 1])
            open_amt = c_open1.number_input("Səhər kassada olan məbləğ (Açılış balansı - AZN)", min_value=0.0, step=1.0)
            if c_open2.form_submit_button("Kassanı Aç"):
                run_action(
                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Kassa Açılışı', :a, 'Kassa', 'Səhər açılışı', :u, :time, :tst)", 
                    {"a": open_amt, "u": st.session_state.user, "time": get_baku_now(), "tst": is_t_active}
                )
                try: log_system(st.session_state.user, f"Kassa açılışı edildi: {open_amt} ₼")
                except: pass
                st.success(f"Günə başlanıldı! Kassa {open_amt} ₼ olaraq qeyd edildi.")
                time.sleep(1); st.rerun()

    if st.session_state.role in ['admin', 'staff', 'manager']:
        with st.expander("🌙 Smeni Bağla və Maaşı Çıxar", expanded=False):
            with st.form("close_shift_form", clear_on_submit=True):
                default_wage = 25.0 if st.session_state.role in ['manager', 'admin'] else 20.0
                c_close1, c_close2 = st.columns([3, 1])
                wage_amt = c_close1.number_input("Günlük Maaş (AZN)", value=default_wage, min_value=0.0, step=1.0)
                if c_close2.form_submit_button("Maaşı Çıxar və Bağla"):
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)", 
                        {"a": wage_amt, "u": st.session_state.user, "subj": st.session_state.user, "time": get_baku_now(), "tst": is_t_active}
                    )
                    try: log_system(st.session_state.user, f"Smen bağlandı və maaş çıxarıldı: {wage_amt} ₼")
                    except: pass
                    st.success(f"Smen bağlandı! {wage_amt} ₼ kassa xərci olaraq qeyd edildi.")
                    time.sleep(1); st.rerun()
    
    b_date = st.date_input("Hansı tarixə qədərki balansı görmək istəyirsiniz?", get_baku_now().date())
    b_end = datetime.datetime.combine(b_date, datetime.time(23,59,59))
    
    test_filter = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
    cond = f"AND created_at <= :e {test_filter}"
    p = {"e": b_end}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Cash', 'Nəğd') {cond}", p).iloc[0]['s'] or 0.0
    e_cash = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", p).iloc[0]['e'] or 0.0
    i_cash = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category != 'Kassa Açılışı' {cond}", p).iloc[0]['i'] or 0.0
    disp_cash = float(s_cash) + float(i_cash) - float(e_cash)
    
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Card', 'Kart') {cond}", p).iloc[0]['s'] or 0.0
    e_card = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Emalatxana Kartı' AND type='out' {cond}", p).iloc[0]['e'] or 0.0
    i_card = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Emalatxana Kartı' AND type='in' AND category != 'Kassa Açılışı' {cond}", p).iloc[0]['i'] or 0.0
    disp_card = float(s_card) + float(i_card) - float(e_card)

    inv_out = run_query(f"SELECT SUM(amount) as e FROM finance WHERE source IN ('Investor', 'Laptop Market Kartı') AND type='out' {cond}", p).iloc[0]['e'] or 0.0
    inv_in = run_query(f"SELECT SUM(amount) as i FROM finance WHERE source IN ('Investor', 'Laptop Market Kartı') AND type='in' {cond}", p).iloc[0]['i'] or 0.0
    inv_debt = float(inv_out) - float(inv_in)

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric(f"🏪 Kassada (Nağd)", f"{disp_cash:.2f} ₼")
    m2.metric(f"💳 Emalatxana Kartı", f"{disp_card:.2f} ₼")
    m3.metric(f"🕴️ İnvestor (Borc)", f"{inv_debt:.2f} ₼")

    default_cats = "Maaş/Avans,Xammal Alışı,Kommunal xərclər,İşıq pulu,Su pulu,İnternet,Market Alış-verişi,Kartdan Karta Transfer,Təsisçi Çıxarışı,Digər"
    saved_cats = get_setting("finance_cats", default_cats)
    cat_list = [c.strip() for c in saved_cats.split(",") if c.strip()]
    
    default_subjs = ",".join(SUBJECTS) if SUBJECTS else "Təsisçi,İşçi,Müştəri,Dövlət,Digər"
    saved_subjs = get_setting("finance_subjs", default_subjs)
    subj_list = [s.strip() for s in saved_subjs.split(",") if s.strip()]

    with st.expander("➕ Yeni Əməliyyat / Daxili Transfer", expanded=True):
        t_op, t_tr = st.tabs(["Standart Əməliyyat", "Daxili Transfer 🔄"])
        
        with t_op:
            c1, c2, c3 = st.columns(3)
            f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"])
            f_source = c2.selectbox("Mənbə", ["Kassa", "Emalatxana Kartı", "Laptop Market Kartı", "Seyf", "Investor"])
            
            f_subj_sel = c3.selectbox("Subyekt", subj_list + ["➕ Yeni əlavə et..."])
            if f_subj_sel == "➕ Yeni əlavə et...":
                final_subj = c3.text_input("Yeni Subyektin Adını Yazın (Yadda qalacaq)")
            else:
                final_subj = f_subj_sel
            
            c4, c5 = st.columns(2)
            f_cat_sel = c4.selectbox("Kateqoriya", cat_list + ["➕ Yeni əlavə et..."])
            if f_cat_sel == "➕ Yeni əlavə et...":
                final_cat = c4.text_input("Yeni Kateqoriyanın Adını Yazın (Yadda qalacaq)")
            else:
                final_cat = f_cat_sel
                
            f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01)
            f_desc = st.text_input("Qeyd")
            
            if st.button("Standart Əməliyyatı Təsdiqlə", type="primary", use_container_width=True):
                if not final_subj or not final_cat:
                    st.error("Subyekt və Kateqoriya boş ola bilməz!")
                else:
                    if final_subj not in subj_list:
                        set_setting("finance_subjs", saved_subjs + "," + final_subj)
                    if final_cat not in cat_list:
                        set_setting("finance_cats", saved_cats + "," + final_cat)
                        
                    db_type, user, now = ('out' if "Məxaric" in f_type else 'in'), st.session_state.user, get_baku_now()
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)", {"t":db_type, "c":final_cat, "a":f_amt, "s":f_source, "d":f_desc, "u":user, "sb":final_subj, "time":now, "tst":is_t_active})
                    
                    if db_type == 'out' and f_source == 'Emalatxana Kartı' and final_cat == 'Kartdan Karta Transfer':
                        comm = max(0.60, f_amt * 0.005)
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, :s, 'Transfer xərci', :u, :sb, :time, :tst)", {"a":comm, "s":f_source, "u":user, "sb":final_subj, "time":now, "tst":is_t_active})
                    st.success("Qeyd olundu!"); time.sleep(1); st.rerun()

        with t_tr:
            with st.form("transfer_trx", clear_on_submit=True):
                t_dir = st.selectbox("Yön", ["🕴️ İnvestor ➡️ 🏪 Kassa", "🏪 Kassa ➡️ 🕴️ İnvestor", "💳 Kart ➡️ 🏪 Kassa", "🏪 Kassa ➡️ 💳 Kart"])
                t_amt = st.number_input("Məbləğ", min_value=0.01)
                t_reason = st.selectbox("Transfer Səbəbi", ["Kassa bərpası", "İnvestisiya (Aylıq büdcə)", "Təsisçi Çıxarışı", "Şəxsi nağdlaşdırma", "Xammal üçün", "Digər"])
                has_comm = st.checkbox("Nağdlaşdırma komissiyası tutulsun? (Min 0.60 ₼, Yalnız Kart-Kassa üçün)")
                
                if st.form_submit_button("Transferi İcra Et"):
                    u, n = st.session_state.user, get_baku_now()
                    if t_dir == "🕴️ İnvestor ➡️ 🏪 Kassa":
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('out', 'İnvestisiya', :a, 'Investor', :d, :n, :is_t)", {"a":t_amt, "d":t_reason, "n":n, "is_t":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('in', 'İnvestisiya', :a, 'Kassa', :d, :n, :is_t)", {"a":t_amt, "d":t_reason, "n":n, "is_t":is_t_active})
                    elif t_dir == "🏪 Kassa ➡️ 🕴️ İnvestor":
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('out', 'Təsisçi Çıxarışı', :a, 'Kassa', :d, :n, :is_t)", {"a":t_amt, "d":t_reason, "n":n, "is_t":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('in', 'Təsisçi Çıxarışı', :a, 'Investor', :d, :n, :is_t)", {"a":t_amt, "d":t_reason, "n":n, "is_t":is_t_active})
                    elif t_dir == "💳 Kart ➡️ 🏪 Kassa":
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('out', 'Transfer', :a, 'Emalatxana Kartı', :d, :n, :is_t)", {"a":t_amt, "d":t_reason, "n":n, "is_t":is_t_active})
                        if has_comm:
                            comm = max(0.60, t_amt * 0.005)
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Emalatxana Kartı', 'Nağdlaşdırma', :n, :is_t)", {"a":comm, "n":n, "is_t":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('in', 'Transfer', :a, 'Kassa', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t_active})
                    elif t_dir == "🏪 Kassa ➡️ 💳 Kart":
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('out', 'Transfer', :a, 'Kassa', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t_active})
                        run_action("INSERT INTO finance (type, category, amount, source, created_at, is_test) VALUES ('in', 'Transfer', :a, 'Emalatxana Kartı', :n, :is_t)", {"a":t_amt, "n":n, "is_t":is_t_active})
                    st.success("Transfer uğurla tamamlandı!"); time.sleep(1); st.rerun()

    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🛠️ Keçmişi Təmir Et (Təkcə Admin üçün)"):
            kassa_ins = run_query(f"SELECT id, created_at, category, amount, description FROM finance WHERE source='Kassa' AND type='in' AND category != 'İnvestisiya (Təmirli)' AND category != 'Kassa Açılışı' {test_filter} ORDER BY created_at DESC LIMIT 30")
            if not kassa_ins.empty:
                for idx, row in kassa_ins.iterrows():
                    c_t1, c_t2, c_t3, c_t4 = st.columns([2, 2, 3, 3])
                    c_t1.write(row['created_at'].strftime("%d.%m.%Y"))
                    c_t2.write(f"{row['amount']} ₼")
                    c_t3.write(row['category'] or "-")
                    if c_t4.button("İnvestor Transferinə Çevir", key=f"fix_{row['id']}"):
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_at, is_test) VALUES ('out', 'Təmir Transferi', :a, 'Investor', 'Kassa mədaxili bərpası', :n, :is_t)", {"a": row['amount'], "n": get_baku_now(), "is_t": is_t_active})
                        run_action("UPDATE finance SET category = 'İnvestisiya (Təmirli)' WHERE id=:id", {"id": row['id']})
                        st.success("Düzəldildi! İnvestor borcu artdı."); time.sleep(1); st.rerun()

    st.markdown("---")
    st.subheader("🔍 Maliyyə Hesabatları")
    f_c1, f_c2 = st.columns(2)
    sd = f_c1.date_input("Hesabat Başlanğıc Tarixi", get_baku_now().date().replace(day=1))
    ed = f_c2.date_input("Hesabat Bitiş Tarixi", get_baku_now().date())
    
    fin_df = run_query(f"SELECT id, created_at, type, category, amount, source, description, created_by, is_test FROM finance WHERE DATE(created_at) BETWEEN :sd AND :ed {test_filter} ORDER BY created_at DESC", {"sd": sd, "ed": ed})
    
    if not fin_df.empty:
        total_comm = fin_df[fin_df['category'] == 'Bank Komissiyası']['amount'].sum()
        if total_comm > 0: st.warning(f"🏦 Bu aralıqda ödənilən cəmi bank komissiyası: **{total_comm:.2f} ₼**")
        
        api_key = os.environ.get("GEMINI_API_KEY") or get_setting("gemini_api_key", "")
        if not api_key:
            new_key = st.text_input("Gemini API Key daxil edin:", type="password")
            if st.button("API Key-i Yadda Saxla"):
                set_setting("gemini_api_key", new_key)
                st.success("Yadda saxlanıldı!"); time.sleep(1); st.rerun()
        else:
            if st.button("🤖 AI CFO Analizi (Səsli)", type="primary", use_container_width=True):
                try:
                    genai.configure(api_key=api_key); model = genai.GenerativeModel('gemini-1.5-flash')
                    total_in = fin_df[fin_df['type'] == 'in']['amount'].sum()
                    total_out = fin_df[fin_df['type'] == 'out']['amount'].sum()
                    prompt = f"Maliyyə hesabatı: Gəlir {total_in} AZN, Xərc {total_out} AZN. {sd} və {ed} tarixləri arasındakı vəziyyət haqqında çox qısa, səmimi və professional maliyyə tövsiyəsi ver."
                    resp = model.generate_content(prompt).text; st.info(resp)
                    tts = gTTS(text=resp, lang='tr'); fp = io.BytesIO(); tts.write_to_fp(fp); st.audio(fp)
                except Exception as e: 
                    if st.button("API Key-i Sıfırla"):
                        run_action("DELETE FROM settings WHERE key='gemini_api_key'")
                        st.rerun()
        
        exp_only = fin_df[fin_df['type'] == 'out']
        if not exp_only.empty:
            fig = px.pie(exp_only.groupby('category')['amount'].sum().reset_index(), values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
            fig.update_layout(height=350, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
            
        if st.session_state.role in ['admin', 'manager']:
            fin_disp = fin_df.copy()
            fin_disp.insert(0, "Seç", False)
            edited_fin = st.data_editor(fin_disp, hide_index=True, use_container_width=True, disabled=['id', 'created_at', 'type', 'category', 'amount', 'source', 'description', 'created_by'], key="fin_editor")
            
            sel_ids = edited_fin[edited_fin["Seç"]]['id'].tolist()
            if sel_ids:
                col_del, col_edit = st.columns(2)
                if col_del.button(f"🗑️ Seçilmiş {len(sel_ids)} qeydi sil", type="primary"):
                    st.session_state.fin_to_del = sel_ids
                    st.rerun()
                    
                if len(sel_ids) == 1:
                    if col_edit.button("✏️ Seçilmiş qeydi düzəlt"):
                        st.session_state.fin_to_edit = sel_ids[0]
                        st.rerun()
                elif len(sel_ids) > 1:
                    col_edit.warning("Düzəliş etmək üçün yalnız 1 qeyd seçin.")

            if st.session_state.get('fin_to_del'):
                @st.dialog("⚠️ Maliyyə Qeydini Sil")
                def del_fin_d():
                    pwd = st.text_input("Admin Şifrəsi", type="password")
                    reason = st.text_input("Silinmə Səbəbi")
                    if st.button("Təsdiqlə və Sil", type="primary"):
                        try:
                            admin_hash = run_query("SELECT password FROM users WHERE username='admin'").iloc[0]['password']
                            if bcrypt.checkpw(pwd.encode('utf-8'), admin_hash.encode('utf-8')) or pwd == os.environ.get("ADMIN_PASS", "admin123"):
                                if len(reason.strip()) < 3:
                                    st.error("Səbəb qeyd edilməlidir!")
                                else:
                                    for fid in st.session_state.fin_to_del:
                                        run_action("DELETE FROM finance WHERE id=:id", {"id": int(fid)})
                                        try:
                                            log_system(st.session_state.user, f"Maliyyə silindi (ID: {fid}). Səbəb: {reason}")
                                        except:
                                            pass
                                    st.session_state.fin_to_del = None
                                    time.sleep(1)
                                    st.rerun()
                            else:
                                st.error("Şifrə yalnışdır!")
                        except Exception as e:
                            st.error(f"Xəta: {e}")
                del_fin_d()

            if st.session_state.get('fin_to_edit'):
                @st.dialog("✏️ Maliyyə Qeydini Düzəlt")
                def edit_fin_d():
                    fid = st.session_state.fin_to_edit
                    row_df = run_query("SELECT * FROM finance WHERE id=:id", {"id": fid})
                    if row_df.empty:
                        st.error("Qeyd tapılmadı.")
                        if st.button("Bağla"):
                            st.session_state.fin_to_edit = None
                            st.rerun()
                        return
                        
                    row = row_df.iloc[0]
                    st.write(f"**Tarix:** {row['created_at']}")
                    
                    t_idx = 0 if row['type'] == 'out' else 1
                    e_type = st.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"], index=t_idx)
                    
                    src_opts = ["Kassa", "Emalatxana Kartı", "Laptop Market Kartı", "Seyf", "Investor"]
                    s_idx = src_opts.index(row['source']) if row['source'] in src_opts else 0
                    e_src = st.selectbox("Mənbə", src_opts, index=s_idx)
                    
                    e_cat = st.text_input("Kateqoriya", value=row['category'] if pd.notna(row['category']) else "")
                    e_amt = st.number_input("Məbləğ", value=float(row['amount']), min_value=0.01)
                    e_desc = st.text_input("Qeyd", value=row['description'] if pd.notna(row['description']) else "")
                    
                    pwd = st.text_input("Admin Şifrəsi", type="password")
                    
                    if st.button("Təsdiqlə və Düzəlt", type="primary"):
                        try:
                            admin_hash = run_query("SELECT password FROM users WHERE username='admin'").iloc[0]['password']
                            if bcrypt.checkpw(pwd.encode('utf-8'), admin_hash.encode('utf-8')) or pwd == os.environ.get("ADMIN_PASS", "admin123"):
                                db_type = 'out' if "Məxaric" in e_type else 'in'
                                run_action(
                                    "UPDATE finance SET type=:t, source=:s, category=:c, amount=:a, description=:d WHERE id=:id",
                                    {"t": db_type, "s": e_src, "c": e_cat, "a": e_amt, "d": e_desc, "id": int(fid)}
                                )
                                try:
                                    log_system(st.session_state.user, f"Maliyyə düzəlişi (ID: {fid}). Yeni: {db_type}, {e_amt} ₼, {e_cat}")
                                except:
                                    pass
                                st.session_state.fin_to_edit = None
                                st.success("Qeyd uğurla yeniləndi!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Şifrə yalnışdır!")
                        except Exception as e:
                            st.error(f"Xəta: {e}")
                edit_fin_d()

        else:
            st.dataframe(fin_df[['created_at', 'type', 'category', 'amount', 'source', 'description', 'created_by']], hide_index=True, use_container_width=True)
