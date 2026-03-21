# modules/pos.py — FINAL PATCHED v5.5 (HİSSƏ 1/4)
import streamlit as st
import json
import time
import logging
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import text

from database import run_query, run_action, run_transaction, get_setting, set_setting, conn
from utils import clean_qr_code, get_baku_now, get_logical_date, get_shift_range, log_system, safe_decimal, SK_CASH_LIMIT, get_active_happy_hour

logger = logging.getLogger(__name__)

@st.dialog("🧾 Satış Çeki")
def show_receipt_dialog(cart_data, total_amt, order_type="Paket"):
    import html as html_mod
    test_badge = "<p style='text-align:center;font-weight:bold;'>*** TEST ***</p>" if st.session_state.get('test_mode') else ""
    items_html = ""
    for item in cart_data:
        name = html_mod.escape(str(item['item_name']))
        qty = int(item['qty'])
        price = Decimal(str(item['price']))
        line = qty * price
        items_html += f"<tr><td>{name} x{qty}</td><td style='text-align:right;'>{line:.2f} ₼</td></tr>"
    total_d = Decimal(str(total_amt))
    receipt_html = f"""
    <div id="receipt_area" style="width:280px;padding:10px;font-family:'Courier New',monospace;color:black;background:white;">
        {test_badge}
        <h2 style="text-align:center;">EMALATKHANA</h2>
        <p style="text-align:center;font-size:12px;margin-bottom:2px;">{get_baku_now().strftime('%d.%m.%Y %H:%M')}</p>
        <p style="text-align:center;font-size:11px;margin-top:0;">Kassir: {html_mod.escape(st.session_state.user)} | Növ: <b>{order_type}</b></p>
        <hr style="border-top:1px dashed black;">
        <table style="width:100%;font-size:12px;">{items_html}</table>
        <hr style="border-top:1px dashed black;">
        <h3 style="text-align:right;">YEKUN: {total_d:.2f} ₼</h3>
        <p style="text-align:center;font-size:10px;margin-top:15px;">Bizi seçdiyiniz üçün təşəkkür edirik!</p>
    </div>
    """
    st.components.v1.html(receipt_html, height=500)
    if st.button("Bağla", use_container_width=True, key="dlg_close_receipt"):
        st.session_state.active_dialog = None
        st.rerun()

@st.dialog("🔐 Admin Təsdiqi (Test Mode)")
def test_auth_dialog():
    from utils import verify_password
    pin = st.text_input("Şifrə:", type="password", key="dlg_test_pin")
    if st.button("Təsdiqlə", type="primary", use_container_width=True, key="dlg_test_confirm"):
        r = run_query("SELECT username, password FROM users WHERE role='admin' LIMIT 1")
        if not r.empty and verify_password(pin, r.iloc[0]['password']):
            st.session_state.test_mode = True
            st.session_state.active_dialog = None
            log_system(st.session_state.user, "TEST_MODE_ENABLED", {"actor": st.session_state.user})
            st.rerun()
        else:
            st.error("Səhv şifrə!")
    if st.button("Ləğv et", use_container_width=True, key="dlg_test_cancel"):
        st.session_state.active_dialog = None
        st.rerun()

@st.dialog("📋 Variant Seçimi")
def variant_dialog(items, cart):
    st.write("Məhsulun növünü seçin:")
    for i, it in enumerate(items):
        if st.button(f"{it['item_name']} | {it['price']}₼", use_container_width=True, key=f"dlg_var_{i}"):
            add_to_cart(cart, {'item_name': it['item_name'], 'price': float(it['price']), 'qty': 1, 'is_coffee': it['is_coffee'], 'category': it['category'], 'status': 'new'})
            st.session_state.active_dialog = None
            st.rerun()
# modules/pos.py — FINAL PATCHED v5.5 (HİSSƏ 2/4)
def get_current_shift_expected_cash():
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)
    q_cond_fin = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (is_deleted IS NULL OR is_deleted=FALSE)"
    params = {"d": sh_start_z, "e": sh_end_z}
    s_cash = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE category='Satış (Nağd)' AND type='in' {q_cond_fin}", params).iloc[0]['s'])
    f_out = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond_fin}", params).iloc[0]['s'])
    f_in = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {q_cond_fin}", params).iloc[0]['s'])
    opening_limit = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
    return opening_limit + s_cash + f_in - f_out

