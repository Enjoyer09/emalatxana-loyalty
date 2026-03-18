# modules/finance.py — FINAL PATCHED v3.2
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
# AUDIT HELPERS
# ============================================================
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
    if original.empty:
        raise ValueError(f"Record {record_id} not found")

    row_data = original.iloc[0].to_dict()

    run_action(
        "UPDATE finance SET is_deleted=TRUE, deleted_by=:by, deleted_at=:at WHERE id=:id",
        {"by": deleted_by, "at": get_baku_now(), "id": record_id}
    )

    audit_finance_action(record_id, "DELETE", row_data, None, deleted_by, reason)

    log_system(
        deleted_by,
        "FINANCE_DELETE",
        {
            "record_id": record_id,
            "amount": row_data.get('amount'),
            "category": row_data.get('category'),
            "source": row_data.get('source'),
            "reason": reason
        }
    )


def update_finance_record(record_id, new_values, updated_by):
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty:
        raise ValueError(f"Record {record_id} not found")

    old_data = original.iloc[0].to_dict()

    run_action(
        "UPDATE finance SET amount=:a, category=:c, description=:d WHERE id=:id",
        {
            "a": str(Decimal(str(new_values['amount']))),
            "c": new_values['category'],
            "d": new_values['description'],
            "id": record_id
        }
    )

    audit_finance_action(record_id, "UPDATE", old_data, new_values, updated_by)

    log_system(
        updated_by,
        "FINANCE_UPDATE",
        {
            "record_id": record_id,
            "old_amount": old_data.get('amount'),
            "new_amount": new_values['amount'],
            "old_category": old_data.get('category'),
            "new_category": new_values['category']
        }
    )


def execute_transfer(direction, amount, desc, user, is_test, commission=0):
    now = get_baku_now()
    amt = str(Decimal(str(amount)))
    comm = str(Decimal(str(commission))) if commission > 0 else "0"
    actions = []

    directions_map = {
        "card_to_cash": [
            ("out", "Daxili Transfer", amt, "Bank Kartı", desc + " (Kassaya)"),
            ("in", "Daxili Transfer", amt, "Kassa", desc + " (Kartdan)")
        ],
        "cash_to_card": [
            ("out", "Daxili Transfer", amt, "Kassa", desc + " (Karta)"),
            ("in", "Daxili Transfer", amt, "Bank Kartı", desc + " (Kassadan)")
        ],
        "cash_to_debt": [
            ("out", "Borc Ödənişi", amt, "Kassa", desc),
            ("in", "Borc Ödənişi", amt, "Nisyə / Borc", "Kassadan ödənildi")
        ],
        "card_to_debt": [
            ("out", "Borc Ödənişi", amt, "Bank Kartı", desc),
            ("in", "Borc Ödənişi", amt, "Nisyə / Borc", "Kartdan ödənildi")
        ]
    }

    entries = directions_map.get(direction, [])
    for typ, cat, a, src, d in entries:
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
            "VALUES (:t, :c, :a, :s, :d, :u, :time, :tst)",
            {"t": typ, "c": cat, "a": a, "s": src, "d": d, "u": user, "time": now, "tst": is_test}
        ))

    if commission > 0:
        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
            "VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Transfer xərci', :u, :time, :tst)",
            {"a": comm, "u": user, "time": now, "tst": is_test}
        ))

    run_transaction(actions)

    log_system(
        user,
        "FINANCE_TRANSFER",
        {
            "direction": direction,
            "amount": amt,
            "commission": comm,
            "description": desc,
            "is_test": is_test
        }
    )


