# modules/analytics.py
import streamlit as st
import pandas as pd
import datetime, time
import json
import google.generativeai as genai
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system
from auth import admin_confirm_dialog

def parse_items_for_display(items_str):
    if not items_str or items_str == "Table Order": return items_str
    try:
        items = json.loads(items_str)
        return ", ".join([f"{i['item_name']} x{i['qty']}" for i in items])
    except:
        return items_str

def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar (Net Monitor)")
    
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Analitika Audit (Satış Tendensiyaları və Mənfəət)"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin (Ayarlar bölməsindən).")
            else:
                if st.button("🔍 Dataları Skan Et və Mənfəəti Analiz Et", use_container_width=True):
                    with st.spinner("AI satış datalarını oxuyur..."):
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            recent = run_query("SELECT SUM(total) as t_rev, SUM(cogs) as t_cogs FROM sales WHERE created_at >= current_date - interval '7 days' AND (is_test IS NULL OR is_test=FALSE)")
                            if not recent.empty and recent.iloc[0]['t_rev']:
                                rev = float(recent.iloc[0]['t_rev'])
                                cogs = float(recent.iloc[0]['t_cogs'])
                                prompt = f"Sən biznes analitikisən. Son 7 günün satışı: {rev} AZN. Maya dəyəri (COGS): {cogs} AZN. Brutto mənfəət: {rev-cogs} AZN. Bu rəqəmləri dəyərləndir və mənfəət marjası haqqında qısa və professional rəy bildir."
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background: #1e2226; padding: 15px; border-left: 5px solid #28a745;'>{response.text}</div>", unsafe_allow_html=True)
                            else: st.info("Kifayət qədər data yoxdur.")
                        except Exception as e: st.error(e)

    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    query = """
        SELECT s.*, c.stars as current_stars, c.type as cust_type 
        FROM sales s 
        LEFT JOIN customers c ON s.customer_card_id = c.card_id 
        WHERE s.created_at BETWEEN :s AND :e
    """
    params = {"s":ts_start, "e":ts_end}
    
    if st.session_state.role == 'staff':
        query += " AND s.cashier = :u"
        params["u"] = st.session_state.user
    query += " ORDER BY s.created_at DESC"
    
    sales = run_query(query, params)
    
    if not sales.empty:
        if 'is_test' not in sales.columns: sales['is_test'] = False
        real_sales = sales[sales['is_test'] != True].copy()
        if 'cogs' not in real_sales.columns: real_sales['cogs'] = 0.0
        
        bank_fee_rate = 0.02 
        real_sales['bank_fee'] = real_sales.apply(lambda x: x['total'] * bank_fee_rate if x['payment_method'] in ['Card', 'Kart'] else 0, axis=1)
        real_sales['net_total'] = real_sales['total'] - real_sales['bank_fee']
        
        total_rev = real_sales['total'].sum()
        total_cogs = real_sales['cogs'].sum()
        total_bank_fee = real_sales['bank_fee'].sum()
        gross_profit = total_rev - total_cogs - total_bank_fee
        
        cash_sales = real_sales[real_sales['payment_method'].isin(['Cash', 'Nəğd'])]['total'].sum()
        card_sales = real_sales[real_sales['payment_method'].isin(['Card', 'Kart'])]['total'].sum()
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ümumi Satış", f"{total_rev:.2f} ₼")
        c2.metric("Nağd", f"{cash_sales:.2f} ₼")
        c3.metric("Kart", f"{card_sales:.2f} ₼")
        c4.metric("Maya (COGS)", f"{total_cogs:.2f} ₼")
        c5.metric("Brutto Mənfəət", f"{gross_profit:.2f} ₼")
        
        st.divider()
        tab1, tab2 = st.tabs(["📋 Çeklər", "☕ Məhsullar"])
        
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Net'] = sales_disp.apply(lambda x: x['total'] * 0.98 if x['payment_method'] in ['Card', 'Kart'] else x['total'], axis=1)
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            sales_disp['Oxunaqlı_Səbət'] = sales_disp['items'].apply(parse_items_for_display)
            
            cols_to_disp = ['id', 'created_at', 'cashier', 'customer_card_id', 'current_stars', 'Oxunaqlı_Səbət', 'original_total', 'discount_amount', 'total']
            if 'cogs' in sales_disp.columns: cols_to_disp.append('cogs')
            cols_to_disp.extend(['payment_method', 'Test?'])
            
            display_df = sales_disp[cols_to_disp].copy()
            display_df.insert(0, "Seç", False)
            
            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_ed_v_final",
                column_config={
                    "cashier": "İşçi (Staff)",
                    "customer_card_id": "Müştəri QR",
                    "current_stars": "Ulduz",
                    "Oxunaqlı_Səbət": "Sifariş Detalı",
                    "original_total": "Brutto",
                    "discount_amount": "Endirim",
                    "total": "Net Ödəniş",
                    "cogs": "Maya",
                    "payment_method": "Ödəniş",
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                }
            )
            
            sel_s_ids = edited_sales[edited_sales["Seç"]]['id'].tolist()
            if st.session_state.role in ['admin', 'manager'] and len(sel_s_ids) > 0:
                col_b1, col_b2 = st.columns(2)
                if len(sel_s_ids) == 1 and col_b1.button("✏️ Düzəliş"):
                    st.session_state.sale_edit_id = int(sel_s_ids[0])
                    st.rerun()
                if col_b2.button("🗑️ Satışları Sil"):
                    st.session_state.sales_to_delete = sel_s_ids
                    st.rerun()

            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    @st.dialog("✏️ Çek Redaktəsi")
                    def edit_dialog(r):
                        with st.form("ed_f"):
                            e_t = st.number_input("Yekun Məbləğ", value=float(r['total']))
                            e_p = st.selectbox("Ödəniş", ["Nəğd", "Kart", "Staff", "Cash", "Card"], index=["Nəğd", "Kart", "Staff", "Cash", "Card"].index(r['payment_method']) if r['payment_method'] in ["Nəğd", "Kart", "Staff", "Cash", "Card"] else 0)
                            if st.form_submit_button("Yadda Saxla"):
                                run_action("UPDATE sales SET total=:t, payment_method=:p WHERE id=:id", {"t":e_t, "p":e_p, "id":r['id']})
                                st.session_state.sale_edit_id = None
                                st.success("Dəyişdi!"); time.sleep(1); st.rerun()
                    edit_dialog(s_res.iloc[0])

            if st.session_state.get('sales_to_delete'):
                @st.dialog("⚠️ Satışı Sil")
                def del_dialog():
                    reason = st.selectbox("Silinmə Səbəbi:", ["Səhv vurulub / Test idi (Stoka qayıtsın)", "Zay məhsul (Stoka qayıtmasın)"])
                    if st.button("Təsdiqlə və Sil", type="primary"):
                        for sid in st.session_state.sales_to_delete:
                            s_row = run_query("SELECT items, is_test, total, payment_method, created_at FROM sales WHERE id=:id", {"id":sid})
                            if not s_row.empty:
                                row_data = s_row.iloc[0]
                                if "qayıtsın" in reason and not row_data['is_test']:
                                    try:
                                        parsed = json.loads(row_data['items'])
                                        for item in parsed:
                                            recs = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m", {"m":item.get('item_name')})
                                            for _, rc in recs.iterrows():
                                                run_action("UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name=:ing", {"q":float(rc['quantity_required'])*item.get('qty', 1), "ing":rc['ingredient_name']})
                                    except: pass
                                
                                if not row_data['is_test']:
                                    t_date = row_data['created_at']
                                    run_action("""
                                        DELETE FROM finance 
                                        WHERE description IN ('POS Satış', 'Masa Satışı', 'Kart Satış Komissiyası', 'Masa Satış Komissiyası', 'Kart Tip', 'Kart Tip (Staffa)') 
                                        AND ABS(EXTRACT(EPOCH FROM (created_at - :td))) < 60
                                    """, {"td": t_date})

                            run_action("DELETE FROM sales WHERE id=:id", {"id":sid})
                            try: log_system(st.session_state.user, f"Satış silindi (ID:{sid}). Səbəb: {reason}")
                            except: pass
                        st.session_state.sales_to_delete = None
                        st.success("Silindi!"); time.sleep(1); st.rerun()
                del_dialog()

        with tab2:
            item_counts = {}
            for items_str in real_sales['items']:
                if isinstance(items_str, str) and items_str != "Table Order":
                    try:
                        parsed_items = json.loads(items_str)
                        for item in parsed_items:
                            n = item.get('item_name')
                            item_counts[n] = item_counts.get(n, 0) + item.get('qty', 0)
                    except:
                        pass
            if item_counts:
                st.bar_chart(pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).set_index('Məhsul'))
    else:
        st.info("Məlumat tapılmadı.")

