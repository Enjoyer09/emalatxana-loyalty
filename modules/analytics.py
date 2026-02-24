import streamlit as st
import pandas as pd
import datetime
import time
import plotly.express as px
import base64
from database import run_query, run_action, get_setting
from utils import get_baku_now, BRAND_NAME

def render_analytics_page():
    st.subheader("📊 Analitika və Satış Hesabatları")
    
    today = get_baku_now().date()
    start_of_month = today.replace(day=1)
    
    # KASSİR (STAFF) ÜÇÜN MÜDAFİƏ FİLTRİ: Əgər daxil olan user staff-dırsa, yalnız özünü görəcək.
    role = st.session_state.get('role', 'staff')
    current_user = st.session_state.get('user', '')
    
    role_filter = ""
    base_params = {}
    if role == 'staff':
        role_filter = " AND cashier = :u"
        base_params["u"] = current_user

    # --- 1. CFO PANELİ (ƏSAS GÖSTƏRİCİLƏR) ---
    td_params = {"d": today, **base_params}
    tm_params = {"d": start_of_month, **base_params}
    
    # Bugünkü Satışlar (Nəğd / Kart bölgüsü)
    td_df = run_query(f"SELECT payment_method, SUM(total) as s FROM sales WHERE DATE(created_at) = :d {role_filter} GROUP BY payment_method", td_params)
    
    td_sales = 0.0
    td_cash = 0.0
    td_card = 0.0
    
    if not td_df.empty:
        for _, r in td_df.iterrows():
            val = float(r['s']) if pd.notna(r['s']) else 0.0
            td_sales += val
            if str(r['payment_method']).upper() == 'NƏĞD': td_cash += val
            elif str(r['payment_method']).upper() == 'KART': td_card += val
            
    # Aylıq Satışlar
    tm_df = run_query(f"SELECT SUM(total) as s FROM sales WHERE DATE(created_at) >= :d {role_filter}", tm_params)
    tm_sales = float(tm_df.iloc[0]['s']) if not tm_df.empty and pd.notna(tm_df.iloc[0]['s']) else 0.0
    
    # Xərclər və Mənfəət yalnız Admin/Manager üçün görünür
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

    # --- 2. TARİX FİLTRİ VƏ AXTARIŞ ---
    st.markdown("### 🔍 Detallı Axtarış və Performans")
    
    # Tarix seçimi
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        date_filter = st.radio("Tarix Aralığı Seçin:", ["Bu Gün", "Bu Ay", "Seçilmiş Tarix Aralığı"], horizontal=True)
        
    with filter_col2:
        if date_filter == "Seçilmiş Tarix Aralığı":
            d_range = st.date_input("Başlanğıc və Bitiş tarixi seçin", [today, today])
            if len(d_range) == 2:
                start_date, end_date = d_range
            else:
                start_date, end_date = today, today
        elif date_filter == "Bu Ay":
            start_date = start_of_month
            end_date = today
        else:
            start_date = today
            end_date = today

    # Dinamik sorğu parametrləri
    perf_params = {"sd": start_date, "ed": end_date}
    if role == 'staff':
        perf_params["u"] = current_user

    # --- 3. İŞÇİ PERFORMANSI VƏ QRAFİK ---
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.markdown("**👥 İşçi Performansı**")
        staff_df = run_query(f"""
            SELECT cashier as "Kassir / İşçi", COUNT(id) as "Sifariş Sayı", SUM(total) as "Cəmi Satış (₼)"
            FROM sales 
            WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {role_filter}
            GROUP BY cashier
            ORDER BY SUM(total) DESC
        """, perf_params)
        
        if not staff_df.empty:
            st.dataframe(staff_df, hide_index=True, use_container_width=True)
        else:
            st.info("Bu aralıqda heç bir satış tapılmadı.")
            
    with g_col2:
        st.markdown("**📈 Satış Trendi (Günlük)**")
        trend_df = run_query(f"""
            SELECT DATE(created_at) as d, SUM(total) as s 
            FROM sales 
            WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {role_filter}
            GROUP BY DATE(created_at) 
            ORDER BY d
        """, perf_params)
        
        if not trend_df.empty and len(trend_df) > 1:
            fig1 = px.line(trend_df, x='d', y='s', markers=True, line_shape="spline", color_discrete_sequence=["#ffd700"])
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), xaxis_title="Tarix", yaxis_title="Məbləğ (₼)")
            st.plotly_chart(fig1, use_container_width=True)
        elif not trend_df.empty and len(trend_df) == 1:
            st.info(f"Yalnız 1 günlük məlumat var: {trend_df.iloc[0]['s']} ₼")
        else:
            st.info("Kifayət qədər məlumat yoxdur.")

    st.divider()

    # --- 4. DETALLI SATIŞLAR CƏDVƏLİ ---
    st.markdown("### 📝 Detallı Satışlar Cədvəli")
    
    sales_list_df = run_query(f"""
        SELECT id, created_at, cashier, payment_method, total, discount_amount, note 
        FROM sales 
        WHERE DATE(created_at) >= :sd AND DATE(created_at) <= :ed {role_filter}
        ORDER BY created_at DESC
    """, perf_params)
    
    if not sales_list_df.empty:
        sales_list_df['created_at'] = pd.to_datetime(sales_list_df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
        # Sütunları səliqəyə salırıq
        sales_list_df = sales_list_df.rename(columns={
            "id": "Çek №",
            "created_at": "Tarix / Saat",
            "cashier": "Kassir",
            "payment_method": "Ödəniş Növü",
            "total": "Məbləğ (₼)",
            "discount_amount": "Endirim (₼)",
            "note": "Qeyd"
        })
        
        st.dataframe(sales_list_df, hide_index=True, use_container_width=True)
        
        # Excel / CSV kimi yükləmək imkanı
        csv = sales_list_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Bu cədvəli yüklə (CSV)",
            data=csv,
            file_name=f"satishlar_{start_date}_to_{end_date}.csv",
            mime="text/csv",
        )
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
        
        # Füzulinin SALES cədvəlindən Sifarişləri cəmləyirik
        orders_df = run_query("SELECT payment_method, SUM(total) as s FROM sales WHERE created_at >= :st GROUP BY payment_method", {"st": shift_start_time})
        cash_sales = 0.0
        card_sales = 0.0
        
        if not orders_df.empty:
            for _, r in orders_df.iterrows():
                if str(r['payment_method']).upper() == 'NƏĞD': cash_sales += float(r['s'])
                elif str(r['payment_method']).upper() == 'KART': card_sales += float(r['s'])
                
        total_sales = cash_sales + card_sales
        
        # Xərclər (Kassadan çıxanlar)
        expenses_df = run_query("SELECT SUM(amount) as s FROM finance WHERE type='out' AND source='Kassa' AND created_at >= :st", {"st": shift_start_time})
        shift_expenses = float(expenses_df.iloc[0]['s']) if not expenses_df.empty and pd.notna(expenses_df.iloc[0]['s']) else 0.0
        
        # Gözlənilən kassa
        expected_cash = cash_sales - shift_expenses
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nəğd Satış", f"{cash_sales:.2f} ₼")
        c2.metric("Kartla Satış", f"{card_sales:.2f} ₼")
        c3.metric("Kassadan Xərc", f"{shift_expenses:.2f} ₼")
        c4.metric("GÖZLƏNİLƏN KASSA", f"{expected_cash:.2f} ₼")
        
        st.divider()
        st.markdown("### 🏁 Növbəni Bağla (Z-Hesabatı Çıxar)")
        
        with st.form("z_report_form"):
            actual_cash = st.number_input("Kassadakı Real Nəğd Pul (₼)", min_value=0.0, step=0.1, value=float(expected_cash))
            diff = actual_cash - expected_cash
            
            st.markdown(f"**Fərq:** {'+ ' if diff > 0 else ''}{diff:.2f} ₼ (Mənfidirsə kəsir, müsbətdirsə artıqdır)")
            
            if st.form_submit_button("🚨 Z-Hesabat Çıxar və Növbəni Bitir", type="primary", use_container_width=True):
                fl_total = float(total_sales)
                fl_cash = float(cash_sales)
                fl_card = float(card_sales)
                fl_exp = float(expected_cash)
                fl_act = float(actual_cash)
                fl_diff = float(diff)
                
                run_action("""
                    UPDATE z_reports 
                    SET shift_end = :e, total_sales = :t, cash_sales = :cs, card_sales = :cds, expected_cash = :ec, actual_cash = :ac, difference = :d
                    WHERE id = :id
                """, {
                    "e": get_baku_now(), "t": fl_total, "cs": fl_cash, "cds": fl_card, 
                    "ec": fl_exp, "ac": fl_act, "d": fl_diff, "id": int(shift_data['id'])
                })
                
                user_str = str(st.session_state.user)
                run_action("""
                    INSERT INTO finance (type, category, amount, source, description, created_by) 
                    VALUES ('out', 'İnkassasiya (Növbə Bağlanışı)', :a, 'Kassa', 'Z-Hesabat Çıxarıldı və Günü Bitirildi', :u)
                """, {"a": fl_exp, "u": user_str})
                
                html_report = f"""
                <html>
                <head><style>body{{font-family:monospace; text-align:center;}} table{{width:100%; text-align:left; border-collapse:collapse;}} th,td{{border-bottom:1px dashed #000; padding:5px;}}</style></head>
                <body>
                    <div style="width:300px; margin:0 auto; padding:10px;">
                        <h2>{BRAND_NAME}</h2>
                        <h3>Z-HESABAT (NÖVBƏ BAĞLANIŞI)</h3>
                        <p>Növbə: {shift_start_time.strftime('%d/%m %H:%M')} - {get_baku_now().strftime('%d/%m %H:%M')}</p>
                        <p>Kassir: {st.session_state.user}</p>
                        <hr>
                        <table>
                            <tr><td>Ümumi Satış:</td><td style='text-align:right;'>{fl_total:.2f} ₼</td></tr>
                            <tr><td>Nəğd:</td><td style='text-align:right;'>{fl_cash:.2f} ₼</td></tr>
                            <tr><td>Kart:</td><td style='text-align:right;'>{fl_card:.2f} ₼</td></tr>
                            <tr><td>Növbə Xərcləri:</td><td style='text-align:right;'>-{shift_expenses:.2f} ₼</td></tr>
                        </table>
                        <hr>
                        <h3>Sistemdə Olmalı: {fl_exp:.2f} ₼</h3>
                        <h3>Təhvil Verildi: {fl_act:.2f} ₼</h3>
                        <p>Fərq: {fl_diff:.2f} ₼</p>
                        <br>
                        <button onclick="window.print()" style="background:#000; color:#fff; padding:10px; width:100%; border:none; cursor:pointer;">ÇAP ET</button>
                    </div>
                </body>
                </html>
                """
                b64 = base64.b64encode(html_report.encode('utf-8')).decode('utf-8')
                st.markdown(f'<a href="data:text/html;base64,{b64}" download="Z_Hesabat_{get_baku_now().strftime("%Y%m%d_%H%M")}.html" target="_blank"><button style="background:#2E7D32; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; width:100%; font-weight:bold; font-size:16px;">⬇️ Z-Hesabatı Yüklə / Çap Et</button></a>', unsafe_allow_html=True)
                
                st.session_state.z_report_active = False
                st.success("✅ Növbə uğurla bağlandı və İnkassasiya qeydə alındı!")
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
