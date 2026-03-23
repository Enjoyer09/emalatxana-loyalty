# modules/finance.py — FULL ARCHITECTURE v7.2 (HİSSƏ 1/2)
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
    inv_in = safe_decimal(run_query(f"SELECT SUM(amount) as i FROM finance WHERE category='İnvestisiya (Kapital)' AND type='in' {f_filt}").iloc[0]['i'])
    inv_out = safe_decimal(run_query(f"SELECT SUM(amount) as e FROM finance WHERE category='İnvestora Ödəniş (Qaytarılma)' AND type='out' {f_filt}").iloc[0]['e'])
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
            <small style="color: #888;">💰 İnvestora Borc (Kapital)</small><br><strong style="font-size: 20px;">{investor_fund:.2f} ₼</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- BUGÜNKÜ CƏDVƏL (ANA EKRANDA) ---
    st.markdown("#### 📊 Bugünkü Əməliyyatların Cədvəli")
    today_hist = run_query("""
        SELECT id, created_at, category, subject, source, amount, type, description 
        FROM finance WHERE created_at >= :d AND created_at < :e AND (is_deleted IS NULL OR is_deleted = FALSE)
        ORDER BY created_at DESC
    """, {"d": shift_start, "e": shift_end})
    
    if not today_hist.empty:
        today_hist['Tarix'] = pd.to_datetime(today_hist['created_at']).dt.strftime('%H:%M')
        today_hist['Məbləğ'] = today_hist.apply(lambda x: f"+{x['amount']}" if x['type']=='in' else f"-{x['amount']}", axis=1)
        st.dataframe(today_hist[['Tarix', 'category', 'subject', 'source', 'Məbləğ', 'description']], hide_index=True, use_container_width=True)
    else:
        st.info("Bu gün üçün hələlik heç bir kassa/maliyyə əməliyyatı yoxdur.")
