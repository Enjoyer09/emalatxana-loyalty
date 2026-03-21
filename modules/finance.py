# modules/finance.py — REDESIGNED ARCHITECTURE v5.0 (HİSSƏ 1/2)
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
    log_system(deleted_by, "FINANCE_DELETE", {"record_id": record_id, "amount": row_data.get('amount'), "category": row_data.get('category'), "source": row_data.get('source'), "reason": reason})

def update_finance_record(record_id, new_values, updated_by):
    original = run_query("SELECT * FROM finance WHERE id=:id", {"id": record_id})
    if original.empty:
        raise ValueError(f"Record {record_id} not found")
    old_data = original.iloc[0].to_dict()
    run_action(
        "UPDATE finance SET amount=:a, category=:c, description=:d WHERE id=:id",
        {"a": str(safe_decimal(new_values['amount'])), "c": new_values['category'], "d": new_values['description'], "id": record_id}
    )
    audit_finance_action(record_id, "UPDATE", old_data, new_values, updated_by)
    log_system(updated_by, "FINANCE_UPDATE", {"record_id": record_id, "old_amount": old_data.get('amount'), "new_amount": new_values['amount']})

def execute_transfer(direction, amount, desc, user, is_test, commission=0):
    now = get_baku_now()
    amt = str(safe_decimal(amount))
    comm = str(safe_decimal(commission)) if commission > 0 else "0"
    actions = []
    directions_map = {
        "card_to_cash": [("out", "Daxili Transfer", amt, "Bank Kartı", desc + " (Kassaya)"), ("in", "Daxili Transfer", amt, "Kassa", desc + " (Kartdan)")],
        "cash_to_card": [("out", "Daxili Transfer", amt, "Kassa", desc + " (Karta)"), ("in", "Daxili Transfer", amt, "Bank Kartı", desc + " (Kassadan)")],
        "cash_to_debt": [("out", "Borc Ödənişi", amt, "Kassa", desc), ("in", "Borc Ödənişi", amt, "Nisyə / Borc", "Kassadan ödənildi")],
        "card_to_debt": [("out", "Borc Ödənişi", amt, "Bank Kartı", desc), ("in", "Borc Ödənişi", amt, "Nisyə / Borc", "Kartdan ödənildi")]
    }
    for typ, cat, a, src, d in directions_map.get(direction, []):
        actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, :s, :d, :u, :time, :tst)", {"t": typ, "c": cat, "a": a, "s": src, "d": d, "u": user, "time": now, "tst": is_test}))
    if commission > 0:
        actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Transfer xərci', :u, :time, :tst)", {"a": comm, "u": user, "time": now, "tst": is_test}))
    run_transaction(actions)
    log_system(user, "FINANCE_TRANSFER", {"direction": direction, "amount": amt, "is_test": is_test})


