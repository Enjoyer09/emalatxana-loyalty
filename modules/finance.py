# modules/finance.py — PATCHED v2.0
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

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

# ============================================================
# AUDIT TRAIL HELPERS
# ============================================================
def audit_finance_action(original_id, action, original_data, new_data, performed_by, reason=""):
    """Immutable audit log for finance changes"""
    run_action(
        "INSERT INTO finance_audit_log (original_id, action, original_data, new_data, performed_by, reason, performed_at) VALUES (:oid, :act, :od, :nd, :by, :r, :at)",
        {"oid": original_id, "act": action, "od": json.dumps(original_data, default=str) if original_data else None,
         "nd": json.dumps(new_data, default=str) if new_data else None, "by": performed_by, "r": reason, "at": get_baku_now()}
    )

def soft_delete_finance(record_id, deleted_by, reason):
    """Soft delete with audit trail"""
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty:
        raise ValueError(f"Record {record_id} not found")
    
    row_data = original.iloc[0].to_dict()
    
    actions = [
        ("UPDATE finance SET is_deleted=TRUE, deleted_by=:by, deleted_at=:at WHERE id=:id",
         {"by": deleted_by, "at": get_baku_now(), "id": record_id}),
    ]
    run_transaction(actions)
    audit_finance_action(record_id, "DELETE", row_data, None, deleted_by, reason)
    log_system(deleted_by, f"FINANCE_DELETE: id={record_id}, amount={row_data.get('amount')}, reason={reason}")

def update_finance_record(record_id, new_values, updated_by):
    """Update with audit trail"""
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty:
        raise ValueError(f"Record {record_id} not found")
    
    old_data = original.iloc[0].to_dict()
    run_action(
        "UPDATE finance SET amount=:a, category=:c, description=:d WHERE id=:id",
        {"a": new_values['amount'], "c": new_values['category'], "d": new_values['description'], "id": record_id}
    )
    audit_finance_action(record_id, "UPDATE", old_data, new_values, updated_by)
    log_system(updated_by, f"FINANCE_UPDATE: id={record_id}, old_amt={old_data.get('amount')}, new_amt={new_values['amount']}")

# ============================================================
# TRANSFER HELPER (Atomic)
# ============================================================
def execute_transfer(direction, amount, desc, user, is_test, commission=0):
    """Atomic double-entry transfer"""
    now = get_baku_now()
    amt = str(Decimal(str(amount)))
    comm = str(Decimal(str(commission))) if commission > 0 else "0"
    actions = []

    directions_map = {
        "card_to_cash": [
            ("out", "Daxili Transfer", amt, "Bank Kartı", desc + " (Kassaya)"),
            ("in", "Daxili Transfer", amt, "Kassa", desc + " (Kartdan)"),
        ],
        "cash_to_card": [
            ("out", "Daxili Transfer", amt, "Kassa", desc + " (Karta)"),
            ("in", "Daxili Transfer", amt, "Bank Kartı", desc + " (Kassadan)"),
        ],
        "cash_to_debt": [
            ("out", "Borc Ödənişi", amt, "Kassa", desc),
            ("in", "Borc Ödənişi", amt, "Nisyə / Borc", "Kassadan ödənildi"),
        ],
        "card_to_debt": [
            ("out", "Borc Ödənişi", amt, "Bank Kartı", desc),
            ("in", "Borc Ödənişi", amt, "Nisyə / Borc", "Kartdan ödənildi"),
        ],
    }

    entries = directions_map.get(direction, [])
    for typ, cat, a, src, d in entries:
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :time, :tst)",
            {"t": typ, "c": cat, "a": a, "s": src, "d": d, "u": user, "time": now, "tst": is_test}
        ))

    if commission > 0:
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Transfer xərci', :u, :time, :tst)",
            {"a": comm, "u": user, "time": now, "tst": is_test}
        ))

    run_transaction(actions)
    log_system(user, f"TRANSFER: {direction}, amount={amt}, commission={comm}")

