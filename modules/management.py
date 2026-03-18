# modules/management.py — FINAL PATCHED v3.0
import streamlit as st
import pandas as pd
import time
import secrets
import random
import zipfile
import json
import re
import datetime
import logging
from decimal import Decimal
from io import BytesIO

from database import run_query, run_action, run_transaction, get_setting
from utils import generate_styled_qr, APP_URL, CAT_ORDER_MAP, PRESET_CATEGORIES, get_baku_now, safe_decimal, log_system
from auth import admin_confirm_dialog

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def call_ai(prompt):
    api_key = get_setting("gemini_api_key", "")
    if not api_key:
        return "⚠️ AI funksiyası üçün 'AI Menecer' səhifəsində API Key daxil edin."
    if genai is None:
        return "⚠️ google-generativeai paketi quraşdırılmayıb."
    try:
        genai.configure(api_key=api_key)
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0]) if valid_models else 'gemini-pro'
        model = genai.GenerativeModel(chosen_model)
        return model.generate_content(prompt).text
    except Exception as e:
        logger.error(f"AI call failed: {e}", exc_info=True)
        return f"Xəta: {e}"


def render_menu_page():
    st.subheader("📋 Menyu")
    try:
        existing_cats = run_query("SELECT DISTINCT category FROM menu")['category'].dropna().tolist()
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        existing_cats = []

    all_cats = sorted(list(set(PRESET_CATEGORIES + existing_cats)))

    if st.session_state.role in ['admin', 'manager']:
        with st.expander("➕ Tək Mal Əlavə Et (Menyu)"):
            with st.form("nmenu", clear_on_submit=True):
                mn = st.text_input("Ad")
                mp = st.number_input("Qiymət", min_value=0.0, step=0.1)
                mc_sel = st.selectbox("Kateqoriya", all_cats + ["➕ Yeni Yarat..."])
                mc = st.text_input("Yeni Kateqoriya Adı") if mc_sel == "➕ Yeni Yarat..." else mc_sel
                mic = st.checkbox("Kofe (Barista hazırlayır)")

                if st.form_submit_button("Yarat"):
                    if mn and mp >= 0 and mc:
                        try:
                            run_action(
                                "INSERT INTO menu (item_name, price, category, is_active, is_coffee) VALUES (:n, :p, :c, TRUE, :ic)",
                                {"n": mn.strip(), "p": str(Decimal(str(mp))), "c": mc.strip(), "ic": mic}
                            )
                            log_system(st.session_state.user, "MENU_ADD", {"item_name": mn, "price": mp, "category": mc, "is_coffee": mic})
                            st.success("Yarandı!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Xəta: {e}")
                    else:
                        st.error("Məlumatları tam doldurun.")

    mdf = run_query("SELECT * FROM menu WHERE is_active=TRUE")
    menu_search = st.text_input("🔍 Menyu Axtarış", placeholder="Məhsul adı...")
    if menu_search and not mdf.empty:
        mdf = mdf[mdf['item_name'].str.contains(menu_search, case=False, na=False)]

    if not mdf.empty:
        mdf.insert(0, "Seç", False)
        try:
            mdf['price'] = mdf['price'].astype(float)
        except:
            pass

        emd = st.data_editor(
            mdf,
            hide_index=True,
            column_config={"Seç": st.column_config.CheckboxColumn(required=True)},
            disabled=["id", "item_name", "price", "category", "is_coffee"],
            use_container_width=True,
            key="menu_ed_safe"
        )

        smd = emd[emd["Seç"]]
        sm_ids = smd['id'].tolist()

        c_m1, c_m2 = st.columns(2)
        if st.session_state.role in ['admin', 'manager']:
            if len(sm_ids) == 1 and c_m1.button("✏️ Düzəliş", key="med_btn"):
                st.session_state.menu_edit_id = int(sm_ids[0])
                st.rerun()
            if sm_ids and c_m2.button("🗑️ Sil", key="mdel_btn"):
                try:
                    for i in sm_ids:
                        item_info = run_query("SELECT item_name FROM menu WHERE id=:id", {"id": int(i)})
                        item_name = item_info.iloc[0]['item_name'] if not item_info.empty else f"ID:{i}"
                        run_action("DELETE FROM menu WHERE id=:id", {"id": int(i)})
                        log_system(st.session_state.user, "MENU_DELETE", {"item_name": item_name, "menu_id": int(i)})
                    st.success("Silindi!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

    if st.session_state.get('menu_edit_id'):
        res = run_query("SELECT * FROM menu WHERE id=:id", {"id": st.session_state.menu_edit_id})
        if not res.empty:
            mr = res.iloc[0]

            @st.dialog("✏️ Menyu Düzəliş")
            def ed_men_d(r):
                with st.form("me"):
                    nn = st.text_input("Ad", r['item_name'])
                    np = st.number_input("Qiymət", value=float(r['price']))
                    ec = st.text_input("Kateqoriya", r['category'])
                    eic = st.checkbox("Kofe?", value=r['is_coffee'])

                    if st.form_submit_button("Yadda Saxla"):
                        try:
                            run_action(
                                "UPDATE menu SET item_name=:n, price=:p, category=:c, is_coffee=:ic WHERE id=:id",
                                {"n": nn.strip(), "p": str(Decimal(str(np))), "c": ec.strip(), "ic": eic, "id": int(r['id'])}
                            )
                            log_system(st.session_state.user, "MENU_EDIT", {"menu_id": int(r['id']), "new_name": nn, "new_price": np, "new_category": ec, "new_is_coffee": eic})
                            st.session_state.menu_edit_id = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Xəta: {e}")
            ed_men_d(mr)

    if st.session_state.role == 'admin':
        with st.expander("📤 Menyu İmport / Export (Excel)"):
            with st.form("menu_imp_form"):
                upl_m = st.file_uploader("📥 Import Menu", type="xlsx")
                if st.form_submit_button("Yüklə (Menu)"):
                    if upl_m:
                        try:
                            df_m = pd.read_excel(upl_m)
                            df_m.columns = [str(c).lower().strip() for c in df_m.columns]
                            menu_map = {"ad": "item_name", "mal": "item_name", "qiymət": "price", "kateqoriya": "category", "kofe": "is_coffee"}
                            df_m.rename(columns=menu_map, inplace=True)

                            for _, r in df_m.iterrows():
                                if pd.isna(r.get('item_name')):
                                    continue
                                run_action(
                                    "INSERT INTO menu (item_name, price, category, is_active, is_coffee) VALUES (:n, :p, :c, TRUE, :ic)",
                                    {
                                        "n": str(r['item_name']),
                                        "p": str(Decimal(str(r['price']))),
                                        "c": str(r['category']),
                                        "ic": bool(r.get('is_coffee', False))
                                    }
                                )
                            log_system(st.session_state.user, "MENU_IMPORT")
                            st.success("Yükləndi!")
                        except Exception as e:
                            st.error(f"Xəta: {e}")

            if st.button("📤 Excel Endir"):
                out = BytesIO()
                run_query("SELECT item_name, price, category, is_coffee FROM menu").to_excel(out, index=False)
                st.download_button("⬇️ Endir (menu.xlsx)", out.getvalue(), "menu.xlsx")


def render_recipe_page():
    st.subheader("📜 Resept və AI Aşpaz")

    menu_items = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE")
    menu_list = menu_items['item_name'].tolist() if not menu_items.empty else []
    sel_p = st.selectbox("Məhsul Seçin", menu_list)

    if sel_p:
        sale_price = safe_decimal(menu_items[menu_items['item_name'] == sel_p].iloc[0]['price'])

        recs = run_query(
            "SELECT r.id, r.ingredient_name, CAST(r.quantity_required AS FLOAT) AS quantity_required, i.unit, i.unit_cost "
            "FROM recipes r LEFT JOIN ingredients i ON r.ingredient_name = i.name WHERE r.menu_item_name=:n",
            {"n": sel_p}
        )

        total_cost = Decimal("0")
        recs_for_ai = []
        if not recs.empty:
            for _, row in recs.iterrows():
                qty = Decimal(str(row['quantity_required']))
                unit_cost = safe_decimal(row['unit_cost'])
                cost = (qty * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_cost += cost
                recs_for_ai.append(f"- {row['ingredient_name']}: {row['quantity_required']} {row['unit']} (Maliyet: {cost:.2f} ₼)")

        st.markdown(f"**Satış Qiyməti:** {sale_price:.2f} ₼ | **Təxmini Maya Dəyəri:** {total_cost:.2f} ₼")

        c_ai1, c_ai2 = st.columns(2)

        with c_ai1:
            if st.button("🤖 Mövcud Resepti Analiz Et", type="secondary", use_container_width=True):
                with st.spinner("AI resepti incələyir..."):
                    prompt = f"Sən kofe shop baş baristasısan. Məhsul: {sel_p}\nSatış: {sale_price} AZN\nMaya: {total_cost} AZN\nTərkibi:\n{chr(10).join(recs_for_ai)}\nQısa rəy ver."
                    ai_reply = call_ai(prompt)
                    st.markdown(f"<div style='background:#1e2226;padding:20px;border-left:5px solid #ffd700;border-radius:10px;margin-top:10px;'>{ai_reply}</div>", unsafe_allow_html=True)

        with c_ai2:
            if st.button("🪄 AI ilə Avtomatik Resept Yarat", type="primary", use_container_width=True):
                with st.spinner("AI anbarı yoxlayır və resept yaradır..."):
                    ing_df = run_query("SELECT name, unit FROM ingredients")
                    if ing_df.empty:
                        st.error("⚠️ Anbarda heç bir xammal yoxdur.")
                    else:
                        inv_str = ", ".join([f"'{r['name']}' ({r['unit']})" for _, r in ing_df.iterrows()])
                        prompt = f"""
                        Sən peşəkar baş baristasan. Mən '{sel_p}' üçün standart resept istəyirəm.
                        Anbarımda olanlar: {inv_str}.
                        YALNIZ JSON qaytar:
                        [{{"ingredient": "Ad", "qty": 0.018}}]
                        """
                        ai_res = call_ai(prompt)
                        try:
                            json_str = re.search(r'\[.*\]', ai_res, re.DOTALL).group(0)
                            recipe_data = json.loads(json_str)
                            if recipe_data:
                                actions = [("DELETE FROM recipes WHERE menu_item_name=:m", {"m": sel_p})]
                                for item in recipe_data:
                                    actions.append((
                                        "INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)",
                                        {"m": sel_p, "i": item['ingredient'], "q": str(Decimal(str(item['qty'])))}
                                    ))
                                run_transaction(actions)
                                log_system(st.session_state.user, "RECIPE_AI_CREATED", {"menu_item_name": sel_p})
                                st.success("✅ Resept yaradıldı!")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ AI düzgün format vermədi: {e}")

        st.divider()

        if not recs.empty:
            recs_disp = recs[['id', 'ingredient_name', 'quantity_required', 'unit']].copy()
            recs_disp['quantity_required'] = recs_disp['quantity_required'].astype(float)
            recs_disp.insert(0, "Seç", False)

            erd = st.data_editor(
                recs_disp,
                hide_index=True,
                column_config={
                    "Seç": st.column_config.CheckboxColumn(required=True),
                    "quantity_required": st.column_config.NumberColumn("Miqdar", format="%.4f")
                },
                disabled=["id", "ingredient_name", "quantity_required", "unit"],
                key="rec_ed_safe",
                use_container_width=True
            )

            srd = erd[erd["Seç"]]['id'].tolist()

            col_r1, col_r2 = st.columns(2)
            if len(srd) == 1 and col_r1.button("✏️ Düzəliş", key="rec_ed_btn"):
                st.session_state.edit_recipe_id = int(srd[0])
                st.rerun()
            if srd and col_r2.button("🗑️ Sil", key="rec_del_btn"):
                try:
                    for i in srd:
                        run_action("DELETE FROM recipes WHERE id=:id", {"id": int(i)})
                        log_system(st.session_state.user, "RECIPE_DELETE", {"recipe_id": int(i)})
                    st.rerun()
                except Exception as e:
                    st.error(f"Xəta: {e}")

        with st.form("new_recipe_form", clear_on_submit=True):
            ing_df = run_query("SELECT name, unit FROM ingredients ORDER BY name")
            if not ing_df.empty:
                ing_map = {row['name']: row['unit'] for _, row in ing_df.iterrows()}
                ing = st.selectbox("Xammal", list(ing_map.keys()), key="new_rec_ing_select")
                unit_label = ing_map.get(ing, "")
                qty_str = st.text_input(f"Miqdar ({unit_label}) (Məs: 0.018 və ya 0,018)", key="new_rec_qty_input")

                if st.form_submit_button("Əlavə Et"):
                    if qty_str and qty_str.strip():
                        try:
                            clean_qty = Decimal(qty_str.replace(",", "."))
                            run_action(
                                "INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)",
                                {"m": sel_p, "i": ing, "q": str(clean_qty)}
                            )
                            log_system(st.session_state.user, "RECIPE_ADD", {"menu_item_name": sel_p, "ingredient_name": ing, "quantity": str(clean_qty)})
                            st.rerun()
                        except Exception as e:
                            st.error(f"Xəta: {e}")
                    else:
                        st.warning("Miqdarı yazın.")
            else:
                st.warning("Anbarda xammal yoxdur.")


def render_crm_page():
    st.subheader("👥 CRM və AI Marketoloq")
    crm_stats = run_query("SELECT type, COUNT(*) as cnt FROM customers GROUP BY type")
    stat_str = []

    if not crm_stats.empty:
        cols = st.columns(len(crm_stats))
        for idx, row in crm_stats.iterrows():
            lbl = row['type'].upper()
            icon = "🥇" if lbl == 'GOLDEN' else "🥈" if lbl == 'PLATINUM' else "💎" if lbl == 'ELITE' else "🎁" if lbl == 'IKRAM' else "🎓" if lbl == 'TELEBE' else "👤"
            with cols[idx % 4]:
                st.metric(f"{icon} {lbl}", row['cnt'])
            stat_str.append(f"{lbl}: {row['cnt']} nəfər")

    st.divider()

    with st.expander("🤖 AI Marketoloq (Kampaniya & Mesaj Strategiyası)", expanded=True):
        camp_goal = st.text_input("🎯 Kampaniya Məqsədi", placeholder="Məs: Tələbələri imtahan ərəfəsində cəlb etmək")
        if st.button("🚀 AI İdeya və Strategiya Yarat", type="primary", use_container_width=True):
            if camp_goal:
                with st.spinner("🤖 AI analiz edir..."):
                    prompt = f"Sən marketoloqsan. Müştəri bazası: {', '.join(stat_str)}. Məqsəd: '{camp_goal}'. 3 qısa mesaj və 1 kampaniya ideyası yaz."
                    ai_msg = call_ai(prompt)
                    st.markdown(f"<div style='background:#1e2226;padding:25px;border-left:6px solid #e6b800;border-radius:12px;box-shadow: inset 3px 3px 8px rgba(0,0,0,0.6);font-size:15px;line-height:1.6;'>{ai_msg}</div>", unsafe_allow_html=True)
            else:
                st.warning("Məqsədi daxil edin!")

    cust_df = run_query("SELECT card_id, type, stars, email FROM customers")
    if not cust_df.empty:
        cust_df.insert(0, "Seç", False)
        ed_cust = st.data_editor(
            cust_df,
            hide_index=True,
            column_config={"Seç": st.column_config.CheckboxColumn(required=True)},
            key="crm_sel"
        )
        sel_cust_ids = ed_cust[ed_cust["Seç"]]['card_id'].tolist()

        st.divider()
        msg = st.text_area("Ekran Mesajı (Müştərinin QR ekranına gedəcək)")
        promo_df = run_query("SELECT code FROM promo_codes") if 'promo_codes' in [t for t in []] else pd.DataFrame()
        promo_list = ["(Kuponsuz)"] + promo_df['code'].tolist() if not promo_df.empty else ["(Kuponsuz)"]
        sel_promo = st.selectbox("Promo Yapışdır (Seçilənlərə)", promo_list)

        if st.button("📢 Seçilənlərə Göndər / Tətbiq Et", key="crm_send_btn", type="primary"):
            if sel_cust_ids:
                try:
                    for cid in sel_cust_ids:
                        if msg:
                            run_action("INSERT INTO notifications (card_id, message) VALUES (:c, :m)", {"c": cid, "m": msg})
                    log_system(st.session_state.user, "CRM_SEND", {"customer_count": len(sel_cust_ids), "promo": sel_promo, "message": msg[:100] if msg else ""})
                    st.success(f"{len(sel_cust_ids)} nəfərə tətbiq edildi!")
                except Exception as e:
                    st.error(f"Xəta: {e}")
            else:
                st.error("Ən azı 1 müştəri seçin!")


def render_qr_page():
    st.subheader("QR Generator")
    c1, c2 = st.columns(2)
    cnt = c1.number_input("Say", 1, 50, key="qr_cnt")
    tp = c2.selectbox("Tip", ["Golden (5%)", "Platinum (10%)", "Elite (20%)", "Thermos (20%)", "Ikram (100%)", "Tələbə (15%)"], key="qr_type")
    use_inventory = st.checkbox("📦 Fiziki Kartı Anbardan Sil", key="qr_inv")
    selected_card_stock = None

    if use_inventory:
        inv_items = run_query("SELECT id, name, stock_qty FROM ingredients WHERE category ILIKE '%Kart%' OR category ILIKE '%Mətbəə%' ORDER BY name")
        if not inv_items.empty:
            item_map = {f"{row['name']} (Qalıq: {int(row['stock_qty'])})": row['id'] for _, row in inv_items.iterrows()}
            sel_label = st.selectbox("Hansı Kart?", list(item_map.keys()), key="qr_stock_sel")
            selected_card_stock = item_map[sel_label]
        else:
            st.warning("⚠️ Anbarda 'Kart' kateqoriyalı mal tapılmadı.")

    if st.button("QR Kodları Yarat 🚀", type="primary"):
        can_proceed = True
        if use_inventory and selected_card_stock:
            curr_qty = safe_decimal(run_query("SELECT stock_qty FROM ingredients WHERE id=:id", {"id": selected_card_stock}).iloc[0]['stock_qty'])
            if curr_qty < Decimal(str(cnt)):
                st.error(f"⛔ Stok yetmir! Qalıq: {int(curr_qty)}, Lazım: {cnt}")
                can_proceed = False

        if can_proceed:
            try:
                type_map = {
                    "Golden (5%)": "golden",
                    "Platinum (10%)": "platinum",
                    "Elite (20%)": "elite",
                    "Thermos (20%)": "thermos",
                    "Ikram (100%)": "ikram",
                    "Tələbə (15%)": "telebe"
                }

                generated_qrs = []
                for _ in range(cnt):
                    cid = str(random.randint(10000000, 99999999))
                    tok = secrets.token_hex(8)
                    run_action(
                        "INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :s)",
                        {"i": cid, "t": type_map[tp], "s": tok}
                    )
                    url = f"{APP_URL}/?id={cid}&t={tok}"
                    img_bytes = generate_styled_qr(url)
                    generated_qrs.append((cid, img_bytes))

                if use_inventory and selected_card_stock:
                    run_action(
                        "UPDATE ingredients SET stock_qty = stock_qty - :q WHERE id=:id",
                        {"q": str(Decimal(str(cnt))), "id": selected_card_stock}
                    )

                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w") as zf:
                    for cid, img in generated_qrs:
                        zf.writestr(f"{cid}_{type_map[tp]}.png", img)

                log_system(st.session_state.user, "QR_GENERATED", {"count": cnt, "type": tp})
                st.success(f"{cnt} QR Kod yaradıldı!")
                st.download_button("📦 Hamsını Endir (ZIP)", zip_buf.getvalue(), "qrcodes.zip", "application/zip")
            except Exception as e:
                st.error(f"Xəta: {e}")
