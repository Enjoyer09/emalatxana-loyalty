# modules/finance.py — FULL ARCHITECTURE v6.5 (HİSSƏ 1/3)
import streamlit as st
import pandas as pd
import datetime
import time
import io
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
import plotly.express as px

from database import run_query, run_action, run_transaction, get_setting, set_setting
from utils import SUBJECTS, get_logical_date, get_shift_range, get_baku_now, log_system, safe_decimal, SK_CASH_LIMIT

logger = logging.getLogger(__name__)

# ============================================================
# AUDIT & DATA HELPERS
# ============================================================
def audit_finance_action(original_id, action, original_data, new_data, performed_by, reason=""):
    """Hər bir maliyyə dəyişikliyini tarixçəyə yazır"""
    run_action(
        "INSERT INTO finance_audit_log (original_id, action, original_data, new_data, performed_by, reason, performed_at) "
        "VALUES (:oid, :act, :od, :nd, :by, :r, :at)",
        {
            "oid": original_id,
            "act": action,
            "od": json.dumps(original_data, default=str) if original_data else None,
            "nd": json.dumps(new_data, default=str) if new_data else None,
            "by": performed_by,
            "r": reason,
            "at": get_baku_now()
        }
    )

def soft_delete_finance(record_id, deleted_by, reason):
    """Məlumatı tam silmir, arxivləşdirir (is_deleted=True)"""
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty: return
    row_data = original.iloc[0].to_dict()
    run_action(
        "UPDATE finance SET is_deleted=TRUE, deleted_by=:by, deleted_at=:at WHERE id=:id",
        {"by": deleted_by, "at": get_baku_now(), "id": record_id}
    )
    audit_finance_action(record_id, "DELETE", row_data, None, deleted_by, reason)

def execute_transfer(direction, amount, desc, user, is_test, commission=0):
    """Hesablararası pul köçürməsi (Kassa -> Bank və s.)"""
    now = get_baku_now()
    amt = str(safe_decimal(amount))
    actions = []
    
    # Yön xəritəsi
    mapping = {
        "cash_to_card": [("out", "Kassa", "Bank Kartı"), ("in", "Bank Kartı", "Kassa")],
        "card_to_cash": [("out", "Bank Kartı", "Kassa"), ("in", "Kassa", "Bank Kartı")],
        "cash_to_debt": [("out", "Kassa", "Borc Ödənişi"), ("in", "Nisyə / Borc", "Kassa")],
    }
    
    steps = mapping.get(direction)
    if steps:
        for typ, src, note_suffix in steps:
            actions.append((
                "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                "VALUES (:t, 'Daxili Transfer', :a, :s, :d, :u, :time, :tst)",
                {"t": typ, "a": amt, "s": src, "d": f"{desc} ({note_suffix})", "u": user, "time": now, "tst": is_test}
            ))
        run_transaction(actions)
