# modules/pos.py
import streamlit as st
from sqlalchemy import text
from database import run_query, run_action, conn, get_setting, set_setting
from utils import clean_qr_code, get_baku_now, get_shift_range, log_system
import time
import os
import bcrypt
import json
import pandas as pd
import google.generativeai as genai

@st.dialog("🧾 Satış Çeki")
def show_receipt_dialog(cart_data, total_amt):
    test_badge = "<p style='text-align: center; font-size: 14px; font-weight: bold; margin-bottom: 5px;'>*** TEST REJİMİ ***</p>" if st.session_state.get('test_mode') else ""
    receipt_html = f"""
    <div id="receipt_area" style="width: 280px; padding: 10px; font-family: 'Courier New', monospace; color: black; background: white; border: 1px solid #eee;">
        {test_badge}
        <h2 style="text-align: center; margin-bottom: 5px; font-weight: bold;">EMALATKHANA</h2>
        <p style="text-align: center; margin-top: 0; font-size: 12px;">{get_baku_now().strftime('%d.%m.%Y %H:%M')}</p>
        <p style="text-align: center; font-size: 11px; margin-bottom: 5px;">Kassir: {st.session_state.user}</p>
        <hr style="border-top: 1px dashed black;">
        <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
            {''.join([f"<tr><td style='padding: 2px 0;'>{item['item_name']} x{item['qty']}</td><td style='text-align:right;'>{item['qty']*item['price']:.2f} ₼</td></tr>" for item in cart_data])}
        </table>
        <hr style="border-top: 1px dashed black;">
        <h3 style="text-align: right; margin: 10px 0; font-weight: bold;">YEKUN: {total_amt:.2f} ₼</h3>
        <p style="text-align: center; font-size: 10px; margin-top: 15px;">Bizi seçdiyiniz üçün təşəkkür edirik!</p>
    </div>
    <script src="https://printjs-4de6.kxcdn.com/print.min.js"></script>
    <button onclick="printJS({{printable: 'receipt_area', type: 'html', targetStyles: ['*'], style: '@page {{ size: auto; margin: 0mm; }}'}})" 
            style="margin-top: 20px; padding: 15px; width: 100%; background: #ffd700; border: none; font-weight: 900; border-radius: 10px; cursor: pointer; font-size: 16px; color: black; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        🖨️ ÇEKİ İNDİ ÇAP ET
    </button>
    """
    st.components.v1.html(receipt_html, height=550)
    if st.button("Bağla", use_container_width=True, key="dlg_close_receipt"):
        st.session_state.active_dialog = None
        st.rerun()

@st.dialog("🔐 Admin Təsdiqi")
def test_auth_dialog():
    pin = st.text_input("Şifrə:", type="password", key="dlg_test_pin")
    if st.button("Təsdiqlə", type="primary", use_container_width=True, key="dlg_test_confirm"):
        r = run_query("SELECT password FROM users WHERE username='admin'")
        db_hash = r.iloc[0]['password'] if not r.empty else ""
        if (db_hash and bcrypt.checkpw(pin.encode(), db_hash.encode())) or pin == os.environ.get("ADMIN_PASS", "admin123"):
            st.session_state.test_mode = True
            st.session_state.active_dialog = None
            st.rerun()
        else: st.error("Səhv şifrə!")
    if st.button("Ləğv et", use_container_width=True, key="dlg_test_cancel"):
        st.session_state.active_dialog = None
        st.rerun()

@st.dialog("📋 Variant Seçimi")
def variant_dialog(items, cart):
    st.write("Məhsulun növünü/ölçüsünü seçin:")
    for i, it in enumerate(items):
        if st.button(f"{it['item_name']} | {it['price']}₼", use_container_width=True, type="secondary", key=f"dlg_var_{i}"): 
            add_to_cart(cart, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'category':it['category'], 'status':'new'})
            st.session_state.active_dialog = None
            st.rerun()

