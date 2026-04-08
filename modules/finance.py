# modules/finance.py
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
from utils import SUBJECTS, get_logical_date, get_shift_range, get_baku_now, log_system, safe_decimal, SK_CASH_LIMIT, close_shift

logger = logging.getLogger(__name__)

def audit_finance_action(original_id, action, original_data, new_data, performed_by, reason=""):
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
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty: return
    row_data = original.iloc[0].to_dict()
    run_action(
        "UPDATE finance SET is_deleted=TRUE, deleted_by=:by, deleted_at=:at WHERE id=:id",
        {"by": deleted_by, "at": get_baku_now(), "id": record_id}
    )
    audit_finance_action(record_id, "DELETE", row_data, None, deleted_by, reason)

def get_payment_mapping(payment_method):
    if payment_method in ['Nəğd', 'Cash']: return {"source": "Kassa", "category": "Satış (Nağd)", "tracks_finance": True}
    if payment_method in ['Kart', 'Card']: return {"source": "Bank Kartı", "category": "Satış (Kart)", "tracks_finance": True}
    return {"source": None, "category": None, "tracks_finance": False}

def get_finance_visibility_filters(include_test=False):
    test_clause = "" if include_test else "AND (is_test IS NULL OR is_test = FALSE)"
    deleted_clause = "AND (is_deleted IS NULL OR is_deleted = FALSE)"
    return test_clause, deleted_clause

def get_shift_finance_snapshot(include_test=False):
    log_date = get_logical_date()
    shift_start, shift_end = get_shift_range(log_date)
    t_filt = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if include_test else "AND (is_test IS NULL OR is_test = FALSE)"
    f_filt = t_filt + " AND (is_deleted IS NULL OR is_deleted = FALSE)"
    params = {"d": shift_start, "e": shift_end}

    cash_sales = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE category='Satış (Nağd)' AND type='in' AND created_at >= :d AND created_at < :e {f_filt}", params).iloc[0]['s'])
    card_sales = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE category='Satış (Kart)' AND type='in' AND created_at >= :d AND created_at < :e {f_filt}", params).iloc[0]['s'])
    cash_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' AND created_at >= :d AND created_at < :e {f_filt}", params).iloc[0]['e'])
    cash_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') AND created_at >= :d AND created_at < :e {f_filt}", params).iloc[0]['i'])
    bank_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' AND created_at >= :d AND created_at < :e {f_filt}", params).iloc[0]['e'])
    bank_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Satış (Kart)') AND created_at >= :d AND created_at < :e {f_filt}", params).iloc[0]['i'])
    opening_balance = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
    
    expected_cash = opening_balance + cash_sales + cash_in - cash_out
    
    cogs = safe_decimal(run_query("SELECT SUM(cogs) as s FROM sales WHERE created_at >= :d AND created_at < :e AND (is_test IS NULL OR is_test = FALSE) AND (status IS NULL OR status!='VOIDED')", params).iloc[0]['s'])
    refund_count = int(run_query("SELECT COUNT(*) as c FROM refunds WHERE created_at >= :d AND created_at < :e", params).iloc[0]['c'] or 0)

    return {
        "log_date": log_date, "shift_start": shift_start, "shift_end": shift_end, "opening_balance": opening_balance,
        "cash_sales": cash_sales, "card_sales": card_sales, "cash_in": cash_in, "cash_out": cash_out,
        "bank_in": bank_in, "bank_out": bank_out, "expected_cash": expected_cash, "cogs": cogs, "refund_count": refund_count,
    }

def get_balance_snapshot(include_test=False):
    t_filt = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if include_test else "AND (is_test IS NULL OR is_test = FALSE)"
    f_filt = t_filt + " AND (is_deleted IS NULL OR is_deleted = FALSE)"

    bank_sales = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE category='Satış (Kart)' AND type='in' {f_filt}").iloc[0]['s'])
    bank_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {f_filt}").iloc[0]['e'])
    bank_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Satış (Kart)') {f_filt}").iloc[0]['i'])
    investor_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE category='İnvestisiya (Kapital)' AND type='in' {f_filt}").iloc[0]['i'])
    investor_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE category='İnvestora Ödəniş (Qaytarılma)' AND type='out' {f_filt}").iloc[0]['e'])

    return {
        "bank_balance": bank_sales + bank_in - bank_out,
        "investor_fund": investor_in - investor_out,
        "bank_sales_total": bank_sales, "bank_in_total": bank_in, "bank_out_total": bank_out,
    }

