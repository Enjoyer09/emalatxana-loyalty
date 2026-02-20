import streamlit as st
import pandas as pd
import time
from database import run_query, run_action
from utils import PRESET_CATEGORIES

def render_inventory_page():
    st.subheader("📦 Anbar İdarəetməsi")
    if st.session_state.role in ['admin','manager']:
        with st.expander("➕ Mədaxil / Yeni Mal"):
             with st.form("smart_add_item", clear_on_submit=True):
                c1, c2, c3 = st.columns(3); mn_name = c1.text_input("Malın Adı"); sel_cat = c2.selectbox("Kateqoriya", PRESET_CATEGORIES + ["➕ Yeni Yarat..."]); mn_unit = c3.selectbox("Vahid", ["L", "KQ", "ƏDƏD"])
                mn_cat_final = st.text_input("Yeni Kateqoriya") if sel_cat == "➕ Yeni Yarat..." else sel_cat
                c4, c5, c6 = st.columns(3); pack_size = c4.number_input("Qab Həcmi", min_value=0.001, value=1.0, step=0.1); pack_price = c5.number_input("Qab Qiyməti", min_value=0.00, value=10.0, step=0.5); pack_count = c6.number_input("Say", min_value=1.0, value=1.0, step=1.0)
                mn_type = st.selectbox("Növ", ["ingredient", "consumable"])
                if st.form_submit_button("Əlavə Et") and mn_name and pack_size > 0:
                     run_action("INSERT INTO ingredients (name, stock_qty, unit, category, type, unit_cost, approx_count) VALUES (:n, :q, :u, :c, :t, :uc, 1) ON CONFLICT (name) DO UPDATE SET stock_qty = ingredients.stock_qty + :q, unit_cost = :uc", {"n":mn_name, "q":pack_size*pack_count, "u":mn_unit, "c":mn_cat_final, "t":mn_type, "uc":pack_price/pack_size}); st.success("✅ OK"); time.sleep(1); st.rerun()

    c1, c2 = st.columns([3,1]); search_query = c1.text_input("🔍 Axtarış..."); df_i = run_query(f"SELECT id, name, stock_qty, unit, unit_cost, category FROM ingredients {'WHERE name ILIKE :s' if search_query else ''} ORDER BY name", {"s":f"%{search_query}%"} if search_query else {})
    rows_per_page = st.selectbox("Səhifə", [20, 40, 60]); total_rows = len(df_i); start_idx = st.session_state.anbar_page * rows_per_page; end_idx = start_idx + rows_per_page
    df_page = df_i.iloc[start_idx:end_idx].copy()
    df_page['stock_qty'] = pd.to_numeric(df_page['stock_qty'], errors='coerce').fillna(0.0); df_page['unit_cost'] = pd.to_numeric(df_page['unit_cost'], errors='coerce').fillna(0.0); df_page['Total Value'] = df_page['stock_qty'] * df_page['unit_cost']

    if st.session_state.role == 'manager':
        df_page_display = df_page[['id', 'name', 'stock_qty', 'unit', 'category']]; df_page_display.insert(0, "Seç", False)
        edited_mgr_anbar = st.data_editor(df_page_display, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, disabled=["id","name","stock_qty","unit","category"], use_container_width=True, key="anbar_mgr_ed")
        sel_mgr_rows = edited_mgr_anbar[edited_mgr_anbar["Seç"]]
        if len(sel_mgr_rows) == 1:
            c1, c2 = st.columns(2)
            if c1.button("➕ Mədaxil", key="anbar_restock_mgr"): st.session_state.restock_item_id = int(sel_mgr_rows.iloc[0]['id']); st.rerun()
            if c2.button("✏️ Düzəliş", key="anbar_edit_mgr"): st.session_state.edit_item_id = int(sel_mgr_rows.iloc[0]['id']); st.rerun()
    else:
        df_page.insert(0, "Seç", False)
        edited_df = st.data_editor(df_page, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True), "unit_cost": st.column_config.NumberColumn(format="%.5f"), "Total Value": st.column_config.NumberColumn(format="%.2f")}, disabled=["id", "name", "stock_qty", "unit", "unit_cost", "category", "Total Value", "type"], use_container_width=True, key="anbar_editor")
        sel_rows = edited_df[edited_df["Seç"]]; sel_ids = sel_rows['id'].tolist()
        c1, c2, c3 = st.columns(3)
        if len(sel_ids) == 1:
            if c1.button("➕ Mədaxil", key="anbar_restock_btn"): st.session_state.restock_item_id = int(sel_ids[0]); st.rerun()
            if c2.button("✏️ Düzəliş", key="anbar_edit_btn"): st.session_state.edit_item_id = int(sel_ids[0]); st.rerun()
        if len(sel_ids) > 0 and c3.button("🗑️ Sil", key="anbar_del_btn"): [run_action("DELETE FROM ingredients WHERE id=:id", {"id":int(i)}) for i in sel_ids]; st.success("Silindi!"); st.rerun()

    pc1, pc2, pc3 = st.columns([1,2,1])
    if pc1.button("⬅️", key="anbar_prev") and st.session_state.anbar_page > 0: st.session_state.anbar_page -= 1; st.rerun()
    pc2.write(f"Səhifə {st.session_state.anbar_page + 1}")
    if pc3.button("➡️", key="anbar_next") and end_idx < total_rows: st.session_state.anbar_page += 1; st.rerun()

    if st.session_state.get('restock_item_id'):
        res = run_query("SELECT * FROM ingredients WHERE id=:id", {"id":st.session_state.restock_item_id})
        if not res.empty:
            r_item = res.iloc[0]
            @st.dialog("➕ Mədaxil")
            def show_restock(r):
                with st.form("rs"):
                    p = st.number_input("Say", min_value=1.0, value=1.0, step=1.0)
                    w = st.number_input(f"Çəki ({r['unit']})", min_value=0.001, value=1.0, step=0.1)
                    pr = st.number_input("Yekun Qiymət", min_value=0.0, value=0.0, step=0.5)
                    if st.form_submit_button("Təsdiq"):
                        tq = p*w; uc = pr/tq if tq>0 else r['unit_cost']
                        run_action("UPDATE ingredients SET stock_qty=stock_qty+:q, unit_cost=:uc WHERE id=:id", {"q":tq,"uc":float(uc),"id":int(r['id'])})
                        st.session_state.restock_item_id=None; st.rerun()
            show_restock(r_item)

    if st.session_state.get('edit_item_id'):
        res = run_query("SELECT * FROM ingredients WHERE id=:id", {"id":st.session_state.edit_item_id})
        if not res.empty:
            r_item = res.iloc[0]
            @st.dialog("✏️ Düzəliş")
            def show_edit(r):
                with st.form("ed"):
                    n = st.text_input("Ad", r['name']); c = st.selectbox("Kat", PRESET_CATEGORIES, index=0); u = st.selectbox("Vahid", ["KQ","L","ƏDƏD"], index=0); uc = st.number_input("Qiymət", value=float(r['unit_cost']))
                    if st.form_submit_button("Yadda Saxla"): 
                        try: run_action("UPDATE ingredients SET name=:n, category=:c, unit=:u, unit_cost=:uc WHERE id=:id", {"n":n,"c":c,"u":u,"uc":float(uc),"id":int(r['id'])}); st.success("Yeniləndi!"); time.sleep(0.5); st.session_state.edit_item_id=None; st.rerun()
                        except Exception as e: st.error(f"Xəta: {e}")
            show_edit(r_item)
