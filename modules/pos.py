# modules/pos.py — TOTAL RECOVERY & FULL ARCHITECTURE v6.0 (HİSSƏ 1/4)
import streamlit as st
import json
import time
import logging
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import text

from database import run_query, run_action, run_transaction, conn, get_setting, set_setting
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
    actual_cash = st.number_input("Kassada olan real məbləğ:", value=float(expected_cash), min_value=0.0, step=1.0)
    if st.button("🤝 Təhvil Ver", use_container_width=True, type="primary"):
        actual_d = Decimal(str(actual_cash))
        diff = actual_d - expected_cash
        u = st.session_state.user; now = get_baku_now(); actions = []
        if abs(diff) > Decimal("0.01"):
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES (:t, :c, :a, 'Kassa', 'X-Hesabat fərqi', :u, :time)", {"t": 'in' if diff > 0 else 'out', "c": 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri', "a": str(abs(diff)), "u": u, "time": now}))
        actions.append(("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:u, :e, :a, :t)", {"u": u, "e": str(expected_cash), "a": str(actual_d), "t": now}))
        run_transaction(actions)
        set_setting(SK_CASH_LIMIT, str(actual_d))
        st.success(f"Təhvil verildi! Kassa: {actual_d:.2f} ₼"); time.sleep(1.5); st.session_state.active_dialog = None; st.rerun()

@st.dialog("🔴 Z-Hesabat və Maaş")
def z_report_dialog():
    expected_cash = get_current_shift_expected_cash()
    st.warning("⚠️ Günü bağlamaq kassanı sıfırlayacaq!")
    st.info(f"Hazırda kassada var: **{expected_cash:.2f} ₼**")
    actual_z = st.number_input("Yeşikdə olan cəmi nağd (AZN):", value=float(expected_cash), step=1.0)
    cash_drop = st.number_input("İnkassasiya (Müdirə verilən):", min_value=0.0, max_value=float(actual_z), value=0.0, step=10.0)
    
    is_wage = st.checkbox("Gündəlik maaşlar çıxılsın?", value=True)
    wage_amt = 25.0 if st.session_state.role in ['admin', 'manager'] else 20.0
    
    next_open = Decimal(str(actual_z)) - Decimal(str(cash_drop))
    if is_wage: next_open -= Decimal(str(wage_amt))
    st.write(f"**Sabaha qalan xırda:** {next_open:.2f} ₼")
    
    if st.button("✅ Günü Bağla", use_container_width=True, type="primary"):
        u = st.session_state.user; now = get_baku_now(); actions = []
        diff = Decimal(str(actual_z)) - expected_cash
        if abs(diff) > Decimal("0.01"):
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat fərqi', :u, :time)", {"t": 'in' if diff > 0 else 'out', "c": 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri', "a": str(abs(diff)), "u": u, "time": now}))
        if cash_drop > 0:
            actions.append(("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('out', 'İnkassasiya', :a, 'Kassa', 'Z-Çıxarışı', :u, :time)", {"a": str(cash_drop), "u": u, "time": now}))
        if is_wage:
            actions.append(("INSERT INTO finance (type, category, amount, source, subject, created_at) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', :u, :t)", {"a": str(wage_amt), "u": u, "t": now}))
        
        try:
            log_date_z = get_logical_date(); sh_start_z, sh_end_z = get_shift_range(log_date_z)
            rp = {"d": sh_start_z, "e": sh_end_z}
            s_cash_z = safe_decimal(run_query("SELECT SUM(total) FROM sales WHERE payment_method IN ('Nəğd','Cash') AND status='COMPLETED' AND created_at>=:d AND created_at<:e", rp).iloc[0,0])
            s_card_z = safe_decimal(run_query("SELECT SUM(total) FROM sales WHERE payment_method IN ('Kart','Card') AND status='COMPLETED' AND created_at>=:d AND created_at<:e", rp).iloc[0,0])
            s_cogs_z = safe_decimal(run_query("SELECT SUM(cogs) FROM sales WHERE status='COMPLETED' AND created_at>=:d AND created_at<:e", rp).iloc[0,0])
            actions.append(("INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)", {"ts": str(s_cash_z + s_card_z), "cs": str(s_cash_z), "crs": str(s_card_z), "cogs": str(s_cogs_z), "ac": str(actual_z), "gb": u, "t": now}))
        except: pass

        run_transaction(actions)
        set_setting(SK_CASH_LIMIT, str(next_open))
        st.success("Günü Bağladıq!"); time.sleep(1.5); st.session_state.active_dialog = None; st.rerun()
