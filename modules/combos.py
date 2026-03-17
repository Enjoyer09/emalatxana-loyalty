# modules/combos.py
import streamlit as st
import pandas as pd
import time
from database import run_query, run_action

def render_combos_page():
    st.subheader("🍔 Kombo (Bundle) Yarat və İdarə Et")
    
    with st.expander("➕ Yeni Kombo Yarat", expanded=True):
        st.info("Bu bölmədə eyni anda bir neçə məhsulu birləşdirərək tək bir 'Kombo' kimi satışa çıxara bilərsiniz. Satılan zaman kombonun tərkibindəki bütün xammallar anbardar avtomatik silinəcək və maya dəyəri (COGS) hesablanacaq.")
        
        combo_name = st.text_input("Kombonun Adı (məs: Tələbə Kombosu - Latte + Kruasan)")
        combo_price = st.number_input("Kombonun Yekun Satiş Qiyməti (₼)", min_value=0.0, step=0.5)
        
        menu_df = run_query("SELECT item_name FROM menu WHERE is_active=TRUE AND category != 'Kombolar'")
        if not menu_df.empty:
            selected_items = st.multiselect("Komboya daxil olan məhsullar (Ən az 2 məhsul seçin)", menu_df['item_name'].tolist())
            
            if st.button("Kombunu Yarat", type="primary"):
                if combo_name and selected_items and combo_price > 0:
                    try:
                        run_action("INSERT INTO menu (item_name, category, price, is_coffee, is_active) VALUES (:n, 'Kombolar', :p, FALSE, TRUE)", {"n": combo_name, "p": combo_price})
                        
                        for item in selected_items:
                            recs = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m", {"m": item})
                            for _, r in recs.iterrows():
                                run_action("INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)", 
                                           {"m": combo_name, "i": r['ingredient_name'], "q": r['quantity_required']})
                        
                        st.success("Kombo uğurla yaradıldı və POS/Anbar sistemi ilə sinxronlaşdırıldı!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kombo yaradılarkən xəta baş verdi: {e}")
        else:
            st.warning("Zəhmət olmasa, əvvəlcə Menyuda normal məhsullar yaradın.")
            
    st.markdown("---")
    st.subheader("Mövcud Kombolar")
    combos = run_query("SELECT * FROM menu WHERE category='Kombolar' ORDER BY id DESC")
    
    if not combos.empty:
        st.dataframe(combos[['item_name', 'price', 'is_active']], hide_index=True, use_container_width=True)
        
        del_col1, del_col2 = st.columns([3, 1])
        del_combo = del_col1.selectbox("Silinəcək Kombo", combos['item_name'].tolist())
        if del_col2.button("Kombunu Sil", use_container_width=True):
            run_action("DELETE FROM recipes WHERE menu_item_name=:m", {"m": del_combo})
            run_action("DELETE FROM menu WHERE item_name=:m AND category='Kombolar'", {"m": del_combo})
            st.success("Kombo silindi!")
            time.sleep(1)
            st.rerun()
    else:
        st.info("Hələ ki heç bir Kombo yaradılmayıb.")