# modules/finance.py — FULL ARCHITECTURE v7.2 (HİSSƏ 2/2)
    tab_ops, tab_history = st.tabs(["➕ Əməliyyatlar & Düzəliş", "📜 Geniş Tarixçə & Analiz"])

    with tab_ops:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🤝 X-Hesabat (Smen)", use_container_width=True):
                st.session_state.active_dialog = ("x_report", current_cash_box); st.rerun()
        with c2:
            if st.button("🔴 Z-Hesabat (Günü Bağla)", type="primary", use_container_width=True):
                st.session_state.active_dialog = ("z_report", current_cash_box); st.rerun()
        with c3:
            if st.button("⚖️ Kassa Düzəlişi", use_container_width=True):
                st.session_state.active_dialog = ("cash_adjust", current_cash_box); st.rerun()

        st.divider()
        with st.form("main_finance_form", clear_on_submit=True):
            st.markdown("##### 📝 Yeni Əməliyyat (Smart Xərc / Mədaxil)")
            
            transaction_type = st.radio("Əməliyyat Növünü Seçin:", ["Məxaric (Çıxış) 🔴", "Mədaxil (Giriş) 🟢"], horizontal=True)

            if transaction_type == "Mədaxil (Giriş) 🟢":
                st.info("💡 **Mədaxil (Giriş):** Kassaya və ya Banka daxil olan əlavə vəsaitlər (Satışdan kənar). Məsələn: İnvestorun pul qoyması, əlavə gəlirlər.")
                f_cat = st.selectbox("Kateqoriya", ["İnvestisiya (Kapital)", "Kredit", "Əlavə Gəlir", "Digər"])
            else:
                st.info("💡 **Məxaric (Çıxış):** Biznesdən çıxan pul. İnvestora pul qaytardıqda 'İnvestora Ödəniş' seçin ki, borcunuzdan silinsin.")
                f_cat = st.selectbox("Kateqoriya", ["İcarə", "İnvestora Ödəniş (Qaytarılma)", "Xammal Alışı", "Maaş/Avans", "Kommunal", "Cərimə/Polis", "Digər"])

            f_src = st.selectbox("Hansı Hesabdan / Hesaba?", ["Kassa (Yeşik)", "Bank Kartı", "Seyf"])
            db_src = "Kassa" if "Kassa" in f_src else f_src

            subs = sorted(list(set(SUBJECTS + ["Azərişıq", "Azərsu", "Market", "Kofe Təchizat", "İnvestor", "Dövlət/Vergi", "Mühafizə"])))
            f_sbj = st.selectbox("Kimə / Kimdən (Subyekt)?", subs)
            
            c_amt, c_date = st.columns(2)
            f_amt = c_amt.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0)
            f_date = c_date.date_input("Tarix (Keçmiş günlər üçün)", datetime.date.today())
            
            f_desc = st.text_input("Açıqlama / Qeyd (Mütləq deyil)")
            
            if st.form_submit_button("✅ Təsdiqlə və Qeydə Al", use_container_width=True):
                if f_amt > 0:
                    db_type = 'out' if "Məxaric" in transaction_type else 'in'
                    current_time = get_baku_now().time()
                    combined_datetime = datetime.datetime.combine(f_date, current_time)

                    run_action(
                        "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) "
                        "VALUES (:t, :c, :a, :s, :d, :u, :sb, :time, :tst)",
                        {"t": db_type, "c": f_cat, "a": str(safe_decimal(f_amt)), "s": db_src, "d": f_desc, "u": st.session_state.user, "sb": f_sbj, "time": combined_datetime, "tst": is_t_active}
                    )
                    st.success("Maliyyə əməliyyatı uğurla qeydə alındı!"); time.sleep(1); st.rerun()
                else:
                    st.error("Məbləğ 0-dan böyük olmalıdır!")

    with tab_history:
        h_start = st.date_input("Başlanğıc", datetime.date.today().replace(day=1), key="hist_start")
        h_end = st.date_input("Bitiş", datetime.date.today(), key="hist_end")
        
        hist = run_query("""
            SELECT id, created_at, category, subject, source, amount, type, description 
            FROM finance WHERE DATE(created_at) BETWEEN :s AND :e AND (is_deleted IS NULL OR is_deleted = FALSE)
            ORDER BY created_at DESC
        """, {"s": h_start, "e": h_end})
        
        if not hist.empty:
            hist['Tarix'] = pd.to_datetime(hist['created_at']).dt.strftime('%d.%m.%Y %H:%M')
            hist['Məbləğ'] = hist.apply(lambda x: f"+{x['amount']}" if x['type']=='in' else f"-{x['amount']}", axis=1)
            st.data_editor(hist[['id', 'Tarix', 'category', 'subject', 'source', 'Məbləğ', 'description']], hide_index=True, use_container_width=True)
            
            if st.checkbox("Analitik Qrafikləri Göstər"):
                exp = hist[hist['type']=='out']
                if not exp.empty:
                    st.plotly_chart(px.pie(exp, values='amount', names='category', title="Xərc Bölgüsü"), use_container_width=True)

    # Dialog çağırışları
    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "x_report": finance_x_dialog(d_data)
        elif d_type == "z_report": finance_z_dialog(d_data)
        elif d_type == "cash_adjust": finance_adjust_dialog(d_data)
        st.stop()

# --- Dialog Funksiyaları ---
@st.dialog("⚖️ Kassa Balansına Düzəliş")
def finance_adjust_dialog(current_calc_cash):
    st.warning("⚠️ Bu əməliyyat kassa qalığını birbaşa dəyişəcək və tarixçəyə 'Kassa Kəsiri' və ya 'Kassa Artığı' kimi düşəcək.")
    st.write(f"Sistemdəki Kassa (Hesablanan): **{current_calc_cash:.2f} ₼**")
    real_cash = st.number_input("Real olaraq kassada olan məbləği yazın:", value=float(current_calc_cash), step=1.0)
    reason = st.text_input("Səbəb / Qeyd:", placeholder="Məs: Xırda pul səhvi")
    
    if st.button("Düzəlişi Təsdiqlə", type="primary"):
        diff = Decimal(str(real_cash)) - Decimal(str(current_calc_cash))
        if abs(diff) > Decimal("0.001"):
            t_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            run_action(
                "INSERT INTO finance (type, category, amount, source, description, created_by, created_at) "
                "VALUES (:t, :c, :a, 'Kassa', :d, :u, :time)",
                {"t": t_type, "c": cat, "a": str(abs(diff)), "d": f"Kassa Düzəlişi: {reason}", "u": st.session_state.user, "time": get_baku_now()}
            )
            st.success(f"Kassa balansı düzəldildi! Fərq: {diff:.2f} ₼")
            time.sleep(1.5)
            st.session_state.active_dialog = None
            st.rerun()
        else:
            st.info("Fərq yoxdur, düzəlişə ehtiyac yoxdur.")

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