def get_current_shift_expected_cash():
    log_date_z = get_logical_date()
    sh_start_z, sh_end_z = get_shift_range(log_date_z)
    q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
    params = {"d":sh_start_z, "e":sh_end_z}

    s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {q_cond}", params).iloc[0]['s'] or 0.0
    f_out = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='out' {q_cond}", params).iloc[0]['s'] or 0.0
    f_in = run_query(f"SELECT SUM(amount) as s FROM finance WHERE source='Kassa' AND type='in' AND category NOT IN ('Kassa Açılışı', 'Satış (Nağd)') {q_cond}", params).iloc[0]['s'] or 0.0
    opening_limit = float(get_setting("cash_limit", "0.0"))
    return opening_limit + float(s_cash) + float(f_in) - float(f_out)

@st.dialog("🤝 X-Hesabat (Smeni Təhvil Ver)")
def x_report_dialog():
    st.write("Növbəni növbəti işçiyə və ya kassaya təhvil verin.")
    expected_cash = get_current_shift_expected_cash()
    st.info(f"Sistemə görə kassada olmalıdır: **{expected_cash:.2f} ₼**")
    
    actual_cash = st.number_input("Kassada olan real məbləğ (AZN):", value=float(expected_cash), min_value=0.0, step=1.0)
    
    if st.button("🤝 Təhvil Ver", use_container_width=True, type="primary"):
        diff = actual_cash - expected_cash
        u = st.session_state.user
        now = get_baku_now()
        
        if abs(diff) > 0.01:
            c_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'X-Hesabat zamanı yaranan fərq', :u, :time, FALSE)", 
                       {"t": c_type, "c": cat, "a": abs(diff), "u": u, "time": now})
        
        run_action("INSERT INTO shift_handovers (handed_by, expected_cash, actual_cash, created_at) VALUES (:u, :e, :a, :t)", 
                   {"u": u, "e": expected_cash, "a": actual_cash, "t": now})
        
        set_setting("cash_limit", str(actual_cash))
        st.success(f"Növbə təhvil verildi! Kassa balansı {actual_cash:.2f} ₼ olaraq yeniləndi.")
        time.sleep(1.5)
        st.session_state.active_dialog = None
        st.rerun()

