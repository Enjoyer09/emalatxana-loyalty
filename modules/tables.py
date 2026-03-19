# modules/tables.py — FIX PACKAGE B FINAL
import streamlit as st
import json
import time
import logging
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import text

from database import run_query, run_action, run_transaction, get_setting, conn
from utils import get_baku_now, CAT_ORDER_MAP, safe_decimal, log_system
from modules.pos import add_to_cart, calculate_smart_total, get_cached_menu
from auth import admin_confirm_dialog

logger = logging.getLogger(__name__)


def safe_json_loads(data, default=None):
    if default is None:
        default = []
    if not data or data == '[]':
        return default
    try:
        return json.loads(data)
    except Exception as e:
        logger.warning(f"JSON parse error: {e}")
        return default


def finalize_table_sale(table_id, table_label, cart_items, final_total, original_total, pm, user, is_test, split_cash=None, split_card=None):
    now = get_baku_now()
    final_d = Decimal(str(final_total))
    original_d = Decimal(str(original_total))
    discount_d = original_d - final_d
    items_json = json.dumps(cart_items)
    total_cogs = Decimal("0")

    with conn.session as s:
        try:
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
                            u_cost = safe_decimal(r['unit_cost'])
                            total_cogs += qty_req * u_cost
                            s.execute(
                                text("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE name=:n"),
                                {"q": str(qty_req), "n": r['ingredient_name']}
                            )

            sale_result = s.execute(
                text("""
                    INSERT INTO sales (items, total, payment_method, cashier, created_at, original_total, discount_amount, is_test, cogs, status)
                    VALUES (:i,:t,:p,:c,:time,:ot,:da,:tst,:cogs,'COMPLETED')
                    RETURNING id
                """),
                {
                    "i": items_json,
                    "t": str(final_d),
                    "p": pm,
                    "c": user,
                    "time": now,
                    "ot": str(original_d),
                    "da": str(discount_d),
                    "tst": is_test,
                    "cogs": str(total_cogs)
                }
            )
            sale_id = sale_result.fetchone()[0]

            # Kitchen order (masa satışı zamanı)
            s.execute(
                text("""
                    INSERT INTO kitchen_orders (sale_source, table_label, items, status, created_by, created_at)
                    VALUES ('TABLE', :tbl, :items, 'NEW', :user, :time)
                """),
                {"tbl": table_label, "items": items_json, "user": user, "time": now}
            )

            # Finance
            if not is_test and final_d > 0:
                if split_cash is not None and split_card is not None:
                    if split_cash > 0:
                        s.execute(
                            text("""
                                INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id)
                                VALUES ('in', 'Satış (Nağd)', :a, 'Kassa', 'Masa Satışı (Split)', :u, :t, FALSE, :sid)
                            """),
                            {"a": str(split_cash), "u": user, "t": now, "sid": sale_id}
                        )
                    if split_card > 0:
                        s.execute(
                            text("""
                                INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id)
                                VALUES ('in', 'Satış (Kart)', :a, 'Bank Kartı', 'Masa Satışı (Split)', :u, :t, FALSE, :sid)
                            """),
                            {"a": str(split_card), "u": user, "t": now, "sid": sale_id}
                        )
                        min_comm = Decimal(str(get_setting("bank_comm_min", "0.60")))
                        pct_comm = Decimal(str(get_setting("bank_comm_pct", "0.02")))
                        comm = max(min_comm, (split_card * pct_comm).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                        s.execute(
                            text("""
                                INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id)
                                VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Masa Satış Komissiyası (Split)', :u, :t, FALSE, :sid)
                            """),
                            {"a": str(comm), "u": user, "t": now, "sid": sale_id}
                        )
                else:
                    db_pm = "Kassa" if pm == "Nəğd" else "Bank Kartı"
                    pm_cat = "Satış (Nağd)" if pm == "Nəğd" else "Satış (Kart)"

                    s.execute(
                        text("""
                            INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id)
                            VALUES ('in', :cat, :a, :src, 'Masa Satışı', :u, :t, FALSE, :sid)
                        """),
                        {"cat": pm_cat, "a": str(final_d), "src": db_pm, "u": user, "t": now, "sid": sale_id}
                    )

                    if pm == "Kart":
                        min_comm = Decimal(str(get_setting("bank_comm_min", "0.60")))
                        pct_comm = Decimal(str(get_setting("bank_comm_pct", "0.02")))
                        comm = max(min_comm, (final_d * pct_comm).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                        s.execute(
                            text("""
                                INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test, sale_id)
                                VALUES ('out', 'Bank Komissiyası', :a, 'Bank Kartı', 'Masa Satış Komissiyası', :u, :t, FALSE, :sid)
                            """),
                            {"a": str(comm), "u": user, "t": now, "sid": sale_id}
                        )

            # Masa sıfırlanır
            s.execute(
                text("UPDATE tables SET is_occupied=FALSE, items='[]', total=0 WHERE id=:id"),
                {"id": table_id}
            )

            s.commit()

            log_system(
                user,
                "TABLE_SALE_CREATED",
                {
                    "sale_id": sale_id,
                    "table_id": table_id,
                    "table_label": table_label,
                    "total": str(final_d),
                    "payment_method": pm,
                    "split_cash": str(split_cash) if split_cash is not None else None,
                    "split_card": str(split_card) if split_card is not None else None,
                    "items_count": len(cart_items),
                    "cogs": str(total_cogs)
                }
            )

        except Exception as e:
            s.rollback()
            logger.error(f"Table sale failed: {e}", exc_info=True)
            raise e


def render_table_menu(cart):
    menu_df = get_cached_menu()
    if menu_df.empty:
        st.info("Menyu boşdur")
        return

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
            for suffix in [" S", " M", " L", " XL", " Single", " Double"]:
                if n.endswith(suffix):
                    base = n[:-len(suffix)]
                    break
            if base not in groups:
                groups[base] = []
            groups[base].append(r)

        group_items = list(groups.items())
        for row_start in range(0, len(group_items), 3):
            cols = st.columns(3)
            row_slice = group_items[row_start:row_start+3]
            for col_idx, (base, items) in enumerate(row_slice):
                with cols[col_idx]:
                    if len(items) > 1:
                        if st.button(f"{base}\n▾", key=f"tbl_grp_{base}_{row_start}_{col_idx}", use_container_width=True, type="secondary"):
                            chosen = items[0]
                            add_to_cart(cart, {
                                'item_name': chosen['item_name'],
                                'price': float(chosen['price']),
                                'qty': 1,
                                'is_coffee': chosen['is_coffee'],
                                'category': chosen['category'],
                                'status': 'new'
                            })
                            st.rerun()
                    else:
                        r = items[0]
                        if st.button(f"{r['item_name']}\n{r['price']}₼", key=f"tbl_p_{r['id']}_{row_start}_{col_idx}", use_container_width=True, type="secondary"):
                            add_to_cart(cart, {
                                'item_name': r['item_name'],
                                'price': float(r['price']),
                                'qty': 1,
                                'is_coffee': r['is_coffee'],
                                'category': r['category'],
                                'status': 'new'
                            })
                            st.rerun()


def render_selected_table(tbl):
    if st.button("⬅️ Qayıt", key="back_tbl_btn"):
        st.session_state.selected_table = None
        st.session_state.cart_table = []
        st.rerun()

    st.markdown(f"### {tbl['label']}")
    c_order, c_menu = st.columns([1.5, 3])

    with c_order:
        raw, final, _, _, _, _, _ = calculate_smart_total(st.session_state.cart_table, is_table=True)

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

        # FIX: Masadan mətbəxə dərhal getsin
        if st.button("🔥 Mətbəxə Göndər", key="kitchen_btn", type="secondary", use_container_width=True):
            if not st.session_state.cart_table:
                st.error("Səbət boşdur!")
            else:
                now = get_baku_now()
                items_json = json.dumps(st.session_state.cart_table)

                actions = [
                    (
                        "UPDATE tables SET is_occupied=TRUE, items=:i, total=:t WHERE id=:id",
                        {"i": items_json, "t": str(final), "id": tbl['id']}
                    ),
                    (
                        "INSERT INTO kitchen_orders (sale_source, table_label, items, status, created_by, created_at) "
                        "VALUES ('TABLE', :tbl, :items, 'NEW', :user, :time)",
                        {"tbl": tbl['label'], "items": items_json, "user": st.session_state.user, "time": now}
                    )
                ]

                try:
                    run_transaction(actions)
                    log_system(
                        st.session_state.user,
                        "TABLE_SENT_TO_KITCHEN",
                        {
                            "table_id": tbl['id'],
                            "table_label": tbl['label'],
                            "items_count": len(st.session_state.cart_table)
                        }
                    )
                    st.success("Mətbəxə göndərildi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

        pm = st.radio("Ödəniş Metodu", ["Nəğd", "Kart", "Bölünmüş ✂️"], horizontal=True, label_visibility="collapsed", key="tbl_pm_radio")

        split_cash = Decimal("0")
        split_card = Decimal("0")
        is_split_valid = True

        if pm == "Bölünmüş ✂️":
            col_s1, col_s2 = st.columns(2)
            split_cash_input = col_s1.number_input("Nağd (₼)", min_value=0.0, max_value=float(final), value=0.0, step=1.0, key="tbl_split_cash")
            split_cash = Decimal(str(split_cash_input))
            split_card = final - split_cash
            col_s2.metric("Kart (₼)", f"{split_card:.2f}")
            if split_cash < 0 or split_card < 0:
                st.error("Məbləğ fərqi var!")
                is_split_valid = False

        if st.button("✅ Masanı Ödə və Bağla", key="pay_tbl_btn", type="primary", use_container_width=True):
            if not st.session_state.cart_table or final <= 0:
                st.error("Masa boşdur!")
            elif pm == "Bölünmüş ✂️" and not is_split_valid:
                st.error("Bölünmüş məbləğləri düzəldin!")
            else:
                is_test_mode = st.session_state.get('test_mode', False)
                try:
                    db_pm = pm
                    if pm == "Bölünmüş ✂️":
                        db_pm = f"Split (Cash:{split_cash:.2f}, Card:{split_card:.2f})"

                    finalize_table_sale(
                        table_id=tbl['id'],
                        table_label=tbl['label'],
                        cart_items=st.session_state.cart_table,
                        final_total=final,
                        original_total=raw,
                        pm=db_pm,
                        user=st.session_state.user,
                        is_test=is_test_mode,
                        split_cash=split_cash if pm == "Bölünmüş ✂️" else None,
                        split_card=split_card if pm == "Bölünmüş ✂️" else None
                    )
                    st.session_state.selected_table = None
                    st.session_state.cart_table = []
                    st.success("Ödəniş qəbul edildi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

    with c_menu:
        render_table_menu(st.session_state.cart_table)


def render_table_management():
    with st.expander("🛠️ Masa İdarə"):
        nl = st.text_input("Yeni masa adı", key="new_table_name")
        if st.button("Yarat", key="create_table_btn"):
            if nl.strip():
                existing = run_query("SELECT 1 FROM tables WHERE label=:l", {"l": nl.strip()})
                if not existing.empty:
                    st.error("Bu adda masa artıq mövcuddur!")
                else:
                    run_action("INSERT INTO tables (label) VALUES (:l)", {"l": nl.strip()})
                    log_system(st.session_state.user, "TABLE_CREATED", {"label": nl.strip()})
                    st.success(f"'{nl.strip()}' yaradıldı!")
                    st.rerun()
            else:
                st.error("Masa adı boş ola bilməz!")

        db_tbls = run_query("SELECT label FROM tables ORDER BY id")
        if not db_tbls.empty:
            dl = st.selectbox("Silinəcək masa", db_tbls['label'].tolist(), key="del_table_sel")
            if st.button("Sil", key="delete_table_btn"):
                occupied = run_query("SELECT is_occupied FROM tables WHERE label=:l", {"l": dl})
                if not occupied.empty and occupied.iloc[0]['is_occupied']:
                    st.error("⚠️ Bu masa hazırda istifadədədir!")
                else:
                    label_to_delete = dl
                    admin_confirm_dialog(
                        f"'{label_to_delete}' masası silinsin?",
                        lambda lbl=label_to_delete: _delete_table(lbl)
                    )


def _delete_table(label):
    run_action("DELETE FROM tables WHERE label=:l", {"l": label})
    log_system(st.session_state.user, "TABLE_DELETED", {"label": label})


def render_table_grid():
    df_t = run_query("SELECT * FROM tables ORDER BY id")
    if df_t.empty:
        st.info("Heç bir masa yaradılmayıb.")
        return

    cols = st.columns(4)
    for i, r in df_t.iterrows():
        with cols[i % 4]:
            is_occupied = r['is_occupied']
            try:
                total_display = f"{float(r['total']):.2f} ₼" if is_occupied and r['total'] else "Boş"
            except:
                total_display = "Boş"

            bg = "#8B0000" if is_occupied else "#006400"
            text_color = "#ffffff"

            st.markdown(
                f"<div style='background:{bg};color:{text_color};padding:8px;border-radius:10px;text-align:center;margin-bottom:5px;font-weight:bold;'>{r['label']}<br>{total_display}</div>",
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


def render_tables_page():
    if st.session_state.role not in ['admin', 'manager', 'staff']:
        st.error("Bu səhifəyə icazəniz yoxdur!")
        return

    if st.session_state.selected_table:
        render_selected_table(st.session_state.selected_table)
    else:
        if st.session_state.role in ['admin', 'manager']:
            render_table_management()
        render_table_grid()
