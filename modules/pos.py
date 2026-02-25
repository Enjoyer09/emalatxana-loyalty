import streamlit as st
from sqlalchemy import text
from database import run_query, run_action, conn
from utils import clean_qr_code, get_baku_now, get_shift_range
import time

def add_to_cart(cart, item):
    for i in cart: 
        if i['item_name'] == item['item_name'] and i.get('status')=='new': 
            i['qty'] += 1
            return
    cart.append(item)

def calculate_smart_total(cart, customer=None, is_table=False, manual_discount_percent=0):
    total = 0.0
    disc_rate = 0.0
    current_stars = 0
    
    if manual_discount_percent > 0:
        disc_rate = manual_discount_percent / 100.0
        final_total = 0.0
        for i in cart: 
            line = i['qty'] * i['price']
            total += line
            final_total += (line - (line * disc_rate))
        if is_table: 
            final_total += final_total * 0.07
        return total, final_total, disc_rate, 0, 0, 0, False
        
    if customer:
        current_stars = customer.get('stars', 0)
        ctype = customer.get('type', 'standard')
        if ctype == 'ikram': 
            return sum([i['qty']*i['price'] for i in cart]), 0.0, 1.0, 0, 0, 0, True
        rates = {'golden':0.05, 'platinum':0.10, 'elite':0.20, 'thermos':0.20}
        disc_rate = rates.get(ctype, 0.0)
        
    coffee_qty = sum([i['qty'] for i in cart if i.get('is_coffee')])
    free_cof = min(int((current_stars + coffee_qty) // 10), coffee_qty)
    final_total = 0.0
    
    free_coffees_to_give = free_cof 
    
    for i in cart:
        line = i['qty'] * i['price']
        total += line
        
        if i.get('is_coffee'):
            if free_coffees_to_give > 0:
                free_from_this_item = min(i['qty'], free_coffees_to_give)
                paid_qty = i['qty'] - free_from_this_item
                final_total += (paid_qty * i['price']) * (1 - disc_rate)
                free_coffees_to_give -= free_from_this_item
            else:
                final_total += (line - (line * disc_rate))
        else: 
            final_total += line
            
    if is_table: 
        final_total += final_total * 0.07
        
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

def set_received_amount(amount): 
    st.session_state.calc_received = float(amount)

def render_menu(cart, key):
    menu_df = get_cached_menu()
    CAT_ORDER_MAP = {cat: i for i, cat in enumerate(["Kofe (Dənələr)", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar"])}
    menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER_MAP).fillna(99)
    menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])
    
    c_search, c_empty = st.columns([1, 1])
    pos_search = c_search.text_input("🔍 Məhsul axtar...", key=f"pos_s_{key}", label_visibility="collapsed")
    if pos_search: menu_df = menu_df[menu_df['item_name'].str.contains(pos_search, case=False, na=False)]
    
    existing_cats = sorted(menu_df['category'].unique().tolist(), key=lambda x: CAT_ORDER_MAP.get(x, 99))
    cats = ["HAMISI"] + [c.upper() for c in existing_cats]
    
    sc_upper = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key=f"c_{key}")
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
            if base not in groups: 
                groups[base] = []
            groups[base].append(r)
        
        cols = st.columns(4)
        i = 0
        for base, items in groups.items():
            with cols[i%4]:
                if len(items) > 1:
                    @st.dialog(f"{base}")
                    def show_variants(its, grp_key):
                        for it in its:
                            if st.button(f"{it['item_name']}\n{it['price']}₼", key=f"v_{it['id']}_{grp_key}", use_container_width=True, type="secondary"): 
                                add_to_cart(cart, {'item_name':it['item_name'], 'price':float(it['price']), 'qty':1, 'is_coffee':it['is_coffee'], 'category':it['category'], 'status':'new'})
                                st.rerun()
                    if st.button(f"{base}\n▾", key=f"grp_{base}_{key}_{sc}", use_container_width=True, type="secondary"): 
                        show_variants(items, f"{key}_{sc}")
                else:
                    r = items[0]
                    if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"p_{r['id']}_{key}_{sc}", use_container_width=True, type="secondary"): 
                        add_to_cart(cart, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'category':r['category'], 'status':'new'})
                        st.rerun()
            i += 1

