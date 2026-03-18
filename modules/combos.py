# modules/combos.py — FINAL PATCHED v2.0
import streamlit as st
import time
import logging
from decimal import Decimal

from database import run_query, run_action, run_transaction
from utils import log_system

logger = logging.getLogger(__name__)


def render_combos_page():
    st.subheader("🍔 Kombo (Bundle) Yarat və İdarə Et")

    with st.expander("➕ Yeni Kombo Yarat", expanded=True):
        st.info("Bu bölmədə eyni anda bir neçə məhsulu birləşdirərək tək bir 'Kombo' kimi satışa çıxara bilərsiniz.")

        combo_name = st.text_input("Kombonun Adı (məs: Tələbə Kombosu - Latte + Kruasan)")
        combo_price = st.number_input("Kombonun Yekun Satış Qiyməti (₼)", min_value=0.0, step=0.5)

        menu_df = run_query("SELECT item_name FROM menu WHERE is_active=TRUE AND category != 'Kombolar'")
        if not menu_df.empty:
            selected_items = st.multiselect("Komboya daxil olan məhsullar (Ən az 2 məhsul seçin)", menu_df['item_name'].tolist())

            if st.button("Kombonu Yarat", type="primary"):
                if not combo_name or not combo_name.strip():
                    st.error("Kombo adı boş ola bilməz!")
                elif len(selected_items) < 2:
                    st.error("Ən azı 2 məhsul seçin!")
                elif combo_price <= 0:
                    st.error("Qiymət 0-dan böyük olmalıdır!")
                else:
                    try:
                        existing = run_query(
                            "SELECT 1 FROM menu WHERE item_name=:n AND category='Kombolar'",
                            {"n": combo_name.strip()}
                        )
                        if not existing.empty:
                            st.error(f"'{combo_name}' adlı kombo artıq mövcuddur!")
                        else:
                            actions = [
                                (
                                    "INSERT INTO menu (item_name, category, price, is_coffee, is_active) VALUES (:n, 'Kombolar', :p, FALSE, TRUE)",
                                    {"n": combo_name.strip(), "p": str(Decimal(str(combo_price)))}
                                )
                            ]

                            for item in selected_items:
                                recs = run_query("SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m", {"m": item})
                                for _, r in recs.iterrows():
                                    actions.append((
                                        "INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)",
                                        {
                                            "m": combo_name.strip(),
                                            "i": r['ingredient_name'],
                                            "q": str(Decimal(str(r['quantity_required'])))
                                        }
                                    ))

                            run_transaction(actions)
                            log_system(
                                st.session_state.user,
                                "COMBO_CREATED",
                                {"combo_name": combo_name.strip(), "price": combo_price, "items": selected_items}
                            )
                            st.success("Kombo uğurla yaradıldı!")
                            time.sleep(1.5)
                            st.rerun()

                    except Exception as e:
                        st.error(f"Kombo yaradılarkən xəta baş verdi: {e}")
        else:
            st.warning("Əvvəlcə menyuda normal məhsullar yaradın.")

    st.markdown("---")
    st.subheader("Mövcud Kombolar")
    combos = run_query("SELECT * FROM menu WHERE category='Kombolar' ORDER BY id DESC")

    if not combos.empty:
        st.dataframe(combos[['item_name', 'price', 'is_active']], hide_index=True, use_container_width=True)

        with st.expander("📋 Kombo Tərkibləri"):
            for _, combo in combos.iterrows():
                combo_recipes = run_query(
                    "SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m",
                    {"m": combo['item_name']}
                )
                if not combo_recipes.empty:
                    st.markdown(f"**{combo['item_name']}** ({combo['price']} ₼):")
                    for _, rec in combo_recipes.iterrows():
                        st.write(f"• {rec['ingredient_name']}: {rec['quantity_required']}")
                else:
                    st.markdown(f
