import streamlit as st
from sqlalchemy import text
from database import run_query, run_action, conn
from utils import clean_qr_code, get_baku_now, get_shift_range
import json

def add_to_cart(cart, item):
    for i in cart: 
        if i['item_name'] == item['item_name'] and i.get('status')=='new': i['qty']+=1; return
    cart.append(item)

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0):
    total = 0.0; disc_rate = 0.0; current_stars = 0
    if manual_discount_percent > 0:
        disc_rate = manual_discount_percent / 100.0; final_total = 0.0
        for i in cart: line = i['qty'] * i['price']; total += line; final_total += (line - (line * disc_rate))
        if is_table: final_total += final_total * 0.07
        return total, final_total, disc_rate, 0, 0, 0, False
    if customer:
        current_stars = customer.get('stars', 0); ctype = customer.get('type', 'standard')
        if ctype == 'ikram': return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20}; disc_rate = rates.get(ctype, 0.0)
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')]); free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty); final_total = 0.0
    for i in cart:
        line = i['qty'] * i['price']; total += line
        if i.get('is_coffee'): final_total += (line - (line * disc_rate))
        else: final_total += line
    if is_table: final_total += final_total * 0.07
    return total, final_total, disc_rate, free_cof, 0, 0, False

def get_cached_menu(): return run_query("SELECT * FROM menu WHERE is_active=TRUE")

def switch_cart(new_id):
    st.session_state.multi_carts[st.session_state.active_cart_id]['cart'] = st.session_state.cart_takeaway
    st.session_state.multi_carts[st.session_state.active_cart_id]['customer'] = st.session_state.current_customer_ta
    st.session_state.active_cart_id = new_id
    st.session_state.cart_takeaway = st.session_state.multi_carts[new_id]['cart']
    st.session_state.current_customer_ta = st.session_state.multi_carts[new_id]['customer']

def clear_customer_data_callback(): st.session_state.current_customer_ta = None; st.session_state.search_key_counter += 1
def set_received_amount(amount): st.session_state.calc_received = float(amount)

def render_menu(cart, key):
    menu_df = get_cached_menu()
    CAT_ORDER_MAP = {cat: i for i, cat in enumerate(["Kofe (Dənələr)", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar"])}
    menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER_MAP).fillna(99); menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])
    pos_search = st.text_input("🔍 Menyu Axtarış", key=f"pos_s_{key}")
    if pos_search: menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]
    existing_cats = sorted(menu_df['category'].unique().tolist(), key=lambda x: CAT_ORDER_MAP.get(x, 99))
    cats = ["Hamısı"] + existing_cats
    sc = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_{key}")
    prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]
    if not prods.empty:
        groups = {}
        for _, r in prods.iterrows():
            n = r['item_name']; base = n
            for s in [" S", " M", " L", " XL", " Single", " Double"]:
                if n.endswith(s): base = n[:-len(s)]; break
            if base not in groups: groups[base] = []
            groups[base].append(r)
        cols = st.columns(3); i = 0
        for base, items in groups.items():
            with cols[i%3]:
                if len(items) > 1:
                    @st.dialog(f"{base}")
                    def show_variants(its, grp_key):
                        for it in its:
                            if st.button(f"{it['item_name']}\n{it['price']}₼", key=f"v_{it['id']}_{grp_key}", use_container_width=True, type="secondary"):
                                add_to_cart(cart, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'category':it['category'], 'status':'new'}); st.rerun()
                    if st.button(f"{base}\n▾", key=f"grp_{base}_{key}_{sc}", use_container_width=True, type="secondary"): show_variants(items, f"{key}_{sc}")
                else:
                    r = items[0]
                    if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}_{sc}", use_container_width=True, type="secondary"):
                        add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'category':r['category'], 'status':'new'}); st.rerun()
            i+=1

