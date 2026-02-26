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
            st.info("💡 Məsləhət: Səhv vurulmuş çeki qutudan seçib SİLƏ və ya DÜZƏLİŞ edə bilərsiniz.")
            sales_disp = sales.copy()
            
            if 'discount' not in sales_disp.columns:
                sales_disp['discount'] = 0.0
            
            sales_disp['Müştəri Kodu'] = sales_disp['customer_card_id']
            sales_disp['Müştəri Tipi'] = sales_disp['cust_type'].fillna('').str.upper()
            sales_disp['Ulduz'] = sales_disp['cust_stars']
            
            sales_disp.loc[sales_disp['Müştəri Kodu'].isna() | (sales_disp['Müştəri Kodu'] == ''), 'Müştəri Tipi'] = ''
            sales_disp.loc[sales_disp['Müştəri Kodu'].isna() | (sales_disp['Müştəri Kodu'] == ''), 'Ulduz'] = None
            
            cols_to_show = ['id', 'created_at', 'cashier', 'items', 'total', 'discount', 'payment_method', 'Müştəri Kodu', 'Müştəri Tipi', 'Ulduz', 'note']
            cols_to_show = [c for c in cols_to_show if c in sales_disp.columns]
            
            display_df = sales_disp[cols_to_show].copy()
            display_df.insert(0, "Seç", False)
            
            # Cədvəl ancaq oxumaq və "Seç"mək üçündür
            edited_sales = st.data_editor(
                display_df, 
                hide_index=True, 
                column_config={
                    "Seç": st.column_config.CheckboxColumn(required=True),
                    "id": st.column_config.NumberColumn("ID"),
                    "created_at": st.column_config.DatetimeColumn("Tarix", format="DD.MM.YYYY HH:mm"),
                    "total": st.column_config.NumberColumn("Məbləğ", format="%.2f ₼"),
                    "discount": st.column_config.NumberColumn("Endirim", format="%.2f ₼"),
                    "Ulduz": st.column_config.NumberColumn(format="%d ⭐")
                }, 
                disabled=cols_to_show, 
                use_container_width=True, 
                key="sales_admin_ed"
            )
            
            sel_sales = edited_sales[edited_sales["Seç"]]
            sel_s_ids = sel_sales['id'].tolist()
            
            is_admin = st.session_state.role in ['admin', 'manager']
            
            if is_admin:
                col_btn1, col_btn2 = st.columns(2)
                
                # --- 1. DÜZƏLİŞ MƏNTİQİ (PƏNCƏRƏ İLƏ) ---
                if len(sel_s_ids) == 1:
                    if col_btn1.button("✏️ Düzəliş", type="secondary"):
                        st.session_state.sale_edit_id = int(sel_s_ids[0])
                        st.rerun()
                        
                # --- 2. SİLİNMƏ MƏNTİQİ ---
                if len(sel_s_ids) > 0:
                    if col_btn2.button(f"🗑️ Seçilən {len(sel_s_ids)} Satışı Sil", type="primary"):
                        st.session_state.sales_to_delete = sel_s_ids
                        st.rerun()

            # --- DÜZƏLİŞ PƏNCƏRƏSİ ---
            if st.session_state.get('sale_edit_id'):
                s_res = run_query("SELECT * FROM sales WHERE id=:id", {"id": st.session_state.sale_edit_id})
                if not s_res.empty:
                    s_row = s_res.iloc[0]
                    @st.dialog("✏️ Satışa Düzəliş Et")
                    def edit_sale_dialog(r):
                        with st.form("edit_sale_form"):
                            st.write(f"ID: {r['id']} | Tarix: {r['created_at'].strftime('%d.%m.%Y %H:%M') if pd.notna(r['created_at']) else ''}")
                            e_cashier = st.text_input("Kassir", r['cashier'])
                            e_items = st.text_input("Məhsullar", r['items'])
                            
                            c_amt, c_disc = st.columns(2)
                            e_total = c_amt.number_input("Məbləğ (AZN)", value=float(r['total']), step=0.1)
                            
                            curr_disc = float(r['discount']) if 'discount' in r and pd.notna(r['discount']) else 0.0
                            e_disc = c_disc.number_input("Endirim (AZN)", value=curr_disc, step=0.1)
                            
                            e_pm = st.selectbox("Ödəniş Növü", ["Cash", "Card", "Staff"], index=["Cash", "Card", "Staff"].index(r['payment_method']) if r['payment_method'] in ["Cash", "Card", "Staff"] else 0)
                            
                            cust_val = r['customer_card_id'] if pd.notna(r['customer_card_id']) else ""
                            e_cust = st.text_input("Müştəri Kodu (Bazada varsa)", cust_val)
                            
                            note_val = r['note'] if pd.notna(r['note']) else ""
                            e_note = st.text_input("Qeyd (Səbəb)", note_val)

                            if st.form_submit_button("💾 Dəyişikliyi Yadda Saxla", type="primary"):
                                params = {
                                    "c": e_cashier, "i": e_items, "t": e_total, "p": e_pm,
                                    "cc": e_cust if e_cust.strip() else None,
                                    "n": e_note if e_note.strip() else None,
                                    "id": int(r['id'])
                                }
                                
                                update_q = "UPDATE sales SET cashier=:c, items=:i, total=:t, payment_method=:p, customer_card_id=:cc, note=:n"
                                if 'discount' in sales.columns:
                                    update_q += ", discount=:d"
                                    params["d"] = e_disc
                                update_q += " WHERE id=:id"
                                
                                try:
                                    run_action(update_q, params)
                                except:
                                    fallback_q = "UPDATE sales SET cashier=:c, items=:i, total=:t, payment_method=:p, customer_card_id=:cc, note=:n WHERE id=:id"
                                    run_action(fallback_q, params)
                                    
                                log_system(st.session_state.user, f"SATIŞ REDAKTƏ EDİLDİ | ID: {r['id']} | Yeni Məbləğ: {e_total} ₼")
                                st.session_state.sale_edit_id = None
                                st.success("✅ Dəyişiklik uğurla yadda saxlanıldı!")
                                time.sleep(1.5)
                                st.rerun()
                    edit_sale_dialog(s_row)

            # --- SİLMƏ PƏNCƏRƏSİ ---
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
        # --- ÇEVİK MAAŞ/AVANS ÖDƏNİŞ BLOKU ---
        with st.expander("💸 GÜNLÜK MAAŞ VƏ AVANS ÖDƏNİŞİ"):
            with st.form("pay_salary_form", clear_on_submit=True):
                st.write("Günü bağlamadan əvvəl işçilərə verilən maaşı/avansı burdan ödəyə bilərsiniz.")
                emp_list = run_query("SELECT username FROM users")['username'].tolist()
                c_emp, c_amt, c_src = st.columns(3)
                p_emp = c_emp.selectbox("İşçi", emp_list)
                p_amt = c_amt.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0)
                p_src = c_src.selectbox("Ödəniş Mənbəyi", ["Kassa", "Bank Kartı", "Seyf"])
                
                p_note = st.text_input("Qeyd", placeholder="Məs: Günlük maaş")
                
                if st.form_submit_button("💰 Ödənişi Təsdiqlə", type="primary"):
                    if p_amt > 0:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Maaş / Avans', :a, :s, :n, :u)", 
                                   {"a":p_amt, "s":p_src, "n":f"{p_emp} - {p_note}", "u":st.session_state.user})
                        log_system(st.session_state.user, f"MAAŞ ÖDƏNİŞİ | İşçi: {p_emp} | Məbləğ: {p_amt} AZN | Mənbə: {p_src}")
                        
                        if p_src == "Kassa":
                            st.success(f"✅ {p_emp} üçün {p_amt} AZN maaş KASSADAN çıxıldı! 'Kassada olmalıdır' məbləği azaldıldı.")
                        else:
                            st.success(f"✅ {p_emp} üçün {p_amt} AZN maaş {p_src} hesabından çıxıldı! (Z-Hesabata təsir etmədi, xərcə yazıldı)")
                        
                        time.sleep(2.5)
                        st.rerun()
                    else:
                        st.warning("Məbləğ daxil edin!")
        # ----------------------------------------
        
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