@st.dialog("🤝 X-Hesabat (Smeni Təhvil Ver)")
def x_report_dialog():
    expected_cash = get_current_shift_expected_cash()
    st.info(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
    actual_cash = st.number_input("Real nağd məbləğ:", value=float(expected_cash), min_value=0.0, step=1.0)
    if st.button("🤝 Təhvil Ver", use_container_width=True, type="primary"):
        actual_d = Decimal(str(actual_cash))
        diff = actual_d - expected_cash
        u = st.session_state.user
        now = get_baku_now()
        actions = []
        if abs(diff) > Decimal("0.01"):
            c_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES (:t, :c, :a, 'Kassa', 'X-Hesabat fərqi', :u, :time)", {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}))
        actions.append(("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:u, :e, :a, :t)", {"u": u, "e": str(expected_cash), "a": str(actual_d), "t": now}))
        run_transaction(actions)
        set_setting(SK_CASH_LIMIT, str(actual_d))
        st.success("Təhvil verildi!")
        time.sleep(1.5); st.session_state.active_dialog = None; st.rerun()

@st.dialog("🔴 Z-Hesabat (Günü Bağla)")
def z_report_dialog():
    expected_cash = get_current_shift_expected_cash()
    st.warning("⚠️ Günü bağlamaq kassanı sıfırlayacaq!")
    st.info(f"Hazırda kassada var: **{expected_cash:.2f} ₼**")
    actual_z = st.number_input("Yeşikdə olan tam pul (AZN):", value=float(expected_cash), step=1.0)
    cash_drop = st.number_input("İnkassasiya (Müdirə verilən):", min_value=0.0, max_value=float(actual_z), value=0.0, step=10.0)
    next_open = Decimal(str(actual_z)) - Decimal(str(cash_drop))
    st.write(f"**Sabaha qalan xırda:** {next_open:.2f} ₼")
    if st.button("✅ Günü Bağla", use_container_width=True, type="primary"):
        u = st.session_state.user; now = get_baku_now()
        actions = []
        diff = Decimal(str(actual_z)) - expected_cash
        if abs(diff) > Decimal("0.01"):
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat fərqi', :u, :time)", {"t": 'in' if diff > 0 else 'out', "c": 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri', "a": str(abs(diff)), "u": u, "time": now}))
        if cash_drop > 0:
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('out', 'İnkassasiya', :a, 'Kassa', 'Z-Çıxarışı', :u, :time)", {"a": str(cash_drop), "u": u, "time": now}))
        run_transaction(actions)
        set_setting(SK_CASH_LIMIT, str(next_open))
        st.success("Gün bağlandı!"); time.sleep(1.5); st.session_state.active_dialog = None; st.rerun()
# modules/pos.py — FINAL PATCHED v5.5 (HİSSƏ 3/4)
def add_to_cart(cart, item):
    for i in cart:
        if i['item_name'] == item['item_name'] and i.get('status') == 'new':
            i['qty'] += 1
            return
    cart.append(item)

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0, is_eco_cup=False):
    total = Decimal("0"); final_total = Decimal("0"); disc_rate = Decimal("0")
    service_fee_pct = Decimal(str(get_setting("service_fee_percent", "0.0"))) / Decimal("100")
    active_hh = get_active_happy_hour() if manual_discount_percent == 0 else None
    
    if active_hh:
        if active_hh['categories'] == 'ALL': manual_discount_percent = active_hh['discount_percent']
    
    if manual_discount_percent > 0:
        disc_rate = Decimal(str(manual_discount_percent)) / Decimal("100")
        for i in cart:
            line = Decimal(str(i['qty'])) * Decimal(str(i['price']))
            total += line
            final_total += (line * (1 - disc_rate)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    else:
        for i in cart:
            line = Decimal(str(i['qty'])) * Decimal(str(i['price']))
            total += line
            final_total += line.quantize(Decimal("0.01"), ROUND_HALF_UP)
            
    if is_table and service_fee_pct > 0:
        final_total += (final_total * service_fee_pct).quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    return total, final_total, disc_rate, 0, 0, 0, False

def get_cached_menu():
    return run_query("SELECT * FROM menu WHERE is_active=TRUE")

def switch_cart(new_id):
    st.session_state.multi_carts[st.session_state.active_cart_id]['cart'] = st.session_state.cart_takeaway
    st.session_state.active_cart_id = new_id
    st.session_state.cart_takeaway = st.session_state.multi_carts[new_id]['cart']

def render_menu(cart, key):
    menu_df = get_cached_menu()
    if menu_df.empty:
        st.warning("Menyu boşdur."); return
    
    c_search, _ = st.columns([1, 1])
    pos_search = c_search.text_input("🔍 Axtar...", key=f"pos_s_{key}", label_visibility="collapsed")
    if pos_search:
        menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]

    existing_cats = sorted(menu_df['category'].dropna().unique().tolist())
    cats = ["HAMISI"] + [c.upper() for c in existing_cats]
    sc_upper = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_rad_{key}")
    sc = "Hamısı" if sc_upper == "HAMISI" else next((c for c in existing_cats if c.upper() == sc_upper), "Hamısı")
    prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]

    for row_start in range(0, len(prods), 4):
        cols = st.columns(4)
        for i, (_, r) in enumerate(prods.iloc[row_start:row_start+4].iterrows()):
            if cols[i].button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}", use_container_width=True):
                add_to_cart(cart, {'item_name': r['item_name'], 'price': float(r['price']), 'qty': 1, 'is_coffee': r['is_coffee'], 'category': r['category'], 'status': 'new'})
                st.rerun()