# ============================================================
# UI RENDER
# ============================================================
def render_finance_page():
    if st.session_state.role not in ['admin', 'manager']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    st.subheader("💰 Maliyyə və Uçot Mərkəzi")
    is_t_active = st.session_state.get('test_mode', False)
    if is_t_active:
        st.warning("⚠️ Hazırda TEST rejimindəsiniz.")

    tab_cash, tab_bank, tab_history = st.tabs([
        "🏪 Gündəlik Kassa (Nağd)", 
        "💳 Ümumi Uçot & Bank", 
        "✏️ Əməliyyatlar & Audit"
    ])

    # ============================================================
    # TAB 1: GÜNDƏLİK KASSA (Sırf Növbə / Shift)
    # ============================================================
    with tab_cash:
        st.info("Bu bölmə **yalnız fiziki kassa yeşiyindəki** (nağd) pulları göstərir və hər Z-hesabatda sıfırlanır.")
        
        log_date = get_logical_date()
        shift_start, shift_end = get_shift_range(log_date)
        
        existing_open = run_query(
            "SELECT COUNT(*) c FROM finance WHERE category='Kassa Açılışı' AND DATE(created_at)=:d "
            "AND (is_test IS NULL OR is_test=FALSE) AND (is_deleted IS NULL OR is_deleted=FALSE)",
            {"d": log_date}
        )
        already_opened = not existing_open.empty and existing_open.iloc[0]['c'] > 0

        if not already_opened:
            st.warning("⚠️ Bu gün üçün Kassa hələ açılmayıb!")
            with st.form("open_register_form"):
                open_amt = st.number_input("Səhər kassada olan xırda pul (Açılış Balansı - AZN)", min_value=0.0, step=1.0)
                if st.form_submit_button("✅ Kassanı Aç"):
                    set_setting(SK_CASH_LIMIT, str(safe_decimal(open_amt)))
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                        "VALUES ('in', 'Kassa Açılışı', :a, 'Kassa', 'Səhər açılış balansı', :u, :t, :tst)",
                        {"a": str(open_amt), "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                    )
                    log_system(st.session_state.user, "CASH_REGISTER_OPENED", {"amount": open_amt})
                    st.success(f"Kassa {open_amt} AZN ilə açıldı!")
                    time.sleep(1)
                    st.rerun()
        else:
            time_cond = "AND created_at >= :d AND created_at < :e"
            params = {"d": shift_start, "e": shift_end}
            t_filt = "AND (is_test IS NULL OR is_test = FALSE OR is_test = TRUE)" if is_t_active else "AND (is_test IS NULL OR is_test = FALSE)"
            f_filt = t_filt + " AND (is_deleted IS NULL OR is_deleted = FALSE)"

            s_cash = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') AND (status IS NULL OR status='COMPLETED') {time_cond} {t_filt}", params).iloc[0]['s'])
            e_cash = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE source='Kassa' AND type='out' {time_cond} {f_filt}", params).iloc[0]['e'])
            i_cash = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {time_cond} {f_filt}", params).iloc[0]['i'])
            
            start_lim = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
            disp_cash = start_lim + s_cash + i_cash - e_cash

            st.markdown(f"""
            <div style='background:#1e2226; padding:20px; border-radius:10px; border-left:5px solid #28a745;'>
                <h2 style='margin:0; color:#28a745;'>{disp_cash:.2f} ₼</h2>
                <p style='margin:0; color:#888;'>Fiziki Yeşikdə Olmalı Olan Nağd Pul</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            c1, c2, c3 = st.columns(3)
            c1.metric("Səhər Açılış", f"{start_lim:.2f} ₼")
            c2.metric("Günlük Nağd Satış", f"{s_cash:.2f} ₼")
            c3.metric("Nağd Xərclər", f"{e_cash:.2f} ₼", delta="Məxaric", delta_color="inverse")

            with st.expander("💸 Kassadan Sürətli Xərc (Məxaric)"):
                with st.form("quick_cash_out", clear_on_submit=True):
                    qo_cat = st.selectbox("Xərc Təyinatı", ["Xammal Alışı", "Kommunal", "Kirayə", "Maaş/Avans", "İnkassasiya (Rəhbərə verilən)", "Digər"])
                    qo_amt = st.number_input("Məbləğ (AZN)", min_value=0.01, step=1.0)
                    qo_desc = st.text_input("Açıqlama")
                    if st.form_submit_button("Təsdiqlə (Kassadan Çıx)"):
                        run_action(
                            "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', :c, :a, 'Kassa', :d, :u, :t, :tst)",
                            {"c": qo_cat, "a": str(safe_decimal(qo_amt)), "d": qo_desc, "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                        )
                        st.success("Məxaric qeydə alındı!")
                        time.sleep(1)
                        st.rerun()
# modules/finance.py — REDESIGNED ARCHITECTURE v5.0 (HİSSƏ 2/2)
            # --- X və Z HESABATLAR ÜÇÜN DIALOQLAR (Görünməsi üçün yuxarıda çağırılır) ---
            if st.session_state.get('active_dialog'):
                d_type, d_data = st.session_state.active_dialog
                if d_type == "x_report": 
                    x_report_dialog(d_data)
                elif d_type == "z_report": 
                    z_report_dialog(d_data)
                st.stop()

            st.write("---")
            c_x, c_z = st.columns(2)
            with c_x:
                if st.button("🤝 X-Hesabat (Növbəni Təhvil Ver)", use_container_width=True):
                    st.session_state.active_dialog = ("x_report", disp_cash)
                    st.rerun()
            with c_z:
                if st.button("🔴 Z-Hesabat (Günü Bağla)", type="primary", use_container_width=True):
                    st.session_state.active_dialog = ("z_report", disp_cash)
                    st.rerun()

    # ============================================================
    # TAB 2: ÜMUMİ UÇOT & BANK (Dəyişməyən Qlobal Balanslar)
    # ============================================================
    with tab_bank:
        st.info("Bu bölmə Z-hesabatla SIFIRLANMAYAN ümumi şirkət vəsaitlərini (Bank və Nisyə) idarə edir.")
        
        # Bütün zamanlar üçün Bank Kartı balansı
        s_card_all = safe_decimal(run_query("SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card', 'Bölünmüş ✂️') AND (status IS NULL OR status='COMPLETED') AND (is_test IS NULL OR is_test = FALSE)").iloc[0]['s'])
        e_card_all = safe_decimal(run_query("SELECT SUM(amount) as e FROM finance WHERE source='Bank Kartı' AND type='out' AND (is_deleted IS NULL OR is_deleted = FALSE) AND (is_test IS NULL OR is_test = FALSE)").iloc[0]['e'])
        i_card_all = safe_decimal(run_query("SELECT SUM(amount) as i FROM finance WHERE source='Bank Kartı' AND type='in' AND category NOT IN ('Satış (Kart)') AND (is_deleted IS NULL OR is_deleted = FALSE) AND (is_test IS NULL OR is_test = FALSE)").iloc[0]['i'])
        
        # Bütün zamanlar üçün Borc balansı
        debt_out_all = safe_decimal(run_query("SELECT SUM(amount) as e FROM finance WHERE source='Nisyə / Borc' AND type='out' AND (is_deleted IS NULL OR is_deleted = FALSE) AND (is_test IS NULL OR is_test = FALSE)").iloc[0]['e'])
        debt_in_all = safe_decimal(run_query("SELECT SUM(amount) as i FROM finance WHERE source='Nisyə / Borc' AND type='in' AND (is_deleted IS NULL OR is_deleted = FALSE) AND (is_test IS NULL OR is_test = FALSE)").iloc[0]['i'])
        
        bank_balance = s_card_all + i_card_all - e_card_all
        debt_balance = debt_out_all - debt_in_all

        b1, b2 = st.columns(2)
        b1.metric("💳 Bank Kartı (Real Balans)", f"{bank_balance:.2f} ₼")
        b2.metric("📝 Müştəri Borcları (Bizə Olan)", f"{debt_balance:.2f} ₼")

        st.write("---")
        with st.expander("💸 Bankdan Çıxarış və ya Xərc"):
            with st.form("bank_out_form", clear_on_submit=True):
                b_cat = st.selectbox("Təyinat", ["Təsisçi Çıxarışı", "İcarə", "Marketinq", "Vergi/Dövlət", "Maaş/Avans", "Digər Xərc"])
                b_amt = st.number_input("Məbləğ (AZN)", min_value=0.01, max_value=float(max(bank_balance, 0.01)), step=10.0)
                b_desc = st.text_input("Açıqlama")
                if st.form_submit_button("Təsdiqlə (Bankdan Çıx)", type="primary"):
                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', :c, :a, 'Bank Kartı', :d, :u, :t, :tst)",
                        {"c": b_cat, "a": str(safe_decimal(b_amt)), "d": b_desc, "u": st.session_state.user, "t": get_baku_now(), "tst": is_t_active}
                    )
                    st.success("Bankdan çıxış qeydə alındı!")
                    time.sleep(1)
                    st.rerun()

        with st.expander("🔄 Hesablararası Transfer"):
            with st.form("transfer_form", clear_on_submit=True):
                t_dir = st.selectbox("Yön", ["Kassadan ➡️ Banka (Mədaxil)", "Bankdan ➡️ Kassaya (Nağdlaşdırma)", "Borc Ödənişi ➡️ Kassaya", "Borc Ödənişi ➡️ Banka"])
                t_amt = st.number_input("Məbləğ (AZN)", min_value=0.01, step=1.0)
                t_desc = st.text_input("Açıqlama")
                has_comm = st.checkbox("Bank Komissiyası var?")
                c_amt = st.number_input("Komissiya (₼)", min_value=0.0, step=0.5) if has_comm else 0.0
                
                if st.form_submit_button("Transfer Et"):
                    dir_map = {
                        "Kassadan ➡️ Banka (Mədaxil)": "cash_to_card",
                        "Bankdan ➡️ Kassaya (Nağdlaşdırma)": "card_to_cash",
                        "Borc Ödənişi ➡️ Kassaya": "cash_to_debt",
                        "Borc Ödənişi ➡️ Banka": "card_to_debt"
                    }
                    execute_transfer(dir_map[t_dir], t_amt, t_desc, st.session_state.user, is_t_active, c_amt)
                    st.success("Transfer tamamlandı!")
                    time.sleep(1)
                    st.rerun()

    # ============================================================
    # TAB 3: ƏMƏLİYYATLAR VƏ AUDİT
    # ============================================================
    with tab_history:
        st.info("Bütün tarixi əməliyyatlara baxış, filtrləmə və səhvlərin düzəldilməsi.")
        
        today = get_baku_now().date()
        start_of_month = today.replace(day=1)

        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            date_filter = st.selectbox("Tarix Aralığı", ["Bu Ay", "Bu Gün", "Keçən Ay", "Xüsusi Aralıq", "Bütün Zamanlar"])
        with f_col2:
            type_filter = st.selectbox("Əməliyyat Növü", ["Hamısı", "Məxaric (Çıxış)", "Mədaxil (Giriş)"])
        with f_col3:
            src_filter = st.selectbox("Mənbə", ["Hamısı", "Kassa", "Bank Kartı", "Nisyə / Borc"])

        hide_pos = st.checkbox("🛒 Gündəlik POS satışlarını (kofe/yemək) gizlət", value=True)

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
            elif len(d_range) == 1:
                sd = ed = d_range[0]
            else:
                sd = ed = today
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
            pos_descriptions = ['POS Satış', 'Masa Satışı', 'POS Satış (Split)', 'Kart Satış Komissiyası', 'Kart Komissiya (Split)']
            fin_df = fin_df[~fin_df['description'].isin(pos_descriptions)]

        if not fin_df.empty and (type_filter in ["Hamısı", "Məxaric (Çıxış)"]):
            expenses_only = fin_df[fin_df['type'] == 'out']
            if not expenses_only.empty:
                exclude_cats = ['Daxili Transfer', 'Borc Ödənişi', 'Sistem Korreksiyası', 'Təsisçi Çıxarışı', 'İnkassasiya (Rəhbərə verilən)']
                exp_grouped = expenses_only[~expenses_only['category'].isin(exclude_cats)].groupby('category')['amount'].sum().reset_index()
                if not exp_grouped.empty:
                    st.markdown("**💸 Xərclərin Kateqoriyalar Üzrə Bölgüsü (Seçilmiş Aralıq)**")
                    fig = px.pie(exp_grouped, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                    st.plotly_chart(fig, use_container_width=True)

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
            
            # Export CSV
            csv = fin_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel/CSV kimi Yüklə", data=csv, file_name=f"Maliyye_Hesabat.csv", mime="text/csv")
            
        else:
            st.write("Seçilmiş filtrlərə uyğun əməliyyat yoxdur.")

# ============================================================
# DIALOG FUNKSİYALARI 
# ============================================================
@st.dialog("🤝 X-Hesabat (Smeni Təhvil Ver)")
def x_report_dialog(expected_cash):
    st.info(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
    actual_cash = st.number_input("Yeşikdə olan real məbləğ (AZN):", value=float(expected_cash), min_value=0.0, step=1.0)
    if st.button("🤝 Təhvil Ver", use_container_width=True, type="primary"):
        diff = Decimal(str(actual_cash)) - expected_cash
        u = st.session_state.user
        now = get_baku_now()
        actions = []
        if abs(diff) > Decimal("0.01"):
            c_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'X-Hesabat fərqi', :u, :time, FALSE)", {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}))
        actions.append(("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:u, :e, :a, :t)", {"u": u, "e": str(expected_cash), "a": str(actual_cash), "t": now}))
        try:
            run_transaction(actions)
            set_setting(SK_CASH_LIMIT, str(actual_cash)) 
            log_system(u, "X_REPORT_CREATED", {"expected_cash": str(expected_cash), "actual_cash": str(actual_cash), "difference": str(diff)})
            st.success(f"Növbə təhvil verildi! Kassa: {actual_cash:.2f} ₼")
            time.sleep(1.5)
            st.session_state.active_dialog = None
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")

@st.dialog("🔴 Z-Hesabat (Günü Bağla)")
def z_report_dialog(expected_cash):
    st.warning("⚠️ Diqqət: Günü bağlamaq kassanı sıfırlayacaq və bütün günlük əməliyyatları arxivləşdirəcək!")
    st.info(f"Hazırda kassada var: **{expected_cash:.2f} ₼**")
    
    with st.form("z_form"):
        actual_z = st.number_input("Yeşikdə olan tam pul (AZN):", value=float(expected_cash), step=1.0)
        cash_drop = st.number_input("İnkassasiya (Rəhbərə verilən/Seyfə qoyulan):", min_value=0.0, max_value=float(actual_z), value=0.0, step=10.0)
        next_open = Decimal(str(actual_z)) - Decimal(str(cash_drop))
        st.write(f"**Sabaha qalan açılış balansı (Xırda):** {next_open:.2f} ₼")
        
        if st.form_submit_button("✅ Günü Bağla", type="primary"):
            actual_z_d = Decimal(str(actual_z))
            drop_d = Decimal(str(cash_drop))
            u = st.session_state.user
            now = get_baku_now()
            diff = actual_z_d - expected_cash
            actions = []
            
            if abs(diff) > Decimal("0.01"):
                c_type = 'in' if diff > 0 else 'out'
                cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
                actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat fərqi', :u, :time, FALSE)", {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}))
            
            if drop_d > 0:
                actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'İnkassasiya (Rəhbərə verilən)', :a, 'Kassa', 'Z-Hesabat Çıxarışı', :u, :time, FALSE)", {"a": str(drop_d), "u": u, "time": now}))
                
            try:
                log_date_z = get_logical_date()
                sh_start_z, sh_end_z = get_shift_range(log_date_z)
                q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (status IS NULL OR status='COMPLETED')"
                rp = {"d": sh_start_z, "e": sh_end_z}
                
                s_cash_z = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {q_cond}", rp).iloc[0]['s'])
                s_card_z = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {q_cond}", rp).iloc[0]['s'])
                s_cogs_z = safe_decimal(run_query(f"SELECT SUM(cogs) as s FROM sales WHERE 1=1 {q_cond}", rp).iloc[0]['s'])
                
                actions.append(("INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)", {"ts": str(s_cash_z + s_card_z), "cs": str(s_cash_z), "crs": str(s_card_z), "cogs": str(s_cogs_z), "ac": str(actual_z_d), "gb": u, "t": now}))
                
                run_transaction(actions)
                set_setting("last_z_report_time", now.isoformat())
                set_setting(SK_CASH_LIMIT, str(next_open))
                log_system(u, "Z_REPORT_CREATED", {"expected_cash": str(expected_cash), "actual_cash": str(actual_z_d), "cash_drop": str(drop_d), "next_open": str(next_open)})
                
                st.success(f"Gün bağlandı! Rəhbərə verilən: {drop_d} AZN. Sabaha qalan: {next_open} AZN.")
                time.sleep(2)
                st.session_state.active_dialog = None
                st.rerun()
            except Exception as e:
                st.error(f"Xəta: {e}")
                logger.error(f"Z-report error: {e}", exc_info=True)