@st.dialog("🔴 Z-Hesabat və Maaş")
def z_report_dialog():
    st.write("Günü tamamlamaq və kassanı bağlamaq üçün:")
    expected_cash = get_current_shift_expected_cash()
    st.info(f"Sistemə görə kassada olmalıdır: **{expected_cash:.2f} ₼**")
    
    actual_z = st.number_input("Sabahkı açılış balansı (Kassada qalan):", value=float(expected_cash), step=1.0, key="z_next_open")
    default_wage = 25.0 if st.session_state.role in ['manager', 'admin'] else 20.0
    wage_amt = st.number_input("Götürülən Maaş (AZN):", value=default_wage, min_value=0.0, step=1.0, key="z_wage_amt")
    
    st.markdown("---")
    if st.button("✅ Günü Bağla və Maaşı Çıxar", use_container_width=True, key="z_confirm_btn"):
        u = st.session_state.user
        now = get_baku_now()
        is_t = st.session_state.get('test_mode', False)
        
        diff = actual_z - (expected_cash - wage_amt)
        if abs(diff) > 0.01:
            c_type = 'in' if diff > 0 else 'out'
            cat = 'Kassa Artığı' if diff > 0 else 'Kassa Kəsiri'
            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES (:t, :c, :a, 'Kassa', 'Z-Hesabat zamanı yaranan fərq', :u, :time, FALSE)", 
                       {"t": c_type, "c": cat, "a": abs(diff), "u": u, "time": now})
        
        run_action(
            "INSERT INTO finance (type, category, amount, source, description, created_by, subject, created_at, is_test) VALUES ('out', 'Maaş/Avans', :a, 'Kassa', 'Smen sonu maaş', :u, :subj, :time, :tst)", 
            {"a": wage_amt, "u": u, "subj": u, "time": now, "tst": is_t}
        )
        
        set_setting("cash_limit", str(actual_z))
        
        try:
            log_date_z = get_logical_date()
            sh_start_z, sh_end_z = get_shift_range(log_date_z)
            q_cond = "AND created_at>=:d AND created_at<:e AND (is_test IS NULL OR is_test = FALSE)"
            s_cash = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Nəğd', 'Cash') {q_cond}", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
            s_card = run_query(f"SELECT SUM(total) as s FROM sales WHERE payment_method IN ('Kart', 'Card') {q_cond}", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
            s_cogs = run_query(f"SELECT SUM(cogs) as s FROM sales WHERE 1=1 {q_cond}", {"d":sh_start_z, "e":sh_end_z}).iloc[0]['s'] or 0.0
            run_action("INSERT INTO z_reports (total_sales, cash_sales, card_sales, total_cogs, actual_cash, generated_by, created_at) VALUES (:ts, :cs, :crs, :cogs, :ac, :gb, :t)",
                       {"ts":float(s_cash)+float(s_card), "cs":float(s_cash), "crs":float(s_card), "cogs":float(s_cogs), "ac":actual_z, "gb":u, "t":now})
        except: pass
        
        log_system(u, f"Günü bağladı. Maaş: {wage_amt} AZN, Sabahkı açılış: {actual_z} AZN")
        st.success(f"Uğurlu! Maaş ({wage_amt} AZN) kassadan çıxıldı və gün bağlandı.")
        time.sleep(1.5)
        st.session_state.active_dialog = None
        st.rerun()

def add_to_cart(cart, item):
    for i in cart: 
        if i['item_name'] == item['item_name'] and i.get('status')=='new': 
            i['qty'] += 1
            return
    cart.append(item)

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0, is_eco_cup=False):
    total = 0.0
    disc_rate = 0.0
    current_stars = 0
    service_fee_pct = float(get_setting("service_fee_percent", "0.0")) / 100.0
    
    has_croissant_promo = customer and "CROISSANT50" in str(customer.get('secret_token', ''))
    
    if manual_discount_percent > 0:
        disc_rate = manual_discount_percent / 100.0
        final_total = 0.0
        for i in cart: 
            line = i['qty'] * i['price']
            total += line
            final_total += (line - (line * disc_rate))
        if is_table and service_fee_pct > 0: final_total += final_total * service_fee_pct
        return total, final_total, disc_rate, 0, 0, 0, False
        
    if customer:
        current_stars = customer.get('stars', 0)
        ctype = customer.get('type', 'standard')
        if ctype == 'ikram': return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20, 'telebe':0.15}
        disc_rate = rates.get(ctype, 0.0)
        
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
    final_total = 0.0
    free_coffees_to_give = free_cof 
    
    for i in cart:
        item_price = i['price']
        if has_croissant_promo and ("kruasan" in i['item_name'].lower() or "croissant" in i['item_name'].lower()):
            item_price = item_price * 0.5 
            
        line_original = i['qty'] * i['price']
        line_after_discount = i['qty'] * item_price
        total += line_original
        
        if i.get('is_coffee'):
            if free_coffees_to_give > 0:
                free_from_this_item = min(i['qty'], free_coffees_to_give)
                paid_qty = i['qty'] - free_from_this_item
                final_total += (paid_qty * item_price) * (1 - disc_rate)
                free_coffees_to_give -= free_from_this_item
            else: final_total += (line_after_discount - (line_after_discount * disc_rate))
        else: final_total += (line_after_discount - (line_after_discount * disc_rate))
            
    if is_table and service_fee_pct > 0: final_total += final_total * service_fee_pct
    if is_eco_cup: final_total = final_total * 0.95 
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
    CAT_ORDER_MAP = {cat: i for i, cat in enumerate(["Kofe (Dənələr)", "Kombolar", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar"])}
    menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER_MAP).fillna(99)
    menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])
    
    c_search, _ = st.columns([1, 1])
    pos_search = c_search.text_input("🔍 Axtar...", key=f"pos_s_{key}", label_visibility="collapsed")
    if pos_search: menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]
    
    existing_cats = sorted(menu_df['category'].unique().tolist(), key=lambda x: CAT_ORDER_MAP.get(x, 99))
    cats = ["HAMISI"] + [c.upper() for c in existing_cats]
    sc_upper = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_rad_{key}")
    sc = "Hamısı" if sc_upper == "HAMISI" else next((c for c in existing_cats if c.upper() == sc_upper), "Hamısı")
    
    prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]
    
    if not prods.empty:
        groups = {}
        for _, r in prods.iterrows():
            n = r['item_name']
            base = n
            for s in [" S", " M", " L", " XL", " Single", " Double"]:
                if n.endswith(s): 
                    base = n[:-len(s)]
                    break
            if base not in groups: groups[base] = []
            groups[base].append(r)
        
        cols = st.columns(4)
        i = 0
        for base, items in groups.items():
            with cols[i%4]:
                if len(items) > 1:
                    if st.button(f"{base}\n▾", key=f"grp_btn_{base}_{key}_{sc}", use_container_width=True, type="secondary"): 
                        st.session_state.active_dialog = ("variants", items)
                        st.rerun()
                else:
                    r = items[0]
                    btn_color = "primary" if r['category'] == "Kombolar" else "secondary"
                    if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"prod_btn_{r['id']}_{key}_{sc}", use_container_width=True, type=btn_color): 
                        add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'category':r['category'], 'status':'new'})
                        st.rerun()
                i += 1

