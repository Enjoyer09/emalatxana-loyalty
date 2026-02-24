import streamlit as st
import pandas as pd
import time
import secrets
import random
import zipfile
import json
import re
import google.generativeai as genai
from io import BytesIO
from database import run_query, run_action, get_setting
from utils import generate_styled_qr, APP_URL, CAT_ORDER_MAP, PRESET_CATEGORIES, get_baku_now
from auth import admin_confirm_dialog

def call_ai(prompt):
    api_key = get_setting("gemini_api_key", "")
    if not api_key: return "⚠️ AI funksiyası üçün 'AI Menecer' səhifəsində API Key daxil edin."
    try:
        genai.configure(api_key=api_key)
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0]) if valid_models else 'gemini-pro'
        model = genai.GenerativeModel(chosen_model)
        return model.generate_content(prompt).text
    except Exception as e:
        return f"Xəta: {e}"

def render_menu_page():
    st.subheader("📋 Menyu")
    try: existing_cats = run_query("SELECT DISTINCT category FROM menu")['category'].tolist()
    except: existing_cats = []
    all_cats = sorted(list(set(PRESET_CATEGORIES + existing_cats)))
    
    if st.session_state.role in ['admin','manager']:
         with st.expander("➕ Tək Mal Əlavə Et (Menyu)"):
              with st.form("nmenu", clear_on_submit=True):
                   mn = st.text_input("Ad")
                   mp = st.number_input("Qiymət", min_value=0.0, step=0.1)
                   mc_sel = st.selectbox("Kateqoriya", all_cats + ["➕ Yeni Yarat..."])
                   mc = st.text_input("Yeni Kateqoriya Adı") if mc_sel == "➕ Yeni Yarat..." else mc_sel
                   mic = st.checkbox("Kofe (Barista hazırlayır)")
                   if st.form_submit_button("Yarat"): 
                        if mn and mp >= 0 and mc:
                            run_action("INSERT INTO menu (item_name,price,category,is_active,is_coffee) VALUES (:n,:p,:c,TRUE,:ic)", {"n":mn,"p":mp,"c":mc,"ic":mic}); st.success("Yarandı!"); time.sleep(0.5); st.rerun()
                        else: st.error("Məlumatları tam doldurun.")
                            
    mdf = run_query("SELECT * FROM menu WHERE is_active=TRUE")
    menu_search = st.text_input("🔍 Menyu Axtarış", placeholder="Məhsul adı...")
    if menu_search: mdf = mdf[mdf['item_name'].str.contains(menu_search, case=False, na=False)]
    mdf.insert(0, "Seç", False); mdf['price'] = mdf['price'].astype(float)
    
    emd = st.data_editor(mdf, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, disabled=["id", "item_name", "price", "category", "is_coffee"], use_container_width=True, key="menu_ed_safe")
    smd = emd[emd["Seç"]]; sm_ids = smd['id'].tolist()
    
    c_m1, c_m2 = st.columns(2)
    if st.session_state.role in ['admin', 'manager']:
        if len(sm_ids) == 1 and c_m1.button("✏️ Düzəliş", key="med_btn"): st.session_state.menu_edit_id = int(sm_ids[0]); st.rerun()
        if sm_ids and c_m2.button("🗑️ Sil", key="mdel_btn"): 
            try: 
                for i in sm_ids: run_action("DELETE FROM menu WHERE id=:id", {"id":int(i)})
                st.success("Silindi!"); time.sleep(0.5); st.rerun()
            except Exception as e: st.error(f"Xəta: {e}")
                
    if st.session_state.get('menu_edit_id'):
        res = run_query("SELECT * FROM menu WHERE id=:id", {"id":st.session_state.menu_edit_id})
        if not res.empty:
            mr = res.iloc[0]
            @st.dialog("✏️ Menyu Düzəliş")
            def ed_men_d(r):
                with st.form("me"):
                    nn = st.text_input("Ad", r['item_name']); np = st.number_input("Qiymət", value=float(r['price'])); ec = st.text_input("Kateqoriya", r['category']); eic = st.checkbox("Kofe?", value=r['is_coffee'])
                    if st.form_submit_button("Yadda Saxla"): 
                        run_action("UPDATE menu SET item_name=:n, price=:p, category=:c, is_coffee=:ic WHERE id=:id", {"n":nn,"p":np,"c":ec,"ic":eic,"id":int(r['id'])}); st.session_state.menu_edit_id=None; st.rerun()
            ed_men_d(mr)
            
    if st.session_state.role == 'admin':
        with st.expander("📤 Menyu İmport / Export (Excel)"):
            with st.form("menu_imp_form"):
                upl_m = st.file_uploader("📥 Import Menu", type="xlsx")
                if st.form_submit_button("Yüklə (Menu)"):
                     if upl_m:
                          try:
                              df_m = pd.read_excel(upl_m); df_m.columns = [str(c).lower().strip() for c in df_m.columns]; menu_map = {"ad": "item_name", "mal": "item_name", "qiymət": "price", "kateqoriya": "category", "kofe": "is_coffee"}; df_m.rename(columns=menu_map, inplace=True)
                              for _, r in df_m.iterrows():
                                  if pd.isna(r['item_name']): continue
                                  run_action("INSERT INTO menu (item_name, price, category, is_active, is_coffee) VALUES (:n, :p, :c, TRUE, :ic)", {"n":str(r['item_name']), "p":float(r['price']), "c":str(r['category']), "ic":bool(r.get('is_coffee', False))})
                              st.success("Yükləndi!")
                          except: st.error("Xəta")
            if st.button("📤 Excel Endir"): out = BytesIO(); run_query("SELECT item_name, price, category, is_coffee FROM menu").to_excel(out, index=False); st.download_button("⬇️ Endir (menu.xlsx)", out.getvalue(), "menu.xlsx")

