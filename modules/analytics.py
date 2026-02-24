import streamlit as st
import pandas as pd
import datetime
import time
import json
import plotly.express as px
import base64
from database import run_query, run_action, get_setting
from utils import get_baku_now, BRAND_NAME

# Məhsul siyahısını JSON-dan təmiz mətnə çevirən köməkçi funksiya
def parse_items(items_str):
    if not items_str: return ""
    try:
        items = json.loads(items_str)
        if isinstance(items, list):
            return ", ".join([f"{i.get('item_name', 'Məhsul')} ({i.get('qty', 1)}x)" for i in items])
        elif isinstance(items, dict):
            return str(items)
    except:
        pass
    return str(items_str)

def render_analytics_page():
    st.subheader("📊 Analitika və Satış Hesabatları (CFO Paneli)")
    
    today = get_baku_now().date()
    start_of_month = today.replace(day=1)
    
    role = st.session_state.get('role', 'staff')
    current_user = st.session_state.get('user', '')
    
    role_filter = ""
    base_params = {}
    if role == 'staff':
        role_filter = " AND cashier = :u"
        base_params["u"] = current_user

    # --- 1. CFO PANELİ (Sarsılmaz Nəğd/Kart Məntiqi ilə) ---
    td_params = {"d": today, **base_params}
    tm_params = {"d": start_of_month, **base_params}
    
    td_df = run_query(f"SELECT payment_method, SUM(total) as s FROM sales WHERE DATE(created_at) = :d {role_filter} GROUP BY payment_method", td_params)
    
    td_sales = 0.0
    td_cash = 0.0
    td_card = 0.0
    
    if not td_df.empty:
        for _, r in td_df.iterrows():
            val = float(r['s']) if pd.notna(r['s']) else 0.0
            td_sales += val
            pm = str(r['payment_method']).strip().upper()
            # Əgər içində KART və ya CARD sözü varsa Kartdır, qalan hər şey Nəğddir! (Sarsılmaz məntiq)
            if 'KART' in pm or 'CARD' in pm: 
                td_card += val
            else: 
                td_cash += val
            
    tm_df = run_query(f"SELECT SUM(total) as s FROM sales WHERE DATE(created_at) >= :d {role_filter}", tm_params)
    tm_sales = float(tm_df.iloc[0]['s']) if not tm_df.empty and pd.notna(tm_df.iloc[0]['s']) else 0.0
    
    if role in ['admin', 'manager']:
        exp_df = run_query("SELECT SUM(amount) as s FROM finance WHERE type='out' AND DATE(created_at) >= :d", {"d": start_of_month})
        tm_expenses = float(exp_df.iloc[0]['s']) if not exp_df.empty and pd.notna(exp_df.iloc[0]['s']) else 0.0
        net_profit = tm_sales - tm_expenses
        
        st.markdown("### 💰 Bu Günün Satışları")
        c1, c2, c3 = st.columns(3)
        c1.metric("Bu Gün (Ümumi)", f"{td_sales:.2f} ₼")
        c2.metric("Nəğd Satış", f"{td_cash:.2f} ₼")
        c3.metric("Kartla Satış", f"{td_card:.2f} ₼")
        
        st.markdown("### 📅 Aylıq Göstəricilər")
        c4, c5, c6 = st.columns(3)
        c4.metric("Bu Ay (Ümumi Satış)", f"{tm_sales:.2f} ₼")
        c5.metric("Bu Ay (Xərc)", f"{tm_expenses:.2f} ₼")
        c6.metric("Xalis Mənfəət", f"{net_profit:.2f} ₼", delta=f"{net_profit:.2f} ₼", delta_color="normal" if net_profit>=0 else "inverse")
    else:
        st.markdown(f"### 👤 {current_user.capitalize()}, Sənin Göstəricilərin")
        c1, c2, c3 = st.columns(3)
        c1.metric("Bu Gün (Ümumi Satışın)", f"{td_sales:.2f} ₼")
        c2.metric("Nəğd Satışın", f"{td_cash:.2f} ₼")
        c3.metric("Kartla Satışın", f"{td_card:.2f} ₼")

    st.divider()

    st.markdown("### 🔍 Detallı Axtarış və Performans")
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        date_filter = st.radio("Tarix Aralığı Seçin:", ["Bu Gün", "Bu Ay", "Seçilmiş Tarix Aralığı"], horizontal=True)
    with filter_col2:
        if date_filter == "Seçilmiş Tarix Aralığı":
            d_range = st.date_input("Başlanğıc və Bitiş tarixi seçin", [today, today])
            if len(d_range) == 2: start_date, end_date = d_range
            else: start_date, end_date = today, today
        elif date_filter == "Bu Ay": start_date, end_date = start_of_month, today
        else: start_date, end_date = today, today

    perf_params = {"sd": start_date, "ed": end_date}
    if role == 'staff': perf_params["u"] = current_user

    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.markdown("**👥 İşçi Performansı**")
        staff_df = run_query(f"""
            SELECT cashier as "Kassir", COUNT(id) as "Sifariş", SUM(total) as "Satış (₼)"
            FROM sales 
            WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {role_filter}
            GROUP BY cashier ORDER BY SUM(total) DESC
        """, perf_params)
        if not staff_df.empty: st.dataframe(staff_df, hide_index=True, use_container_width=True)
        else: st.info("Bu aralıqda satış tapılmadı.")
            
    with g_col2:
        st.markdown("**📈 Satış Trendi**")
        trend_df = run_query(f"SELECT DATE(created_at) as d, SUM(total) as s FROM sales WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {role_filter} GROUP BY DATE(created_at) ORDER BY d", perf_params)
        if not trend_df.empty and len(trend_df) > 1:
            fig1 = px.line(trend_df, x='d', y='s', markers=True, line_shape="spline", color_discrete_sequence=["#ffd700"])
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig1, use_container_width=True)
        elif not trend_df.empty and len(trend_df) == 1: st.info(f"Yalnız 1 günlük məlumat var: {trend_df.iloc[0]['s']} ₼")
        else: st.info("Kifayət qədər məlumat yoxdur.")

    st.divider()

    # --- 4. DETALLI SATIŞLAR CƏDVƏLİ ---
    st.markdown("### 📝 Detallı Satışlar (Nə Satıldığını Görün)")
    sales_list_df = run_query(f"""
        SELECT id, created_at, cashier, items, payment_method, total, discount_amount, note 
        FROM sales 
        WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {role_filter}
        ORDER BY created_at DESC
    """, perf_params)
    
    if not sales_list_df.empty:
        # Cədvəli göstərmək üçün kopyasını alırıq
        display_df = sales_list_df.copy()
        display_df['items'] = display_df['items'].apply(parse_items)
        display_df['created_at'] = pd.to_datetime(display_df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
        display_df = display_df.rename(columns={"id": "Çek №", "created_at": "Tarix", "cashier": "Kassir", "items": "Satılan Mallar", "payment_method": "Ödəniş", "total": "Məbləğ (₼)", "discount_amount": "Endirim", "note": "Qeyd"})
        st.dataframe(display_df, hide_index=True, use_container_width=True)
        
        # ========================================================
        # 🗑️ ÇEK İPTALI VƏ ANBARA QAYTARMA (YALNIZ ADMIN/MANAGER)
        # ========================================================
        if role in ['admin', 'manager']:
            st.markdown("---")
            st.markdown("<h4 style='color:#ff4b4b;'>⚠️ Çek İptalı və Geri Qaytarma</h4>", unsafe_allow_html=True)
            
            with st.form("delete_sale_form", clear_on_submit=True):
                del_c1, del_c2, del_c3 = st.columns([1, 2, 1])
                with del_c1:
                    sale_ids = ["Seçilməyib"] + sales_list_df['id'].astype(str).tolist()
                    selected_id = st.selectbox("Silinəcək Çek №:", sale_ids)
                with del_c2:
                    reason = st.selectbox("Səbəb:", [
                        "Test / Yanlış Vuruş (Xammal anbara geri QAYIDACAQ)", 
                        "Xarab / Zay oldu (Xammal anbara QAYITMAYACAQ)"
                    ])
                with del_c3:
                    st.write("") # Boşluq
                    submit_del = st.form_submit_button("🗑️ Çeki İptal Et", type="primary", use_container_width=True)
                
                if submit_del and selected_id != "Seçilməyib":
                    # 1. Çekin içindəki malları (JSON) alırıq
                    target_sale = sales_list_df[sales_list_df['id'] == int(selected_id)].iloc[0]
                    items_str = target_sale['items']
                    
                    # 2. Əgər TEST-dirsə anbara xammalı geri qaytarırıq (Rollback Logic)
                    if "QAYIDACAQ" in reason and items_str:
                        try:
                            items = json.loads(items_str)
                            for item in items:
                                m_name = item.get('item_name', '')
                                qty = float(item.get('qty', 1))
                                
                                # Bu məhsulun reseptini tap
                                rec_df = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name = :m", {"m": m_name})
                                for _, r_row in rec_df.iterrows():
                                    ing_name = r_row['ingredient_name']
                                    req_qty = float(r_row['quantity_required'])
                                    # İstifadə olunan xammalı hesablayıb anbara (+) edirik
                                    total_return = req_qty * qty
                                    run_action("UPDATE ingredients SET stock_qty = stock_qty + :q WHERE name = :n", {"q": total_return, "n": ing_name})
                        except Exception as e:
                            pass # JSON oxunmasa davam et
                            
                    # 3. Çeki cədvəldən tamamilə silirik
                    run_action("DELETE FROM sales WHERE id = :id", {"id": int(selected_id)})
                    st.success(f"✅ Çek №{selected_id} uğurla silindi! ({reason})")
                    time.sleep(1.5)
                    st.rerun()
    else:
        st.warning("Seçilmiş tarix aralığında heç bir detal tapılmadı.")


def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    
    active_shift = run_query("SELECT * FROM z_reports WHERE shift_end IS NULL ORDER BY shift_start DESC LIMIT 1")
    
    if active_shift.empty:
        st.warning("⚠️ Hazırda aktiv növbə yoxdur.")
        if st.button("🟢 Yeni Növbəni Başlat", type="primary", use_container_width=True):
            run_action("INSERT INTO z_reports (shift_start, generated_by) VALUES (:s, :u)", {"s": get_baku_now(), "u": st.session_state.user})
            st.session_state.z_report_active = True
            st.success("Yeni növbə başladı! Uğurlar! ☕")
            time.sleep(1)
            st.rerun()
    else:
        shift_data = active_shift.iloc[0]
        shift_start_time = pd.to_datetime(shift_data['shift_start'])
        st.info(f"🟢 **Aktiv Növbə:** Başlama vaxtı: {shift_start_time.strftime('%d/%m/%Y %H:%M')}")
        
        orders_df = run_query("SELECT payment_method, SUM(total) as s FROM sales WHERE created_at >= :st GROUP BY payment_method", {"st": shift_start_time})
        cash_sales = 0.0
        card_sales = 0.0
        
        if not orders_df.empty:
            for _, r in orders_df.iterrows():
                val = float(r['s'])
                pm = str(r['payment_method']).strip().upper()
                if 'KART' in pm or 'CARD' in pm: card_sales += val
                else: cash_sales += val
                
        total_sales = cash_sales + card_sales
        expenses_df = run_query("SELECT SUM(amount) as s FROM finance WHERE type='out' AND source='Kassa' AND created_at >= :st", {"st": shift_start_time})
        shift_expenses = float(expenses_df.iloc[0]['s']) if not expenses_df.empty and pd.notna(expenses_df.iloc[0]['s']) else 0.0
        
        expected_cash = cash_sales - shift_expenses
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nəğd Satış", f"{cash_sales:.2f} ₼")
        c2.metric("Kartla Satış", f"{card_sales:.2f} ₼")
        c3.metric("Kassadan Xərc", f"{shift_expenses:.2f} ₼")
        c4.metric("GÖZLƏNİLƏN KASSA", f"{expected_cash:.2f} ₼")
        
        st.divider()
        
        st.markdown("### 📋 Bu Növbədəki Satışlar (Nə Satmısınız?)")
        role = st.session_state.get('role', 'staff')
        current_user = st.session_state.get('user', '')
        
        shift_role_filter = " AND cashier = :u" if role == 'staff' else ""
        shift_params = {"st": shift_start_time, "u": current_user} if role == 'staff' else {"st": shift_start_time}
        
        shift_sales_df = run_query(f"""
            SELECT id, created_at, cashier, items, payment_method, total 
            FROM sales 
            WHERE created_at >= :st {shift_role_filter}
            ORDER BY created_at DESC
        """, shift_params)
        
        if not shift_sales_df.empty:
            shift_sales_df['items'] = shift_sales_df['items'].apply(parse_items)
            shift_sales_df['created_at'] = pd.to_datetime(shift_sales_df['created_at']).dt.strftime('%H:%M')
            shift_sales_df = shift_sales_df.rename(columns={"id": "Çek №", "created_at": "Saat", "cashier": "Kassir", "items": "Satılan Mallar", "payment_method": "Ödəniş", "total": "Məbləğ (₼)"})
            st.dataframe(shift_sales_df, hide_index=True, use_container_width=True)
        else:
            st.info("Bu növbədə hələ heç nə satılmayıb.")
            
        st.divider()
        st.markdown("### 🏁 Növbəni Bağla (Z-Hesabatı Çıxar)")
        
        with st.form("z_report_form"):
            actual_cash = st.number_input("Kassadakı Real Nəğd Pul (₼)", min_value=0.0, step=0.1, value=float(expected_cash))
            diff = actual_cash - expected_cash
            st.markdown(f"**Fərq:** {'+ ' if diff > 0 else ''}{diff:.2f} ₼")
            
            if st.form_submit_button("🚨 Z-Hesabat Çıxar və Növbəni Bitir", type="primary", use_container_width=True):
                run_action("UPDATE z_reports SET shift_end = :e, total_sales = :t, cash_sales = :cs, card_sales = :cds, expected_cash = :ec, actual_cash = :ac, difference = :d WHERE id = :id", {"e": get_baku_now(), "t": float(total_sales), "cs": float(cash_sales), "cds": float(card_sales), "ec": float(expected_cash), "ac": float(actual_cash), "d": float(diff), "id": int(shift_data['id'])})
                run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'İnkassasiya (Növbə Bağlanışı)', :a, 'Kassa', 'Z-Hesabat Çıxarıldı', :u)", {"a": float(expected_cash), "u": str(st.session_state.user)})
                st.session_state.z_report_active = False
                st.success("✅ Növbə bağlandı!")
                time.sleep(2)
                st.rerun()

    st.divider()
    with st.expander("📂 Keçmiş Z-Hesabatlar Arxivi"):
        past_z = run_query("SELECT id, shift_start, shift_end, total_sales, expected_cash, actual_cash, difference, generated_by FROM z_reports WHERE shift_end IS NOT NULL ORDER BY shift_end DESC LIMIT 30")
        if not past_z.empty:
            past_z['shift_start'] = pd.to_datetime(past_z['shift_start']).dt.strftime('%d/%m/%Y %H:%M')
            past_z['shift_end'] = pd.to_datetime(past_z['shift_end']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(past_z, hide_index=True, use_container_width=True)
        else:
            st.info("Keçmiş hesabat tapılmadı.")