# modules/pos.py — TOTAL RECOVERY & FULL ARCHITECTURE v6.0 (HİSSƏ 2/4)
def add_to_cart(cart, item):
    for i in cart:
        if i['item_name'] == item['item_name'] and i.get('status') == 'new':
            i['qty'] += 1
            return
    cart.append(item)

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0, is_eco_cup=False):
    total = Decimal("0"); final_total = Decimal("0"); disc_rate = Decimal("0")
    current_stars = 0; free_cof = 0; is_ikram = False
    service_fee_pct = Decimal(str(get_setting("service_fee_percent", "0.0"))) / Decimal("100")
    
    # Happy Hour yoxlanışı
    active_hh = get_active_happy_hour() if manual_discount_percent == 0 else None
    hh_category_discount = False; allowed_cats = []; hh_disc_rate = Decimal("0")
    if active_hh:
        if active_hh['categories'] == 'ALL': manual_discount_percent = active_hh['discount_percent']
        else:
            hh_category_discount = True; allowed_cats = [c.strip() for c in active_hh['categories'].split(',')]
            hh_disc_rate = Decimal(str(active_hh['discount_percent'])) / Decimal("100")

    if manual_discount_percent > 0:
        disc_rate = Decimal(str(manual_discount_percent)) / Decimal("100")
        for i in cart:
            line = Decimal(str(i['qty'])) * Decimal(str(i['price']))
            total += line
            final_total += (line * (1 - disc_rate)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    else:
        if customer:
            current_stars = customer.get('stars', 0)
            if customer.get('type') == 'ikram': return sum([Decimal(str(i['qty']))*Decimal(str(i['price'])) for i in cart], Decimal("0")), Decimal("0"), Decimal("1"), 0, 0, 0, True
            rates = {'golden': '0.05', 'platinum': '0.10', 'elite': '0.20', 'thermos': '0.20', 'telebe': '0.15'}
            disc_rate = Decimal(rates.get(customer.get('type'), '0'))
        
        coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
        free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
        free_remaining = free_cof
        
        for i in cart:
            item_price = Decimal(str(i['price']))
            if hh_category_discount and i.get('category') in allowed_cats: item_price = (item_price * (1 - hh_disc_rate))
            
            line_orig = Decimal(str(i['qty'])) * Decimal(str(i['price']))
            total += line_orig
            
            if i.get('is_coffee') and free_remaining > 0:
                f_this = min(i['qty'], free_remaining)
                final_total += (Decimal(str(i['qty'] - f_this)) * item_price * (1 - disc_rate))
                free_remaining -= f_this
            else:
                final_total += (Decimal(str(i['qty'])) * item_price * (1 - disc_rate))

    if is_table and service_fee_pct > 0: final_total += (final_total * service_fee_pct)
    return total, final_total.quantize(Decimal("0.01"), ROUND_HALF_UP), disc_rate, free_cof, 0, 0, is_ikram

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
# modules/pos.py — TOTAL RECOVERY & FULL ARCHITECTURE v6.0 (HİSSƏ 3/4)
def render_menu(cart, key):
    menu_df = get_cached_menu()
    CAT_ORDER = {"Kofe (Dənələr)": 0, "Kombolar": 1, "Süd Məhsulları": 2, "Bar Məhsulları (Su/Buz)": 3, "Siroplar": 4}
    if menu_df.empty: st.warning("Menyu boşdur."); return
    menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER).fillna(99)
    menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])
    
    c_search, _ = st.columns([1, 1])
    pos_search = c_search.text_input("🔍 Axtar...", key=f"pos_s_{key}", label_visibility="collapsed")
    if pos_search: menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]

    existing_cats = sorted(menu_df['category'].dropna().unique().tolist())
    cats = ["HAMISI"] + [c.upper() for c in existing_cats]
    sc_upper = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_rad_{key}")
    sc = "Hamısı" if sc_upper == "HAMISI" else next((c for c in existing_cats if c.upper() == sc_upper), "Hamısı")
    prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]

    groups = {}
    for _, r in prods.iterrows():
        n = r['item_name']; base = n
        for s in [" S", " M", " L", " XL", " Single", " Double"]:
            if n.endswith(s): base = n[:-len(s)]; break
        if base not in groups: groups[base] = []
        groups[base].append(r)

    group_items = list(groups.items())
    for row_start in range(0, len(group_items), 4):
        cols = st.columns(4)
        for col_idx, (base, items) in enumerate(group_items[row_start:row_start+4]):
            if len(items) > 1:
                if cols[col_idx].button(f"{base}\n▾", key=f"grp_{base}_{key}_{row_start}_{col_idx}", use_container_width=True):
                    st.session_state.active_dialog = ("variants", items); st.rerun()
            else:
                r = items[0]
                if cols[col_idx].button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}", use_container_width=True):
                    add_to_cart(cart, {'item_name': r['item_name'], 'price': float(r['price']), 'qty': 1, 'is_coffee': r['is_coffee'], 'category': r['category'], 'status': 'new'})
                    st.rerun()

