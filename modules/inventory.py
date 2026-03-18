# modules/inventory.py — PATCHED v2.0
import streamlit as st
import pandas as pd
import time
import logging
from decimal import Decimal, ROUND_HALF_UP

from database import run_query, run_action, run_transaction, get_setting
from utils import PRESET_CATEGORIES, get_baku_now, safe_decimal, log_system

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def render_inventory_page():
    st.subheader("📦 Anbar İdarəetməsi və AI Analiz")
    
    # ============================================================
    # AI ANALİZ (Orijinal)
    # ============================================================
    if st.session_state.role in ['admin', 'manager']:
        api_key = get_setting("gemini_api_key", "")
        with st.expander("🤖 Süni İntellektlə Anbar Analizi", expanded=False):
            if not api_key:
                st.warning("⚠️ AI funksiyası üçün 'AI Menecer' səhifəsində API Key daxil edin.")
            elif genai is None:
                st.warning("⚠️ google-generativeai paketi quraşdırılmayıb.")
            else:
                st.info("AI bütün anbar qalıqlarınızı yoxlayacaq və bitmək üzrə olan malları, ehtimal olunan təhlükələri bildirəcək.")
                if st.button("🧠 Anbarı İndi Analiz Et", type="primary"):
                    with st.spinner("🤖 AI anbarı sayır və analiz edir..."):
                        try:
                            genai.configure(api_key=api_key)
                            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0]) if valid_models else 'gemini-pro'
                            model = genai.GenerativeModel(chosen_model)
                            
                            inv_df = run_query("SELECT name, stock_qty, unit, category FROM ingredients")
                            if inv_df.empty:
                                st.warning("Anbarda məlumat yoxdur.")
                            else:
                                inv_str = "\n".join([f"- {r['name']}: {r['stock_qty']} {r['unit']} ({r['category']})" for _, r in inv_df.iterrows()])
                                prompt = f"""
                                Sən 'Füzuli' kofe şopunun Anbardarısan.
                                Aşağıdakı anbar qalıqlarına bax və mənə qısa hesabat ver:
                                1. Təcili alınmalı olanlar (Bitmək üzrə olanlar).
                                2. Anbar israfı barədə xəbərdarlıq.
                                
                                Anbar Siyahısı:
                                {inv_str}
                                """
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background: #1e2226; padding: 20px; border-left: 5px solid #ffd700; border-radius: 10px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);'>{response.text}</div>", unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Xəta: {e}")

    # ============================================================
    # MƏDAXİL / YENİ MAL (Orijinal + Decimal fix)
    # ============================================================
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("➕ Mədaxil / Yeni Mal"):
            with st.form("smart_add_item", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                mn_name = c1.text_input("Malın Adı")
                sel_cat = c2.selectbox("Kateqoriya", PRESET_CATEGORIES + ["➕ Yeni Yarat..."])
                mn_unit = c3.selectbox("Vahid", ["L", "KQ", "ƏDƏD"])
                
                mn_cat_final = st.text_input("Yeni Kateqoriya") if sel_cat == "➕ Yeni Yarat..." else sel_cat
                
                c4, c5, c6 = st.columns(3)
                pack_size = c4.number_input("Qab Həcmi", min_value=0.001, value=1.0, step=0.1)
                pack_price = c5.number_input("Qab Qiyməti", min_value=0.00, value=10.0, step=0.5)
                pack_count = c6.number_input("Say", min_value=1.0, value=1.0, step=1.0)
                
                mn_type = st.selectbox("Növ", ["ingredient", "consumable"])
                
                min_lim = st.number_input("Minimum Qalıq Limiti (Kritik Hədd)", value=10.0)
                
                if st.form_submit_button("Əlavə Et") and mn_name and pack_size > 0:
                    try:
                        # Decimal hesablama
                        total_qty = Decimal(str(pack_size)) * Decimal(str(pack_count))
                        unit_cost = (Decimal(str(pack_price)) / Decimal(str(pack_size))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                        
                        run_action(
                            "INSERT INTO ingredients (name, stock_qty, unit, category, type, unit_cost, min_limit) "
                            "VALUES (:n, :q, :u, :c, :t, :uc, :ml) "
                            "ON CONFLICT (name) DO UPDATE SET stock_qty = ingredients.stock_qty + :q, unit_cost = :uc, min_limit = :ml",
                            {
                                "n": mn_name.strip(),
                                "q": str(total_qty),
                                "u": mn_unit,
                                "c": mn_cat_final,
                                "t": mn_type,
                                "uc": str(unit_cost),
                                "ml": str(Decimal(str(min_lim)))
                            }
                        )
                        log_system(st.session_state.user, f"INVENTORY_ADD: {mn_name}, qty={total_qty}, cost={unit_cost}")
                        st.success("✅ OK")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Xəta: {e}")
                        logger.error(f"Inventory add failed: {e}", exc_info=True)

    # ============================================================
    # AXTARIŞ VƏ CƏDVƏL (Orijinal)
    # ============================================================
    c1, c2 = st.columns([3, 1])
    search_query = c1.text_input("🔍 Axtarış...")
    
    if search_query:
        df_i = run_query(
            "SELECT id, name, category, stock_qty, unit, min_limit, unit_cost FROM ingredients WHERE name ILIKE :s ORDER BY name",
            {"s": f"%{search_query}%"}
        )
    else:
        df_i = run_query("SELECT id, name, category, stock_qty, unit, min_limit, unit_cost FROM ingredients ORDER BY name")
    
    rows_per_page = st.selectbox("Səhifə", [20, 40, 60])
    total_rows = len(df_i)
    start_idx = st.session_state.anbar_page * rows_per_page
    end_idx = start_idx + rows_per_page
    df_page = df_i.iloc[start_idx:end_idx].copy()
    
    df_page['stock_qty'] = pd.to_numeric(df_page['stock_qty'], errors='coerce').fillna(0.0)
    df_page['unit_cost'] = pd.to_numeric(df_page['unit_cost'], errors='coerce').fillna(0.0)
    
    if 'min_limit' not in df_page.columns:
        df_page['min_limit'] = 10.0
    df_page['min_limit'] = pd.to_numeric(df_page['min_limit'], errors='coerce').fillna(10.0)
    
    df_page['Status'] = df_page.apply(
        lambda x: "🔴 KRİTİK" if x['stock_qty'] <= x['min_limit'] else "🟢 NORMAL",
        axis=1
    )

    df_page.insert(0, "Seç", False)
    
    edited_df = st.data_editor(
        df_page,
        hide_index=True,
        column_config={
            "Seç": st.column_config.CheckboxColumn(required=True),
            "unit_cost": st.column_config.NumberColumn("Alış Qiyməti", format="%.2f ₼"),
            "stock_qty": st.column_config.NumberColumn("Mövcud Qalıq"),
            "min_limit": st.column_config.NumberColumn("Kritik Hədd (Min)"),
            "Status": st.column_config.TextColumn("Status")
        },
        disabled=["id", "name", "category", "stock_qty", "unit", "min_limit", "unit_cost", "Status"],
        use_container_width=True,
        key="anbar_editor"
    )
    
    sel_rows = edited_df[edited_df["Seç"]]
    sel_ids = sel_rows['id'].tolist()
    
    # ============================================================
    # DÜYMƏLƏR (Orijinal)
    # ============================================================
    c1_btn, c2_btn, c3_btn, c4_btn = st.columns(4)
    if len(sel_ids) == 1:
        if c1_btn.button("➕ Mədaxil", key="anbar_restock_btn", use_container_width=True):
            st.session_state.restock_item_id = int(sel_ids[0])
            st.rerun()
        if c2_btn.button("➖ Məxaric (Zay)", key="anbar_loss_btn", use_container_width=True):
            st.session_state.loss_item_id = int(sel_ids[0])
            st.rerun()
        if c3_btn.button("✏️ Düzəliş", key="anbar_edit_btn", use_container_width=True):
            st.session_state.edit_item_id = int(sel_ids[0])
            st.rerun()

    if len(sel_ids) > 0 and c4_btn.button("🗑️ Sil", key="anbar_del_btn", use_container_width=True):
        for i in sel_ids:
            item_info = run_query("SELECT name FROM ingredients WHERE id=:id", {"id": int(i)})
            item_name = item_info.iloc[0]['name'] if not item_info.empty else f"ID:{i}"
            run_action("DELETE FROM ingredients WHERE id=:id", {"id": int(i)})
            log_system(st.session_state.user, f"INVENTORY_DELETE: {item_name}")
        st.success("Silindi!")
        time.sleep(1)
        st.rerun()

    # ============================================================
    # PAGİNASİYA (Orijinal)
    # ============================================================
    pc1, pc2, pc3 = st.columns([1, 2, 1])
    if pc1.button("⬅️", key="anbar_prev") and st.session_state.anbar_page > 0:
        st.session_state.anbar_page -= 1
        st.rerun()
    pc2.write(f"Səhifə {st.session_state.anbar_page + 1}")
    if pc3.button("➡️", key="anbar_next") and end_idx < total_rows:
        st.session_state.anbar_page += 1
        st.rerun()

    # ============================================================
    # MƏDAXİL MODAL (Orijinal + Decimal)
    # ============================================================
    if st.session_state.get('restock_item_id'):
        res = run_query("SELECT * FROM ingredients WHERE id=:id", {"id": st.session_state.restock_item_id})
        if not res.empty:
            r_item = res.iloc[0]

            @st.dialog("➕ Mədaxil")
            def show_restock(r):
                with st.form("rs"):
                    p = st.number_input("Say", min_value=1.0, value=1.0, step=1.0)
                    w = st.number_input(f"Çəki/Həcm ({r['unit']})", min_value=0.001, value=1.0, step=0.1)
                    pr = st.number_input("Yekun Qiymət", min_value=0.0, value=0.0, step=0.5)
                    if st.form_submit_button("Təsdiq"):
                        # Decimal hesablama
                        total_qty = Decimal(str(p)) * Decimal(str(w))
                        if total_qty > 0 and pr > 0:
                            new_unit_cost = (Decimal(str(pr)) / total_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                        else:
                            new_unit_cost = safe_decimal(r['unit_cost'])

                        run_action(
                            "UPDATE ingredients SET stock_qty=stock_qty+:q, unit_cost=:uc WHERE id=:id",
                            {"q": str(total_qty), "uc": str(new_unit_cost), "id": int(r['id'])}
                        )
                        log_system(st.session_state.user, f"INVENTORY_RESTOCK: {r['name']}, qty={total_qty}")
                        st.session_state.restock_item_id = None
                        st.rerun()

            show_restock(r_item)

    # ============================================================
    # MƏXARİC (ZAY/İTKİ) MODAL (Orijinal + Transaction + Audit)
    # ============================================================
    if st.session_state.get('loss_item_id'):
        res = run_query("SELECT * FROM ingredients WHERE id=:id", {"id": st.session_state.loss_item_id})
        if not res.empty:
            r_item = res.iloc[0]

            @st.dialog("➖ Məxaric (Zay / İtki)")
            def show_loss(r):
                current_qty = safe_decimal(r['stock_qty'])
                unit_cost = safe_decimal(r['unit_cost'])

                st.warning(f"Zay olan mal: **{r['name']}**\n\nMövcud Qalıq: **{current_qty} {r['unit']}**\n\nMaya Dəyəri: **{unit_cost:.4f} ₼**")

                with st.form("loss_form"):
                    q = st.number_input(f"Silinəcək Miqdar ({r['unit']})", min_value=0.001, max_value=float(current_qty), value=1.0, step=0.1)
                    reason = st.text_input("Səbəb (Açıqlama)", placeholder="Məsələn: Çürüyüb, yerə dağılıb və s.")

                    if st.form_submit_button("Təsdiqlə və Sil", type="primary"):
                        if not reason.strip():
                            st.error("Səbəb yazılmalıdır!")
                        else:
                            qty_d = Decimal(str(q))
                            loss_amt = (qty_d * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                            # Atomic transaction
                            actions = [
                                (
                                    "UPDATE ingredients SET stock_qty=stock_qty-:q WHERE id=:id",
                                    {"q": str(qty_d), "id": int(r['id'])}
                                )
                            ]

                            if loss_amt > 0:
                                actions.append((
                                    "INSERT INTO finance (type, category, amount, source, description, created_by, created_at, is_test) "
                                    "VALUES ('out', 'Anbar İtkisi', :a, 'Anbar', :d, :u, :t, FALSE)",
                                    {
                                        "a": str(loss_amt),
                                        "d": f"{r['name']} - {reason}",
                                        "u": st.session_state.user,
                                        "t": get_baku_now()
                                    }
                                ))

                            try:
                                run_transaction(actions)
                                log_system(st.session_state.user, f"INVENTORY_LOSS: {r['name']}, qty={qty_d}, loss={loss_amt}, reason={reason}")
                                st.session_state.loss_item_id = None
                                st.success(f"Məxaric edildi və {loss_amt:.2f} ₼ şirkət zərəri kimi loqlandı!")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Xəta: {e}")
                                logger.error(f"Inventory loss failed: {e}", exc_info=True)

            show_loss(r_item)

    # ============================================================
    # DÜZƏLİŞ MODAL (Orijinal)
    # ============================================================
    if st.session_state.get('edit_item_id'):
        res = run_query("SELECT * FROM ingredients WHERE id=:id", {"id": st.session_state.edit_item_id})
        if not res.empty:
            r_item = res.iloc[0]

            @st.dialog("✏️ Düzəliş")
            def show_edit(r):
                with st.form("ed"):
                    n = st.text_input("Ad", r['name'])

                    # Kateqoriya index
                    try:
                        cat_idx = PRESET_CATEGORIES.index(r['category']) if r['category'] in PRESET_CATEGORIES else 0
                    except:
                        cat_idx = 0
                    c = st.selectbox("Kat", PRESET_CATEGORIES, index=cat_idx)

                    # Vahid index
                    units = ["KQ", "L", "ƏDƏD"]
                    try:
                        unit_idx = units.index(r['unit']) if r['unit'] in units else 0
                    except:
                        unit_idx = 0
                    u = st.selectbox("Vahid", units, index=unit_idx)

                    uc = st.number_input("Qiymət (Alış)", value=float(safe_decimal(r['unit_cost'])))
                    m_lim = st.number_input("Minimum Limit", value=float(safe_decimal(r.get('min_limit', 10.0))))

                    if st.form_submit_button("Yadda Saxla"):
                        try:
                            run_action(
                                "UPDATE ingredients SET name=:n, category=:c, unit=:u, unit_cost=:uc, min_limit=:ml WHERE id=:id",
                                {
                                    "n": n.strip(),
                                    "c": c,
                                    "u": u,
                                    "uc": str(Decimal(str(uc))),
                                    "ml": str(Decimal(str(m_lim))),
                                    "id": int(r['id'])
                                }
                            )
                            log_system(st.session_state.user, f"INVENTORY_EDIT: {n}")
                            st.success("Yeniləndi!")
                            time.sleep(0.5)
                            st.session_state.edit_item_id = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Xəta: {e}")
                            logger.error(f"Inventory edit failed: {e}", exc_info=True)

            show_edit(r_item)
