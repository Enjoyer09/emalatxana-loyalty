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
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    # Müştəri məlumatları ilə birlikdə SQL sorğusu
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
        
        bank_fee_rate = 0.02 
        real_sales['bank_fee'] = real_sales.apply(lambda x: x['total'] * bank_fee_rate if x['payment_method'] == 'Card' else 0, axis=1)
        real_sales['net_total'] = real_sales['total'] - real_sales['bank_fee']
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cəmi Brutto", f"{real_sales['original_total'].sum():.2f} ₼")
        c2.metric("Cəmi Endirim", f"{real_sales['discount_amount'].sum():.2f} ₼")
        c3.metric("Yekun Net", f"{real_sales['net_total'].sum():.2f} ₼")
        c4.metric("Nağd", f"{real_sales[real_sales['payment_method']=='Cash']['total'].sum():.2f} ₼")
        
        st.divider()
        tab1, tab2 = st.tabs(["📋 Çeklər", "☕ Məhsullar"])
        
        with tab1:
            sales_disp = sales.copy()
            sales_disp['Net'] = sales_disp.apply(lambda x: x['total'] * 0.98 if x['payment_method'] == 'Card' else x['total'], axis=1)
            sales_disp['Test?'] = sales_disp['is_test'].apply(lambda x: '🧪' if x else '')
            
            # 📋 Müştəri ID, Ulduz və Endirim sütunları əlavə edildi
            display_df = sales_disp[[
                'id', 'created_at', 'customer_card_id', 'current_stars', 'items', 
                'original_total', 'discount_amount', 'total', 'payment_method', 'Test?'
            ]].copy()
            display_df.insert(0, "Seç", False)
            
            edited_sales = st.data_editor(
                display_df, hide_index=True, use_container_width=True, key="sales_ed_v_final",
                column_config={
                    "customer_card_id": "Müştəri ID",
                    "current_stars": "Mövcud ⭐",
                    "original_total": "Məbləğ",
                    "discount_amount": "Endirim",
                    "total": "Yekun Ödəniş",
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM HH:mm")
                }
            )
            
            # Silmə və Düzəliş funksiyaları... (Hissə 2-də davam edir)
sel_s_ids = edited_sales[edited_sales["Seç"]]['id'].tolist()
            if st.session_state.role in ['admin', 'manager'] and len(sel_s_ids) > 0:
                col_b1, col_b2 = st.columns(2)
                if len(sel_s_ids) == 1 and col_b1.button("✏️ Düzəliş"):
                    st.session_state.sale_edit_id = int(sel_s_ids[0]); st.rerun()
                if col_b2.button(f"🗑️ Satışları Sil"):
                    st.session_state.sales_to_delete = sel_s_ids; st.rerun()

            # Dialoq menecerləri
            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    @st.dialog("✏️ Çek Redaktəsi")
                    def edit_dialog(r):
                        with st.form("ed_f"):
                            e_t = st.number_input("Yekun Məbləğ", value=float(r['total']))
                            e_p = st.selectbox("Ödəniş", ["Cash", "Card", "Staff"], index=["Cash", "Card", "Staff"].index(r['payment_method']))
                            if st.form_submit_button("Yadda Saxla"):
                                run_action("UPDATE sales SET total=:t, payment_method=:p WHERE id=:id", {"t":e_t, "p":e_p, "id":r['id']})
                                st.session_state.sale_edit_id = None; st.success("Dəyişdi!"); time.sleep(1); st.rerun()
                    edit_dialog(s_res.iloc[0])

        with tab2:
            # Məhsul analitikası...
            item_counts = {}
            for items_str in real_sales['items']:
                if isinstance(items_str, str):
                    for p in items_str.split(", "):
                        if " x" in p:
                            try:
                                n, q = p.rsplit(" x", 1); item_counts[n] = item_counts.get(n, 0) + int(q.split()[0])
                            except: pass
            if item_counts:
                st.bar_chart(pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).set_index('Məhsul'))

def render_z_report_page():
    # Z-Hesabat kodu pos (3).py faylındakı yeni Z-dialoqu ilə sinxronlaşdırılmalıdır
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    # ... (Z-Hesabat detalları və Samir-in maaş düyməsi bura daxildir)            
