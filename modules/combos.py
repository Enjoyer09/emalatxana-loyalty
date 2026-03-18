# modules/combos.py — PATCHED v2.0
import streamlit as st
import pandas as pd
import time
import logging
from decimal import Decimal, ROUND_HALF_UP

from database import run_query, run_action, run_transaction
from utils import log_system, safe_decimal

logger = logging.getLogger(__name__)


def render_combos_page():
    st.subheader("🍔 Kombo (Bundle) Yarat və İdarə Et")

    # ============================================================
    # YENİ KOMBO YARAT (Orijinal + Transaction + Decimal + Audit)
    # ============================================================
    with st.expander("➕ Yeni Kombo Yarat", expanded=True):
        st.info("Bu bölmədə eyni anda bir neçə məhsulu birləşdirərək tək bir 'Kombo' kimi satışa çıxara bilərsiniz. Satılan zaman kombonun tərkibindəki bütün xammallar anbardar avtomatik silinəcək və maya dəyəri (COGS) hesablanacaq.")

        combo_name = st.text_input("Kombonun Adı (məs: Tələbə Kombosu - Latte + Kruasan)")
        combo_price = st.number_input("Kombonun Yekun Satiş Qiyməti (₼)", min_value=0.0, step=0.5)

        menu_df = run_query("SELECT item_name FROM menu WHERE is_active=TRUE AND category != 'Kombolar'")
        if not menu_df.empty:
            selected_items = st.multiselect("Komboya daxil olan məhsullar (Ən az 2 məhsul seçin)", menu_df['item_name'].tolist())

            if st.button("Kombunu Yarat", type="primary"):
                if not combo_name or not combo_name.strip():
                    st.error("Kombo adı boş ola bilməz!")
                elif len(selected_items) < 2:
                    st.error("Ən azı 2 məhsul seçin!")
                elif combo_price <= 0:
                    st.error("Qiymət 0-dan böyük olmalıdır!")
                else:
                    try:
                        # Duplicate check
                        existing = run_query(
                            "SELECT 1 FROM menu WHERE item_name=:n AND category='Kombolar'",
                            {"n": combo_name.strip()}
                        )
                        if not existing.empty:
                            st.error(f"'{combo_name}' adlı kombo artıq mövcuddur!")
                        else:
                            # Atomic transaction: menu + recipes
                            actions = [
                                (
                                    "INSERT INTO menu (item_name, category, price, is_coffee, is_active) "
                                    "VALUES (:n, 'Kombolar', :p, FALSE, TRUE)",
                                    {"n": combo_name.strip(), "p": str(Decimal(str(combo_price)))}
                                )
                            ]

                            # Collect recipes from selected items
                            for item in selected_items:
                                recs = run_query(
                                    "SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m",
                                    {"m": item}
                                )
                                for _, r in recs.iterrows():
                                    actions.append((
                                        "INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) "
                                        "VALUES (:m, :i, :q)",
                                        {
                                            "m": combo_name.strip(),
                                            "i": r['ingredient_name'],
                                            "q": str(Decimal(str(r['quantity_required'])))
                                        }
                                    ))

                            run_transaction(actions)
                            log_system(
                                st.session_state.user,
                                f"COMBO_CREATED: {combo_name}, price={combo_price}, items={selected_items}"
                            )
                            st.success("Kombo uğurla yaradıldı və POS/Anbar sistemi ilə sinxronlaşdırıldı!")
                            time.sleep(1.5)
                            st.rerun()

                    except Exception as e:
                        st.error(f"Kombo yaradılarkən xəta baş verdi: {e}")
                        logger.error(f"Combo creation failed: {e}", exc_info=True)
        else:
            st.warning("Zəhmət olmasa, əvvəlcə Menyuda normal məhsullar yaradın.")

    # ============================================================
    # MÖVCUD KOMBOLAR (Orijinal + Transaction + Audit)
    # ============================================================
    st.markdown("---")
    st.subheader("Mövcud Kombolar")
    combos = run_query("SELECT * FROM menu WHERE category='Kombolar' ORDER BY id DESC")

    if not combos.empty:
        st.dataframe(combos[['item_name', 'price', 'is_active']], hide_index=True, use_container_width=True)

        # Kombo tərkibini göstər
        with st.expander("📋 Kombo Tərkibləri"):
            for _, combo in combos.iterrows():
                combo_recipes = run_query(
                    "SELECT ingredient_name, quantity_required FROM recipes WHERE menu_item_name=:m",
                    {"m": combo['item_name']}
                )
                if not combo_recipes.empty:
                    st.markdown(f"**{combo['item_name']}** ({combo['price']} ₼):")
                    for _, rec in combo_recipes.iterrows():
                        st.write(f"  • {rec['ingredient_name']}: {rec['quantity_required']}")
                else:
                    st.markdown(f"**{combo['item_name']}** — resept yoxdur ⚠️")

        # Silmə
        del_col1, del_col2 = st.columns([3, 1])
        del_combo = del_col1.selectbox("Silinəcək Kombo", combos['item_name'].tolist())
        if del_col2.button("Kombonu Sil", use_container_width=True):
            try:
                # Atomic delete: recipes + menu
                actions = [
                    ("DELETE FROM recipes WHERE menu_item_name=:m", {"m": del_combo}),
                    ("DELETE FROM menu WHERE item_name=:m AND category='Kombolar'", {"m": del_combo})
                ]
                run_transaction(actions)
                log_system(st.session_state.user, f"COMBO_DELETED: {del_combo}")
                st.success("Kombo silindi!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Silmə xətası: {e}")
                logger.error(f"Combo delete failed: {e}", exc_info=True)
    else:
        st.info("Hələ ki heç bir Kombo yaradılmayıb.")
