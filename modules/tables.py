# modules/tables.py
import streamlit as st
import json
import time
from sqlalchemy import text
from database import run_query, run_action
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
                
            if st.button("✅ Masanı Ödə və Bağla", key="pay_tbl_btn", type="primary"):
                if final > 0:
                    try:
                        items_json = json.dumps(st.session_state.cart_table)
                        for it in st.session_state.cart_table:
                            recs = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m", {"m":it['item_name']})
                            if not recs.empty:
                                for _, r in recs.iterrows():
                                    run_action("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n", {"q":float(r['quantity_required'])*it['qty'], "n":r['ingredient_name']})
                                    
                        run_action("INSERT INTO sales (items, total, payment_method, cashier, created_at, original_total, discount_amount) VALUES (:i,:t,'Cash',:c,:time,:ot,:da)", 
                                  {"i": items_json, "t": final, "c": st.session_state.user, "time": get_baku_now(), "ot": raw, "da": raw-final})
                        
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
