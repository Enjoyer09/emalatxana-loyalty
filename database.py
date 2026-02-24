import streamlit as st
import pandas as pd
import datetime
import time
import plotly.express as px
import base64
from database import run_query, run_action, get_setting
from utils import get_baku_now, BRAND_NAME

def render_analytics_page():
    st.subheader("📊 Analitika və CFO Paneli")
    
    # --- 1. CFO PANELİ (ƏSAS GÖSTƏRİCİLƏR) ---
    today = get_baku_now().date()
    start_of_month = today.replace(day=1)
    
    # Bügünkü satışlar
    td_df = run_query("SELECT SUM(total_price) as s FROM orders WHERE DATE(created_at) = :d", {"d": today})
    td_sales = float(td_df.iloc[0]['s']) if not td_df.empty and pd.notna(td_df.iloc[0]['s']) else 0.0
    
    # Aylıq satışlar
    tm_df = run_query("SELECT SUM(total_price) as s FROM orders WHERE DATE(created_at) >= :d", {"d": start_of_month})
    tm_sales = float(tm_df.iloc[0]['s']) if not tm_df.empty and pd.notna(tm_df.iloc[0]['s']) else 0.0
    
    # Aylıq Xərclər (Maaş və digər)
    exp_df = run_query("SELECT SUM(amount) as s FROM finance WHERE type='out' AND DATE(created_at) >= :d", {"d": start_of_month})
    tm_expenses = float(exp_df.iloc[0]['s']) if not exp_df.empty and pd.notna(exp_df.iloc[0]['s']) else 0.0
    
    net_profit = tm_sales - tm_expenses
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Bu Gün (Satış)", f"{td_sales:.2f} ₼")
    c2.metric("📅 Bu Ay (Satış)", f"{tm_sales:.2f} ₼")
    c3.metric("💸 Bu Ay (Xərc)", f"{tm_expenses:.2f} ₼")
    c4.metric("📈 Xalis Mənfəət", f"{net_profit:.2f} ₼", delta=f"{net_profit:.2f} ₼", delta_color="normal" if net_profit>=0 else "inverse")
    
    st.divider()
    
    # --- 2. QRAFİKLƏR ---
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.markdown("**📅 Son 7 Günün Satış Qrafiki**")
        sev_days_ago = today - datetime.timedelta(days=7)
        trend_df = run_query("SELECT DATE(created_at) as d, SUM(total_price) as s FROM orders WHERE DATE(created_at) >= :sd GROUP BY DATE(created_at) ORDER BY d", {"sd": sev_days_ago})
        if not trend_df.empty:
            fig1 = px.line(trend_df, x='d', y='s', markers=True, line_shape="spline", color_discrete_sequence=["#ffd700"])
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Kifayət qədər məlumat yoxdur.")
            
    with g_col2:
        st.markdown("**🔥 Ən Çox Satılan 5 Məhsul (Bu Ay)**")
        top_df = run_query("""
            SELECT oi.item_name, SUM(oi.quantity) as q 
            FROM order_items oi 
            JOIN orders o ON oi.order_id = o.id 
            WHERE DATE(o.created_at) >= :sd 
            GROUP BY oi.item_name 
            ORDER BY q DESC LIMIT 5
        """, {"sd": start_of_month})
        if not top_df.empty:
            fig2 = px.bar(top_df, x='item_name', y='q', color_discrete_sequence=["#E65100"])
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Kifayət qədər məlumat yoxdur.")
            
    st.divider()

    # --- 3. İŞÇİ GÖSTƏRİCİLƏRİ VƏ MƏHDUDİYYƏTLƏR ---
    st.markdown("### 👥 İşçi Performansı və Növbələr")
    staff_df = run_query("""
        SELECT o.created_by as user, COUNT(o.id) as orders, SUM(o.total_price) as total 
        FROM orders o 
        WHERE DATE(o.created_at) >= :sd 
        GROUP BY o.created_by
    """, {"sd": start_of_month})
    
    if not staff_df.empty:
        st.dataframe(staff_df, hide_index=True, use_container_width=True)
    else:
        st.info("Bu ay hələ sifariş yoxdur.")

def render_z_report_page():
    st.subheader("📊 Z-Hesabat və Növbə İdarəetməsi")
    
    # Aktiv növbənin yoxlanması
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
        
        # Sifarişləri cəmləyirik
        orders_df = run_query("SELECT payment_method, SUM(total_price) as s FROM orders WHERE created_at >= :st GROUP BY payment_method", {"st": shift_start_time})
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
        
        # Gözlənilən kassa = Nəğd satışlar - Kassadan çıxan xərclər
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
                # ZİREHLİ MÜDAFİƏ: Bütün rəqəmləri məcburi olaraq Python Float formatına salırıq
                fl_total = float(total_sales)
                fl_cash = float(cash_sales)
                fl_card = float(card_sales)
                fl_exp = float(expected_cash)
                fl_act = float(actual_cash)
                fl_diff = float(diff)
                
                # Z-Hesabat cədvəlini bağla
                run_action("""
                    UPDATE z_reports 
                    SET shift_end = :e, total_sales = :t, cash_sales = :cs, card_sales = :cds, expected_cash = :ec, actual_cash = :ac, difference = :d
                    WHERE id = :id
                """, {
                    "e": get_baku_now(), "t": fl_total, "cs": fl_cash, "cds": fl_card, 
                    "ec": fl_exp, "ac": fl_act, "d": fl_diff, "id": int(shift_data['id'])
                })
                
                # İnkassasiya qeydini Maliyyəyə əlavə et
                user_str = str(st.session_state.user)
                run_action("""
                    INSERT INTO finance (type, category, amount, source, description, created_by) 
                    VALUES ('out', 'İnkassasiya (Növbə Bağlanışı)', :a, 'Kassa', 'Z-Hesabat Çıxarıldı və Günü Bitirildi', :u)
                """, {"a": fl_exp, "u": user_str})
                
                # Çıxarılmış Z-Hesabatın HTML formasını hazırla
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

    # --- KEÇMİŞ Z-HESABATLAR ARXİVİ ---
    st.divider()
    with st.expander("📂 Keçmiş Z-Hesabatlar Arxivi"):
        past_z = run_query("SELECT id, shift_start, shift_end, total_sales, expected_cash, actual_cash, difference, generated_by FROM z_reports WHERE shift_end IS NOT NULL ORDER BY shift_end DESC LIMIT 30")
        if not past_z.empty:
            past_z['shift_start'] = pd.to_datetime(past_z['shift_start']).dt.strftime('%d/%m/%Y %H:%M')
            past_z['shift_end'] = pd.to_datetime(past_z['shift_end']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(past_z, hide_index=True, use_container_width=True)
        else:
            st.info("Keçmiş hesabat tapılmadı.")
