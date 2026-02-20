import streamlit as st
import pandas as pd
import datetime
import time
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now
from auth import admin_confirm_dialog

def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar")
    
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    sales = run_query("SELECT * FROM sales WHERE created_at BETWEEN :s AND :e ORDER BY created_at DESC", {"s":ts_start, "e":ts_end})
    
    if not sales.empty:
        total_rev = sales['total'].sum()
        cash_rev = sales[sales['payment_method']=='Cash']['total'].sum()
        card_rev = sales[sales['payment_method']=='Card']['total'].sum()
        staff_rev = sales[sales['payment_method']=='Staff']['total'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cəmi Satış", f"{total_rev:.2f} ₼")
        c2.metric("Nağd", f"{cash_rev:.2f} ₼")
        c3.metric("Kart", f"{card_rev:.2f} ₼")
        c4.metric("Personal", f"{staff_rev:.2f} ₼")
        
        st.divider()
        
        tab1, tab2 = st.tabs(["📋 Çeklər (Satış Siyahısı)", "☕ Satılan Məhsullar (Detallı)"])
        
        with tab1:
            st.write("Səhv vurulmuş çeki seçib silə bilərsiniz.")
            sales_disp = sales.copy()
            sales_disp.insert(0, "Seç", False)
            
            # Data Editor for Deletion
            ed_sales = st.data_editor(sales_disp, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, disabled=["id", "items", "total", "payment_method", "created_at", "cashier"], use_container_width=True, key="sales_admin_ed")
            sel_sales = ed_sales[ed_sales["Seç"]]; sel_s_ids = sel_sales['id'].tolist()
            
            if len(sel_s_ids) > 0 and st.session_state.role == 'admin':
                if st.button(f"🗑️ Seçilən {len(sel_s_ids)} Satışı Sil", type="primary"):
                    for i in sel_s_ids: run_action("DELETE FROM sales WHERE id=:id", {"id":int(i)})
                    st.success("Satış(lar) silindi! 🗑️"); time.sleep(1); st.rerun()

        with tab2:
            st.write("Bu aralıqda nədən neçə ədəd satılıb:")
            item_counts = {}
            for items_str in sales['items']:
                if not isinstance(items_str, str) or items_str == "Table Order": continue
                parts = items_str.split(", ")
                for p in parts:
                    if " x" in p:
                        try:
                            name_part, qty_part = p.rsplit(" x", 1)
                            qty = int(qty_part.split()[0]) # [Eko Mod] kimi yazıları atmaq üçün
                            item_counts[name_part] = item_counts.get(name_part, 0) + qty
                        except: pass
            
            if item_counts:
                df_items = pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).sort_values(by='Say', ascending=False)
                st.dataframe(df_items, hide_index=True, use_container_width=True)
            else:
                st.info("Detallı məhsul tapılmadı.")
    else:
        st.info("Seçilmiş tarixdə satış yoxdur.")

def render_z_report_page():
    st.subheader("📊 Z-Hesabat (Növbənin Bağlanması)")
    
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)
    
    st.info(f"Növbə: {sh_start_z.strftime('%d %b %H:%M')} - {sh_end_z.strftime('%d %b %H:%M')}")
    
    # 1. Satış Məlumatları
    s_cash = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
    s_card = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
    s_staff = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Staff' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
    total_sales = float(s_cash) + float(s_card) + float(s_staff)
    
    # 2. Xərc və Mədaxil
    f_out = run_query("SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
    f_in = run_query("SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
    
    # 3. Kassa Vəziyyəti
    opening_limit = float(get_setting("cash_limit", "0.0"))
    expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)
    
    # Ekrana Yazdırmaq
    c1, c2 = st.columns(2)
    c1.metric("CƏMİ SATIŞ", f"{total_sales:.2f} ₼")
    c1.write(f"💳 Kartla: {float(s_card):.2f} ₼")
    c1.write(f"💵 Nağd: {float(s_cash):.2f} ₼")
    c1.write(f"👥 Personal: {float(s_staff):.2f} ₼")
    
    c2.metric("KASSADA OLMALIDIR", f"{expected_cash:.2f} ₼")
    c2.write(f"Səhər (Açılış): {opening_limit:.2f} ₼")
    c2.write(f"Kassaya Giriş (+): {float(f_in):.2f} ₼")
    c2.write(f"Kassadan Çıxış (-): {float(f_out):.2f} ₼")
    
    st.divider()
    
    if st.button("🔴 Günü Bitir və Sıfırla (Z-Hesabat)", type="primary"):
        st.session_state.z_report_active = True
        st.rerun()
        
    if st.session_state.z_report_active:
        @st.dialog("Təsdiqləyirsiniz?")
        def z_final_d():
            st.warning("⚠️ Gün bağlanacaq və 'Kassada Olmalıdır' məbləği sabahın yeni limiti olacaq.")
            if st.button("✅ Bəli, Günü Bitir"):
                # Növbəti gün üçün kassa limitini yenilə
                set_setting("cash_limit", str(expected_cash))
                set_setting("last_z_report_time", get_baku_now().isoformat())
                
                st.session_state.z_report_active=False
                st.success("GÜN UĞURLA BAĞLANDI! 🌙")
                time.sleep(2)
                st.rerun()
        z_final_d()