# ============================================================
# MAIN
# ============================================================
def render_finance_page():
    if st.session_state.role not in ['admin', 'manager']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    st.subheader("💰 Maliyyə Mərkəzi (Nəzarət & Düzəliş)")

    is_t_active = st.session_state.get('test_mode', False)
    if is_t_active:
        st.warning("⚠️ Hazırda TEST rejimindəsiniz.")

    with st.expander("🔓 Səhər Kassanı Aç (Opening Balance)", expanded=False):
        today = get_logical_date()
        existing_open = run_query(
            "SELECT COUNT(*) c FROM finance WHERE category='Kassa Açılışı' AND DATE(created_at)=:d "
            "AND (is_test IS NULL OR is_test=FALSE) AND (is_deleted IS NULL OR is_deleted=FALSE)",
            {"d": today}
        )
        already_opened = not existing_open.empty and existing_open.iloc[0]['c'] > 0

        if already_opened:
            st.info("✅ Bu gün kassa artıq açılıb.")
        else:
            with st.form("open_register_form", clear_on_submit=True):
                c_open1, c_open2 = st.columns([3, 1])
                open_amt = c_open1.number_input("Səhər kassada olan məbləğ (AZN)", min_value=0.0, step=1.0)
                if c_open2.form_submit_button("✅ Kassanı Bu Məbləğlə Aç"):
                    set_setting(SK_CASH_LIMIT, str(Decimal(str(open_amt))))
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                        "VALUES ('in', 'Kassa Açılışı', :a, 'Kassa', 'Səhər açılış balansı', :u, :t, :tst)",
                        {"a": str(open_amt), "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                    )
                    log_system(
                        st.session_state.user,
                        "CASH_REGISTER_OPENED",
                        {"amount": open_amt, "is_test": is_t_active}
                    )
                    st.success(f"Gün {open_amt} AZN ilə başladı!")
                    time.sleep(1.5)
                    st.rerun()

    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
    log_date = get_logical_date()
    shift_start, shift_end = get_shift_range(log_date)

    sales_test_filter = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
    finance_test_filter = sales_test_filter + " AND (is_deleted IS NULL OR is_deleted = FALSE)"

    if "Növbə" in view_mode:
        time_cond = "AND created_at >= :d AND created_at < :e"
        params = {"d": shift_start, "e": shift_end}
    else:
        last_z = get_setting("last_z_report_time")
        last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else get_baku_now() - datetime.timedelta(days=365)
        time_cond = "AND created_at > :d"
        params = {"d": last_z_dt}

    s_cash = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') AND (status IS NULL OR status='COMPLETED') {time_cond} {sales_test_filter}", params).iloc[0]['s'])
    s_card = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') AND (status IS NULL OR status='COMPLETED') {time_cond} {sales_test_filter}", params).iloc[0]['s'])

    e_cash = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {time_cond} {finance_test_filter}", params).iloc[0]['e'])
    i_cash = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {time_cond} {finance_test_filter}", params).iloc[0]['i'])
    e_card = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {time_cond} {finance_test_filter}", params).iloc[0]['e'])
    i_card = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Kart)') {time_cond} {finance_test_filter}", params).iloc[0]['i'])
    debt_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Nisyə / Borc' AND type='out' {time_cond} {finance_test_filter}", params).iloc[0]['e'])
    debt_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Nisyə / Borc' AND type='in' {time_cond} {finance_test_filter}", params).iloc[0]['i'])

    start_lim = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
    disp_cash = start_lim + s_cash + i_cash - e_cash
    disp_card_view = s_card + i_card - e_card
    disp_debt = debt_out - debt_in

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("🏪 Kassa (Cibdə Olan)", f"{disp_cash:.2f} ₼")
    m2.metric(f"💳 Bank Kartı ({'Növbə' if 'Növbə' in view_mode else 'Seçilmiş'})", f"{disp_card_view:.2f} ₼")
    m3.metric("📝 Ödəniləcək Borc (Nisyə)", f"{disp_debt:.2f} ₼", delta="Bizim Borcumuz" if disp_debt > 0 else "Borc Yoxdur", delta_color="inverse")

    st.markdown("---")

    # AI audit
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Maliyyə Audit"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin.")
            elif genai is None:
                st.warning("google-generativeai paketi quraşdırılmayıb.")
            else:
                if st.button("🔍 Maliyyə Məlumatlarını Skan Et", use_container_width=True):
                    with st.spinner("AI incələyir..."):
                        try:
                            genai.configure(api_key=api_key)
                            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else 'models/gemini-pro')
                            model = genai.GenerativeModel(chosen_model)
                            recent_fin = run_query(
                                "SELECT id, type, category, amount, source, description FROM finance "
                                "WHERE (is_deleted IS NULL OR is_deleted=FALSE) ORDER BY created_at DESC LIMIT 50"
                            )
                            if not recent_fin.empty:
                                fin_str = "\n".join([f"Növ:{r['type']}|Kat:{r['category']}|Məbləğ:{r['amount']}|Mənbə:{r['source']}" for _, r in recent_fin.iterrows()])
                                prompt = f"Biznes auditor kimi son 50 maliyyə əməliyyatında şübhəli xərcləri tap:\n{fin_str}"
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background:#1e2226;padding:15px;border-left:5px solid #dc3545;'>{response.text}</div>", unsafe_allow_html=True)
                            else:
                                st.info("Data yoxdur.")
                        except Exception as e:
                            st.error(e)

        with st.expander("💳 Bank Kartından Çıxarış", expanded=False):
            st.info("Kartda yığılan məbləği çıxarış edin.")
            with st.form("card_withdraw_form"):
                c_amt, c_rsn = st.columns(2)
                max_wd = max(float(disp_card_view), 0.0)
                cw_amt = c_amt.number_input("Çıxarılan Məbləğ (AZN)", max_value=max_wd if max_wd > 0 else 10000.0,
                                            value=max_wd if max_wd > 0 else 0.0, step=1.0)
                cw_reason = c_rsn.selectbox("Səbəb", ["Təsisçi Çıxarışı", "Xərc Ödənişi", "Transfer", "Digər"])
                cw_desc = st.text_input("Açıqlama", "Kartdan çıxarış")

                if st.form_submit_button("Kartdan Çıxarış Et", type="primary"):
                    if cw_amt > 0:
                        run_action(
                            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                            "VALUES ('out', :c, :a, 'Bank Kartı', :d, :u, :t, :tst)",
                            {"c": cw_reason, "a": str(Decimal(str(cw_amt))), "d": cw_desc, "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                        )
                        log_system(
                            st.session_state.user,
                            "CARD_WITHDRAWAL",
                            {
                                "amount": cw_amt,
                                "reason": cw_reason,
                                "description": cw_desc,
                                "is_test": is_t_active
                            }
                        )
                        st.success(f"{cw_amt} AZN kartdan çıxarıldı!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Məbləğ 0-dan böyük olmalıdır.")

        MAX_AUTO_CORRECTION = Decimal("50.00")
        with st.expander("⚖️ Balans Korreksiyası (Sinxronizasiya)", expanded=False):
            st.warning("Məcburi balans bərabərləşdirmə.")
            with st.form("sync_balance"):
                new_cash = st.number_input("Kassada olan HƏQİQİ nağd (AZN):", value=float(disp_cash), step=1.0)
                new_card = st.number_input("Kartda olan HƏQİQİ məbləğ (AZN):", value=float(disp_card_view), step=1.0)
                correction_reason = st.text_input("Korreksiya səbəbi (məcburi):", "")

                if st.form_submit_button("Balansları İndi Bərabərləşdir"):
                    if not correction_reason.strip():
                        st.error("Korreksiya səbəbi yazılmalıdır!")
                    else:
                        cash_diff = Decimal(str(new_cash)) - disp_cash
                        card_diff = Decimal(str(new_card)) - disp_card_view
                        total_correction = abs(cash_diff) + abs(card_diff)

                        if total_correction > MAX_AUTO_CORRECTION:
                            run_action(
                                "INSERT INTO correction_requests (requested_by, cash_diff, card_diff, reason, status, created_at) "
                                "VALUES (:u, :cd, :crd, :r, 'PENDING', :t)",
                                {"u": st.session_state.user, "cd": str(cash_diff), "crd": str(card_diff), "r": correction_reason, "t": get_baku_now()}
                            )
                            log_system(
                                st.session_state.user,
                                "BALANCE_CORRECTION_REQUEST",
                                {
                                    "cash_diff": str(cash_diff),
                                    "card_diff": str(card_diff),
                                    "reason": correction_reason,
                                    "status": "PENDING"
                                }
                            )
                            st.warning(f"⚠️ Korreksiya ({total_correction:.2f} ₼) həddən yüksəkdir. Admin təsdiqi gözlənilir.")
                        else:
                            u = st.session_state.user
                            now = get_baku_now()
                            actions = []

                            if abs(cash_diff) > Decimal("0.01"):
                                c_type = 'in' if cash_diff > 0 else 'out'
                                actions.append((
                                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                                    "VALUES (:t, 'Sistem Korreksiyası', :a, 'Kassa', :d, :u, :time, FALSE)",
                                    {"t": c_type, "a": str(abs(cash_diff)), "d": f"Korreksiya: {correction_reason}", "u": u, "time": now}
                                ))
                            if abs(card_diff) > Decimal("0.01"):
                                c_type = 'in' if card_diff > 0 else 'out'
                                actions.append((
                                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                                    "VALUES (:t, 'Sistem Korreksiyası', :a, 'Bank Kartı', :d, :u, :time, FALSE)",
                                    {"t": c_type, "a": str(abs(card_diff)), "d": f"Korreksiya: {correction_reason}", "u": u, "time": now}
                                ))

                            if actions:
                                run_transaction(actions)
                                log_system(
                                    u,
                                    "BALANCE_CORRECTION_APPLIED",
                                    {
                                        "cash_diff": str(cash_diff),
                                        "card_diff": str(card_diff),
                                        "reason": correction_reason
                                    }
                                )
                            st.success("✅ Sinxronlaşdırıldı!")
                            time.sleep(1.5)
                            st.rerun()

    with st.expander("➕ Yeni Əməliyyat / Daxili Transfer", expanded=False):
        t_op, t_tr = st.tabs(["Standart Əməliyyat", "Daxili Transfer 🔄"])

        with t_op:
            with st.form("new_fin_trx", clear_on_submit=True):
                st.info("💡 Əgər xərci kartla etmisinizsə, mənbə olaraq mütləq 'Bank Kartı' seçin.")
                c1, c2, c3 = st.columns(3)
                f_type = c1.selectbox("Növ", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"])
                f_source = c2.selectbox("Mənbə (Ödəmə Şəkli)", ["Kassa", "Bank Kartı", "Seyf", "Nisyə / Borc"])
                f_subj = c3.selectbox("Subyekt", SUBJECTS)

                c4, c5 = st.columns(2)
                f_cat = c4.selectbox("Kateqoriya", ["Xammal Alışı", "Kassa Açılışı", "Kommunal", "Kirayə", "Maaş/Avans", "Digər", "İnkassasiya (Rəhbərə verilən)"])
                f_amt = c5.number_input("Məbləğ (AZN)", min_value=0.01, step=0.01)
                f_desc = st.text_input("Qeyd")

                if st.form_submit_button("Təsdiqlə"):
                    db_type = 'out' if "Məxaric" in f_type else 'in'
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) "
                        "VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)",
                        {
                            "t": db_type,
                            "c": f_cat,
                            "a": str(Decimal(str(f_amt))),
                            "s": f_source,
                            "d": f_desc,
                            "u": st.session_state.user,
                            "sb": f_subj,
                            "time": get_baku_now(),
                            "tst": is_t_active
                        }
                    )
                    log_system(
                        st.session_state.user,
                        "FINANCE_ENTRY_CREATED",
                        {
                            "type": db_type,
                            "category": f_cat,
                            "amount": f_amt,
                            "source": f_source,
                            "subject": f_subj,
                            "description": f_desc,
                            "is_test": is_t_active
                        }
                    )
                    st.success("Yazıldı!")
                    time.sleep(1)
                    st.rerun()

        with t_tr:
            with st.form("transfer_trx", clear_on_submit=True):
                st.info("Kassadan Karta (və ya tərsi) transferlər üçün.")
                c1, c2 = st.columns(2)
                t_dir_display = c1.selectbox("Transfer Yönü", [
                    "💳 Bank Kartından ➡️ 🏪 Kassaya",
                    "🏪 Kassadan ➡️ 💳 Bank Kartına",
                    "🏪 Kassadan ➡️ 📝 Borcun Ödənməsinə",
                    "💳 Bank Kartından ➡️ 📝 Borcun Ödənməsinə"
                ])
                t_amt = c2.number_input("Transfer Məbləği (AZN)", min_value=0.01, step=0.01)
                t_desc = st.text_input("Açıqlama", "Transfer / Ödəniş")

                st.write("---")
                has_comm = st.checkbox("Bu transfer üçün Bank Komissiyası tutulub?")
                comm_amt = st.number_input("Komissiya Məbləği (AZN)", min_value=0.0, step=0.01, value=0.0) if has_comm else 0.0

                if st.form_submit_button("Transferi Təsdiqlə"):
                    dir_map = {
                        "💳 Bank Kartından ➡️ 🏪 Kassaya": "card_to_cash",
                        "🏪 Kassadan ➡️ 💳 Bank Kartına": "cash_to_card",
                        "🏪 Kassadan ➡️ 📝 Borcun Ödənməsinə": "cash_to_debt",
                        "💳 Bank Kartından ➡️ 📝 Borcun Ödənməsinə": "card_to_debt"
                    }
                    direction = dir_map.get(t_dir_display, "card_to_cash")
                    try:
                        execute_transfer(direction, t_amt, t_desc, st.session_state.user, is_t_active, comm_amt)
                        st.success("Transfer İcra Edildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Transfer xətası: {e}")

    st.markdown("---")
    st.subheader("✏️ Maliyyə Əməliyyatları (Düzəliş & Silmə)")
    st.info("Səhv yazılmış əməliyyatları seçin, dəyişib 'Yadda Saxla' basın və ya silin.")

    today = get_baku_now().date()
    start_of_month = today.replace(day=1)

    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        date_filter = st.selectbox("Tarix Aralığı", ["Bu Ay", "Bu Gün", "Keçən Ay", "Bütün Zamanlar", "Xüsusi Aralıq"])
    with f_col2:
        type_filter = st.selectbox("Əməliyyat Növü", ["Hamısı", "Məxaric (Çıxış)", "Mədaxil (Giriş)"])
    with f_col3:
        src_filter = st.selectbox("Mənbə", ["Hamısı", "Kassa", "Bank Kartı", "Seyf", "Nisyə / Borc"])

    hide_pos = st.checkbox("🛒 Gündəlik POS satışlarını gizlət", value=True)

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
        if len(d_range) == 2:
            sd, ed = d_range
        else:
            sd, ed = today, today
    else:
        sd, ed = datetime.date(2000, 1, 1), today

    conditions = [
        "DATE(created_at) >= :sd",
        "DATE(created_at) <= :ed",
        "(is_deleted IS NULL OR is_deleted = FALSE)"
    ]
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
        pos_descriptions = ['POS Satış', 'Masa Satışı', 'Kart Satış Komissiyası', 'Masa Satış Komissiyası', 'POS Satış (Split)', 'Masa Satışı (Split)']
        fin_df = fin_df[~fin_df['description'].isin(pos_descriptions)]

    if not fin_df.empty and (type_filter in ["Hamısı", "Məxaric (Çıxış)"]):
        expenses_only = fin_df[fin_df['type'] == 'out']
        if not expenses_only.empty:
            exclude_cats = ['Daxili Transfer', 'Borc Ödənişi', 'Sistem Korreksiyası', 'Təsisçi Çıxarışı', 'Bank Komissiyası']
            exp_grouped = expenses_only[~expenses_only['category'].isin(exclude_cats)].groupby('category')['amount'].sum().reset_index()
            if not exp_grouped.empty:
                st.markdown("**💸 Xərclərin Kateqoriyalar Üzrə Bölgüsü**")
                fig = px.pie(exp_grouped, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig, use_container_width=True)

    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        if not fin_df.empty:
            csv = fin_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel/CSV kimi Yüklə", data=csv, file_name=f"Maliyye_{sd}_{ed}.csv", mime="text/csv", use_container_width=True)

    with action_col2:
        api_key = get_setting("gemini_api_key", "")
        if st.button("🤖 AI Maliyyə Analizi Çıxar", type="primary", use_container_width=True):
            if fin_df.empty:
                st.warning("Analiz üçün kifayət qədər data yoxdur.")
            elif not api_key:
                st.error("⚠️ AI API Açarı tapılmadı!")
            elif genai is None:
                st.error("google-generativeai paketi quraşdırılmayıb.")
            else:
                try:
                    genai.configure(api_key=api_key)
                    valid_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else 'gemini-pro')
                    model = genai.GenerativeModel(chosen_model)

                    with st.spinner("🤖 AI analiz edir..."):
                        total_in = fin_df[fin_df['type'] == 'in']['amount'].sum()
                        total_out = fin_df[fin_df['type'] == 'out']['amount'].sum()

                        expenses_str = ""
                        exp_only = fin_df[fin_df['type'] == 'out']
                        if not exp_only.empty:
                            eg = exp_only.groupby('category')['amount'].sum().sort_values(ascending=False)
                            expenses_str = ", ".join([f"{cat}: {amt:.2f} AZN" for cat, amt in eg.items() if cat not in ['Daxili Transfer', 'Borc Ödənişi']])

                        prompt = f"""Sən kofe şopunun baş maliyyəçisisən.
{sd} - {ed} tarixləri arası:
- Mədaxil: {total_in:.2f} AZN
- Məxaric: {total_out:.2f} AZN
- Xərc kateqoriyaları: {expenses_str}
Qısa professional analiz və 2 cümləlik tövsiyə ver."""

                        response = model.generate_content(prompt)
                        st.success("✅ AI Analizi Tamamlandı!")

                        if gTTS is not None:
                            try:
                                tts = gTTS(text=response.text, lang='tr')
                                fp = io.BytesIO()
                                tts.write_to_fp(fp)
                                st.audio(fp, format='audio/mp3')
                            except Exception as audio_e:
                                st.warning(f"Səs xətası: {audio_e}")

                        st.markdown(f"""
                        <div style="background:#1e2226;padding:20px;border-left:5px solid #ffd700;border-radius:10px;">
                            {response.text}
                        </div>""", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"AI Analiz xətası: {e}")

    if not fin_df.empty:
        disp_df = fin_df.copy()
        disp_df['Tip'] = disp_df['type'].apply(lambda x: "🟢 Giriş" if x == 'in' else "🔴 Çıxış")
        disp_df['Tarix'] = pd.to_datetime(disp_df['created_at']).dt.strftime('%d.%m.%Y %H:%M')

        edit_cols = ['id', 'Tarix', 'Tip', 'category', 'amount', 'source', 'description']
        display_df = disp_df[edit_cols].copy()
        display_df.insert(0, "Seç", False)

        edited_fin = st.data_editor(
            display_df,
            hide_index=True,
            column_config={
                "Seç": st.column_config.CheckboxColumn(required=True),
                "amount": st.column_config.NumberColumn("Məbləğ (₼)", format="%.2f")
            },
            disabled=['id', 'Tarix', 'Tip', 'source'],
            use_container_width=True,
            key="fin_editor"
        )

        sel_fin = edited_fin[edited_fin["Seç"]]
        c_f1, c_f2 = st.columns(2)

        if c_f1.button("💾 Seçilənlərə Düzəliş Et", type="primary"):
            for _, r in sel_fin.iterrows():
                update_finance_record(
                    int(r['id']),
                    {"amount": r['amount'], "category": r['category'], "description": r['description']},
                    st.session_state.user
                )
            st.success("Yeniləndi!")
            time.sleep(1.5)
            st.rerun()

        if not sel_fin.empty:
            delete_reason = st.text_input("Silmə səbəbi (məcburi):", key="del_reason_input")
            if c_f2.button("🗑️ Seçilənləri Sil"):
                if not delete_reason.strip():
                    st.error("❌ Səbəb yazılmadan silmək olmaz!")
                else:
                    for i in sel_fin['id'].tolist():
                        soft_delete_finance(int(i), st.session_state.user, delete_reason)
                    st.success("Silindi (arxivləndi)!")
                    time.sleep(1.5)
                    st.rerun()
    else:
        st.write("Seçilmiş filtrlərə uyğun əməliyyat yoxdur.")