def process_shift_handover(actual_cash, user, diff_note="X-Hesabat zamanı fərq", log_action="X_REPORT_CREATED"):
    snapshot = get_shift_finance_snapshot()
    expected_cash = snapshot["expected_cash"]
    actual_d = Decimal(str(actual_cash))
    diff = actual_d - expected_cash
    now = get_baku_now()
    actions = []

    if abs(diff) > Decimal("0.01"):
        c_type = 'in' if diff > 0 else 'out'
        cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', :d, :u, :time, FALSE)",
            {"t": c_type, "c": cat, "a": str(abs(diff)), "d": diff_note, "u": user, "time": now}
        ))

    actions.append((
        "INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:u, :e, :a, :t)",
        {"u": user, "e": str(expected_cash), "a": str(actual_d), "t": now}
    ))

    run_transaction(actions)
    set_setting(SK_CASH_LIMIT, str(actual_d))
    log_system(user, log_action, {"expected_cash": str(expected_cash), "actual_cash": str(actual_d), "difference": str(diff)})
    return {"expected_cash": expected_cash, "actual_cash": actual_d, "difference": diff}

def process_z_report(actual_cash, cash_drop, wage_amount, user, is_test=False, close_current_shift=True):
    snapshot = get_shift_finance_snapshot(include_test=is_test)
    expected_cash = snapshot["expected_cash"]
    actual_d = Decimal(str(actual_cash))
    drop_d = Decimal(str(cash_drop))
    wage_d = Decimal(str(wage_amount))
    next_open = actual_d - drop_d - wage_d
    if next_open < Decimal("0"): raise ValueError("Sabaha qalan açılış balansı mənfi ola bilməz.")
    diff = actual_d - expected_cash
    now = get_baku_now()
    actions = []

    if abs(diff) > Decimal("0.01"):
        c_type = 'in' if diff > 0 else 'out'
        cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat zamanı fərq', :u, :time, FALSE)",
            {"t": c_type, "c": cat, "a": str(abs(diff)), "u": user, "time": now}
        ))

    if drop_d > 0:
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'İnkassasiya (Rəhbərə verilən)', :a, 'Kassa', 'Z-Hesabat Çıxarışı', :u, :time, FALSE)",
            {"a": str(drop_d), "u": user, "time": now}
        ))

    if wage_d > 0:
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)",
            {"a": str(wage_d), "u": user, "subj": user, "time": now, "tst": is_test}
        ))

    actions.append((
        "INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)",
        {"ts": str(snapshot["cash_sales"] + snapshot["card_sales"]), "cs": str(snapshot["cash_sales"]), "crs": str(snapshot["card_sales"]), "cogs": str(snapshot["cogs"]), "ac": str(actual_d), "gb": user, "t": now}
    ))

    run_transaction(actions)
    set_setting(SK_CASH_LIMIT, str(next_open))
    if close_current_shift: close_shift(user)
    log_system(user, "Z_REPORT_CREATED", {"expected_cash": str(expected_cash), "actual_cash": str(actual_d), "cash_drop": str(drop_d), "wage_amount": str(wage_d), "next_open_cash": str(next_open), "difference": str(diff)})
    return {"expected_cash": expected_cash, "actual_cash": actual_d, "cash_drop": drop_d, "wage_amount": wage_d, "next_open": next_open, "difference": diff, "snapshot": snapshot}