def render_recipe_page():
    st.subheader("📜 Resept və AI Aşpaz")
    
    # ------------------ BAZA CƏRRAHİYYƏSİ (ULTIMATE FIX) ------------------
    if st.session_state.role in ['admin', 'manager']:
        with st.expander("🛠️ Sistem Təmiri (Qramajlar '0' olursa bura daxil olun)", expanded=False):
            st.warning("Bu əməliyyat bazadakı 'quantity_required' sütununu kökündən silib, kəsr ədəd (FLOAT) kimi yenidən yaradacaq. Bir dəfə etmək kifayətdir.")
            if st.button("🔧 Qramaj Xətasını Birdəfəlik Həll Et", type="primary"):
                with st.spinner("Əməliyyat gedir, lütfən gözləyin..."):
                    # 1. POSTGRESQL CƏHDi
                    try:
                        run_action("ALTER TABLE recipes ALTER COLUMN quantity_required TYPE NUMERIC(15,4) USING quantity_required::numeric")
                        st.success("✅ PostgreSQL bazası uğurla yeniləndi! Artıq 0.018 yazılacaq.")
                    except Exception as pg_err:
                        # 2. SQLITE CƏHDİ (Drop/Create metodu)
                        try:
                            # Təhlükəsizlik üçün cədvəli addım-addım yenidən qururuq
                            run_action("CREATE TABLE IF NOT EXISTS recipes_new (id INTEGER PRIMARY KEY AUTOINCREMENT, menu_item_name TEXT, ingredient_name TEXT, quantity_required REAL)")
                            run_action("INSERT INTO recipes_new (id, menu_item_name, ingredient_name, quantity_required) SELECT id, menu_item_name, ingredient_name, CAST(quantity_required AS REAL) FROM recipes")
                            run_action("DROP TABLE recipes")
                            run_action("ALTER TABLE recipes_new RENAME TO recipes")
                            st.success("✅ SQLite bazası uğurla yeniləndi! Cədvəl dəyişdirildi. Artıq itki olmayacaq.")
                        except Exception as sq_err:
                            st.error(f"XƏTA BİLDİRİŞİ:\nPostgres: {pg_err}\nSQLite: {sq_err}")
    # ----------------------------------------------------------------------

    menu_items = run_query("SELECT item_name, price FROM menu WHERE is_active=TRUE")
    menu_list = menu_items['item_name'].tolist() if not menu_items.empty else []
    sel_p = st.selectbox("Məhsul Seçin", menu_list)
    
    if sel_p:
        sale_price = float(menu_items[menu_items['item_name'] == sel_p].iloc[0]['price'])
        
        recs = run_query("SELECT r.id, r.ingredient_name, CAST(r.quantity_required AS FLOAT) AS quantity_required, i.unit, i.unit_cost FROM recipes r LEFT JOIN ingredients i ON r.ingredient_name = i.name WHERE r.menu_item_name=:n", {"n":sel_p})
        
        total_cost = 0.0
        recs_for_ai = []
        if not recs.empty:
            for _, row in recs.iterrows():
                cost = float(row['quantity_required']) * float(row['unit_cost'] if pd.notna(row['unit_cost']) else 0)
                total_cost += cost
                recs_for_ai.append(f"- {row['ingredient_name']}: {row['quantity_required']} {row['unit']} (Maliyet: {cost:.2f} ₼)")
        
        st.markdown(f"**Satış Qiyməti:** {sale_price:.2f} ₼ | **Təxmini Maya Dəyəri:** {total_cost:.2f} ₼")
        
        c_ai1, c_ai2 = st.columns(2)
        
        with c_ai1:
            if st.button("🤖 Mövcud Resepti Analiz Et", type="secondary", use_container_width=True):
                with st.spinner("AI resepti incələyir..."):
                    prompt = f"Sən 'Füzuli' kofe şopunun Baş Aşpazı və Maliyyəçisisən. Məhsul: {sel_p}\nSatış: {sale_price} AZN\nMaya: {total_cost} AZN\nTərkibi:\n{chr(10).join(recs_for_ai)}\n1. Qazanc Marjası necədir?\n2. Qramajlar standartlara uyğundurmu?\n3. Premium etmək üçün gizli toxunuş təklif et."
                    ai_reply = call_ai(prompt)
                    st.markdown(f"<div style='background: #1e2226; padding:20px; border-left:5px solid #ffd700; border-radius:10px; margin-top:10px;'>{ai_reply}</div>", unsafe_allow_html=True)
        
        with c_ai2:
            if st.button("🪄 AI ilə Avtomatik Resept Yarat", type="primary", use_container_width=True):
                with st.spinner("AI anbarı yoxlayır və resept yaradır..."):
                    ing_df = run_query("SELECT name, unit FROM ingredients")
                    if ing_df.empty:
                        st.error("⚠️ Anbarda heç bir xammal yoxdur. Əvvəlcə anbara mal əlavə edin.")
                    else:
                        inv_str = ", ".join([f"'{r['name']}' ({r['unit']})" for _, r in ing_df.iterrows()])
                        prompt = f"""
                        Sən peşəkar baş baristasan. Mən '{sel_p}' adlı məhsul üçün beynəlxalq standartlara uyğun resept yaratmaq istəyirəm.
                        Mənim anbarımda YALNIZ bu xammallar var: {inv_str}.
                        ŞƏRTLƏR:
                        1. Anbarımda olan xammal adlarından TAM eyni şəkildə istifadə et.
                        2. Qramajları vahidə uyğun rəqəmlə yaz (məsələn: 18 qram kofe üçün 0.018, 150 ml süd üçün 0.150, 1 ədəd stəkan üçün 1).
                        3. Yalnız lazım olan əsas maddələri (kofe, süd, stəkan, qapaq və s.) seç.
                        CAVAB FORMATI (Yalnız JSON qaytar):
                        [ {{"ingredient": "Ad", "qty": 0.018}} ]
                        """
                        ai_res = call_ai(prompt)
                        try:
                            json_str = re.search(r'\[.*\]', ai_res, re.DOTALL).group(0)
                            recipe_data = json.loads(json_str)
                            if recipe_data:
                                run_action("DELETE FROM recipes WHERE menu_item_name=:m", {"m": sel_p})
                                for item in recipe_data:
                                    run_action("INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)", {"m":sel_p, "i":item['ingredient'], "q":float(item['qty'])})
                                st.success("✅ Resept avtomatik yaradıldı və cədvələ əlavə olundu!")
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ AI düzgün formatda cavab vermədi. Bir daha cəhd edin.")

        st.divider()

        recs_disp = recs[['id', 'ingredient_name', 'quantity_required', 'unit']].copy()
        recs_disp['quantity_required'] = recs_disp['quantity_required'].astype(float)
        recs_disp.insert(0, "Seç", False)
        
        erd = st.data_editor(recs_disp, hide_index=True, column_config={
            "Seç": st.column_config.CheckboxColumn(required=True),
            "quantity_required": st.column_config.NumberColumn("Miqdar", format="%.4f")
        }, key="rec_ed_safe", use_container_width=True)
        
        srd = erd[erd["Seç"]]['id'].tolist()
        
        col_r1, col_r2 = st.columns(2)
        if len(srd) == 1 and col_r1.button("✏️ Düzəliş", key="rec_ed_btn"): st.session_state.edit_recipe_id = int(srd[0]); st.rerun()
        if srd and col_r2.button("🗑️ Sil", key="rec_del_btn"): 
            for i in srd: run_action("DELETE FROM recipes WHERE id=:id", {"id":int(i)})
            st.rerun()
            
        with st.form("nrec", clear_on_submit=True):
            ing_df = run_query("SELECT name, unit FROM ingredients ORDER BY name")
            if not ing_df.empty:
                ing_map = {row['name']: row['unit'] for _, row in ing_df.iterrows()}
                ing = st.selectbox("Xammal", list(ing_map.keys()))
                unit_label = ing_map.get(ing, "")
                qty = st.number_input(f"Miqdar ({unit_label})", format="%.4f", step=0.001)
                if st.form_submit_button("Əlavə Et"): 
                    # Burada məcburi FLOAT qoyuruq ki heç bir şansı qalmasın
                    run_action("INSERT INTO recipes (menu_item_name,ingredient_name,quantity_required) VALUES (:m,:i,:q)", {"m":sel_p,"i":ing,"q":float(qty)}); st.rerun()
            else: st.warning("Anbarda xammal yoxdur.")
                
    if st.session_state.get('edit_recipe_id'):
        r_res = run_query("SELECT * FROM recipes WHERE id=:id", {"id":st.session_state.edit_recipe_id})
        if not r_res.empty:
            rec_item = r_res.iloc[0]
            @st.dialog("✏️ Resept Düzəliş")
            def edit_recipe_dialog(r):
                with st.form("edit_rec_form"):
                    all_ings = run_query("SELECT name FROM ingredients ORDER BY name")['name'].tolist()
                    curr_ing_idx = all_ings.index(r['ingredient_name']) if r['ingredient_name'] in all_ings else 0
                    new_ing = st.selectbox("Xammal", all_ings, index=curr_ing_idx)
                    new_qty = st.number_input("Miqdar", format="%.4f", step=0.001, value=float(r['quantity_required']))
                    if st.form_submit_button("Yadda Saxla"): 
                        run_action("UPDATE recipes SET ingredient_name=:i, quantity_required=:q WHERE id=:id", {"i":new_ing, "q":float(new_qty), "id":int(r['id'])}); st.session_state.edit_recipe_id = None; st.success("Yeniləndi!"); time.sleep(0.5); st.rerun()
            edit_recipe_dialog(rec_item)
            
    if st.session_state.role == 'admin':
        with st.expander("📤 Reseptləri İmport / Export (Excel)"):
            if st.button("⚠️ Bütün Reseptləri Sil (Təmizlə)", type="primary"): admin_confirm_dialog("Bütün reseptlər silinsin?", lambda: run_action("DELETE FROM recipes"))
            with st.form("recipe_import_form"):
                upl_rec = st.file_uploader("📥 Import", type="xlsx")
                if st.form_submit_button("Reseptləri Yüklə"):
                    if upl_rec:
                        try:
                            df_r = pd.read_excel(upl_rec); df_r.columns = [str(c).lower().strip() for c in df_r.columns]; r_map = {"mal": "menu_item_name", "məhsul": "menu_item_name", "xammal": "ingredient_name", "miqdar": "quantity_required"}; df_r.rename(columns=r_map, inplace=True); cnt = 0
                            for _, r in df_r.iterrows():
                                if pd.isna(r['menu_item_name']): continue
                                run_action("INSERT INTO recipes (menu_item_name, ingredient_name, quantity_required) VALUES (:m, :i, :q)", {"m":str(r['menu_item_name']), "i":str(r['ingredient_name']), "q":float(r['quantity_required'])}); cnt += 1
                            st.success(f"{cnt} resept sətri yükləndi!")
                        except Exception as e: st.error(f"Xəta: {e}")
            if st.button("📤 Reseptləri Excel Kimi Endir"): out = BytesIO(); run_query("SELECT * FROM recipes").to_excel(out, index=False); st.download_button("⬇️ Endir (recipes.xlsx)", out.getvalue(), "recipes.xlsx")

