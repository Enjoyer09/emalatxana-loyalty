import streamlit as st
import pandas as pd
import datetime
from database import run_query
from utils import get_logical_date, get_baku_now, get_shift_range

def render_analytics_page():
    st.subheader("📊 CFO Maliyyə Analitikası (P&L)")
    
    st.markdown("""
        <style>
        .cfo-card {
            background: var(--metal-panel);
            border: 2px solid #3a4149;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 4px 4px 10px rgba(0,0,0,0.5);
            margin-bottom: 15px;
        }
        .cfo-card h4 { color: #aaa !important; font-size: 16px; margin-bottom: 5px; font-weight: 700; }
        .cfo-card h2 { color: #ffffff !important; font-size: 26px; font-family: 'Jura'; margin: 0; font-weight: 900; }
        
        .cfo-rev h2 { color: #64b5f6 !important; }
        .cfo-cost h2 { color: #e57373 !important; }
        .cfo-gross h2 { color: #ffd700 !important; }
        .cfo-opex h2 { color: #ffb74d !important; }
        
        .cfo-net { border-color: #2E7D32 !important; background: linear-gradient(145deg, #1b3b22, #122616) !important; }
        .cfo-net h4 { color: #81c784 !important; }
        .cfo-net h2 { color: #4CAF50 !important; font-size: 30px; text-shadow: 0 0 10px rgba(76, 175, 80, 0.4); }
        </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
    d1 = c1.date_input("Başlanğıc Tarixi", get_logical_date() - datetime.timedelta(days=7))
    d2 = c2.date_input("Bitiş Tarixi", get_logical_date())
    
    if c3.button("📈 Hesabla", type="primary", use_container_width=True):
        ts_start = datetime.datetime.combine(d1, datetime.time(0,0))
        ts_end = datetime.datetime.combine(d2, datetime.time(23,59))
        
        # 1. DÖVRİYYƏ (Revenue)
        sales = run_query("SELECT items, total FROM sales WHERE created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
        total_rev = sales['total'].sum() if not sales.empty else 0.0
        
        # 2. MAYA DƏYƏRİ (Food Cost / COGS) hesablanması
        menu_costs = {}
        recs = run_query("""
            SELECT r.menu_item_name, CAST(r.quantity_required AS FLOAT) as q, i.unit_cost 
            FROM recipes r JOIN ingredients i ON r.ingredient_name = i.name
        """)
        for _, r in recs.iterrows():
            m_name = r['menu_item_name']
            cost = float(r['q']) * float(r['unit_cost'] if pd.notna(r['unit_cost']) else 0)
            menu_costs[m_name] = menu_costs.get(m_name, 0.0) + cost
        
        total_cogs = 0.0
        if not sales.empty:
            for items_str in sales['items']:
                if not isinstance(items_str, str) or items_str == "Table Order": continue
                for p in items_str.split(", "):
                    if " x" in p:
                        try:
                            n_part, q_part = p.rsplit(" x", 1)
                            qty = int(q_part.split()[0])
                            total_cogs += menu_costs.get(n_part, 0.0) * qty
                        except: pass
        
        # 3. BRÜT QAZANC (Gross Profit)
        gross_profit = total_rev - total_cogs
        
        # 4. ƏMƏLİYYAT XƏRCLƏRİ (OPEX - İcarə, Maaş, Kommunal)
        fin = run_query("SELECT amount FROM finance WHERE type='out' AND created_at BETWEEN :s AND :e", {"s":ts_start, "e":ts_end})
        total_opex = fin['amount'].sum() if not fin.empty else 0.0
        
        # 5. XALİS QAZANC (Net Profit)
        net_profit = gross_profit - total_opex
        
        # Ekrana Çıxarış
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.markdown(f"<div class='cfo-card cfo-rev'><h4>Dövriyyə</h4><h2>{total_rev:.2f} ₼</h2></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='cfo-card cfo-cost'><h4>Maya Dəyəri</h4><h2>-{total_cogs:.2f} ₼</h2></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='cfo-card cfo-gross'><h4>Brüt Qazanc</h4><h2>{gross_profit:.2f} ₼</h2></div>", unsafe_allow_html=True)
        m4.markdown(f"<div class='cfo-card cfo-opex'><h4>Xərclər (OPEX)</h4><h2>-{total_opex:.2f} ₼</h2></div>", unsafe_allow_html=True)
        m5.markdown(f"<div class='cfo-card cfo-net'><h4>XALİS QAZANC</h4><h2>{net_profit:.2f} ₼</h2></div>", unsafe_allow_html=True)
        
        st.info("💡 Məsləhət: Maya Dəyəri Dövriyyənin 25-30%-dən yuxarıdırsa, təchizatçı qiymətlərinizi və israfı yoxlayın.")

def render_z_report_page():
    st.subheader("🧾 Z-Hesabat (Gündəlik)")
    start_dt, end_dt = get_shift_range()
    
    sales = run_query("SELECT payment_method, original_total, discount_amount, total FROM sales WHERE created_at >= :d", {"d": start_dt})
    fin_in = run_query("SELECT amount, source FROM finance WHERE type='in' AND created_at >= :d", {"d": start_dt})
    fin_out = run_query("SELECT amount, source FROM finance WHERE type='out' AND created_at >= :d", {"d": start_dt})
    
    total_sales = sales['total'].sum() if not sales.empty else 0.0
    total_disc = sales['discount_amount'].sum() if not sales.empty else 0.0
    
    cash_sales = sales[sales['payment_method']=='Cash']['total'].sum() if not sales.empty else 0.0
    card_sales = sales[sales['payment_method']=='Card']['total'].sum() if not sales.empty else 0.0
    staff_sales = sales[sales['payment_method']=='Staff']['total'].sum() if not sales.empty else 0.0
    
    cash_in = fin_in[fin_in['source']=='Kassa']['amount'].sum() if not fin_in.empty else 0.0
    card_in = fin_in[fin_in['source']=='Bank Kartı']['amount'].sum() if not fin_in.empty else 0.0
    
    cash_out = fin_out[fin_out['source']=='Kassa']['amount'].sum() if not fin_out.empty else 0.0
    card_out = fin_out[fin_out['source']=='Bank Kartı']['amount'].sum() if not fin_out.empty else 0.0
    
    expected_cash = cash_sales + cash_in - cash_out
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="background:var(--metal-panel); padding:20px; border-radius:10px; border:1px solid var(--border-color);">
            <h3 style="color:#ffd700; margin-top:0;">💰 Satışlar</h3>
            <p><strong>Dövriyyə:</strong> {total_sales + total_disc:.2f} ₼</p>
            <p><strong>Güzəşt:</strong> -{total_disc:.2f} ₼</p>
            <h4 style="color:#4CAF50;">Xalis Satış: {total_sales:.2f} ₼</h4>
            <hr>
            <p>Nağd Satış: {cash_sales:.2f} ₼</p>
            <p>Kartla Satış: {card_sales:.2f} ₼</p>
            <p>Personal: {staff_sales:.2f} ₼</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div style="background:var(--metal-panel); padding:20px; border-radius:10px; border:1px solid var(--border-color);">
            <h3 style="color:#64b5f6; margin-top:0;">💸 Kassa Hərəkəti</h3>
            <p>➕ Mədaxil (Nağd): {cash_in:.2f} ₼</p>
            <p>➕ Mədaxil (Kart): {card_in:.2f} ₼</p>
            <hr>
            <p>➖ Məxaric (Nağd): {cash_out:.2f} ₼</p>
            <p>➖ Məxaric (Kart): {card_out:.2f} ₼</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""
        <div style="background:var(--metal-panel); padding:20px; border-radius:10px; border:2px solid #ffd700; text-align:center;">
            <h3 style="color:#ffd700; margin-top:0;">KASSA QALIĞI (Gözlənilən)</h3>
            <h1 style="color:#4CAF50; font-size:40px; margin:10px 0;">{expected_cash:.2f} ₼</h1>
            <p style="color:#aaa; font-size:12px;">(Nağd Satış + Nağd Mədaxil - Nağd Məxaric)</p>
        </div>
        """, unsafe_allow_html=True)
