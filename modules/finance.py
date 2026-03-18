# modules/finance.py — PATCHED v2.1
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
    log_system(deleted_by, f"FINANCE_DELETE: id={record_id}, amount={row_data.get('amount')}, reason={reason}")


def update_finance_record(record_id, new_values, updated_by):
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty:
        raise ValueError(f"Record {record_id} not found")

    old_data = original.iloc[0].to_dict()
    run_action(
        "UPDATE finance SET amount=:a, category=:c, description=:d WHERE id=:id",
        {"a": new_values['amount'], "c": new_values['category'], "d": new_values['description'], "id": record_id}
    )
    audit_finance_action(record_id, "UPDATE", old_data, new_values, updated_by)
    log_system(updated_by, f"FINANCE_UPDATE: id={record_id}")


# ============================================================
# TRANSFER HELPER
# ============================================================
def execute_transfer(direction, amount, desc, user, is_test, commission=0):
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
    log_system(user, f"TRANSFER: {direction}, amount={amt}, commission={comm}")


# ============================================================
# MAIN PAGE
# ============================================================
def render_finance_page():
    if st.session_state.role not in ['admin', 'manager']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    st.subheader("💰 Maliyyə Mərkəzi (Nəzarət & Düzəliş)")

    is_t_active = st.session_state.get('test_mode', False)
    if is_t_active:
        st.warning("⚠️ Hazırda TEST rejimindəsiniz.")

    # ---- Kassa Açılışı ----
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
                    log_system(st.session_state.user, f"Kassa açılışı: {open_amt} ₼")
                    st.success(f"Gün {open_amt} AZN ilə başladı!")
                    time.sleep(1.5)
                    st.rerun()

    # ---- View Mode ----
    view_mode = st.radio("Görünüş Rejimi:", ["🕒 Bu Növbə (08:00+)", "📅 Ümumi Balans (Yekun)"], horizontal=True)
    log_date = get_logical_date()
    shift_start, shift_end = get_shift_range(log_date)

    # AYRICALIQ: sales table-da is_deleted yoxdur, finance-da var
    # sales üçün filter:
    sales_test_filter = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
    # finance üçün filter (is_deleted daxil):
    finance_test_filter = sales_test_filter + " AND (is_deleted IS NULL OR is_deleted = FALSE)"

    if "Növbə" in view_mode:
        time_cond = "AND created_at >= :d AND created_at < :e"
        params = {"d": shift_start, "e": shift_end}
    else:
        last_z = get_setting("last_z_report_time")
        last_z_dt = datetime.datetime.fromisoformat(last_z) if last_z else get_baku_now() - datetime.timedelta(days=365)
        time_cond = "AND created_at > :d"
        params = {"d": last_z_dt}

    # ---- Balans (Decimal) ----
    # SALES queries — NO is_deleted
    s_cash = safe_decimal(
        run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {time_cond} {sales_test_filter}", params).iloc[0]['s']
    )
    s_card = safe_decimal(
        run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {time_cond} {sales_test_filter}", params).iloc[0]['s']
    )

    # FINANCE queries — WITH is_deleted
    e_cash = safe_decimal(
        run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {time_cond} {finance_test_filter}", params).iloc[0]['e']
    )
    i_cash = safe_decimal(
        run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {time_cond} {finance_test_filter}", params).iloc[0]['i']
    )
    e_card = safe_decimal(
        run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' {time_cond} {finance_test_filter}", params).iloc[0]['e']
    )
    i_card = safe_decimal(
        run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Kart)') {time_cond} {finance_test_filter}", params).iloc[0]['i']
    )
    debt_out = safe_decimal(
        run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Nisyə / Borc' AND type='out' {time_cond} {finance_test_filter}", params).iloc[0]['e']
    )
    debt_in = safe_decimal(
        run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Nisyə / Borc' AND type='in' {time_cond} {finance_test_filter}", params).iloc[0]['i']
    )

    start_lim = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0" if "Növbə" in view_mode else "100.0"))
    disp_cash = start_lim + s_cash + i_cash - e_cash
    disp_card_view = s_card + i_card - e_card
    disp_debt = debt_out - debt_in

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("🏪 Kassa (Cibdə Olan)", f"{disp_cash:.2f} ₼")
    m2.metric(f"💳 Bank Kartı ({'Növbə' if 'Növbə' in view_mode else 'Seçilmiş'})", f"{disp_card_view:.2f} ₼")
    m3.metric("📝 Ödəniləcək Borc (Nisyə)", f"{disp_debt:.2f} ₼",
              delta="Bizim Borcumuz" if disp_debt > 0 else "Borc Yoxdur", delta_color="inverse")

    st.markdown("---")

    # ---- AI Audit ----
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: Maliyyə Audit"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin (Ayarlar).")
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
                                fin_str = "\n".join([
                                    f"Növ:{r['type']}|Kat:{r['category']}|Məbləğ:{r['amount']}|Mənbə:{r['source']}"
                                    for _, r in recent_fin.iterrows()
                                ])
                                prompt = f"Biznes auditor kimi son 50 maliyyə əməliyyatında şübhəli xərcləri tap:\n{fin_str}"
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background:#1e2226;padding:15px;border-left:5px solid #dc3545;'>{response.text}</div>", unsafe_allow_html=True)
                            else:
                                st.info("Data yoxdur.")
                        except Exception as e:
                            st.error(e)

        # ---- Kart Çıxarış ----
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
                            {"c": cw_reason, "a": str(Decimal(str(cw_amt))), "d": cw_desc,
                             "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                        )
                        st.success(f"{cw_amt} AZN kartdan çıxarıldı!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Məbləğ 0-dan böyük olmalıdır.")

        # ---- Balans Korreksiyası ----
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
                        