def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)
    
    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    params = {"d":sh_start_z, "e":sh_end_z}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {q_cond}", params).iloc[0]['s'] or 0.0
    s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {q_cond}", params).iloc[0]['s'] or 0.0
    try: s_cogs = run_query(f"SELECT SUM(cogs) as s FROM sales WHERE 1=1 {q_cond}", params).iloc[0]['s'] or 0.0
    except: s_cogs = 0.0
    
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond}", params).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {q_cond}", params).iloc[0]['s'] or 0.0
    
    opening_limit = float(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)

    if st.session_state.role == 'staff':
        my_sales = run_query(f"SELECT * FROM sales WHERE cashier=:u {q_cond} ORDER BY created_at DESC", {"u": st.session_state.user, "d": sh_start_z, "e": sh_end_z})
        if not my_sales.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Mənim Növbə Satışım", f"{my_sales['total'].sum():.2f} ₼")
            m2.metric("Nağd", f"{my_sales[my_sales['payment_method'].isin(['Nəğd', 'Cash'])]['total'].sum():.2f} ₼")
            m3.metric("Kart", f"{my_sales[my_sales['payment_method'].isin(['Kart', 'Card'])]['total'].sum():.2f} ₼")
            disp_cols = ['id', 'created_at', 'items', 'total', 'payment_method']
            if 'cogs' in my_sales.columns: disp_cols.append('cogs')
            st.dataframe(my_sales[disp_cols], hide_index=True, use_container_width=True)
        else:
            st.warning("Bu növbədə hələ satışınız yoxdur.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Kassa Açılış Balansı", f"{opening_limit:.2f} ₼")
        c2.metric("Nağd Satış", f"{float(s_cash):.2f} ₼")
        c3.metric("Kart Satış", f"{float(s_card):.2f} ₼")

        st.markdown("---")
        c4, c5, c6 = st.columns(3)
        c4.metric("Kassaya Mədaxil (Satışsız)", f"{float(f_in):.2f} ₼")
        c5.metric("Kassadan Məxaric (Xərc)", f"{float(f_out):.2f} ₼")
        c6.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")

        if st.session_state.role in ['admin', 'manager']:
            st.markdown(f"**Günlük Maya Dəyəri (COGS):** {float(s_cogs):.2f} ₼ | **Günlük Brutto Mənfəət:** {(float(s_cash)+float(s_card)) - float(s_cogs):.2f} ₼")
        
        with st.expander("💸 GÜNLÜK MAAŞ/AVANS ÖDƏ"):
            with st.form("salary_form_fix"):
                emp = st.selectbox("İşçi", run_query("SELECT username FROM users")['username'].tolist())
                amt = st.number_input("Məbləğ", min_value=0.0)
                if st.form_submit_button("💰 Ödə"):
                    run_action("INSERT INTO finance (type, category, amount, source, created_by, description, created_at) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', :u, :d, :t)", {"a":amt, "u":st.session_state.user, "d":f"{emp} avans", "t":get_baku_now()})
                    st.success("Ödənildi!"); time.sleep(1); st.rerun()

    cx, cz = st.columns(2)
    if cx.button("🤝 Növbəni Təhvil Ver (X)", use_container_width=True):
        @st.dialog("🤝 X-Hesabat")
        def x_dialog_fix():
            actual = st.number_input("Kassadakı nağd:", value=float(expected_cash))
            if st.button("Təsdiqlə"):
                run_action("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:hb, :ec, :ac, :t)", {"hb":st.session_state.user, "ec":expected_cash, "ac":actual, "t":get_baku_now()})
                st.success("Təhvil verildi!"); time.sleep(1); st.rerun()
        x_dialog_fix()

    if cz.button("🔴 Günü Bitir (Z)", type="primary", use_container_width=True):
        @st.dialog("🔴 Z-Hesabat və Maaş")
        def z_dialog_updated():
            st.write(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
            actual_z = st.number_input("Sabahkı açılış balansı (Kassada qalan):", value=float(expected_cash))
            
            default_wage = 25.0 if st.session_state.role in ['manager', 'admin'] else 20.0
            wage_amt = st.number_input("Götürülən Maaş (AZN):", value=default_wage, min_value=0.0)
            
            if st.button("✅ Günü Bağla və Maaşı Çıxar"):
                u = st.session_state.user
                now = get_baku_now()
                is_t = st.session_state.get('test_mode', False)
                
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)", 
                           {"a": wage_amt, "u": u, "subj": u, "time": now, "tst": is_t})
                
                try:
                    run_action("INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)",
                               {"ts":float(s_cash)+float(s_card), "cs":float(s_cash), "crs":float(s_card), "cogs":float(s_cogs), "ac":actual_z, "gb":u, "t":now})
                except: pass
                
                set_setting("cash_limit", str(actual_z))
                st.success("GÜN BAĞLANDI!"); time.sleep(1); st.rerun()
        z_dialog_updated()
