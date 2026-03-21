# modules/pos.py — REDESIGNED ARCHITECTURE v5.0 (HİSSƏ 1/2)
import streamlit as st
import json
import time
import logging
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import text

from database import run_query, run_action, run_transaction, get_setting, set_setting, conn
from utils import clean_qr_code, get_baku_now, get_logical_date, get_shift_range, log_system, safe_decimal, SK_CASH_LIMIT, get_active_happy_hour
from modules.finance import execute_transfer # Finance modulundakı transfer funksiyası ehtiyac olarsa deyə

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
            log_system(st.session_state.get('user', 'unknown'), "TEST_MODE_FAILED")
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


def get_current_shift_expected_cash():
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)
    q_cond_sales = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (status IS NULL OR status='COMPLETED')"
    q_cond_fin = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (is_deleted IS NULL OR is_deleted=FALSE)"
    params = {"d": sh_start_z, "e": sh_end_z}
    
    s_cash = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE category='Satış (Nağd)' AND type='in' {q_cond_fin}", params).iloc[0]['s'])
    f_out = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond_fin}", params).iloc[0]['s'])
    f_in = safe_decimal(run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {q_cond_fin}", params).iloc[0]['s'])
    opening_limit = safe_decimal(get_setting(SK_CASH_LIMIT, "0.0"))
    
    return opening_limit + s_cash + f_in - f_out


@st.dialog("🤝 X-Hesabat (Növbəni Təhvil Ver)")
def x_report_dialog():
    expected_cash = get_current_shift_expected_cash()
    st.info(f"Kassada olmalıdır: **{expected_cash:.2f} ₼**")
    actual_cash = st.number_input("Kassada olan real məbləğ:", value=float(expected_cash), min_value=0.0, step=1.0)
    if st.button("🤝 Təhvil Ver", use_container_width=True, type="primary"):
        actual_d = Decimal(str(actual_cash))
        diff = actual_d - expected_cash
        u = st.session_state.user
        now = get_baku_now()
        actions = []
        if abs(diff) > Decimal("0.01"):
            c_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'X-Hesabat zamanı fərq', :u, :time, FALSE)", {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}))
        actions.append(("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:u, :e, :a, :t)", {"u": u, "e": str(expected_cash), "a": str(actual_d), "t": now}))
        try:
            run_transaction(actions)
            set_setting(SK_CASH_LIMIT, str(actual_d))
            log_system(u, "X_REPORT_CREATED", {"expected_cash": str(expected_cash), "actual_cash": str(actual_d), "difference": str(diff)})
            st.success(f"Təhvil verildi! Kassa: {actual_d:.2f} ₼")
            time.sleep(1.5)
            st.session_state.active_dialog = None
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")