# ============================================================
# MAIN FINANCE PAGE
# ============================================================
def render_finance_page():
    # Role guard
    if st.session_state.role not in ['admin', 'manager']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    st.subheader("💰 Maliyyə Mərkəzi")

    is_t_active = st.session_state.get('test_mode', False)
    if is_t_active:
        st.warning("⚠️ TEST rejimi aktiv")

    # ---- Opening Balance ----
    with st.expander("🔓 Səhər Kassanı Aç", expanded=False):
        # Check if already opened today
        today = get_logical_date()
        existing_open = run_query(
            "SELECT COUNT(*) c FROM finance WHERE category='Kassa Açılışı' AND DATE(created_at)=:d AND (is_test IS NULL OR is_test=FALSE) AND (is_deleted IS NULL OR is_deleted=FALSE)",
            {"d": today}
        )
        already_opened = not existing_open.empty and existing_open.iloc[0]['c'] > 0

        if already_opened:
            st.info("✅ Bu gün kassa artıq açılıb.")
        else:
            with st.form("open_register_form", clear_on_submit=True):
                c_open1, c_open2 = st.columns([3, 1])
                open_amt = c_open1.number_input("Açılış balansı (AZN)", min_value=0.0, step=1.0)
                if c_open2.form_submit_button("✅ Kassanı Aç"):
                    set_setting(SK_CASH_LIMIT, str(Decimal(str(open_amt))))
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', 'Kassa Açılışı', :a, 'Kassa', 'Səhər açılış balansı', :u, :t, :tst)",
                        {"a": str(open_amt), "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                    )
                    log_system(st.session_state.user, f"KASSA_OPENED: {open_amt} ₼")
                    st.success(f"Gün {open_amt} AZN ilə başladı!")
                    time.sleep(1.5)
                    st.rerun()

    # ---- View Mode ----
    view_mode = st.radio("Görünüş:", ["🕒 Bu Növbə", "📅 Ümumi Balans"], horizontal=True)
    log_date = get_logical_date()
    shift_start, shift_end = get_shift_range(log_date)

    not_deleted = "AND (is_deleted IS NULL OR is_deleted = FALSE)"
    test_filter = f"AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE) {not_deleted}" if is_t_active else f"AND (is_test IS NULL OR is_test = FALSE) {not_deleted}"

    if "Növbə" in view_mode:
        cond = f"AND created_at >= :d AND created_at < :e {test_filter}"
        params = {"d": shift_start, "e": shift_end}
    else:
        last_z = get_setting("last_z_report_time")
        last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else get_baku_now() - datetime.timedelta(days=365)
        cond = f"AND created_at > :d {test_filter}"
        params = {"d": last_z_dt}

    # ---- Balance Calculations (Decimal) ----
    s_cash = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {cond}", params).iloc[0]['s'])
    e_cash = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {cond}", params).iloc[0]['e'])
    i_cash = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {cond}", params).iloc[0]['i'])
    start_lim = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
    disp_cash = start_lim + s_cash + i_cash - e_cash

    s_card = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {cond}", params).iloc[0]['s'])
    e_card = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {cond}", params).iloc[0]['e'])
    i_card = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Kart)') {cond}", params).iloc[0]['i'])
    disp_card_view = s_card + i_card - e_card

    debt_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Nisyə / Borc' AND type='out' {cond}", params).iloc[0]['e'])
    debt_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Nisyə / Borc' AND type='in' {cond}", params).iloc[0]['i'])
    disp_debt = debt_out - debt_in

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("🏪 Kassa", f"{disp_cash:.2f} ₼")
    m2.metric("💳 Bank Kartı", f"{disp_card_view:.2f} ₼")
    m3.metric("📝 Borc", f"{disp_debt:.2f} ₼",
              delta="Bizim Borcumuz" if disp_debt > 0 else "Borc Yoxdur", delta_color="inverse")

    st.markdown("---")

    # ---- Card Withdrawal ----
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("💳 Bank Kartından Çıxarış", expanded=False):
            with st.form("card_withdraw_form"):
                c_amt, c_rsn = st.columns(2)
                max_withdraw = max(float(disp_card_view), 0.0)
                cw_amt = c_amt.number_input("Məbləğ (AZN)", max_value=max_withdraw, value=min(max_withdraw, 0.0), step=1.0)
                cw_reason = c_rsn.selectbox("Səbəb", ["Təsisçi Çıxarışı", "Xərc Ödənişi", "Transfer", "Digər"])
                cw_desc = st.text_input("Açıqlama", "Kartdan çıxarış")

                if st.form_submit_button("Kartdan Çıxarış Et", type="primary"):
                    if cw_amt > 0:
                        run_action(
                            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', :c, :a, 'Bank Kartı', :d, :u, :t, :tst)",
                            {"c": cw_reason, "a": str(Decimal(str(cw_amt))), "d": cw_desc, "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                        )
                        log_system(st.session_state.user, f"CARD_WITHDRAW: {cw_amt} AZN, reason={cw_reason}")
                        st.success(f"{cw_amt} AZN kartdan çıxarıldı!")
                        time.sleep(1.5)
                        st.rerun()

        # ---- Balance Correction ----
        MAX_AUTO_CORRECTION = Decimal("50.00")
        with st.expander("⚖️ Balans Korreksiyası", expanded=False):
            st.warning("Dikkatli olun! Böyük korreksiyalar admin təsdiqi tələb edəcək.")
            with st.form("sync_balance"):
                new_cash = st.number_input("Kassada olan HƏQİQİ məbləğ:", value=float(disp_cash), step=1.0)
                new_card = st.number_input("Kartda olan HƏQİQİ məbləğ:", value=float(disp_card_view), step=1.0)
                correction_reason = st.text_input("Korreksiya səbəbi (məcburi):", "")

                if st.form_submit_button("Balansları Bərabərləşdir"):
                    if not correction_reason.strip():
                        st.error("Korreksiya səbəbi yazılmalıdır!")
                    else:
                        cash_diff = Decimal(str(new_cash)) - disp_cash
                        card_diff = Decimal(str(new_card)) - disp_card_view
                        total_correction = abs(cash_diff) + abs(card_diff)

                        if total_correction > MAX_AUTO_CORRECTION:
                            # Create pending request
                            run_action(
                                "INSERT INTO correction_requests (requested_by, cash_diff, card_diff, reason, status, created_at) VALUES (:u, :cd, :crd, :r, 'PENDING', :t)",
                                {"u": st.session_state.user, "cd": str(cash_diff), "crd": str(card_diff), "r": correction_reason, "t": get_baku_now()}
                            )
                            st.warning(f"⚠️ Korreksiya ({total_correction:.2f} ₼) həddən yüksəkdir. Admin təsdiqi gözlənilir.")
                        else:
                            u = st.session_state.user
                            now = get_baku_now()
                            actions = []

                            if abs(cash_diff) > Decimal("0.01"):
                                c_type = 'in' if cash_diff > 0 else 'out'
                                actions.append((
                                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, 'Sistem Korreksiyası', :a, 'Kassa', :d, :u, :time, FALSE)",
                                    {"t": c_type, "a": str(abs(cash_diff)), "d": f"Korreksiya: {correction_reason}", "u": u, "time": now}
                                ))
                            if abs(card_diff) > Decimal("0.01"):
                                c_type = 'in' if card_diff > 0 else 'out'
                                actions.append((
                                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, 'Sistem Korreksiyası', :a, 'Bank Kartı', :d, :u, :time, FALSE)",
                                    {"t": c_type, "a": str(abs(card_diff)), "d": f"Korreksiya: {correction_reason}", "u": u, "time": now}
                                ))

                            if actions:
                                run_transaction(actions)
                                log_system(u, f"BALANCE_CORRECTION: cash_diff={cash_diff}, card_diff={card_diff}, reason={correction_reason}")
                            st.success("✅ Sinxronlaşdırıldı!")
                            time.sleep(1.5)
                            st.rerun()

    # ---- New Transaction ----
    with st.expander("➕ Yeni Əməliyyat / Transfer", expanded=False):
        t_op, t_tr = st.tabs(["Standart Əməliyyat", "Daxili Transfer 🔄"])

        with t_op:
            with st.form("new_fin_trx", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"])
                f_source = c2.selectbox("Mənbə", ["Kassa", "Bank Kartı", "Seyf", "Nisyə / Borc"])
                f_subj = c3.selectbox("Subyekt", SUBJECTS)

                c4, c5 = st.columns(2)
                f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kassa Açılışı", "Kommunal", "Kirayə", "Maaş/Avans", "Digər", "İnkassasiya"])
                f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
                f_desc = st.text_input("Qeyd")

                if st.form_submit_button("Təsdiqlə"):
                    db_type = 'out' if "Məxaric" in f_type else 'in'
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)",
                        {"t": db_type, "c": f_cat, "a": str(Decimal(str(f_amt))), "s": f_source, "d": f_desc,
                         "u": st.session_state.user, "sb": f_subj, "time": get_baku_now(), "tst": is_t_active}
                    )
                    log_system(st.session_state.user, f"FINANCE_NEW: {db_type}, {f_cat}, {f_amt} AZN")
                    st.success("Yazıldı!")
                    time.sleep(1)
                    st.rerun()

        with t_tr:
            with st.form("transfer_trx", clear_on_submit=True):
                c1, c2 = st.columns(2)
                t_dir_display = c1.selectbox("Transfer Yönü", [
                    "💳 Kartdan ➡️ 🏪 Kassaya",
                    "🏪 Kassadan ➡️ 💳 Karta",
                    "🏪 Kassadan ➡️ 📝 Borca",
                    "💳 Kartdan ➡️ 📝 Borca"
                ])
                t_amt = c2.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
                t_desc = st.text_input("Açıqlama", "Transfer")

                has_comm = st.checkbox("Bank Komissiyası var?")
                comm_amt = st.number_input("Komissiya (AZN)", min_value=0.0, step=0.01, value=0.0) if has_comm else 0.0

                if st.form_submit_button("Transferi Təsdiqlə"):
                    dir_map = {
                        "💳 Kartdan ➡️ 🏪 Kassaya": "card_to_cash",
                        "🏪 Kassadan ➡️ 💳 Karta": "cash_to_card",
                        "🏪 Kassadan ➡️ 📝 Borca": "cash_to_debt",
                        "💳 Kartdan ➡️ 📝 Borca": "card_to_debt",
                    }
                    direction = dir_map.get(t_dir_display, "card_to_cash")
                    try:
                        execute_transfer(direction, t_amt, t_desc, st.session_state.user, is_t_active, comm_amt)
                        st.success("Transfer İcra Edildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Transfer xətası: {e}")

    # ---- Transaction Table (Edit/Delete) ----
    st.markdown("---")
    st.subheader("✏️ Maliyyə Əməliyyatları")

    today = get_baku_now().date()
    start_of_month = today.replace(day=1)

    f_col1, f_col2, f_col3 = st.columns(3)
    date_filter = f_col1.selectbox("Tarix", ["Bu Ay", "Bu Gün", "Keçən Ay", "Bütün Zamanlar", "Xüsusi Aralıq"])
    type_filter = f_col2.selectbox("Növ", ["Hamısı", "Məxaric (Çıxış)", "Mədaxil (Giriş)"])
    src_filter = f_col3.selectbox("Mənbə", ["Hamısı", "Kassa", "Bank Kartı", "Seyf", "Nisyə / Borc"])
    hide_pos = st.checkbox("🛒 POS satışlarını gizlət", value=True)

    if date_filter == "Bu Ay":
        sd, ed = start_of_month, today
    elif date_filter == "Bu Gün":
        sd, ed = today, today
    elif date_filter == "Keçən Ay":
        first_day_last = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        last_day_last = today.replace(day=1) - datetime.timedelta(days=1)
        sd, ed = first_day_last, last_day_last
    elif date_filter == "Xüsusi Aralıq":
        d_range = st.date_input("Tarix Seçin", [today, today])
        sd, ed = (d_range[0], d_range[1]) if len(d_range) == 2 else (today, today)
    else:
        sd, ed = datetime.date(2000, 1, 1), today

    # Build query with proper conditions
    conditions = ["DATE(created_at) >= :sd", "DATE(created_at) <= :ed", "(is_deleted IS NULL OR is_deleted = FALSE)"]
    q_params = {"sd": sd, "ed": ed}

    if not is_t_active:
        conditions.append("(is_test IS NULL OR is_test = FALSE)")
    if type_filter == "Məxaric (Çıxış)":
        conditions.append("type = 'out'")
    elif type_filter == "Mədaxil (Giriş)":
        conditions.append("type = 'in'")
    if src_filter != "Hamısı":
        conditions.append("source = :src")
        q_params["src"] = src_filter

    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM finance WHERE {where_clause} ORDER BY created_at DESC"
    fin_df = run_query(query, q_params)

    if hide_pos and not fin_df.empty:
        pos_descriptions = ['POS Satış', 'Masa Satışı', 'Kart Satış Komissiyası', 'Masa Satış Komissiyası']
        fin_df = fin_df[~fin_df['description'].isin(pos_descriptions)]

    # Expense chart
    if not fin_df.empty and type_filter in ["Hamısı", "Məxaric (Çıxış)"]:
        expenses_only = fin_df[fin_df['type'] == 'out']
        if not expenses_only.empty:
            exclude_cats = ['Daxili Transfer', 'Borc Ödənişi', 'Sistem Korreksiyası', 'Təsisçi Çıxarışı', 'Bank Komissiyası']
            exp_grouped = expenses_only[~expenses_only['category'].isin(exclude_cats)].groupby('category')['amount'].sum().reset_index()
            