def render_pos_page():
    if st.session_state.get('active_dialog'):
        d_type, d_data = st.session_state.active_dialog
        if d_type == "variants": variant_dialog(d_data, st.session_state.cart_takeaway)
        elif d_type == "test_auth": test_auth_dialog()
        elif d_type == "receipt": show_receipt_dialog(d_data['cart'], d_data['total'])
        elif d_type == "z_report": z_report_dialog()
        elif d_type == "x_report": x_report_dialog()
        st.stop()

    c_carts = st.columns([1, 1, 1, 1, 1, 1])
    for cid in [1, 2, 3]:
        count = len(st.session_state.multi_carts[cid]['cart']) if cid != st.session_state.active_cart_id else len(st.session_state.cart_takeaway)
        if c_carts[cid-1].button(f"🛒 Səbət {cid} ({count})", key=f"nav_cart_{cid}", type="primary" if cid == st.session_state.active_cart_id else "secondary", use_container_width=True): 
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
                st.session_state.test_mode = False; st.rerun()
        else:
            if st.button("🧪 Test: OFF", type="secondary", use_container_width=True, key="test_on_btn"):
                st.session_state.active_dialog = ("test_auth", None); st.rerun()

    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🤖 Süni İntellekt: POS Audit (Anormal Endirimlər və Ləğvlər)"):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("AI funksiyası üçün API Key daxil edin (Ayarlar).")
            else:
                if st.button("🔍 POS Datalarını Skan Et", use_container_width=True):
                    with st.spinner("AI şübhəli satışları incələyir..."):
                        try:
                            genai.configure(api_key=api_key)
                            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else 'models/gemini-pro')
                            model = genai.GenerativeModel(chosen_model)
                            recent_sales = run_query("SELECT id, cashier, total, discount_amount, created_at, is_test FROM sales ORDER BY created_at DESC LIMIT 50")
                            if not recent_sales.empty:
                                sales_str = "\n".join([f"ID: {r['id']} | İşçi: {r['cashier']} | Məbləğ: {r['total']} | Endirim: {r['discount_amount']} | Test: {r['is_test']}" for _, r in recent_sales.iterrows()])
                                prompt = f"Sən kofe şopun auditorusan. Aşağıdakı son 50 satışda anormal endirimləri, çoxlu test satışlarını tap və qısa məlumat ver:\n\n{sales_str}"
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background: #1e2226; padding: 15px; border-left: 5px solid #dc3545;'>{response.text}</div>", unsafe_allow_html=True)
                            else: st.info("Kifayət qədər satış yoxdur.")
                        except Exception as e: st.error(e)

    st.markdown("---")
    if st.session_state.get('test_mode'): st.warning("⚠️ TEST REJİMİ AKTİVDİR")
    
    eco_mode = st.toggle("🍃 Eco-Stakan Modulu", key="nav_eco_toggle")
    c_menu, c_cart = st.columns([2.5, 1.2])
    
    with c_menu: render_menu(st.session_state.cart_takeaway, "ta")

    with c_cart:
        with st.container(border=True):
            st.markdown(f"### 🛒 Səbət {st.session_state.active_cart_id}")
            
            c_src, c_btn = st.columns([4,1], vertical_alignment="bottom")
            code = c_src.text_input("Müştəri (QR)", label_visibility="collapsed", placeholder="Skan et...", key=f"cust_qr_{st.session_state.search_key_counter}")
            
            if c_btn.button("🔍", key="cust_search_btn") or code:
                cid = str(code).split("id=")[1].split("&")[0] if "id=" in str(code) else str(code).strip()
                r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                if not r.empty: 
                    st.session_state.current_customer_ta = r.iloc[0].to_dict()
                    st.session_state.search_key_counter += 1; st.rerun()
                else: st.error("⛔ Tapılmadı!"); time.sleep(1); st.rerun()
                
            cust = st.session_state.current_customer_ta
            if cust: 
                c_head, c_del = st.columns([4,1], vertical_alignment="bottom")
                c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                c_del.button("❌", key="cust_clear_btn", on_click=clear_customer_data_callback)
            
            disc_options = {"0%": 0, "10%": 10, "15% (Tələbə)": 15, "20%": 20, "30%": 30, "40%": 40, "50%": 50, "100%": 100}
            man_disc_label = st.selectbox("Endirim %", list(disc_options.keys()), index=0, key="cart_disc_sel")
            man_disc_val = disc_options[man_disc_label]
            is_table_order = st.checkbox("🍽️ Masada (Servis)", key="cart_table_check")
                
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust, is_table=is_table_order, manual_discount_percent=man_disc_val, is_eco_cup=eco_mode)
            
            if not st.session_state.cart_takeaway: st.markdown("<p style='text-align:center; color:#888;'>Səbət boşdur</p>", unsafe_allow_html=True)
            else:
                for i, item in enumerate(st.session_state.cart_takeaway):
                    c_n, c_q, c_btn_col = st.columns([4, 1, 2], vertical_alignment="center")
                    c_n.markdown(f"**{item['item_name']}**")
                    c_q.write(f"x{item['qty']}")
                    with c_btn_col:
                        btn_min, btn_plus = st.columns(2)
                        if btn_min.button("➖", key=f"cart_dec_{i}"): 
                            if item['qty'] > 1: item['qty'] -= 1
                            else: st.session_state.cart_takeaway.pop(i)
                            st.rerun()
                        if btn_plus.button("➕", key=f"cart_inc_{i}"): item['qty'] += 1; st.rerun()
                            
            pm = st.radio("Metod", ["Nəğd", "Kart", "Staff"], horizontal=True, label_visibility="collapsed", key="cart_pm_radio")
            
            if pm == "Staff":
                now_date = get_baku_now().date()
                st_check = run_query("SELECT COUNT(*) as count FROM sales WHERE cashier=:u AND payment_method='Staff' AND DATE(created_at)=:d AND (is_test IS NULL OR is_test=FALSE)", {"u": st.session_state.user, "d": now_date})
                staff_calc = 0.0
                used_discount = (not st_check.empty and st_check.iloc[0]['count'] > 0)
                nc_applied = used_discount 
                
                for it in st.session_state.cart_takeaway:
                    if it.get('is_coffee'): 
                        staff_calc += (it['qty'] * it['price'])
                    else:
                        if not nc_applied:
                            staff_calc += 2.0
                            if it['qty'] > 1: staff_calc += (it['qty'] - 1) * it['price']
                            nc_applied = True
                        else: staff_calc += (it['qty'] * it['price'])
                
                if staff_calc <= 6.0:
                    final = 0.0
                    st.success(f"✅ Limit daxilində. Ödəniş: 0 ₼")
                else:
                    final = staff_calc - 6.0
                    st.warning(f"⚠️ Limit keçildi. Ödənilməli: {final:.2f} ₼")

            st.markdown(f"<h1 style='text-align:center; color:#ffd700; font-size: 48px;'>{final:.2f} ₼</h1>", unsafe_allow_html=True)
            if is_ikram: st.success("🎁 İKRAM")
            elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
            
            card_tips = st.number_input("Çayvoy?", min_value=0.0, step=0.5, key="cart_tip_inp") if pm == "Kart" else 0.0
            
            if st.button("✅ ÖDƏNİŞİ TAMAMLA", type="primary", use_container_width=True, key="cart_pay_btn"):
                if not st.session_state.cart_takeaway: st.error("Səbət boşdur"); st.stop()
                is_test_mode = st.session_state.get('test_mode', False)
                
                try:
                    items_json = json.dumps(st.session_state.cart_takeaway)
                    total_cogs = 0.0
                    now = get_baku_now()
                    
                    if not is_test_mode:
                        for it in st.session_state.cart_takeaway:
                            recs = run_query("SELECT r.ingredient_name, r.quantity_required, i.unit_cost FROM recipes r LEFT JOIN ingredients i ON r.ingredient_name = i.name WHERE r.menu_item_name=:m", {"m":it['item_name']})
                            if not recs.empty:
                                for _, r in recs.iterrows():
                                    qty_req = float(r['quantity_required']) * it['qty']
                                    u_cost = float(r['unit_cost']) if pd.notna(r['unit_cost']) else 0.0
                                    total_cogs += (qty_req * u_cost)
                                    run_action("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n", {"q":qty_req, "n":r['ingredient_name']})
                    
                    run_action("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, tip_amount, is_test, cogs) VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da, :tip, :tst, :cogs)", 
                              {"i":items_json,"t":final,"p":pm,"c":st.session_state.user,"time":now,"cid":cust['card_id'] if cust else None, "ot":raw, "da":raw-final, "tip":card_tips, "tst":is_test_mode, "cogs":total_cogs})
                    
                    if not is_test_mode and final > 0:
                        db_pm = "Kassa" if pm == "Nəğd" else "Bank Kartı"
                        pm_cat = "Satış (Nağd)" if pm == "Nəğd" else "Satış (Kart)"
                        
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', :cat, :a, :src, 'POS Satış', :u, :t, FALSE)", 
                                   {"cat": pm_cat, "a": final, "src": db_pm, "u": st.session_state.user, "t": now})
                        
                        if pm == "Kart":
                            min_comm = float(get_setting("bank_comm_min", "0.60"))
                            pct_comm = float(get_setting("bank_comm_pct", "0.02"))
                            comm = max(min_comm, final * pct_comm)
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Kart Satış Komissiyası', :u, :t, FALSE)", 
                                       {"a": comm, "u": st.session_state.user, "t": now})

                        if card_tips > 0:
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('in', 'Tips / Çayvoy', :a, 'Bank Kartı', 'Kart Tip', :u, :t)", {"a":card_tips, "u":st.session_state.user, "t":now})
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at) VALUES ('out', 'Tips / Çayvoy', :a, 'Kassa', 'Kart Tip (Staffa)', :u, :t)", {"a":card_tips, "u":st.session_state.user, "t":now})
                    
                    if not is_test_mode and cust:
                        new_stars = (cust['stars'] + sum([i['qty'] for i in st.session_state.cart_takeaway if i.get('is_coffee')])) - (free * 10)
                        run_action("UPDATE customers SET stars = :ns WHERE card_id = :cid", {"ns": max(0, new_stars), "cid": cust['card_id']})
                    
                    receipt_data = {"cart": st.session_state.cart_takeaway.copy(), "total": final}
                    st.session_state.cart_takeaway, st.session_state.current_customer_ta = [], None
                    st.session_state.search_key_counter += 1
                    st.session_state.active_dialog = ("receipt", receipt_data)
                    st.rerun()
                except Exception as e: 
                    st.error(f"Baza xətası: {e}")
