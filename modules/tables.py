# modules/tables.py
import streamlit as st
import json
import time
import pandas as pd
from sqlalchemy import text
from database import run_query, run_action, get_setting
from utils import get_baku_now, CAT_ORDER_MAP
from modules.pos import add_to_cart, calculate_smart_total, get_cached_menu
from auth import admin_confirm_dialog

def render_tables_page():
    if st.session_state.selected_table:
        tbl = st.session_state.selected_table
        if st.button("⬅️ Qayıt", key="back_tbl_btn"): 
            st.session_state.selected_table = None
            st.session_state.cart_table = []
            st.rerun()
            
        st.markdown(f"### {tbl['label']}")
        c1, c2 = st.columns([1.5, 3])
        
        with c1:
            raw, final, _, _, _, _, _ = calculate_smart_total(st.session_state.cart_table, is_table=True)
            for i, it in enumerate(st.session_state.cart_table): 
                st.write(f"{it['item_name']} x{it['qty']}")
            st.metric("Yekun", f"{final:.2f} ₼")
            
            if st.button("🔥 Mətbəxə Göndər", key="kitchen_btn", type="secondary"): 
                run_action("UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id", 
                           {"i": json.dumps(st.session_state.cart_table), "t": final, "id": tbl['id']})
                st.success("Mətbəxə göndərildi!")
                time.sleep(1)
                st.rerun()
            
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            pm = st.radio("Ödəniş Metodu", ["Nəğd", "Kart"], horizontal=True, label_visibility="collapsed", key="tbl_pm_radio")
            
            if st.button("✅ Masanı Ödə və Bağla", key="pay_tbl_btn", type="primary"):
                if final > 0:
                    is_test_mode = st.session_state.get('test_mode', False)
                    try:
                        items_json = json.dumps(st.session_state.cart_table)
                        total_cogs = 0.0
                        now = get_baku_now()
                        
                        if not is_test_mode:
                            for it in st.session_state.cart_table:
                                recs = run_query("SELECT r.ingredient_name, r.quantity_required, i.unit_cost FROM recipes r LEFT JOIN ingredients i ON r.ingredient_name = i.name WHERE r.menu_item_name=:m", {"m":it['item_name']})
                                if not recs.empty:
                                    for _, r in recs.iterrows():
                                        qty_req = float(r['quantity_required']) * it['qty']
                                        u_cost = float(r['unit_cost']) if pd.notna(r['unit_cost']) else 0.0
                                        total_cogs += (qty_req * u_cost)
                                        run_action("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n", {"q":qty_req, "n":r['ingredient_name']})
                                        
                        run_action("INSERT INTO sales (items, total, payment_method, cashier, created_at, original_total, discount_amount, is_test, cogs) VALUES (:i,:t,:p,:c,:time,:ot,:da,:tst,:cogs)", 
                                  {"i": items_json, "t": final, "p": pm, "c": st.session_state.user, "time": now, "ot": raw, "da": raw-final, "tst": is_test_mode, "cogs": total_cogs})
                        
                        if not is_test_mode:
                            db_pm = "Kassa" if pm == "Nəğd" else "Bank Kartı"
                            pm_cat = "Satış (Nağd)" if pm == "Nəğd" else "Satış (Kart)"
                            run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('in', :cat, :a, :src, 'Masa Satışı', :u, :t, FALSE)", 
                                       {"cat": pm_cat, "a": final, "src": db_pm, "u": st.session_state.user, "t": now})
                            
                            if pm == "Kart":
                                min_comm = float(get_setting("bank_comm_min", "0.60"))
                                pct_comm = float(get_setting("bank_comm_pct", "0.02"))
                                comm = max(min_comm, final * pct_comm)
                                run_action("INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Masa Satış Komissiyası', :u, :t, FALSE)", 
                                           {"a": comm, "u": st.session_state.user, "t": now})

                        run_action("UPDATE tables SET is_occupied=FALSE, items='[]', total=0 WHERE id=:id", {"id": tbl['id']})
                        st.session_state.selected_table = None
                        st.session_state.cart_table = []
                        st.success("Ödəniş qəbul edildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Xəta: {e}")
                else:
                    st.error("Masa boşdur!")

        with c2:
            menu_df = get_cached_menu()
            menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER_MAP).fillna(99)
            menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])
            
            existing_cats = sorted(menu_df['category'].unique().tolist(), key=lambda x: CAT_ORDER_MAP.get(x, 99))
            cats = ["HAMISI"] + [c.upper() for c in existing_cats]
            sc_upper = st.radio("Kat", cats, horizontal=True, label_visibility="collapsed", key="tbl_c_rad")
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
                
                cols = st.columns(3)
                i = 0
                for base, items in groups.items():
                    with cols[i%3]:
                        if len(items) > 1:
                            if st.button(f"{base}\n▾", key=f"tbl_grp_{base}", use_container_width=True, type="secondary"): 
                                st.session_state.active_dialog = ("variants_tbl", items)
                                st.rerun()
                        else:
                            r = items[0]
                            if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"tbl_p_{r['id']}", use_container_width=True, type="secondary"): 
                                add_to_cart(st.session_state.cart_table, {'item_name':r['item_name'], 'price':float(r['price']), 'qty':1, 'is_coffee':r['is_coffee'], 'category':r['category'], 'status':'new'})
                                st.rerun()
                        i+=1
    else:
        if st.session_state.role in ['admin','manager']:
            with st.expander("🛠️ Masa İdarə"):
                nl = st.text_input("Ad") 
                if st.button("Yarat", key="create_table_btn"): 
                    run_action("INSERT INTO tables (label) VALUES (:l)", {"l":nl})
                    st.rerun()
                
                db_tbls = run_query("SELECT label FROM tables")
                dl = st.selectbox("Sil", db_tbls['label'].tolist() if not db_tbls.empty else [])
                if st.button("Sil", key="delete_table_btn"): 
                    admin_confirm_dialog("Silinsin?", lambda: run_action("DELETE FROM tables WHERE label=:l", {"l":dl}))
                    
        df_t = run_query("SELECT * FROM tables ORDER BY id")
        if not df_t.empty:
            cols = st.columns(4)
            for i, r in df_t.iterrows():
                with cols[i%4]:
                    bg = "#ffcccc" if r['is_occupied'] else "#ccffcc"
                    st.markdown(f"<div style='background-color:{bg}; padding:10px; border-radius:10px; text-align:center;'>", unsafe_allow_html=True)
                    if st.button(f"{r['label']}\n{r['total'] if r['is_occupied'] else 'Boş'} ₼", key=f"tbl_{r['id']}", use_container_width=True):
                        st.session_state.selected_table = r.to_dict()
                        st.session_state.cart_table = json.loads(r['items']) if r['items'] and r['items'] != '[]' else []
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