# modules/finance.py — FULL ARCHITECTURE v6.5 (HİSSƏ 2/3)
def render_finance_page():
    if st.session_state.role not in ['admin', 'manager']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    st.subheader("💰 Maliyyə və Uçot Mərkəzi")
    is_t_active = st.session_state.get('test_mode', False)

    # --- Dinamik Balans Hesablamaları ---
    log_date = get_logical_date()
    shift_start, shift_end = get_shift_range(log_date)
    t_filt = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
    f_filt = t_filt + " AND (is_deleted IS NULL OR is_deleted = FALSE)"

    # 1. KASSA (Nağd Yeşik)
    s_cash = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') AND (status IS NULL OR status='COMPLETED') AND created_at >= :d AND created_at < :e {t_filt}", {"d": shift_start, "e": shift_end}).iloc[0]['s'])
    e_cash = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' AND created_at >= :d AND created_at < :e {f_filt}", {"d": shift_start, "e": shift_end}).iloc[0]['e'])
    i_cash = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') AND created_at >= :d AND created_at < :e {f_filt}", {"d": shift_start, "e": shift_end}).iloc[0]['i'])
    opening_bal = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
    current_cash_box = opening_bal + s_cash + i_cash - e_cash

    # 2. BANK (Terminal və Kart)
    s_card = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') AND (status IS NULL OR status='COMPLETED') {t_filt}").iloc[0]['s'])
    e_card = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {f_filt}").iloc[0]['e'])
    i_card = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Satış (Kart)') {f_filt}").iloc[0]['i'])
    bank_balance = s_card + i_card - e_card

    # 3. İNVESTOR (Seyf / Cib)
    inv_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Seyf' AND type='in' {f_filt}").iloc[0]['i'])
    inv_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Seyf' AND type='out' {f_filt}").iloc[0]['e'])
    investor_fund = inv_in - inv_out

    # --- Vizual Panel ---
    st.markdown(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
        <div style="flex: 1; background: #1e2226; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745;">
            <small style="color: #888;">🏪 Kassa (Yeşik)</small><br><strong style="font-size: 20px;">{current_cash_box:.2f} ₼</strong>
        </div>
        <div style="flex: 1; background: #1e2226; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff;">
            <small style="color: #888;">💳 Bank Hesabı</small><br><strong style="font-size: 20px;">{bank_balance:.2f} ₼</strong>
        </div>
        <div style="flex: 1; background: #1e2226; padding: 15px; border-radius: 10px; border-left: 5px solid #ffc107;">
            <small style="color: #888;">💰 İnvestor Fondu</small><br><strong style="font-size: 20px;">{investor_fund:.2f} ₼</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_ops, tab_history, tab_ai = st.tabs(["➕ Yeni Əməliyyat", "📜 Tarixçə & Analiz", "🤖 AI Auditor"])
# modules/finance.py — FULL ARCHITECTURE v6.5 (HİSSƏ 3/3)
    with tab_ops:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🤝 X-Hesabat (Smen Təhvil)", use_container_width=True):
                st.session_state.active_dialog = ("x_report", current_cash_box); st.rerun()
        with c2:
            if st.button("🔴 Z-Hesabat (Günü Bağla)", type="primary", use_container_width=True):
                st.session_state.active_dialog = ("z_report", current_cash_box); st.rerun()

        st.divider()
        with st.form("main_finance_form", clear_on_submit=True):
            st.markdown("##### 📝 Yeni Əməliyyat")
            f1, f2, f3 = st.columns(3)
            f_type = f1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"])
            f_src = f2.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf"])
            
            subs = sorted(list(set(SUBJECTS + ["Azərişıq", "Azərsu", "Market", "Kofe Təchizat", "İnvestor", "Dövlət/Vergi", "Mühafizə"])))
            f_sbj = f3.selectbox("Subyekt", subs)
            
            f4, f5 = st.columns(2)
            f_cat = f4.selectbox("Kateqoriya", ["Xammal Alışı", "Maaş/Avans", "Kirayə", "Kommunal", "Təsisçi İnvestisiyası", "Cərimə/Polis", "Digər"])
            f_amt = f5.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0)
            f_desc = st.text_input("Açıqlama")
            
            if st.form_submit_button("Təsdiqlə", use_container_width=True):
                run_action(
                    "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) "
                    "VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)",
                    {"t": 'out' if "Məxaric" in f_type else 'in', "c": f_cat, "a": str(safe_decimal(f_amt)), "s": f_src, "d": f_desc, "u": st.session_state.user, "sb": f_sbj, "time": get_baku_now(), "tst": is_t_active}
                )
                st.success("Qeydə alındı!"); time.sleep(1); st.rerun()

    with tab_history:
        h_start = st.date_input("Başlanğıc", datetime.date.today().replace(day=1))
        h_end = st.date_input("Bitiş", datetime.date.today())
        
        hist = run_query("""
            SELECT id, created_at, category, subject, source, amount, type, description 
            FROM finance WHERE DATE(created_at) BETWEEN :s AND :e AND (is_deleted IS NULL OR is_deleted = FALSE)
            ORDER BY created_at DESC
        """, {"s": h_start, "e": h_end})
        
        if not hist.empty:
            hist['Tarix'] = pd.to_datetime(hist['created_at']).dt.strftime('%d.%m %H:%M')
            hist['Məbləğ'] = hist.apply(lambda x: f"+{x['amount']}" if x['type']=='in' else f"-{x['amount']}", axis=1)
            
            st.data_editor(hist[['id', 'Tarix', 'category', 'subject', 'source', 'Məbləğ', 'description']], hide_index=True, use_container_width=True)
            
            # Analitika Diaqramı
            if st.checkbox("Analitik Qrafikləri Göstər"):
                exp = hist[hist['type']=='out']
                if not exp.empty:
                    st.plotly_chart(px.pie(exp, values='amount', names='category', title="Xərc Bölgüsü"), use_container_width=True)
        else:
            st.info("Məlumat yoxdur.")

    # Dialog çağırışları
    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "x_report": finance_x_dialog(d_data)
        elif d_type == "z_report": finance_z_dialog(d_data)
        st.stop()

# --- Dialog Funksiyaları ---
@st.dialog("🤝 X-Hesabat")
def finance_x_dialog(expected):
    st.write(f"Kassada olmalı: **{expected:.2f} ₼**")
    actual = st.number_input("Real məbləğ:", value=float(expected))
    if st.button("Təhvil Ver"):
        set_setting(SK_CASH_LIMIT, str(actual))
        st.success("Təhvil verildi!"); time.sleep(1); st.session_state.active_dialog = None; st.rerun()

@st.dialog("🔴 Z-Hesabat")
def finance_z_dialog(expected):
    st.write(f"Kassada cəmi: **{expected:.2f} ₼**")
    actual = st.number_input("Yeşikdə olan tam pul:", value=float(expected))
    drop = st.number_input("Müdirə verilən (İnkassasiya):", min_value=0.0, max_value=float(actual))
    
    # Maaş seçimi
    is_wage = st.checkbox("Gündəlik maaşlar çıxılsın?", value=True)
    wage_amt = 25.0 if st.session_state.role == 'admin' else 20.0
    
    final_next_day = Decimal(str(actual)) - Decimal(str(drop))
    if is_wage: final_next_day -= Decimal(str(wage_amt))
    
    st.write(f"Sabaha qalan xırda: **{final_next_day:.2f} ₼**")
    
    if st.button("Günü Bağla", type="primary"):
        now = get_baku_now()
        actions = []
        if is_wage:
            actions.append(("INSERT INTO finance (type, category, amount, source, subject, created_at) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', :u, :t)", {"a": str(wage_amt), "u": st.session_state.user, "t": now}))
        if drop > 0:
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_at) VALUES ('out', 'İnkassasiya', :a, 'Kassa', 'Z-Hesabat Çıxarışı', :t)", {"a": str(drop), "t": now}))
        
        run_transaction(actions)
        set_setting(SK_CASH_LIMIT, str(final_next_day))
        st.success("Gün bağlandı!"); time.sleep(1); st.session_state.active_dialog = None; st.rerun()    
