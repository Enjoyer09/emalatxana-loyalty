# modules/tables.py — PATCHED v2.0
import streamlit as st
import json
import time
import logging
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

from database import run_query, run_action, run_transaction, get_setting
from utils import get_baku_now, CAT_ORDER_MAP, safe_decimal, log_system, SK_CASH_LIMIT
from modules.pos import add_to_cart, calculate_smart_total, get_cached_menu
from auth import admin_confirm_dialog

logger = logging.getLogger(__name__)


# ============================================================
# SAFE JSON PARSE
# ============================================================
def safe_json_loads(data, default=None):
    """Safely parse JSON string, return default on failure"""
    if default is None:
        default = []
    if not data or data == '[]':
        return default
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON parse error: {e}, data={data[:100] if data else 'None'}")
        return default


# ============================================================
# ATOMIC TABLE SALE (reuses pos.py finalize_sale pattern)
# ============================================================
def finalize_table_sale(table_id, cart_items, final_total, original_total, pm, user, is_test):
    """
    All-or-nothing table sale:
    sales + finance + stock deduction + table reset
    """
    now = get_baku_now()
    final_d = Decimal(str(final_total))
    original_d = Decimal(str(original_total))
    discount_d = original_d - final_d
    items_json = json.dumps(cart_items)
    total_cogs = Decimal("0")
    actions = []

    # ---- Stock deduction + COGS ----
    if not is_test:
        for it in cart_items:
            recs = run_query(
                "SELECT r.ingredient_name, r.quantity_required, i.unit_cost "
                "FROM recipes r LEFT JOIN ingredients i ON r.ingredient_name = i.name "
                "WHERE r.menu_item_name=:m",
                {"m": it['item_name']}
            )
            if not recs.empty:
                for _, r in recs.iterrows():
                    qty_req = Decimal(str(r['quantity_required'])) * Decimal(str(it['qty']))
                    u_cost = Decimal(str(r['unit_cost'])) if pd.notna(r['unit_cost']) else Decimal("0")
                    total_cogs += qty_req * u_cost
                    actions.append((
                        "UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n",
                        {"q": str(qty_req), "n": r['ingredient_name']}
                    ))

    # ---- Sales record ----
    actions.append((
        "INSERT INTO sales (items, total, payment_method, cashier, created_at, "
        "original_total, discount_amount, is_test, cogs) "
        "VALUES (:i,:t,:p,:c,:time,:ot,:da,:tst,:cogs)",
        {
            "i": items_json, "t": str(final_d), "p": pm, "c": user,
            "time": now, "ot": str(original_d), "da": str(discount_d),
            "tst": is_test, "cogs": str(total_cogs)
        }
    ))

    # ---- Finance entries ----
    if not is_test and final_d > 0:
        db_pm = "Kassa" if pm == "Nəğd" else "Bank Kartı"
        pm_cat = "Satış (Nağd)" if pm == "Nəğd" else "Satış (Kart)"

        actions.append((
            "INSERT INTO finance (type, category, amount, source, description, "
            "created_by, created_at, is_test) "
            "VALUES ('in', :cat, :a, :src, 'Masa Satışı', :u, :t, FALSE)",
            {"cat": pm_cat, "a": str(final_d), "src": db_pm, "u": user, "t": now}
        ))

        if pm == "Kart":
            min_comm = Decimal(str(get_setting("bank_comm_min", "0.60")))
            pct_comm = Decimal(str(get_setting("bank_comm_pct", "0.02")))
            comm = max(min_comm, (final_d * pct_comm).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            actions.append((
                "INSERT INTO finance (type, category, amount, source, description, "
                "created_by, created_at, is_test) "
                "VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', "
                "'Masa Satış Komissiyası', :u, :t, FALSE)",
                {"a": str(comm), "u": user, "t": now}
            ))

    # ---- Reset table ----
    actions.append((
        "UPDATE tables SET is_occupied=FALSE, items='[]', total=0 WHERE id=:id",
        {"id": table_id}
    ))

    # ---- Execute ALL at once ----
    run_transaction(actions)
    log_system(user, f"TABLE_SALE: table_id={table_id}, total={final_d}, pm={pm}, test={is_test}")


# ============================================================
# MENU RENDERER FOR TABLES (DRY — shared with pos)
# ============================================================
def render_table_menu(cart):
    """Render menu grid for table ordering"""
    menu_df = get_cached_menu()
    if menu_df.empty:
        st.info("Menyu boşdur")
        return

    menu_df['cat_order'] = menu_df['category'].map(CAT_ORDER_MAP).fillna(99)
    menu_df = menu_df.sort_values(by=['cat_order', 'item_name'])

    existing_cats = sorted(
        menu_df['category'].unique().tolist(),
        key=lambda x: CAT_ORDER_MAP.get(x, 99)
    )
    cats = ["HAMISI"] + [c.upper() for c in existing_cats]
    sc_upper = st.radio(
        "Kat", cats, horizontal=True,
        label_visibility="collapsed", key="tbl_c_rad"
    )
    sc = "Hamısı" if sc_upper == "HAMISI" else next(
        (c for c in existing_cats if c.upper() == sc_upper), "Hamısı"
    )

    prods = menu_df if sc == "Hamısı" else menu_df[menu_df['category'] == sc]

    if not prods.empty:
        groups = {}
        for _, r in prods.iterrows():
            n = r['item_name']
            base = n
            for suffix in [" S", " M", " L", " XL", " Single", " Double"]:
                if n.endswith(suffix):
                    base = n[:-len(suffix)]
                    break
            if base not in groups:
                groups[base] = []
            groups[base].append(r)

        cols = st.columns(3)
        idx = 0
        for base, items in groups.items():
            with cols[idx % 3]:
                if len(items) > 1:
                    if st.button(f"{base}\n▾", key=f"tbl_grp_{base}",
                                 use_container_width=True, type="secondary"):
                        st.session_state.active_dialog = ("variants_tbl", items)
                        st.rerun()
                else:
                    r = items[0]
                    if st.button(f"{r['item_name']}\n{r['price']}₼",
                                 key=f"tbl_p_{r['id']}",
                                 use_container_width=True, type="secondary"):
                        add_to_cart(cart, {
                            'item_name': r['item_name'],
                            'price': float(r['price']),
                            'qty': 1,
                            'is_coffee': r['is_coffee'],
                            'category': r['category'],
                            'status': 'new'
                        })
                        st.rerun()
                idx += 1


# ============================================================
# SELECTED TABLE VIEW (Order + Pay)
# ============================================================
def render_selected_table(tbl):
    """Render the selected table's order management"""
    if st.button("⬅️ Qayıt", key="back_tbl_btn"):
        st.session_state.selected_table = None
        st.session_state.cart_table = []
        st.rerun()

    st.markdown(f"### {tbl['label']}")
    c_order, c_menu = st.columns([1.5, 3])

    with c_order:
        raw, final, _, _, _, _, _ = calculate_smart_total(
            st.session_state.cart_table, is_table=True
        )

        # ---- Cart display ----
        if not st.session_state.cart_table:
            st.info("Masa boşdur. Sağdan məhsul əlavə edin.")
        else:
            for i, it in enumerate(st.session_state.cart_table):
                c_name, c_qty, c_btns = st.columns([4, 1, 2], vertical_alignment="center")
                c_name.markdown(f"**{it['item_name']}**")
                c_qty.write(f"x{it['qty']}")
                with c_btns:
                    b_min, b_plus = st.columns(2)
                    if b_min.button("➖", key=f"tbl_dec_{i}"):
                        if it['qty'] > 1:
                            it['qty'] -= 1
                        else:
                            st.session_state.cart_table.pop(i)
                        st.rerun()
                    if b_plus.button("➕", key=f"tbl_inc_{i}"):
                        it['qty'] += 1
                        st.rerun()

        st.metric("Yekun", f"{final:.2f} ₼")

        # ---- Send to kitchen ----
        if st.button("🔥 Mətbəxə Göndər", key="kitchen_btn", type="secondary",
                      use_container_width=True):
            if not st.session_state.cart_table:
                st.error("Səbət boşdur!")
            else:
                run_action(
                    "UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id",
                    {
                        "i": json.dumps(st.session_state.cart_table),
                        "t": str(final),
                        "id": tbl['id']
                    }
                )
                log_system(st.session_state.user,
                           f"KITCHEN_SEND: table={tbl['label']}, items={len(st.session_state.cart_table)}")
                st.success("Mətbəxə göndərildi!")
                time.sleep(1)
                st.rerun()

        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

        # ---- Payment ----
        pm = st.radio(
            "Ödəniş Metodu", ["Nəğd", "Kart"],
            horizontal=True, label_visibility="collapsed", key="tbl_pm_radio"
        )

        if st.button("✅ Masanı Ödə və Bağla", key="pay_tbl_btn",
                      type="primary", use_container_width=True):
            if not st.session_state.cart_table or final <= 0:
                st.error("Masa boşdur!")
            else:
                is_test_mode = st.session_state.get('test_mode', False)
                try:
                    finalize_table_sale(
                        table_id=tbl['id'],
                        cart_items=st.session_state.cart_table,
                        final_total=final,
                        original_total=raw,
                        pm=pm,
                        user=st.session_state.user,
                        is_test=is_test_mode
                    )
                    st.session_state.selected_table = None
                    st.session_state.cart_table = []
                    st.success("Ödəniş qəbul edildi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")
                    logger.error(f"Table sale failed: {e}", exc_info=True)

    with c_menu:
        render_table_menu(st.session_state.cart_table)


# ============================================================
# TABLE MANAGEMENT (Admin)
# ============================================================
def render_table_management():
    """Admin/Manager: Create and delete tables"""
    with st.expander("🛠️ Masa İdarə"):
        # ---- Create ----
        nl = st.text_input("Yeni masa adı", key="new_table_name")
        if st.button("Yarat", key="create_table_btn"):
            if nl.strip():
                existing = run_query(
                    "SELECT 1 FROM tables WHERE label=:l", {"l": nl.strip()}
                )
                if not existing.empty:
                    st.error("Bu adda masa artıq mövcuddur!")
                else:
                    run_action(
                        "INSERT INTO tables (label) VALUES (:l)",
                        {"l": nl.strip()}
                    )
                    log_system(st.session_state.user, f"TABLE_CREATED: {nl.strip()}")
                    st.success(f"'{nl.strip()}' yaradıldı!")
                    st.rerun()
            else:
                st.error("Masa adı boş ola bilməz!")

        # ---- Delete ----
        db_tbls = run_query("SELECT label FROM tables ORDER BY id")
        if not db_tbls.empty:
            dl = st.selectbox("Silinəcək masa", db_tbls['label'].tolist(), key="del_table_sel")
            if st.button("Sil", key="delete_table_btn"):
                # Check if occupied
                occupied = run_query(
                    "SELECT is_occupied FROM tables WHERE label=:l", {"l": dl}
                )
                if not occupied.empty and occupied.iloc[0]['is_occupied']:
                    st.error("⚠️ Bu masa hazırda istifadədədir! Əvvəlcə bağlayın.")
                else:
                    # Capture dl value properly for lambda
                    label_to_delete = dl
                    admin_confirm_dialog(
                        f"'{label_to_delete}' masası silinsin?",
                        lambda lbl=label_to_delete: _delete_table(lbl)
                    )


def _delete_table(label):
    """Callback for table deletion (used by admin_confirm_dialog)"""
    run_action("DELETE FROM tables WHERE label=:l", {"l": label})
    log_system(st.session_state.user, f"TABLE_DELETED: {label}")


# ============================================================
# TABLE GRID VIEW
# ============================================================
def render_table_grid():
    """Display all tables as a grid"""
    df_t = run_query("SELECT * FROM tables ORDER BY id")
    if df_t.empty:
        st.info("Heç bir masa yaradılmayıb. Yuxarıdan əlavə edin.")
        return

    cols = st.columns(4)
    for i, r in df_t.iterrows():
        with cols[i % 4]:
            is_occupied = r['is_occupied']
            total_display = f"{r['total']:.2f} ₼" if is_occupied and r['total'] else "Boş"

            bg = "#8B0000" if is_occupied else "#006400"
            text_color = "#ffffff"

            st.markdown(
                f"<div style='background:{bg};color:{text_color};padding:8px;"
                f"border-radius:10px;text-align:center;margin-bottom:5px;"
                f"font-weight:bold;'>{r['label']}<br>{total_display}</div>",
                unsafe_allow_html=True
            )

            if st.button(
                f"{'📋 Aç' if is_occupied else '➕ Sifariş'}",
                key=f"tbl_{r['id']}",
                use_container_width=True,
                type="primary" if is_occupied else "secondary"
            ):
                st.session_state.selected_table = r.to_dict()
                st.session_state.cart_table = safe_json_loads(r['items'])
                st.rerun()


# ============================================================
# MAIN RENDER FUNCTION
# ============================================================
def render_tables_page():
    """Main entry point for tables module"""
    # Role guard
    if st.session_state.role not in ['admin', 'manager', 'staff']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    if st.session_state.selected_table:
        render_selected_table(st.session_state.selected_table)
    else:
        # Admin/Manager: Table management
        if st.session_state.role in ['admin', 'manager']:
            render_table_management()

        # Table grid
        render_table_grid()