def render_finance_page():
    if st.session_state.role not in ['admin', 'manager']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    st.subheader("💰 Maliyyə və Uçot Mərkəzi")
    is_t_active = st.session_state.get('test_mode', False)

    snapshot = get_shift_finance_snapshot(include_test=is_t_active)
    balance_snapshot = get_balance_snapshot(include_test=is_t_active)
    shift_start = snapshot["shift_start"]
    shift_end = snapshot["shift_end"]
    current_cash_box = snapshot["expected_cash"]

    t_filt = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
    f_filt = t_filt + " AND (is_deleted IS NULL OR is_deleted = FALSE)"
    opening_bal = snapshot["opening_balance"]
    bank_balance = balance_snapshot["bank_balance"]
    investor_fund = balance_snapshot["investor_fund"]

    st.markdown(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 20px;">
        <div style="flex: 1; background: #1e2226; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745;">
            <small style="color: #888;">🏪 Kassa (Cari Smen)</small><br><strong style="font-size: 20px;">{current_cash_box:.2f} ₼</strong>
        </div>
        <div style="flex: 1; background: #1e2226; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff;">
            <small style="color: #888;">💳 Bank Hesabı (Ümumi)</small><br><strong style="font-size: 20px;">{bank_balance:.2f} ₼</strong>
        </div>
        <div style="flex: 1; background: #1e2226; padding: 15px; border-radius: 10px; border-left: 5px solid #ffc107;">
            <small style="color: #888;">💰 İnvestora Borc (Ümumi)</small><br><strong style="font-size: 20px;">{investor_fund:.2f} ₼</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Reconciliation Checklist"):
        rec1, rec2, rec3, rec4 = st.columns(4)
        rec1.metric("Açılış Balansı", f"{opening_bal:.2f} ₼")
        rec2.metric("Nağd Satış", f"{snapshot['cash_sales']:.2f} ₼")
        rec3.metric("Satışsız Mədaxil", f"{snapshot['cash_in']:.2f} ₼")
        rec4.metric("Məxaric", f"{snapshot['cash_out']:.2f} ₼")
        st.write(f"Gözlənilən kassa: **{snapshot['expected_cash']:.2f} ₼**")
        st.write(f"Refund sayı: **{snapshot['refund_count']}** | Kart satış: **{snapshot['card_sales']:.2f} ₼** | COGS: **{snapshot['cogs']:.2f} ₼**")

    st.markdown("#### 📊 Bugünkü Əməliyyatların Cədvəli")
    hist_test_clause, hist_deleted_clause = get_finance_visibility_filters(include_test=is_t_active)
    today_hist = run_query(f"SELECT id, created_at, category, subject, source, amount, type, description FROM finance WHERE created_at >= :d AND created_at < :e {hist_test_clause} {hist_deleted_clause} ORDER BY created_at DESC", {"d": shift_start, "e": shift_end})
    
    if not today_hist.empty:
        today_hist['Tarix'] = pd.to_datetime(today_hist['created_at']).dt.strftime('%H:%M')
        today_hist['Məbləğ'] = today_hist.apply(lambda x: f"+{x['amount']}" if x['type']=='in' else f"-{x['amount']}", axis=1)
        st.dataframe(today_hist[['Tarix', 'category', 'subject', 'source', 'Məbləğ', 'description']], hide_index=True, use_container_width=True)

    tab_ops, tab_history = st.tabs(["➕ Əməliyyatlar & Düzəliş", "📜 Geniş Tarixçə"])

    with tab_ops:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🤝 X-Hesabat (Smen)", use_container_width=True): st.session_state.active_dialog = ("x_report", current_cash_box); st.rerun()
        with c2:
            if st.button("🔴 Z-Hesabat (Günü Bağla)", type="primary", use_container_width=True): st.session_state.active_dialog = ("z_report", current_cash_box); st.rerun()
        with c3:
            if st.button("⚖️ Kassa Düzəlişi", use_container_width=True): st.session_state.active_dialog = ("cash_adjust", current_cash_box); st.rerun()

        st.divider()
        with st.form("main_finance_form", clear_on_submit=True):
            st.markdown("##### 📝 Yeni Əməliyyat (Smart Xərc / Mədaxil)")
            transaction_type = st.radio("Əməliyyat Növünü Seçin:", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"], horizontal=True)
            if transaction_type == "Mədaxil (Giriş) 🟢": f_cat = st.selectbox("Kateqoriya", ["İnvestisiya (Kapital)", "Kredit", "Əlavə Gəlir", "Digər"])
            else: f_cat = st.selectbox("Kateqoriya", ["İcarə", "İnvestora Ödəniş (Qaytarılma)", "Xammal Alışı", "Maaş/Avans", "Kommunal", "Cərimə/Polis", "Digər"])

            f_src = st.selectbox("Hansı Hesabdan / Hesaba?", ["Kassa (Yeşik)", "Bank Kartı", "Seyf"])
            db_src = "Kassa" if "Kassa" in f_src else f_src
            subs = sorted(list(set(SUBJECTS + ["Azərişıq", "Azərsu", "Market", "Kofe Təchizat", "İnvestor", "Dövlət/Vergi", "Mühafizə"])))
            f_sbj = st.selectbox("Kimə / Kimdən (Subyekt)?", subs)
            c_amt, c_date = st.columns(2)
            f_amt = c_amt.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0)
            f_date = c_date.date_input("Tarix", datetime.date.today())
            f_desc = st.text_input("Açıqlama / Qeyd")
            
            if st.form_submit_button("✅ Təsdiqlə və Qeydə Al", use_container_width=True):
                if f_amt > 0:
                    db_type = 'out' if "Məxaric" in transaction_type else 'in'
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)", {"t": db_type, "c": f_cat, "a": str(safe_decimal(f_amt)), "s": db_src, "d": f_desc, "u": st.session_state.user, "sb": f_sbj, "time": datetime.datetime.combine(f_date, get_baku_now().time()), "tst": is_t_active})
                    st.success("Maliyyə əməliyyatı uğurla qeydə alındı!"); time.sleep(1); st.rerun()

    with tab_history:
        h_start = st.date_input("Başlanğıc", datetime.date.today().replace(day=1), key="hist_start")
        h_end = st.date_input("Bitiş", datetime.date.today(), key="hist_end")
        hist = run_query(f"SELECT id, created_at, category, subject, source, amount, type, description FROM finance WHERE DATE(created_at) BETWEEN :s AND :e {hist_test_clause} {hist_deleted_clause} ORDER BY created_at DESC", {"s": h_start, "e": h_end})
        if not hist.empty:
            hist['Tarix'] = pd.to_datetime(hist['created_at']).dt.strftime('%d.%m.%Y %H:%M')
            hist['Məbləğ'] = hist.apply(lambda x: f"+{x['amount']}" if x['type']=='in' else f"-{x['amount']}", axis=1)
            st.data_editor(hist[['id', 'Tarix', 'category', 'subject', 'source', 'Məbləğ', 'description']], hide_index=True, use_container_width=True)

    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "x_report": finance_x_dialog(d_data)
        elif d_type == "z_report": finance_z_dialog(d_data)
        elif d_type == "cash_adjust": finance_adjust_dialog(d_data)
        st.stop()