def render_crm_page():
    # CRM kodu əvvəlki kimi
    st.subheader("👥 CRM və AI Marketoloq")
    crm_stats = run_query("SELECT type, COUNT(*) as cnt FROM customers GROUP BY type")
    if not crm_stats.empty:
        cols = st.columns(len(crm_stats))
        stat_str = []
        for idx, row in crm_stats.iterrows():
            lbl = row['type'].upper()
            icon = "🥇" if lbl=='GOLDEN' else "🥈" if lbl=='PLATINUM' else "💎" if lbl=='ELITE' else "🎁" if lbl=='IKRAM' else "👤"
            with cols[idx % 4]: st.metric(f"{icon} {lbl}", row['cnt'])
            stat_str.append(f"{lbl}: {row['cnt']} nəfər")
            
    st.divider()
    
    if st.session_state.role in ['admin','manager']:
         with st.expander("🎫 Yeni Kupon / Promo Kod Yarat", expanded=False):
            with st.form("new_promo_code_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                pc_code = c1.text_input("Kod (Məs: YAY2026)")
                pc_disc = c2.number_input("Endirim %", 1, 100)
                pc_days = c3.number_input("Gün", 1, 365)
                if st.form_submit_button("Kodu Yarat"):
                    valid_until = get_baku_now() + datetime.timedelta(days=pc_days)
                    run_action("INSERT INTO promo_codes (code, discount_percent, valid_until, assigned_user_id, is_used) VALUES (:c, :d, :v, 'system', FALSE)", {"c":pc_code, "d":pc_disc, "v":valid_until}); st.success("Yaradıldı!"); st.rerun()
                    
    cust_df = run_query("SELECT card_id, type, stars, email FROM customers")
    cust_df.insert(0, "Seç", False)
    ed_cust = st.data_editor(cust_df, hide_index=True, column_config={"Seç": st.column_config.CheckboxColumn(required=True)}, key="crm_sel")
    sel_cust_ids = ed_cust[ed_cust["Seç"]]['card_id'].tolist()
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 AI Mesaj İdeyası (Marketoloq)", type="secondary"):
            with st.spinner("Marketoloq düşünür..."):
                prompt = f"Sən 'Füzuli' kofe şopunun Marketinq müdirisən. Müştərilərin yenidən gəlməsini təşviq edəcək, şirin, emojilərlə 3 fərqli qısa mesaj şablonu ver. Azərbaycan dilində yaz."
                ai_msg = call_ai(prompt)
                st.markdown(f"<div style='background: #1e2226; padding:20px; border-left:5px solid #ffd700; border-radius:10px; margin-bottom:15px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5);'>{ai_msg}</div>", unsafe_allow_html=True)

        msg = st.text_area("Ekran Mesajı (Müştərinin QR ekranına gedəcək)")
        promo_list = ["(Kuponsuz)"] + run_query("SELECT code FROM promo_codes")['code'].tolist()
        sel_promo = st.selectbox("Promo Yapışdır (Seçilənlərə)", promo_list)
        if st.button("📢 Seçilənlərə Göndər / Tətbiq Et", key="crm_send_btn", type="primary"):
            if sel_cust_ids:
                for cid in sel_cust_ids:
                    if msg: run_action("INSERT INTO notifications (card_id, message) VALUES (:c, :m)", {"c":cid, "m":msg})
                    if sel_promo != "(Kuponsuz)": 
                        expires = get_baku_now() + datetime.timedelta(days=30)
                        run_action("INSERT INTO customer_coupons (card_id, coupon_type, expires_at) VALUES (:c, :t, :e)", {"c":cid, "t":sel_promo, "e":expires})
                st.success(f"{len(sel_cust_ids)} nəfərə tətbiq edildi!")
            else:
                st.error("Cədvəldən ən azı 1 müştəri seçin!")

def render_qr_page():
    st.subheader("QR Generator")
    c1, c2 = st.columns(2)
    cnt = c1.number_input("Say", 1, 50, key="qr_cnt")
    tp = c2.selectbox("Tip", ["Golden (5%)","Platinum (10%)","Elite (20%)","Thermos (20%)","Ikram (100%)"], key="qr_type")
    use_inventory = st.checkbox("📦 Fiziki Kartı Anbardan Sil", key="qr_inv")
    selected_card_stock = None
    
    if use_inventory:
        inv_items = run_query("SELECT id, name, stock_qty FROM ingredients WHERE category ILIKE '%Kart%' OR category ILIKE '%Mətbəə%' ORDER BY name")
        if not inv_items.empty: 
            item_map = {f"{row['name']} (Qalıq: {int(row['stock_qty'])})": row['id'] for _, row in inv_items.iterrows()}
            sel_label = st.selectbox("Hansı Kart?", list(item_map.keys()), key="qr_stock_sel")
            selected_card_stock = item_map[sel_label]
        else: st.warning("⚠️ Anbarda 'Kart' kateqoriyalı mal tapılmadı.")
            
    if st.button("QR Kodları Yarat 🚀", type="primary"):
        can_proceed = True
        if use_inventory and selected_card_stock:
            curr_qty = run_query("SELECT stock_qty FROM ingredients WHERE id=:id", {"id":selected_card_stock}).iloc[0]['stock_qty']
            if curr_qty < cnt: 
                st.error(f"⛔ Stok yetmir! Qalıq: {int(curr_qty)}, Lazım: {cnt}"); can_proceed = False
                
        if can_proceed:
            type_map = {"Golden (5%)":"golden", "Platinum (10%)":"platinum", "Elite (20%)":"elite", "Thermos (20%)":"thermos", "Ikram (100%)":"ikram"}
            generated_qrs = []
            for _ in range(cnt):
                cid = str(random.randint(10000000,99999999))
                tok = secrets.token_hex(8)
                run_action("INSERT INTO customers (card_id, stars, type, secret_token) VALUES (:i, 0, :t, :s)", {"i":cid, "t":type_map[tp], "s":tok})
                url = f"{APP_URL}/?id={cid}&t={tok}"
                img_bytes = generate_styled_qr(url)
                generated_qrs.append((cid, img_bytes))
                
            if use_inventory and selected_card_stock: 
                run_action("UPDATE ingredients SET stock_qty = stock_qty - :q WHERE id=:id", {"q":cnt, "id":selected_card_stock})
                st.toast(f"📦 Anbardan {cnt} ədəd kart silindi.")
                
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for cid, img in generated_qrs: zf.writestr(f"{cid}_{type_map[tp]}.png", img)
                    
            st.success(f"{cnt} QR Kod yaradıldı!")
            st.download_button("📦 Hamsını Endir (ZIP)", zip_buf.getvalue(), "qrcodes.zip", "application/zip")