# modules/pos.py — FINAL PATCHED v5.5 (HİSSƏ 4/4)
def finalize_sale(cart_items, final_total, original_total, pm, user, cust, card_tips, is_test, split_cash=None, split_card=None, order_type="Paket"):
    now = get_baku_now(); final_d = Decimal(str(final_total)); original_d = Decimal(str(original_total))
    items_json = json.dumps(cart_items)
    
    with conn.session as s:
        try:
            sale_result = s.execute(text("""
                INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, tip_amount, is_test, status) 
                VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da,:tip,:tst,'COMPLETED') RETURNING id
            """), {"i": items_json, "t": str(final_d), "p": pm, "c": user, "time": now, "cid": cust['card_id'] if cust else None, "ot": str(original_d), "da": str(original_d-final_d), "tip": str(card_tips), "tst": is_test})
            sale_id = sale_result.fetchone()[0]
            
            # Kuxnaya "Növ" (Paket/Masa) ilə göndəririk
            s.execute(text("INSERT INTO kitchen_orders (sale_source, items, status, created_by, created_at, notes) VALUES ('POS', :items, 'NEW', :user, :time, :notes)"), {"items": items_json, "user": user, "time": now, "notes": f"Növ: {order_type}"})
            
            # Maliyyə yazılışı
            if not is_test:
                src = "Kassa" if "Nəğd" in pm else "Bank Kartı"
                cat = "Satış (Nağd)" if "Nəğd" in pm else "Satış (Kart)"
                s.execute(text("INSERT INTO finance (type, category, amount, source, created_by, created_at, sale_id) VALUES ('in', :cat, :a, :src, :u, :t, :sid)"), {"cat": cat, "a": str(final_d), "src": src, "u": user, "t": now, "sid": sale_id})
            
            s.commit()
            return sale_id
        except Exception as e:
            s.rollback(); raise e

def render_pos_page():
    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "receipt": show_receipt_dialog(d_data['cart'], d_data['total'], d_data.get('order_type', 'Paket'))
        elif d_type == "z_report": z_report_dialog()
        elif d_type == "x_report": x_report_dialog()
        elif d_type == "test_auth": test_auth_dialog()
        st.stop()

    # Naviqasiya
    c_nav = st.columns(6)
    for cid in [1, 2, 3]:
        if c_nav[cid-1].button(f"🛒 Səbət {cid}", type="primary" if cid == st.session_state.active_cart_id else "secondary", use_container_width=True):
            switch_cart(cid); st.rerun()
    if c_nav[3].button("🤝 X-Hesabat", use_container_width=True): st.session_state.active_dialog = ("x_report", None); st.rerun()
    if c_nav[4].button("🔴 Z-Hesabat", use_container_width=True): st.session_state.active_dialog = ("z_report", None); st.rerun()

    c_menu, c_cart = st.columns([2.5, 1.2])
    with c_menu: render_menu(st.session_state.cart_takeaway, "ta")
    with c_cart:
        with st.container(border=True):
            st.markdown(f"### 🛒 Səbət {st.session_state.active_cart_id}")
            
            # Sifariş Növü Seçimi
            order_type = st.radio("Sifariş Növü:", ["Paket 🥡", "Masada 🍽️"], horizontal=True)
            is_table = "Masada" in order_type
            
            raw, final, disc, free, _, _, _ = calculate_smart_total(st.session_state.cart_takeaway, is_table=is_table)
            
            for i, item in enumerate(st.session_state.cart_takeaway):
                st.write(f"**{item['item_name']}** x{item['qty']} ({item['price']*item['qty']:.2f}₼)")
            
            st.markdown(f"## {final:.2f} ₼")
            pm = st.radio("Metod", ["Nəğd", "Kart"], horizontal=True)
            
            if st.button("✅ ÖDƏNİŞİ TAMAMLA", type="primary", use_container_width=True):
                if not st.session_state.cart_takeaway: st.error("Səbət boşdur"); st.stop()
                sid = finalize_sale(st.session_state.cart_takeaway, final, raw, pm, st.session_state.user, None, 0, st.session_state.get('test_mode', False), order_type=order_type)
                st.session_state.active_dialog = ("receipt", {"cart": st.session_state.cart_takeaway.copy(), "total": float(final), "order_type": order_type})
                st.session_state.cart_takeaway = []; st.rerun()                