@st.dialog("⚖️ Kassa Balansına Düzəliş")
def finance_adjust_dialog(current_calc_cash):
    st.write(f"Sistemdəki Kassa: **{current_calc_cash:.2f} ₼**")
    real_cash = st.number_input("Real olaraq kassada olan məbləği yazın:", value=float(current_calc_cash), step=1.0)
    reason = st.text_input("Səbəb / Qeyd:")
    if st.button("Düzəlişi Təsdiqlə", type="primary"):
        diff = Decimal(str(real_cash)) - Decimal(str(current_calc_cash))
        if abs(diff) > Decimal("0.001"):
            t_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES (:t, :c, :a, 'Kassa', :d, :u, :time)", {"t": t_type, "c": cat, "a": str(abs(diff)), "d": f"Kassa Düzəlişi: {reason}", "u": st.session_state.user, "time": get_baku_now()})
            st.session_state.active_dialog = None
            st.rerun()

@st.dialog("🤝 X-Hesabat")
def finance_x_dialog(expected):
    if st.session_state.role == 'staff':
        st.warning("⚠️ KOR TƏHVİL REJİMİ (BLIND DROP)")
        actual = st.number_input("Kassanı sayın və olan real məbləği daxil edin:", min_value=0.0, step=1.0)
    else:
        st.write(f"Kassada olmalı: **{expected:.2f} ₼**")
        actual = st.number_input("Real məbləğ:", value=float(expected))
        
    if st.button("Təhvil Ver"):
        try:
            process_shift_handover(actual, st.session_state.user)
            st.session_state.active_dialog = None
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")

@st.dialog("🔴 Z-Hesabat")
def finance_z_dialog(expected):
    if st.session_state.role == 'staff':
        st.warning("⚠️ KOR TƏHVİL REJİMİ (BLIND DROP)")
        actual = st.number_input("Yeşikdə olan tam pulu sayın və daxil edin:", min_value=0.0, step=1.0)
    else:
        st.write(f"Kassada cəmi: **{expected:.2f} ₼**")
        actual = st.number_input("Yeşikdə olan tam pul:", value=float(expected))
        
    drop = st.number_input("Müdirə verilən (İnkassasiya):", min_value=0.0, max_value=float(actual))
    is_wage = st.checkbox("Gündəlik maaşlar çıxılsın?", value=True)
    wage_amt = 25.0 if st.session_state.role == 'admin' else 20.0
    
    final_next_day = Decimal(str(actual)) - Decimal(str(drop))
    if is_wage: final_next_day -= Decimal(str(wage_amt))
    st.write(f"Sabaha qalan xırda: **{final_next_day:.2f} ₼**")
    
    if st.button("Günü Bağla", type="primary"):
        try:
            process_z_report(actual, drop, wage_amt if is_wage else 0, st.session_state.user, is_test=st.session_state.get('test_mode', False), close_current_shift=True)
            st.session_state.active_dialog = None
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")