def finalize_sale(cart_items, final_total, original_total, pm, user, cust, card_tips, is_test, split_cash=None, split_card=None, order_type="Paket"):
    now = get_baku_now(); final_d = Decimal(str(final_total)); original_d = Decimal(str(original_total)); items_json = json.dumps(cart_items)
    total_cogs = Decimal("0")
    
    with conn.session as s:
        try:
            # Maya dəyəri və Anbar
            for it in cart_items:
                recs = run_query("SELECT r.quantity_required, i.unit_cost, r.ingredient_name FROM recipes r JOIN ingredients i ON r.ingredient_name = i.name WHERE r.menu_item_name=:m", {"m": it['item_name']})
                for _, r in recs.iterrows():
                    ing_name = str(r[2]).lower()
                    if it.get('is_eco') and any(x in ing_name for x in ['stəkan', 'stakan', 'cup', 'qab']): continue
                    q = Decimal(str(r[0])) * Decimal(str(it['qty']))
                    total_cogs += q * safe_decimal(r[1])
                    if not is_test: s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n"), {"q": str(q), "n": r[2]})

            # Satışın özü
            sale_result = s.execute(text("""
                INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, tip_amount, is_test, cogs, status) 
                VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da,:tip,:tst,:cogs,'COMPLETED') RETURNING id
            """), {"i": items_json, "t": str(final_d), "p": pm, "c": user, "time": now, "cid": cust['card_id'] if cust else None, "ot": str(original_d), "da": str(original_d-final_d), "tip": str(card_tips), "tst": is_test, "cogs": str(total_cogs)})
            sale_id = sale_result.fetchone()[0]
            
            # Kuxnaya (Notes-da növü qeyd edirik)
            s.execute(text("INSERT INTO kitchen_orders (sale_source, items, status, created_by, created_at, notes) VALUES ('POS', :items, 'NEW', :user, :time, :notes)"), {"items": items_json, "user": user, "time": now, "notes": f"Növ: {order_type}"})
            
            if not is_test and final_d > 0:
                if split_cash is not None:
                    if split_cash > 0: s.execute(text("INSERT INTO finance (type, category, amount, source, created_by, created_at, sale_id) VALUES ('in','Satış (Nağd)',:a,'Kassa',:u,:t,:sid)"), {"a": str(split_cash), "u": user, "t": now, "sid": sale_id})
                    if split_card > 0: s.execute(text("INSERT INTO finance (type, category, amount, source, created_by, created_at, sale_id) VALUES ('in','Satış (Kart)',:a,'Bank Kartı',:u,:t,:sid)"), {"a": str(split_card), "u": user, "t": now, "sid": sale_id})
                else:
                    src = "Kassa" if "Nəğd" in pm else "Bank Kartı"; cat = f"Satış ({pm})"
                    s.execute(text("INSERT INTO finance (type, category, amount, source, created_by, created_at, sale_id) VALUES ('in',:cat,:a,:src,:u,:t,:sid)"), {"cat": cat, "a": str(final_d), "src": src, "u": user, "t": now, "sid": sale_id})

            if cust and not is_test:
                cof_qty = sum([i['qty'] for i in cart_items if i.get('is_coffee')])
                free_c = min(int((cust['stars'] + cof_qty) // 10), cof_qty)
                s.execute(text("UPDATE customers SET stars = stars + :q - (:f * 10) WHERE card_id = :cid"), {"q": cof_qty, "f": free_c, "cid": cust['card_id']})
            
            s.commit(); return sale_id
        except Exception as e:
            s.rollback(); logger.error(f"Sale fail: {e}"); raise e
            # modules/pos.py — TOTAL RECOVERY & FULL ARCHITECTURE v6.0 (HİSSƏ 4/4)
def render_pos_page():
    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "receipt": show_receipt_dialog(d_data['cart'], d_data['total'], d_data.get('order_type'))
        elif d_type == "variants": variant_dialog(d_data, st.session_state.cart_takeaway)
        elif d_type == "z_report": z_report_dialog()
        elif d_type == "x_report": x_report_dialog()
        elif d_type == "test_auth": test_auth_dialog()
        st.stop()

    # Üst Naviqasiya
    c_nav = st.columns(6)
    for cid in [1, 2, 3]:
        count = len(st.session_state.multi_carts[cid]['cart']) if cid != st.session_state.active_cart_id else len(st.session_state.cart_takeaway)
        if c_nav[cid-1].button(f"🛒 Səbət {cid} ({count})", type="primary" if cid == st.session_state.active_cart_id else "secondary", use_container_width=True):
            switch_cart(cid); st.rerun()
    if c_nav[3].button("🤝 X-Hesabat", use_container_width=True): st.session_state.active_dialog = ("x_report", None); st.rerun()
    if c_nav[4].button("🔴 Z-Hesabat", use_container_width=True): st.session_state.active_dialog = ("z_report", None); st.rerun()
    
    # Happy Hour Banner
    active_hh = get_active_happy_hour()
    if active_hh: st.success(f"⏰ HAPPY HOUR: {active_hh['name']} ({active_hh['discount_percent']}%)")

    c_menu, c_cart = st.columns([2.5, 1.2])
    with c_menu: render_menu(st.session_state.cart_takeaway, "ta")
    
    with c_cart:
        with st.container(border=True):
            st.markdown(f"### 🛒 Səbət {st.session_state.active_cart_id}")
            
            # MÜŞTƏRİ QR
            c_qr, c_src = st.columns([4, 1], vertical_alignment="bottom")
            code = c_qr.text_input("Müştəri (QR)", label_visibility="collapsed", placeholder="Skan et...", key=f"qr_{st.session_state.search_key_counter}")
            if c_src.button("🔍") or code:
                cid = str(code).split("id=")[1].split("&")[0] if "id=" in str(code) else str(code).strip()
                r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id": cid})
                if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.session_state.search_key_counter += 1; st.rerun()
                else: st.error("Tapılmadı!")
            
            cust = st.session_state.current_customer_ta
            if cust:
                ch, cd = st.columns([4, 1]); ch.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                if cd.button("❌"): clear_customer_data_callback(); st.rerun()

            # AYARLAR
            order_type = st.radio("Növ:", ["🥡 Paket", "🍽️ Masada"], horizontal=True)
            disc_opt = {"0%": 0, "10%": 10, "15%": 15, "20%": 20, "50%": 50, "100%": 100}
            man_disc = st.selectbox("Endirim", list(disc_opt.keys()), key="man_disc")
            
            st.divider()
            raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, customer=cust, is_table=("Masada" in order_type), manual_discount_percent=disc_opt[man_disc])
            
            # SƏBƏT LİSTİ
            for i, item in enumerate(st.session_state.cart_takeaway):
                c_n, c_q, c_b = st.columns([3, 1, 2])
                c_n.write(f"**{item['item_name']}**")
                c_q.write(f"x{item['qty']}")
                with c_b:
                    b1, b2, b3 = st.columns(3)
                    if b1.button("➖", key=f"dec_{i}"):
                        if item['qty'] > 1: item['qty'] -= 1
                        else: st.session_state.cart_takeaway.pop(i)
                        st.rerun()
                    if b2.button("➕", key=f"inc_{i}"): item['qty'] += 1; st.rerun()
                    item['is_eco'] = b3.checkbox("🌿", value=item.get('is_eco', False), key=f"eco_{i}")

            st.markdown(f"## {final:.2f} ₼")
            if is_ikram: st.success("🎁 İKRAM")
            elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
            
            pm = st.radio("Ödəniş", ["Nəğd", "Kart", "Bölünmüş ✂️"], horizontal=True)
            split_cash = 0; split_card = 0
            if pm == "Bölünmüş ✂️":
                s1, s2 = st.columns(2)
                split_cash = s1.number_input("Nağd", max_value=float(final), step=1.0)
                split_card = float(final) - split_cash; s2.metric("Kart", f"{split_card:.2f}")

            if st.button("✅ TƏSDİQLƏ", type="primary", use_container_width=True):
                if not st.session_state.cart_takeaway: st.error("Səbət boşdur"); st.stop()
                finalize_sale(st.session_state.cart_takeaway, final, raw, pm, st.session_state.user, cust, 0, st.session_state.get('test_mode', False), split_cash=Decimal(str(split_cash)) if pm=="Bölünmüş ✂️" else None, split_card=Decimal(str(split_card)) if pm=="Bölünmüş ✂️" else None, order_type=order_type)
                r_data = {"cart": st.session_state.cart_takeaway.copy(), "total": float(final), "order_type": order_type}
                st.session_state.cart_takeaway = []; st.session_state.current_customer_ta = None; st.session_state.active_dialog = ("receipt", r_data); st.rerun()
            
