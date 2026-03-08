import streamlit as st
import pandas as pd
import datetime, time
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system
from auth import admin_confirm_dialog

def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")
    
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())
    
    ts_s = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_e = datetime.datetime.combine(d2, datetime.time(23,59))
    
    q = "SELECT s.*, c.type FROM sales s LEFT JOIN customers c ON s.customer_card_id = c.card_id WHERE s.created_at BETWEEN :s AND :e ORDER BY s.created_at DESC"
    sales = run_query(q, {"s":ts_s, "e":ts_e})
    
    if not sales.empty:
        if 'is_test' not in sales.columns: sales['is_test'] = False
        real = sales[sales['is_test'] != True].copy()
        
        # Bank Faizi (2%) Hesablaması
        real['net'] = real.apply(lambda x: x['total'] * 0.98 if x['payment_method'] == 'Card' else x['total'], axis=1)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cəmi Brutto", f"{real['total'].sum():.2f} ₼")
        c2.metric("Cəmi Net", f"{real['net'].sum():.2f} ₼")
        c3.metric("Nağd", f"{real[real['payment_method']=='Cash']['total'].sum():.2f} ₼")
        c4.metric("Kart (Net)", f"{real[real['payment_method']=='Card']['net'].sum():.2f} ₼")
        
        tab1, tab2 = st.tabs(["📋 Çeklər", "☕ Məhsullar"])
        with tab1:
            disp = sales.copy()
            disp['Net'] = disp.apply(lambda x: x['total'] * 0.98 if x['payment_method'] == 'Card' else x['total'], axis=1)
            disp.insert(0, "Seç", False)
            ed = st.data_editor(disp[['Seç', 'id', 'created_at', 'cashier', 'items', 'total', 'Net', 'payment_method', 'note']], hide_index=True, use_container_width=True, key="an_ed_p1")
            
            sel = ed[ed["Seç"]]['id'].tolist()
            if st.session_state.role in ['admin', 'manager'] and sel:
                col1, col2 = st.columns(2)
                if len(sel) == 1 and col1.button("✏️ Düzəliş"):
                    st.session_state.sale_edit_id = int(sel[0]); st.rerun()
                if col2.button(f"🗑️ {len(sel)} Satışı Sil"):
                    st.session_state.sales_to_delete = sel; st.rerun()

            if st.session_state.get('sale_edit_id'):
                @st.dialog("✏️ Redaktə")
                def edit_d(sid):
                    r = run_query("SELECT * FROM sales WHERE id=:id", {"id":sid}).iloc[0]
                    with st.form("ed_f"):
                        t = st.number_input("Məbləğ", value=float(r['total']))
                        p = st.selectbox("Ödəniş", ["Cash", "Card", "Staff"], index=["Cash", "Card", "Staff"].index(r['payment_method']))
                        if st.form_submit_button("Saxla"):
                            run_action("UPDATE sales SET total=:t, payment_method=:p WHERE id=:id", {"t":t, "p":p, "id":sid})
                            st.session_state.sale_edit_id = None; st.success("Yadda qaldı!"); time.sleep(1); st.rerun()
                edit_d(st.session_state.sale_edit_id)

        with tab2:
            counts = {}
            for s in real['items']:
                if isinstance(s, str) and s != "Table Order":
                    for p in s.split(", "):
                        if " x" in p:
                            n, q = p.rsplit(" x", 1); counts[n] = counts.get(n, 0) + int(q.split()[0])
            if counts: st.bar_chart(pd.DataFrame(list(counts.items()), columns=['Məhsul', 'Say']).set_index('Məhsul'))
    else: st.info("Məlumat yoxdur.")
def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    ldz = get_logical_date(); ss_z, se_z = get_shift_range(ldz)
    cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    p = {"d":ss_z, "e":se_z}

    # Ümumi Hesablamalar
    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' {cond}", p).iloc[0]['s'] or 0.0
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method='Card' {cond}", p).iloc[0]['s'] or 0.0
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {cond}", p).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' {cond}", p).iloc[0]['s'] or 0.0
    exp_cash = float(get_setting("cash_limit", "0.0")) + float(s_cash) + float(f_in) - float(f_out)

    # 👤 STAFF ÜÇÜN FƏRDİ CƏDVƏL (BƏRPA EDİLDİ)
    if st.session_state.role == 'staff':
        st.info(f"Sizin bugünkü növbə göstəriciləriniz ({st.session_state.user})")
        my_sales = run_query(f"SELECT * FROM sales WHERE cashier=:u {cond} ORDER BY created_at DESC", {"u": st.session_state.user, "d": ss_z, "e": se_z})
        
        if not my_sales.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Mənim Satışım", f"{my_sales['total'].sum():.2f} ₼")
            m2.metric("Nağd", f"{my_sales[my_sales['payment_method']=='Cash']['total'].sum():.2f} ₼")
            m3.metric("Kart", f"{my_sales[my_sales['payment_method']=='Card']['total'].sum():.2f} ₼")
            
            st.dataframe(my_sales[['id', 'created_at', 'items', 'total', 'payment_method']], hide_index=True, use_container_width=True)
        else: st.warning("Bu növbədə hələ satışınız yoxdur.")

    # 🔑 ADMIN / MANAGER GÖRÜNÜŞÜ
    else:
        c1, c2 = st.columns(2)
        c1.metric("Kassa (Nağd)", f"{exp_cash:.2f} ₼")
        c2.metric("Kart (Net 98%)", f"{float(s_card)*0.98:.2f} ₼")
        
        with st.expander("💸 GÜNLÜK MAAŞ ÖDƏNİŞİ"):
            with st.form("sal_p2"):
                emp = st.selectbox("Staff", run_query("SELECT username FROM users")['username'].tolist())
                amt = st.number_input("Məbləğ", min_value=0.0)
                if st.form_submit_button("💰 Ödə"):
                    run_action("INSERT INTO finance (type, category, amount, source, created_by, description) VALUES ('out', 'Maaş', :a, 'Kassa', :u, :d)", {"a":amt, "u":st.session_state.user, "d":f"{emp} avans"})
                    st.success("Ödənildi!"); time.sleep(1); st.rerun()

    # X/Z Düymələri
    cx, cz = st.columns(2)
    if cx.button("🤝 Növbəni Təhvil Ver (X)", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_d():
            act = st.number_input("Kassadakı nağd:", value=float(exp_cash))
            if st.button("Təhvil Ver"):
                run_action("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash) VALUES (:hb, :ec, :ac)", {"hb":st.session_state.user, "ec":exp_cash, "ac":act})
                st.success("Təhvil verildi!"); time.sleep(1); st.rerun()
        x_d()

    if cz.button("🔴 Günü Bağla (Z)", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat")
        def z_d():
            act_z = st.number_input("Sabahkı açılış balansı:", value=float(exp_cash))
            if st.button("✅ Günü Bitir"):
                run_action("INSERT INTO z_reports (total_sales, cash_sales, card_sales, actual_cash, generated_by) VALUES (:ts, :cs, :crs, :ac, :gb)", {"ts":float(s_cash)+float(s_card), "cs":float(s_cash), "crs":float(s_card), "ac":act_z, "gb":st.session_state.user})
                set_setting("cash_limit", str(act_z)); set_setting("last_z_report_time", get_baku_now().isoformat())
                st.success("GÜN BAĞLANDI!"); time.sleep(1); st.rerun()
        z_d()        
