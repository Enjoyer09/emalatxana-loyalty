import streamlit as st
import pandas as pd
import datetime
import time
from database import run_query, run_action, get_setting, set_setting
from utils import get_logical_date, get_shift_range, get_baku_now, log_system
from auth import admin_confirm_dialog

def render_analytics_page():
    st.subheader("📊 Analitika və Satışlar")
    
    c_d1, c_d2 = st.columns(2)
    d1 = c_d1.date_input("Başlanğıc", get_logical_date())
    d2 = c_d2.date_input("Bitiş", get_logical_date())
    
    ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
    ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
    
    query = """
        SELECT s.*, c.type as cust_type, c.stars as cust_stars 
        FROM sales s 
        LEFT JOIN customers c ON s.customer_card_id = c.card_id 
        WHERE s.created_at BETWEEN :s AND :e 
        ORDER BY s.created_at DESC
    """
    sales = run_query(query, {"s":ts_start, "e":ts_end})
    
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
            st.info("💡 Məsləhət: Səhv vurulmuş çeki silə, yaxud cədvəlin üzərində dəyişiklik (Kassir, Məbləğ, Endirim və s.) edib yadda saxlaya bilərsiniz.")
            sales_disp = sales.copy()
            
            sales_disp['Müştəri Kodu'] = sales_disp['customer_card_id']
            sales_disp['Müştəri Tipi'] = sales_disp['cust_type'].fillna('').str.upper()
            sales_disp['Ulduz'] = sales_disp['cust_stars']
            
            sales_disp.loc[sales_disp['Müştəri Kodu'].isna() | (sales_disp['Müştəri Kodu'] == ''), 'Müştəri Tipi'] = ''
            sales_disp.loc[sales_disp['Müştəri Kodu'].isna() | (sales_disp['Müştəri Kodu'] == ''), 'Ulduz'] = None
            
            # Cədvəldə görünəcək sütunlar (Endirim də əlavə edildi!)
            cols_to_show = ['id', 'created_at', 'cashier', 'items', 'total', 'discount', 'payment_method', 'Müştəri Kodu', 'Müştəri Tipi', 'Ulduz', 'note']
            cols_to_show = [c for c in cols_to_show if c in sales_disp.columns]
            
            display_df = sales_disp[cols_to_show].copy()
            display_df.insert(0, "Seç", False)
            
            is_admin = st.session_state.role in ['admin', 'manager']
            disabled_cols = ['id', 'created_at', 'Müştəri Tipi', 'Ulduz'] if is_admin else cols_to_show
            
            edited_sales = st.data_editor(
                display_df, 
                hide_index=True, 
                column_config={
                    "Seç": st.column_config.CheckboxColumn(required=True),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM.YYYY HH:mm", disabled=True),
                    "cashier": st.column_config.TextColumn("Kassir (Kim Satıb)"),
                    "items": st.column_config.TextColumn("Məhsullar (Nə Satılıb)"),
                    "total": st.column_config.NumberColumn("Məbləğ", format="%.2f ₼"),
                    "discount": st.column_config.NumberColumn("Endirim", format="%.2f ₼"),
                    "payment_method": st.column_config.SelectboxColumn("Ödəniş Növü", options=["Cash", "Card", "Staff"]),
                    "note": st.column_config.TextColumn("Qeyd"),
                    "Ulduz": st.column_config.NumberColumn(format="%d ⭐", disabled=True)
                }, 
                disabled=disabled_cols, 
                use_container_width=True, 
                key="sales_admin_ed"
            )
            
            # --- 1. DƏYİŞİKLİKLƏRİ YADDA SAXLA (UPDATE) MƏNTİQİ ---
            # Burada 'Seç' checkbox-unu görməzlikdən gəlirik ki, ancaq söz/rəqəm dəyişəndə işə düşsün!
            if is_admin:
                real_edits_count = 0
                edited_indices = []
                
                if "sales_admin_ed" in st.session_state:
                    edits = st.session_state["sales_admin_ed"].get("edited_rows", {})
                    for row_idx_str, changes in edits.items():
                        # Əgər dəyişilən xana 'Seç' (Checkbox) DEYİLSƏ, deməli real dəyişiklikdir!
                        if any(k != 'Seç' for k in changes.keys()):
                            real_edits_count += 1
                            edited_indices.append(int(row_idx_str))
                
                if real_edits_count > 0:
                    st.warning(f"Cədvəldə {real_edits_count} sətirdə dəyişiklik etdiniz. Təsdiqləmək üçün düyməni sıxın.")
                    if st.button("💾 Dəyişiklikləri Yadda Saxla", type="primary"):
                        for idx in edited_indices:
                            row = edited_sales.iloc[idx]
                            real_id = int(row['id'])
                            
                            update_fields = "cashier=:c, items=:i, total=:t, payment_method=:p, customer_card_id=:cc, note=:n"
                            params = {
                                "c": row['cashier'], 
                                "i": row['items'], 
                                "t": float(row['total']), 
                                "p": row['payment_method'], 
                                "cc": row['Müştəri Kodu'] if pd.notna(row['Müştəri Kodu']) and str(row['Müştəri Kodu']).strip() else None,
                                "n": row['note'] if pd.notna(row['note']) and str(row['note']).strip() else None,
                                "id": real_id
                            }
                            
                            # Əgər bazada 'discount' sütunu varsa, onu da yeniləyirik
                            if 'discount' in row:
                                update_fields += ", discount=:d"
                                params["d"] = float(row['discount']) if pd.notna(row['discount']) else 0.0
                                
                            run_action(f"UPDATE sales SET {update_fields} WHERE id=:id", params)
                            log_system(st.session_state.user, f"SATIŞ REDAKTƏ EDİLDİ | ID: {real_id} | Yeni Kassir: {row['cashier']} | Yeni Məbləğ: {row['total']}")
                        
                        st.success("✅ Dəyişikliklər uğurla yadda saxlanıldı!")
                        time.sleep(1.5)
                        st.rerun()

            # --- 2. SİLİNMƏ (DELETE) MƏNTİQİ ---
            sel_sales = edited_sales[edited_sales["Seç"]]
            sel_s_ids = sel_sales['id'].tolist()
            
            if len(sel_s_ids) > 0 and is_admin:
                if st.button(f"🗑️ Seçilən {len(sel_s_ids)} Satışı Sil", type="primary"):
                    st.session_state.sales_to_delete = sel_s_ids
                    st.rerun()

            if st.session_state.get('sales_to_delete'):
                @st.dialog("⚠️ Satışı Silmə Səbəbi")
                def del_sale_dialog():
                    st.warning(f"Diqqət: {len(st.session_state.sales_to_delete)} ədəd satışı silirsiniz.")
                    reason = st.selectbox("Silinmə Səbəbi:", [
                        "Test / Sınaq (Xammal Anbara Geri Qaytarılsın)", 
                        "Səhv Vurulub (Xammal Anbara Geri Qaytarılsın)",
                        "Zay Məhsul / Dağıldı (Xammal Anbara QAYTARILMASIN)"
                    ])
                    note = st.text_input("Əlavə Qeyd (İstəyə bağlı)")
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("Təsdiqlə və Sil", type="primary"):
                        for i in st.session_state.sales_to_delete:
                            s_info = run_query("SELECT items, total FROM sales WHERE id=:id", {"id": int(i)})
                            if not s_info.empty:
                                i_str = s_info.iloc[0]['items']
                                t_val = s_info.iloc[0]['total']
                                log_system(st.session_state.user, f"SİLİNDİ | Səbəb: {reason} | Məbləğ: {t_val} AZN | Məhsullar: {i_str} | Qeyd: {note}")
                                
                                # Anbara qaytarma (Rollback)
                                if "Qaytarılsın" in reason and isinstance(i_str, str) and i_str != "Table Order":
                                    parts = i_str.split(", ")
                                    for p in parts:
                                        if " x" in p:
                                            try:
                                                name_part, qty_part = p.rsplit(" x", 1)
                                                qty = int(qty_part.split()[0])
                                                rec_df = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name = :m", {"m": name_part})
                                                for _, r_row in rec_df.iterrows():
                                                    ing_name = r_row['ingredient_name']
                                                    req_qty = float(r_row['quantity_required'])
                                                    total_return = req_qty * qty
                                                    run_action("UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name = :n", {"q": total_return, "n": ing_name})
                                            except Exception as e:
                                                pass
                                
                            run_action("DELETE FROM sales WHERE id=:id", {"id":int(i)})
                        st.session_state.sales_to_delete = None
                        st.success("Satış silindi və lazım idisə xammal anbara qaytarıldı!")
                        time.sleep(2)
                        st.rerun()
                    if c_btn2.button("Ləğv Et"):
                        st.session_state.sales_to_delete = None
                        st.rerun()
                del_sale_dialog()

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
                            qty = int(qty_part.split()[0])
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
    
    user_role = st.session_state.role
    
    if user_role == 'staff':
        my_sales_df = run_query("SELECT * FROM sales WHERE cashier=:u AND created_at>=:d AND created_at<:e ORDER BY created_at DESC", 
                                {"u": st.session_state.user, "d": sh_start_z, "e": sh_end_z})
        
        if not my_sales_df.empty:
            my_total = my_sales_df['total'].sum()
            my_cash = my_sales_df[my_sales_df['payment_method']=='Cash']['total'].sum()
            my_card = my_sales_df[my_sales_df['payment_method']=='Card']['total'].sum()
            
            st.markdown("### 👤 Mənim Bugünkü Satışlarım")
            c1, c2, c3 = st.columns(3)
            c1.metric("Cəmi Satışım", f"{my_total:.2f} ₼")
            c2.metric("Nağd", f"{my_cash:.2f} ₼")
            c3.metric("Kart", f"{my_card:.2f} ₼")
            
            st.divider()
            tab1, tab2 = st.tabs(["📋 Vurduğum Çeklər", "☕ Satdığım Məhsullar"])
            
            with tab1:
                disp_df = my_sales_df[['id', 'created_at', 'items', 'total', 'payment_method', 'note']].copy()
                st.dataframe(
                    disp_df, 
                    hide_index=True, 
                    column_config={"created_at": st.column_config.DatetimeColumn("Tarix", format="HH:mm")},
                    use_container_width=True
                )
                
            with tab2:
                item_counts = {}
                for items_str in my_sales_df['items']:
                    if not isinstance(items_str, str) or items_str == "Table Order": continue
                    parts = items_str.split(", ")
                    for p in parts:
                        if " x" in p:
                            try:
                                name_part, qty_part = p.rsplit(" x", 1)
                                qty = int(qty_part.split()[0])
                                item_counts[name_part] = item_counts.get(name_part, 0) + qty
                            except: pass
                if item_counts:
                    df_items = pd.DataFrame(list(item_counts.items()), columns=['Məhsul', 'Say']).sort_values(by='Say', ascending=False)
                    st.dataframe(df_items, hide_index=True, use_container_width=True)
                else:
                    st.info("Detallı məhsul tapılmadı.")
        else:
            st.info("Siz bu növbədə hələ satış etməmisiniz.")
            
    else:
        s_cash = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Cash' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
        s_card = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Card' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
        s_staff = run_query("SELECT SUM(total) as s FROM sales WHERE payment_method='Staff' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
        total_sales = float(s_cash) + float(s_card) + float(s_staff)
        
        my_sales = run_query("SELECT SUM(total) as s FROM sales WHERE cashier=:u AND created_at>=:d AND created_at<:e", {"u": st.session_state.user, "d": sh_start_z, "e": sh_end_z}).iloc[0]['s'] or 0.0
        
        f_out = run_query("SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
        f_in = run_query("SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND created_at>=:d AND created_at<:e", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
        
        opening_limit = float(get_setting("cash_limit", "0.0"))
        expected_cash = opening_limit + float(s_cash) + float(f_in) - float(f_out)
        
        c1, c2 = st.columns(2)
        c1.metric("CƏMİ SATIŞ", f"{total_sales:.2f} ₼")
        c1.write(f"💳 Kartla: {float(s_card):.2f} ₼")
        c1.write(f"💵 Nağd: {float(s_cash):.2f} ₼")
        c1.write(f"👥 Personal: {float(s_staff):.2f} ₼")
        
        c1.markdown(f"<div style='background:#E8F5E9; padding:5px; border-radius:5px; margin-top:5px;'>👤 Sizin vurduğunuz satış: <b>{float(my_sales):.2f} ₼</b></div>", unsafe_allow_html=True)
        
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
                    set_setting("cash_limit", str(expected_cash))
                    set_setting("last_z_report_time", get_baku_now().isoformat())
                    st.session_state.z_report_active=False
                    st.success("GÜN UĞURLA BAĞLANDI! 🌙")
                    time.sleep(2)
                    st.rerun()
            z_final_d()