def render_pos_page():
    c_carts = st.columns(3)
    for cid in [1, 2, 3]:
        count = len(st.session_state.multi_carts[cid]['cart'])
        if cid == st.session_state.active_cart_id: count = len(st.session_state.cart_takeaway)
        btn_type = "primary" if cid == st.session_state.active_cart_id else "secondary"
        if c_carts[cid-1].button(f"🛒 Səbət {cid} ({count})", key=f"cart_sw_{cid}", type=btn_type, use_container_width=True): switch_cart(cid); st.rerun()
    st.divider()
    c1, c2 = st.columns([1.5, 3])
    with c1:
        st.info(f"🧾 Al-Apar (Səbət {st.session_state.active_cart_id})")
        if 'search_key_counter' not in st.session_state: st.session_state.search_key_counter = 0
        c_src, c_btn = st.columns([5,1]); code = c_src.text_input("Müştəri (QR)", label_visibility="collapsed", placeholder="Skan...", key=f"search_input_ta_{st.session_state.search_key_counter}")
        if c_btn.button("🔍", key="search_btn_ta") or code:
            cid = clean_qr_code(code)
            try: 
                r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                if not r.empty: st.session_state.current_customer_ta = r.iloc[0].to_dict(); st.toast(f"✅ Müştəri: {cid}"); st.rerun()
                else: st.error("Tapılmadı")
            except: pass
        cust = st.session_state.current_customer_ta
        if cust: c_head, c_del = st.columns([4,1]); c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}"); c_del.button("❌", key="clear_cust", on_click=clear_customer_data_callback)
        with st.expander("💙 Yalnız Çayvoy (Satışsız)"):
            t_amt = st.number_input("Tip Məbləği (AZN)", min_value=0.0, step=1.0, value=st.session_state.tip_input_val, key="tip_standalone_inp")
            if st.button("💳 Karta Tip Vur", key="tip_only_btn"):
                if t_amt > 0:
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Tips / Çayvoy', :a, 'Bank Kartı', 'Satışsız Tip', :u)", {"a":t_amt, "u":st.session_state.user})
                    run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Tips / Çayvoy', :a, 'Kassa', 'Satışsız Tip (Staffa)', :u)", {"a":t_amt, "u":st.session_state.user})
                    run_action("INSERT INTO expenses (amount, reason, spender, source) VALUES (:a, 'Tips / Çayvoy', :u, 'Kassa')", {"a":t_amt, "u":st.session_state.user})
                    st.success(f"✅ {t_amt} AZN Tip qeyd olundu!"); st.session_state.tip_input_val = 0.0; time.sleep(2); st.rerun()
        man_disc_val = st.selectbox("Endirim (%)", [0, 10, 20, 30, 40, 50], index=0, key="manual_disc_sel"); disc_note = ""
        if man_disc_val > 0: disc_note = st.text_input("Səbəb (Məcburi!)", placeholder="Məs: Dost, Menecer jesti", key="disc_reason_inp"); 
        if man_disc_val>0 and not disc_note: st.warning("Səbəb yaz!")
        raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust, manual_discount_percent=man_disc_val)
        if st.session_state.cart_takeaway:
            for i, item in enumerate(st.session_state.cart_takeaway):
                c_n, c_d, c_q, c_u = st.columns([3, 1, 1, 1]); c_n.write(f"{item['item_name']}"); c_q.write(f"x{item['qty']}")
                if c_d.button("➖", key=f"dec_{i}"): 
                     if item['qty'] > 1: item['qty'] -= 1
                     else: st.session_state.cart_takeaway.pop(i)
                     st.rerun()
                if c_u.button("➕", key=f"inc_{i}"): item['qty'] += 1; st.rerun()
        st.markdown(f"<h2 style='text-align:right;color:#E65100'>{final:.2f} ₼</h2>", unsafe_allow_html=True)
        if is_ikram: st.success("🎁 İKRAM")
        elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
        if final > 0:
            st.markdown("---"); cb1, cb2, cb3, cb4, cb5 = st.columns(5)
            if cb1.button(f"{final:.2f}", type="secondary"): set_received_amount(final); st.rerun()
            if cb2.button("5 ₼", type="secondary"): set_received_amount(5); st.rerun()
            if cb3.button("10 ₼", type="secondary"): set_received_amount(10); st.rerun()
            if cb4.button("20 ₼", type="secondary"): set_received_amount(20); st.rerun()
            if cb5.button("50 ₼", type="secondary"): set_received_amount(50); st.rerun()
            c_calc1, c_calc2 = st.columns([1,2]); 
            with c_calc1: gm = st.number_input("Verilən:", min_value=0.0, step=0.5, value=st.session_state.calc_received, key="calc_inp_box"); 
            if gm!=st.session_state.calc_received: st.session_state.calc_received=gm
            with c_calc2: 
                if gm > 0: ch = gm - final; st.markdown(f"<h3 style='color:#2E7D32'>💱 QAYTAR: {ch:.2f} ₼</h3>", unsafe_allow_html=True) if ch>=0 else st.error(f"Əskik: {abs(ch):.2f}")
        pm = st.radio("Metod", ["Nəğd", "Kart", "Personal (Staff)"], horizontal=True)
        card_tips = 0.0
        if pm == "Kart": card_tips = st.number_input("Çayvoy (Tips)?", min_value=0.0, step=0.5, key="tips_inp")
        own_cup = st.checkbox("🥡 Öz Stəkanı / Eko", key="eco_mode_check")
        btn_disabled = True if (man_disc_val > 0 and not disc_note) else False
        if st.button("✅ ÖDƏNİŞ", type="primary", use_container_width=True, disabled=btn_disabled, key="pay_btn"):
            if not st.session_state.cart_takeaway: st.error("Boşdur"); st.stop()
            # ... (Transaction Logic - Qalanı eynidir, yalnız receipt logic silinib) ...
            # ... (Burada köhnə transaction kodu olmalıdır) ...
            # Transaction bitəndən sonra:
            st.session_state.last_receipt_data = {'cart':st.session_state.cart_takeaway.copy(), 'total':final, 'email':cust['email'] if cust else None}
            st.session_state.show_receipt_popup = True
            st.session_state.cart_takeaway = []; st.session_state.current_customer_ta = None
            st.session_state.multi_carts[st.session_state.active_cart_id] = {'cart': [], 'customer': None}
            st.session_state.calc_received = 0.0; st.session_state.search_key_counter += 1
            st.rerun()
    with c2: render_menu(st.session_state.cart_takeaway, "ta")