def render_pos_page():
    c_carts = st.columns([1, 1, 1, 3])
    for cid in [1, 2, 3]:
        count = len(st.session_state.multi_carts[cid]['cart']) if cid != st.session_state.active_cart_id else len(st.session_state.cart_takeaway)
        btn_type = "primary" if cid == st.session_state.active_cart_id else "secondary"
        if c_carts[cid-1].button(f"🛒 Növbə {cid} ({count})", key=f"cart_sw_{cid}", type=btn_type, use_container_width=True): 
            switch_cart(cid)
            st.rerun()
    
    with c_carts[3]:
        with st.popover("☕ Yalnız Çayvoy Vur"):
            t_amt = st.number_input("Məbləğ (AZN)", min_value=0.0, step=1.0, value=st.session_state.tip_input_val, key="tip_standalone_inp")
            if st.button("💳 Karta Vur", key="tip_only_btn", type="primary"):
                if t_amt > 0:
                    try:
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('in', 'Tips / Çayvoy', :a, 'Bank Kartı', 'Satışsız Tip', :u)", {"a":t_amt, "u":st.session_state.user})
                        run_action("INSERT INTO finance (type, category, amount, source, description, created_by) VALUES ('out', 'Tips / Çayvoy', :a, 'Kassa', 'Satışsız Tip (Staffa)', :u)", {"a":t_amt, "u":st.session_state.user})
                        st.success(f"✅ {t_amt} AZN Tip qeyd olundu!")
                        st.session_state.tip_input_val = 0.0
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Xəta: {e}")

    st.divider()
    
    c_menu, c_cart = st.columns([2.5, 1.2])
    
    with c_menu:
        render_menu(st.session_state.cart_takeaway, "ta")

    with c_cart:
        with st.container(border=True):
            st.markdown(f"### 🛒 Səbət {st.session_state.active_cart_id}")
            
            if 'search_key_counter' not in st.session_state: 
                st.session_state.search_key_counter = 0
                
            c_src, c_btn = st.columns([4,1], vertical_alignment="bottom")
            code = c_src.text_input("Müştəri (QR)", label_visibility="collapsed", placeholder="QR skan et...", key=f"search_input_ta_{st.session_state.search_key_counter}")
            
            if c_btn.button("🔍", key="search_btn_ta") or code:
                # SUPER TƏMİZLƏYİCİ: Linkdən ancaq ID-ni qoparmaq
                raw_code = str(code).strip()
                cid = raw_code
                
                if "id=" in raw_code:
                    try:
                        cid = raw_code.split("id=")[1].split("&")[0]
                    except:
                        pass
                
                cid = cid.strip()
                
                try: 
                    r = run_query("SELECT * FROM customers WHERE card_id=:id", {"id":cid})
                    if not r.empty: 
                        st.session_state.current_customer_ta = r.iloc[0].to_dict()
                        st.toast(f"✅ Müştəri tapıldı (ID: {cid})")
                        st.session_state.search_key_counter += 1 # Xananı sıfırlayırıq ki donmasın!
                        st.rerun()
                    else: 
                        st.error(f"⛔ Tapılmadı! Axtarılan ID: '{cid}'")
                        st.session_state.search_key_counter += 1 # Xananı sıfırlayırıq
                        time.sleep(2)
                        st.rerun()
                except Exception as e: 
                    st.error(f"Baza xətası: {e}")
                    st.session_state.search_key_counter += 1
                    time.sleep(2)
                    st.rerun()
                
            cust = st.session_state.current_customer_ta
            if cust: 
                c_head, c_del = st.columns([4,1], vertical_alignment="bottom")
                c_head.success(f"👤 {cust['card_id']} | ⭐ {cust['stars']}")
                c_del.button("❌", key="clear_cust", on_click=clear_customer_data_callback)
                
            man_disc_val = st.selectbox("Endirim (%)", [0, 10, 20, 30, 40, 50], index=0, key="manual_disc_sel", label_visibility="collapsed")
            disc_note = ""
            if man_disc_val > 0: 
                disc_note = st.text_input("Səbəb (Məcburi!)", placeholder="Endirim səbəbini yazın...", key="disc_reason_inp")
                if not disc_note: st.warning("Səbəb mütləqdir!")
                
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            raw, final, disc, free, _, _, is_ikram = calculate_smart_total(st.session_state.cart_takeaway, cust, manual_discount_percent=man_disc_val)
            
            if not st.session_state.cart_takeaway:
                st.markdown("<p style='text-align:center; color:#6c7a87; margin-top:30px; font-size:20px;'>Səbət boşdur</p>", unsafe_allow_html=True)
            else:
                for i, item in enumerate(st.session_state.cart_takeaway):
                    c_n, c_q, c_btn_col = st.columns([4, 1, 2], vertical_alignment="center")
                    c_n.markdown(f"<span style='font-size:16px; font-weight:800; font-family:Jura; color:#fff;'>{item['item_name']}</span>", unsafe_allow_html=True)
                    c_q.markdown(f"<span style='font-size:16px; font-weight:700;'>x{item['qty']}</span>", unsafe_allow_html=True)
                    with c_btn_col:
                        btn_min, btn_plus = st.columns(2)
                        if btn_min.button("➖", key=f"dec_{i}"): 
                             if item['qty'] > 1: 
                                 item['qty'] -= 1
                             else: 
                                 st.session_state.cart_takeaway.pop(i)
                             st.rerun()
                        if btn_plus.button("➕", key=f"inc_{i}"): 
                            item['qty'] += 1
                            st.rerun()
                            
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            st.markdown(f"<h1 style='text-align:center; font-family:Jura; color:var(--accent-gold); font-size: 56px; font-weight:900; text-shadow: 0 0 10px rgba(255,215,0,0.3); margin:0;'>{final:.2f} ₼</h1>", unsafe_allow_html=True)
            
            if is_ikram: st.success("🎁 İKRAM")
            elif free > 0: st.success(f"🎁 {free} Kofe Hədiyyə")
            
            if final > 0:
                cb1, cb2, cb3 = st.columns(3)
                if cb1.button("5 ₼", type="secondary", use_container_width=True): set_received_amount(5); st.rerun()
                if cb2.button("10 ₼", type="secondary", use_container_width=True): set_received_amount(10); st.rerun()
                if cb3.button("20 ₼", type="secondary", use_container_width=True): set_received_amount(20); st.rerun()
                
                gm = st.number_input("Verilən pul:", min_value=0.0, step=0.5, value=st.session_state.calc_received, key="calc_inp_box", label_visibility="collapsed")
                if gm != st.session_state.calc_received: st.session_state.calc_received = gm
                if gm > 0: 
                    ch = gm - final
                    st.markdown(f"<h4 style='color:#75b798; text-align:center;'>QAYTAR: {ch:.2f} ₼</h4>", unsafe_allow_html=True) if ch>=0 else st.error(f"Əskik: {abs(ch):.2f}")
                    
            pm = st.radio("Metod", ["Nəğd", "Kart", "Personal"], horizontal=True, label_visibility="collapsed")
            card_tips = 0.0
            if pm == "Kart": 
                card_tips = st.number_input("Çayvoy?", min_value=0.0, step=0.5, key="tips_inp")
            own_cup = st.checkbox("🥡 Öz Stəkanı / Eko", key="eco_mode_check")
            
            btn_disabled = True if (man_disc_val > 0 and not disc_note) else False
            
            if st.button("✅ ÖDƏNİŞİ TAMAMLA", type="primary", use_container_width=True, disabled=btn_disabled, key="pay_btn"):
                if not st.session_state.cart_takeaway: 
                    st.error("Səbət boşdur")
                    st.stop()
                    
                final_db_total = final
                final_note = disc_note
                
                if pm == "Personal":
                    start_sh, _ = get_shift_range()
                    used = run_query("SELECT SUM(original_total) as s FROM sales WHERE cashier=:u AND payment_method='Staff' AND created_at >= :d", {"u":st.session_state.user, "d":start_sh}).iloc[0]['s'] or 0.0
                    staff_limit = 6.00
                    current_cart_raw_val = sum([i['price']*i['qty'] for i in st.session_state.cart_takeaway])
                    remaining_limit = max(0, staff_limit - float(used))
                    if current_cart_raw_val > remaining_limit: 
                        overdraft = current_cart_raw_val - remaining_limit
                        final_db_total = overdraft
                        final_note = f"Limit: {staff_limit} | Borc: {overdraft:.2f}"
                        st.warning(f"⚠️ Limit Doldu! Bu çekdən {overdraft:.2f} AZN ödəməlisiniz.")
                    else: 
                        final_db_total = 0.00
                        final_note = f"Staff Limit ({used + current_cart_raw_val:.2f}/{staff_limit})"
                        
                try:
                    with conn.session as s:
                        for it in st.session_state.cart_takeaway:
                            recs = s.execute(text("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m"), {"m":it['item_name']}).fetchall()
                            for r in recs:
                                ing_name = r[0]
                                ing_info = s.execute(text("SELECT category FROM ingredients WHERE name=:n"), {"n":ing_name}).fetchone()
                                ing_cat = ing_info[0] if (ing_info and ing_info[0]) else ""
                                if own_cup and ("Qablaşdırma" in ing_cat or "Stəkan" in ing_name or "Qapaq" in ing_name): 
                                    continue 
                                s.execute(text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n AND stock_qty >= :q"), {"q":float(r[1])*it['qty'], "n":ing_name})
                                
                        items_str = ", ".join([f"{x['item_name']} x{x['qty']}" for x in st.session_state.cart_takeaway])
                        if own_cup: final_note += " [Eko Mod]"
                        
                        if cust:
                            coffee_count_in_cart = sum([i['qty'] for i in st.session_state.cart_takeaway if i.get('is_coffee')])
                            new_stars = cust['stars'] + coffee_count_in_cart
                            if free > 0:
                                new_stars -= (free * 10)
                                if new_stars < 0: new_stars = 0 
                            s.execute(text("UPDATE customers SET stars = :ns WHERE card_id = :cid"), {"ns": new_stars, "cid": cust['card_id']})
                        
                        s.execute(text("INSERT INTO sales (items, total, payment_method, cashier, created_at, customer_card_id, original_total, discount_amount, note, tip_amount) VALUES (:i,:t,:p,:c,:time,:cid,:ot,:da,:n, :tip)"), {"i":items_str,"t":final_db_total,"p":("Cash" if pm=="Nəğd" else "Card" if pm=="Kart" else "Staff"),"c":st.session_state.user,"time":get_baku_now(),"cid":cust['card_id'] if cust else None, "ot":raw, "da":raw-final, "n":final_note, "tip":card_tips})
                        s.commit()
                        
                    st.session_state.last_receipt_data = {'cart':st.session_state.cart_takeaway.copy(), 'total':final_db_total, 'email':cust['email'] if cust else None}
                    st.session_state.show_receipt_popup = True
                    st.session_state.cart_takeaway = []
                    st.session_state.current_customer_ta = None
                    st.session_state.multi_carts[st.session_state.active_cart_id] = {'cart': [], 'customer': None}
                    st.session_state.calc_received = 0.0
                    st.session_state.search_key_counter += 1
                    st.rerun()
                except Exception as e: 
                    st.error(f"Xəta: {e}")