@st.dialog("🔴 Z-Hesabat (Günü Bağla)")
def z_report_dialog():
    expected_cash = get_current_shift_expected_cash()
    st.warning("⚠️ Diqqət: Günü bağlamaq kassanı sıfırlayacaq və bütün günlük əməliyyatları arxivləşdirəcək!")
    st.info(f"Hazırda kassada var: **{expected_cash:.2f} ₼**")
    
    actual_z = st.number_input("Yeşikdə olan tam pul (AZN):", value=float(expected_cash), step=1.0)
    cash_drop = st.number_input("İnkassasiya (Rəhbərə çatan pul):", min_value=0.0, max_value=float(actual_z), value=0.0, step=10.0)
    
    default_wage = 25.0 if st.session_state.role in ['manager', 'admin'] else 20.0
    wage_amt = st.number_input("Götürülən Maaş (AZN):", value=default_wage, min_value=0.0, step=1.0)
    
    next_open = Decimal(str(actual_z)) - Decimal(str(cash_drop)) - Decimal(str(wage_amt))
    st.write(f"**Sabaha qalan açılış balansı (Xırda):** {next_open:.2f} ₼")

    if st.button("✅ Günü Bağla", use_container_width=True, type="primary"):
        actual_z_d = Decimal(str(actual_z))
        wage_d = Decimal(str(wage_amt))
        drop_d = Decimal(str(cash_drop))
        u = st.session_state.user
        now = get_baku_now()
        is_t = st.session_state.get('test_mode', False)
        diff = actual_z_d - expected_cash
        actions = []
        
        if abs(diff) > Decimal("0.01"):
            c_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat zamanı fərq', :u, :time, FALSE)", {"t": c_type, "c": cat, "a": str(abs(diff)), "u": u, "time": now}))
        
        if drop_d > 0:
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'İnkassasiya (Rəhbərə verilən)', :a, 'Kassa', 'Z-Hesabat Çıxarışı', :u, :time, FALSE)", {"a": str(drop_d), "u": u, "time": now}))
            
        if wage_d > 0:
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)", {"a": str(wage_d), "u": u, "subj": u, "time": now, "tst": is_t}))
            
        try:
            log_date_z = get_logical_date()
            sh_start_z, sh_end_z = get_shift_range(log_date_z)
            q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE) AND (status IS NULL OR status='COMPLETED')"
            rp = {"d": sh_start_z, "e": sh_end_z}
            s_cash_z = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {q_cond}", rp).iloc[0]['s'])
            s_card_z = safe_decimal(run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {q_cond}", rp).iloc[0]['s'])
            s_cogs_z = safe_decimal(run_query(f"SELECT SUM(cogs) as s FROM sales WHERE 1=1 {q_cond}", rp).iloc[0]['s'])
            
            actions.append(("INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)", {"ts": str(s_cash_z + s_card_z), "cs": str(s_cash_z), "crs": str(s_card_z), "cogs": str(s_cogs_z), "ac": str(actual_z_d), "gb": u, "t": now}))
        except Exception as e:
            logger.error(f"Z-report data error: {e}")
            
        try:
            run_transaction(actions)
            set_setting(SK_CASH_LIMIT, str(next_open))
            set_setting("last_z_report_time", now.isoformat())
            log_system(u, "Z_REPORT_CREATED", {"expected_cash": str(expected_cash), "next_open_cash": str(next_open), "wage_amount": str(wage_d), "drop": str(drop_d)})
            st.success(f"Gün bağlandı! Sabaha qalan xırda: {next_open} AZN.")
            time.sleep(1.5)
            st.session_state.active_dialog = None
            st.rerun()
        except Exception as e:
            st.error(f"Xəta: {e}")


def add_to_cart(cart, item):
    for i in cart:
        if i['item_name'] == item['item_name'] and i.get('status') == 'new':
            i['qty'] += 1
            return
    cart.append(item)


def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0, is_eco_cup=False):
    total = Decimal("0")
    final_total = Decimal("0")
    disc_rate = Decimal("0")
    current_stars = 0
    service_fee_pct = Decimal(str(get_setting("service_fee_percent", "0.0"))) / Decimal("100")
    is_ikram = False
    has_croissant_promo = customer and "CROISSANT50" in str(customer.get('secret_token', ''))

    active_hh = get_active_happy_hour() if manual_discount_percent == 0 else None
    hh_category_discount = False
    allowed_cats = []
    hh_disc_rate = Decimal("0")

    if active_hh:
        hh_cats = active_hh['categories']
        hh_pct = active_hh['discount_percent']
        if hh_cats == 'ALL':
            manual_discount_percent = hh_pct
        else:
            hh_category_discount = True
            allowed_cats = [c.strip() for c in hh_cats.split(',')]
            hh_disc_rate = Decimal(str(hh_pct)) / Decimal("100")

    if manual_discount_percent > 0:
        disc_rate = Decimal(str(manual_discount_percent)) / Decimal("100")
        for i in cart:
            line = Decimal(str(i['qty'])) * Decimal(str(i['price']))
            total += line
            final_total += (line - (line * disc_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if is_table and service_fee_pct > 0:
            final_total += (final_total * service_fee_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return total, final_total, disc_rate, 0, 0, 0, False

    if customer:
        current_stars = customer.get('stars', 0)
        ctype = customer.get('type', 'standard')
        if ctype == 'ikram':
            total = sum([Decimal(str(i['qty'])) * Decimal(str(i['price'])) for i in cart], Decimal("0"))
            return total, Decimal("0"), Decimal("1"), 0, 0, 0, True
        rates = {'golden': '0.05', 'platinum': '0.10', 'elite': '0.20', 'thermos': '0.20', 'telebe': '0.15'}
        disc_rate = Decimal(rates.get(ctype, '0'))

    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
    free_coffees_to_give = free_cof

    for i in cart:
        item_price = Decimal(str(i['price']))
        if has_croissant_promo and ("kruasan" in i['item_name'].lower() or "croissant" in i['item_name'].lower()):
            item_price = (item_price * Decimal("0.5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if hh_category_discount and i.get('category') in allowed_cats:
            item_price = (item_price * (Decimal("1") - hh_disc_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        line_original = Decimal(str(i['qty'])) * Decimal(str(i['price']))
        total += line_original

        if i.get('is_coffee') and free_coffees_to_give > 0:
            free_from_this = min(i['qty'], free_coffees_to_give)
            paid_qty = i['qty'] - free_from_this
            line_paid = (Decimal(str(paid_qty)) * item_price * (Decimal("1") - disc_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            final_total += line_paid
            free_coffees_to_give -= free_from_this
        else:
            line_disc = (Decimal(str(i['qty'])) * item_price * (Decimal("1") - disc_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            final_total += line_disc

    if is_table and service_fee_pct > 0:
        final_total += (final_total * service_fee_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return total, final_total, disc_rate, free_cof, 0, 0, False


def get_cached_menu():
    return run_query("SELECT * FROM menu WHERE is_active=TRUE")

def switch_cart(new_id):
    st.session_state.multi_carts[st.session_state.active_cart_id]['cart'] = st.session_state.cart_takeaway
    st.session_state.multi_carts[st.session_state.active_cart_id]['customer'] = st.session_state.current_customer_ta
    st.session_state.active_cart_id = new_id
    st.session_state.cart_takeaway = st.session_state.multi_carts[new_id]['cart']
    st.session_state.current_customer_ta = st.session_state.multi_carts[new_id]['customer']

def clear_customer_data_callback():
    st.session_state.current_customer_ta = None
    st.session_state.search_key_counter += 1
    def render_menu(cart, key):
    menu_df = get_cached_menu()
    CAT_ORDER = {"Kofe (Dənələr)": 0, "Kombolar": 1, "Süd Məhsulları": 2, "Bar Məhsulları (Su/Buz)": 3, "Siroplar": 4, "Soslar və Pastalar": 5, "Qablaşdırma (Stəkan/Qapaq)": 6, "Şirniyyat (Hazır)": 7, "İçkilər (Hazır)": 8, "Meyvə-Tərəvəz": 9, "Təsərrüfat/Təmizlik": 10, "Mətbəə / Kartlar": 11}

    if menu_df.empty:
        st.warning("Menyu boşdur.")
        return

    menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER).fillna(99)
    menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])

    c_search, _ = st.columns([1, 1])
    pos_search = c_search.text_input("🔍 Axtar...", key=f"pos_s_{key}", label_visibility="collapsed")
    if pos_search:
        menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]

    existing_cats = sorted(menu_df['category'].dropna().unique().tolist(), key=lambda x: CAT_ORDER.get(x, 99))
    cats = ["HAMISI"] + [c.upper() for c in existing_cats]
    sc_upper = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_rad_{key}")
    sc = "Hamısı" if sc_upper == "HAMISI" else next((c for c in existing_cats if c.upper() == sc_upper), "Hamısı")

    prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]

    if prods.empty:
        st.info("Bu kateqoriyada məhsul yoxdur.")
        return

    groups = {}
    for _, r in prods.iterrows():
        n = r['item_name']
        base = n
        for s in [" S", " M", " L", " XL", " Single", " Double"]:
            if n.endswith(s):
                base = n[:-len(s)]
                break
        if base not in groups:
            groups[base] = []
        groups[base].append(r)

    group_items = list(groups.items())
    for row_start in range(0, len(group_items), 4):
        cols = st.columns(4)
        row_slice = group_items[row_start:row_start + 4]
        for col_idx, (base, items) in enumerate(row_slice):
            with cols[col_idx]:
                if len(items) > 1:
                    if st.button(f"{base}\n▾", key=f"grp_btn_{base}_{key}_{sc}_{row_start}_{col_idx}", use_container_width=True, type="secondary"):
                        st.session_state.active_dialog = ("variants", items)
                        st.rerun()
                else:
                    r = items[0]
                    btn_color = "primary" if r['category'] == "Kombolar" else "secondary"
                    if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"prod_btn_{r['id']}_{key}_{sc}_{row_start}_{col_idx}", use_container_width=True, type=btn_color):
                        add_to_cart(cart, {'item_name': r['item_name'], 'price': float(r['price']), 'qty': 1, 'is_coffee': r['is_coffee'], 'category': r['category'], 'status': 'new'})
                        st.rerun()


# ============ HİSSƏ 2 BAŞLAYIR ============

def finalize_sale(cart_items, final_total, original_total, pm, user, cust, card_tips, is_test, split_cash=None, split_card=None, order_type="Paket"):
    now = get_baku_now()
    final_d = Decimal(str(final_total))
    original_d = Decimal(str(original_total))
    tips_d = Decimal(str(card_tips))
    discount_d = original_d - final_d
    items_json = json.dumps(cart_items)
    total_cogs = Decimal("0")

    if not is_test:
        with conn.session as s:
            try:
                for it in cart_items:
                    recs = run_query("SELECT r.ingredient_name, r.quantity_required, i.unit_cost FROM recipes r LEFT JOIN ingredients i ON r.ingredient_name = i.name WHERE r.menu_item_name=:m", {"m": it['item_name']})
                    if not recs.empty:
                        for _, r in recs.iterrows():
                            # Eko stekan
                            ing_name = str(r['ingredient_name']).lower()
                            if it.get('is_eco', False) and ('stəkan' in ing_name or 'stakan' in ing_name or 'cup' in ing_name or 'qab' in ing_name):
                                continue
                                
                            qty_req = Decimal(str(r['quantity_required'])) * Decimal(str(it['qty']))
                            u_cost = safe_decimal(r['unit_cost'])
                            total_cogs += qty_req * u_cost
                            s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n"), {"q": str(qty_req), "n": r['ingredient_name']})

                sale_result = s.execute(text("""
                    INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, tip_amount, is_test, cogs, status) 
                    VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da,:tip,:tst,:cogs,'COMPLETED') RETURNING id
                """), {"i": items_json, "t": str(final_d), "p": pm, "c": user, "time": now, "cid": cust['card_id'] if cust else None, "ot": str(original_d), "da": str(discount_d), "tip": str(tips_d), "tst": is_test, "cogs": str(total_cogs)})
                sale_id = sale_result.fetchone()[0]

                # Mətbəx ekranına növü (Paket/Masada) göndəririk
                s.execute(text("INSERT INTO kitchen_orders (sale_source, items, status, created_by, created_at, notes) VALUES ('POS', :items, 'NEW', :user, :time, :notes)"), {"items": items_json, "user": user, "time": now, "notes": f"Növ: {order_type}"})

                if final_d > 0:
                    if split_cash is not None and split_card is not None:
                        if split_cash > 0:
                            s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id) VALUES ('in', 'Satış (Nağd)', :a, 'Kassa', 'POS Satış (Split)', :u, :t, FALSE, :sid)"), {"a": str(split_cash), "u": user, "t": now, "sid": sale_id})
                        if split_card > 0:
                            s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id) VALUES ('in', 'Satış (Kart)', :a, 'Bank Kartı', 'POS Satış (Split)', :u, :t, FALSE, :sid)"), {"a": str(split_card), "u": user, "t": now, "sid": sale_id})
                            min_comm = Decimal(str(get_setting("bank_comm_min", "0.60")))
                            pct_comm = Decimal(str(get_setting("bank_comm_pct", "0.02")))
                            comm = max(min_comm, (split_card * pct_comm).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                            s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Kart Komissiya (Split)', :u, :t, FALSE, :sid)"), {"a": str(comm), "u": user, "t": now, "sid": sale_id})
                    else:
                        if pm != 'Staff':
                            db_pm = "Kassa" if pm == "Nəğd" else "Bank Kartı"
                            pm_cat = "Satış (Nağd)" if pm == "Nəğd" else "Satış (Kart)"
                            s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id) VALUES ('in', :cat, :a, :src, 'POS Satış', :u, :t, FALSE, :sid)"), {"cat": pm_cat, "a": str(final_d), "src": db_pm, "u": user, "t": now, "sid": sale_id})
                            if pm == "Kart":
                                min_comm = Decimal(str(get_setting("bank_comm_min", "0.60")))
                                pct_comm = Decimal(str(get_setting("bank_comm_pct", "0.02")))
                                comm = max(min_comm, (final_d * pct_comm).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                                s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Kart Satış Komissiyası', :u, :t, FALSE, :sid)"), {"a": str(comm), "u": user, "t": now, "sid": sale_id})

                if tips_d > 0:
                    s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, sale_id) VALUES ('in', 'Tips / Çayvoy', :a, 'Bank Kartı', 'Kart Tip', :u, :t, :sid)"), {"a": str(tips_d), "u": user, "t": now, "sid": sale_id})
                    s.execute(text("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, sale_id) VALUES ('out', 'Tips / Çayvoy', :a, 'Kassa', 'Kart Tip (Staffa)', :u, :t, :sid)"), {"a": str(tips_d), "u": user, "t": now, "sid": sale_id})

                if cust:
                    coffee_qty = sum([i['qty'] for i in cart_items if i.get('is_coffee')])
                    current_stars = cust.get('stars', 0)
                    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
                    new_stars = max(0, current_stars + coffee_qty - (free_cof * 10))
                    s.execute(text("UPDATE customers SET stars = :ns WHERE card_id = :cid"), {"ns": new_stars, "cid": cust['card_id']})

                s.commit()
                log_system(user, "SALE_CREATED", {"sale_id": sale_id, "total": str(final_d), "payment_method": pm, "is_test": is_test, "items_count": len(cart_items), "split_cash": str(split_cash) if split_cash is not None else None, "split_card": str(split_card) if split_card is not None else None, "customer_card_id": cust['card_id'] if cust else None, "discount_amount": str(discount_d), "tip_amount": str(tips_d), "cogs": str(total_cogs), "order_type": order_type})
                return sale_id
            except Exception as e:
                s.rollback()
                logger.error(f"finalize_sale failed: {e}", exc_info=True)
                raise e
    else:
        with conn.session as s:
            try:
                sale_result = s.execute(text("""
                    INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, tip_amount, is_test, cogs, status) 
                    VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da,:tip,:tst,:cogs,'COMPLETED') RETURNING id
                """), {"i": items_json, "t": str(final_d), "p": pm, "c": user, "time": now, "cid": cust['card_id'] if cust else None, "ot": str(original_d), "da": str(discount_d), "tip": str(tips_d), "tst": True, "cogs": "0"})
                sale_id = sale_result.fetchone()[0]
                s.execute(text("INSERT INTO kitchen_orders (sale_source, items, status, created_by, created_at, notes) VALUES ('POS', :items, 'NEW', :user, :time, :notes)"), {"items": items_json, "user": user, "time": now, "notes": f"Növ: {order_type}"})
                s.commit()
                log_system(user, "SALE_CREATED", {"sale_id": sale_id, "total": str(final_d), "payment_method": pm, "is_test": True, "items_count": len(cart_items), "split_cash": str(split_cash) if split_cash is not None else None, "split_card": str(split_card) if split_card is not None else None, "customer_card_id": cust['card_id'] if cust else None, "discount_amount": str(discount_d), "tip_amount": str(tips_d), "cogs": "0", "order_type": order_type})
                return sale_id
            except Exception as e:
                s.rollback()
                logger.error(f"finalize_sale test mode failed: {e}", exc_info=True)
                raise e


def render_pos_page():
    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "variants": variant_dialog(d_data, st.session_state.cart_takeaway)
        elif d_type == "test_auth": test_auth_dialog()
        elif d_type == "receipt": show_receipt_dialog(d_data['cart'], d_data['total'], d_data.get('order_type', 'Paket'))
        elif d_type == "z_report": z_report_dialog()
        elif d_type == "x_report": x_report_dialog()
        st.stop()

    c_carts = st.columns([1, 1, 1, 1, 1, 1])
    for cid in [1, 2, 3]:
        count = len(st.session_state.multi_carts[cid]['cart']) if cid != st.session_state.active_cart_id else len(st.session_state.cart_takeaway)
        if c_carts[cid - 1].button(f"🛒 Səbət {cid} ({count})", key=f"nav_cart_{cid}", type="primary" if cid == st.session_state.active_cart_id else "secondary", use_container_width=True):
            switch_cart(cid)
            st.rerun()

    with c_carts[3]:
        if st.button("🤝 X-Hesabat", key="x_report_trigger_btn", use_container_width=True):
            st.session_state.active_dialog = ("x_report", None)
            st.rerun()
    with c_carts[4]:
        if st.button("🔴 Z-Hesabat", key="z_report_trigger_btn", use_container_width=True):
            st.session_state.active_dialog = ("z_report", None)
            st.rerun()
    with c_carts[5]:
        if st.session_state.get('test_mode'):
            if st.button("🧪 Test: ON", type="primary", use_container_width=True, key="test_off_btn"):
                st.session_state.test_mode = False
                log_system(st.session_state.user, "TEST_MODE_DISABLED", {"actor": st.session_state.user})
                st.rerun()
        else:
            if st.button("🧪 Test: OFF", type="secondary", use_container_width=True, key="test_on_btn"):
                st.session_state.active_dialog = ("test_auth", None)
                st.rerun()

    st.markdown("---")
    if st.session_state.get('test_mode'):
        st.warning("⚠️ TEST REJİMİ AKTİVDİR")

    active_hh = get_active_happy_hour()
    if active_hh:
        hh_end = active_hh['end_time'][:5]
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #FF6B35, #F7C948); color: #000; padding: 12px 20px; border-radius: 12px; margin-bottom: 10px; text-align: center; font-weight: 900;">
            ⏰ HAPPY HOUR! <b>{active_hh['discount_percent']}% ENDİRİM</b> · {active_hh['name']} · {hh_end}-ə qədər
        </div>
        """, unsafe_allow_html=True)

    eco_mode = st.toggle("🍃 Eco-Stakan", key="nav_eco_toggle")
    c_menu, c_cart = st.columns([2.5, 1.2])

    with c_menu:
        render_menu(st.session_state.cart_takeaway, "ta")

    with c_cart:
        with st.container(border=True):
            st.markdown(f"### 🛒 Səbət {st.session_state.active_cart_id}")

            c_src, c_btn = st.columns([4, 1], vertical_alignment="bottom")
            code = c_src.text_input("Müştəri (QR)", label_visibility="collapsed", placeholder="Skan et...", key=f"cust_qr_{st.session_state.search_key_counter}")

            if c_btn.button("🔍", key="cust_search_btn") or code:
                cid = str(code).split("id=")[1].split("&")[0] if "id=" in str(code) else str(code).strip()
                r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": cid})
                if not r.empty:
                    st.session_state.current_customer_ta = r.iloc[0].to_dict()
                    st.session_state.search_key_counter += 1
                    st.rerun()
                else:
                    st.error("⛔ Tapılmadı!")
                    time.sleep(1)
                    st.rerun()

            cust = st.session_state.current_customer_ta
            if cust:
                c_head, c_del = st.columns([4, 1], vertical_alignment="bottom")
                c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                c_del.button("❌", key="cust_clear_btn", on_click=clear_customer_data_callback)

            # Sifariş növü və endirim/xidmət haqqı seçimi
            order_type_selection = st.radio("Sifariş Növü:", ["Paket (Özü ilə) 🥡", "Masada 🍽️"], horizontal=True)
            is_table_order = "Masada" in order_type_selection
            
            disc_options = {"0%": 0, "10%": 10, "15%": 15, "20%": 20, "30%": 30, "40%": 40, "50%": 50, "100%": 100}
            man_disc_label = st.selectbox("Endirim %", list(disc_options.keys()), index=0, key="cart_disc_sel")
            man_disc_val = disc_options[man_disc_label]

            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            raw, final, disc, free, _, _, is_ikram = calculate_smart_total(
                st.session_state.cart_takeaway, cust, is_table=is_table_order,
                manual_discount_percent=man_disc_val, is_eco_cup=eco_mode
            )

            if not st.session_state.cart_takeaway:
                st.markdown("<p style='text-align:center;color:#888;'>Səbət boşdur</p>", unsafe_allow_html=True)
            else:
                for i, item in enumerate(st.session_state.cart_takeaway):
                    c_n, c_q, c_btn_col = st.columns([4, 1, 2], vertical_alignment="center")
                    c_n.markdown(f"**{item['item_name']}**")
                    c_q.write(f"x{item['qty']}")
                    
                    # Eko stekan isaresi
                    eco_key = f"eco_check_{st.session_state.active_cart_id}_{i}"
                    is_eco = st.checkbox("🌿", value=item.get('is_eco', False), key=eco_key, help="Eko Stəkan (Müştəri öz qabı ilə)")
                    item['is_eco'] = is_eco

                    with c_btn_col:
                        btn_min, btn_plus = st.columns(2)
                        if btn_min.button("➖", key=f"cart_dec_{i}"):
                            if item['qty'] > 1:
                                item['qty'] -= 1
                            else:
                                st.session_state.cart_takeaway.pop(i)
                            st.rerun()
                        if btn_plus.button("➕", key=f"cart_inc_{i}"):
                            item['qty'] += 1
                            st.rerun()

            pm = st.radio("Metod", ["Nəğd", "Kart", "Bölünmüş ✂️", "Staff"], horizontal=True, label_visibility="collapsed", key="cart_pm_radio")

            split_cash = Decimal("0")
            split_card = Decimal("0")
            is_split_valid = True

            if pm == "Bölünmüş ✂️":
                with st.container(border=True):
                    st.markdown(f"**Yekun: {final:.2f} ₼**")
                    col_s1, col_s2 = st.columns(2)
                    split_cash_input = col_s1.number_input("Nağd hissə (₼):", min_value=0.0, max_value=float(final), value=0.0, step=1.0, key="split_cash_inp")
                    split_cash = Decimal(str(split_cash_input))
                    split_card = final - split_cash
                    col_s2.metric("Kartla", f"{split_card:.2f} ₼")
                    if split_cash < 0 or split_card < 0:
                        st.error("Məbləğ mənfi ola bilməz!")
                        is_split_valid = False

            elif pm == "Staff":
                DAILY_STAFF_LIMIT = Decimal("6.00")
                now_date = get_baku_now().date()
                st_check = run_query("SELECT COUNT(*) as count FROM sales WHERE cashier=:u AND payment_method='Staff' AND DATE(created_at)=:d AND (is_test IS NULL OR is_test=FALSE)", {"u": st.session_state.user, "d": now_date})
                staff_calc = Decimal("0")
                used_discount = (not st_check.empty and st_check.iloc[0]['count'] > 0)
                nc_applied = used_discount

                for it in st.session_state.cart_takeaway:
                    if it.get('is_coffee'):
                        staff_calc += Decimal(str(it['qty'])) * Decimal(str(it['price']))
                    else:
                        if not nc_applied:
                            staff_calc += Decimal("2.0")
                            if it['qty'] > 1:
                                staff_calc += Decimal(str(it['qty'] - 1)) * Decimal(str(it['price']))
                            nc_applied = True
                        else:
                            staff_calc += Decimal(str(it['qty'])) * Decimal(str(it['price']))

                if staff_calc <= DAILY_STAFF_LIMIT:
                    final = Decimal("0")
                    st.success("✅ Limit daxilində. Ödəniş: 0 ₼")
                else:
                    final = staff_calc - DAILY_STAFF_LIMIT
                    st.warning(f"⚠️ Limit keçildi: {final:.2f} ₼")

            st.markdown(f"<h1 style='text-align:center;color:#ffd700;font-size:48px;'>{final:.2f} ₼</h1>", unsafe_allow_html=True)
            if is_ikram:
                st.success("🎁 İKRAM")
            elif free > 0:
                st.success(f"🎁 {free} Kofe Hədiyyə")

            if active_hh and man_disc_val == 0:
                st.success(f"⏰ Happy Hour: {active_hh['name']} ({active_hh['discount_percent']}%)")

            card_tips = st.number_input("Çayvoy (₼)?", min_value=0.0, step=0.5, key="cart_tip_inp") if pm in ["Kart", "Bölünmüş ✂️"] else 0.0

            if st.button("✅ ÖDƏNİŞİ TAMAMLA", type="primary", use_container_width=True, key="cart_pay_btn"):
                if not st.session_state.cart_takeaway:
                    st.error("Səbət boşdur")
                    st.stop()

                if pm == "Bölünmüş ✂️" and not is_split_valid:
                    st.error("Bölünmüş məbləğləri düzəldin!")
                    st.stop()

                is_test_mode = st.session_state.get('test_mode', False)

                try:
                    db_pm = pm
                    if pm == "Bölünmüş ✂️":
                        db_pm = f"Split (Cash:{split_cash:.2f}, Card:{split_card:.2f})"

                    finalize_sale(
                        cart_items=st.session_state.cart_takeaway,
                        final_total=final,
                        original_total=raw,
                        pm=db_pm,
                        user=st.session_state.user,
                        cust=cust,
                        card_tips=card_tips,
                        is_test=is_test_mode,
                        split_cash=split_cash if pm == "Bölünmüş ✂️" else None,
                        split_card=split_card if pm == "Bölünmüş ✂️" else None,
                        order_type=order_type_selection
                    )

                    receipt_data = {"cart": st.session_state.cart_takeaway.copy(), "total": float(final), "order_type": order_type_selection}
                    st.session_state.cart_takeaway = []
                    st.session_state.current_customer_ta = None
                    st.session_state.search_key_counter += 1
                    st.session_state.active_dialog = ("receipt", receipt_data)
                    st.rerun()
                except Exception as e:
                    st.error(f"Satış xətası: {e}")
                    logger.error(f"Sale failed: {e}", exc_info=True)
