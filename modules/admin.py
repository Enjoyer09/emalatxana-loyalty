# admin.py
import streamlit as st
import pandas as pd
import bcrypt
import time
import json
import datetime
from database import run_query, run_action, get_setting, set_setting, conn
from sqlalchemy import text
from utils import log_system, get_baku_now

def render_settings_page():
    st.subheader("⚙️ Ayarlar və İdarəetmə")
    
    tab_settings, tab_users, tab_crm, tab_app = st.tabs(["🍽️ Restoran Ayarları", "👥 İstifadəçilər", "📱 Müştəri CRM & QR", "📱 Müştəri Tətbiqi (App)"])
    
    with tab_settings:
        st.markdown("### 🍽️ Servis Haqqı Tənzimləməsi")
        current_fee = float(get_setting("service_fee_percent", "0.0"))
        new_fee = st.number_input("Servis Haqqı (%)", min_value=0.0, max_value=100.0, step=1.0, value=current_fee)
        
        if st.button("Servis Haqqını Yenilə"):
            set_setting("service_fee_percent", str(new_fee))
            st.success("Yeniləndi!")
        
        st.markdown("### 🕒 Növbə və Vaxt Ayarları (Baku Time)")
        time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        
        c1, c2, c3 = st.columns(3)
        current_start = get_setting("shift_start_time", "08:00")
        current_end = get_setting("shift_end_time", "23:59")
        current_offset = get_setting("utc_offset", "4")
        
        s_idx = time_options.index(current_start) if current_start in time_options else 16
        e_idx = time_options.index(current_end) if current_end in time_options else -1
        
        new_start = c1.selectbox("Smen Başlanğıcı", time_options, index=s_idx)
        new_end = c2.selectbox("Smen Bitişi", time_options, index=e_idx)
        new_off = c3.number_input("UTC Offset (Baku=+4)", value=int(current_offset))
        
        if st.button("Vaxt Ayarlarını Saxla"):
            set_setting("shift_start_time", new_start)
            set_setting("shift_end_time", new_end)
            set_setting("utc_offset", str(new_off))
            st.success("Vaxt ayarları yeniləndi!")

    with tab_users:
        st.markdown("### 👥 İstifadəçi İdarəetməsi")
        users = run_query("SELECT username, role, last_seen FROM users")
        if not users.empty:
            st.dataframe(users, hide_index=True)
            
        with st.expander("➕ Yeni İstifadəçi / Şifrə Yeniləmə"):
            u_name = st.text_input("İstifadəçi Adı")
            u_pass = st.text_input("Şifrə", type="password")
            u_role = st.selectbox("Rol", ["staff", "manager", "admin"])
            
            if st.button("Yadda Saxla"):
                if u_name and u_pass:
                    p_hash = bcrypt.hashpw(u_pass.encode(), bcrypt.gensalt()).decode()
                    try:
                        run_action("INSERT INTO users (username, password, role) VALUES (:u, :p, :r) ON CONFLICT (username) DO UPDATE SET password=:p, role=:r", 
                                   {"u": u_name, "p": p_hash, "r": u_role})
                        log_system(st.session_state.user, f"İstifadəçi yeniləndi/yaradıldı: {u_name}")
                        st.success("İstifadəçi qeydə alındı!")
                    except Exception as e:
                        st.error(f"Xəta: {e}")
                else:
                    st.error("Ad və Şifrə boş ola bilməz.")

        with st.expander("🗑️ İstifadəçi Sil"):
            if not users.empty:
                del_user = st.selectbox("Silinəcək İstifadəçi", users['username'].tolist())
                if st.button("İstifadəçini Sil", type="primary"):
                    if del_user == 'admin':
                        st.error("Əsas admin istifadəçisi silinə bilməz!")
                    else:
                        run_action("DELETE FROM users WHERE username=:u", {"u": del_user})
                        log_system(st.session_state.user, f"İstifadəçi silindi: {del_user}")
                        st.success("Silindi!")
                        time.sleep(1); st.rerun()

    with tab_crm:
        st.markdown("### 📱 Müştəri QR və Loyallıq (CRM)")
        with st.form("add_customer"):
            card_id = st.text_input("Müştəri Kartı / QR ID (məs: 1001)")
            c_type = st.selectbox("Müştəri Tipi / Loyallıq Dərəcəsi", ["standard", "golden", "platinum", "elite", "thermos", "ikram", "telebe"])
            c_stars = st.number_input("Başlanğıc Ulduz Sayı", min_value=0, value=0, step=1)
            
            if st.form_submit_button("Müştərini Qeydiyyata Al"):
                if card_id:
                    run_action("INSERT INTO customers (card_id, type, stars) VALUES (:cid, :t, :s) ON CONFLICT (card_id) DO UPDATE SET type=:t, stars=:s",
                               {"cid": card_id, "t": c_type, "s": c_stars})
                    st.success(f"Müştəri ({card_id}) uğurla qeydiyyata alındı/yeniləndi!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("QR ID boş ola bilməz.")
                    
        # 🤖 AI İLƏ KAMPANİYA VƏ MARKETİNQ TƏKLİFLƏRİ YARATMA (YENİ)
        with st.expander("🤖 AI ilə Kampaniya və Marketinq Təklifləri Yarat", expanded=False):
            api_key = get_setting("gemini_api_key", "")
            if not api_key:
                st.warning("⚠️ AI funksiyası üçün 'Ayarlar' və ya 'AI Menecer' bölməsində API Key daxil edin.")
            else:
                camp_goal = st.text_input("🎯 Kampaniyanın Məqsədi (məs: Tələbələri cəlb etmək, Səhər satışlarını artırmaq)")
                if st.button("🚀 AI Kampaniya Yarat", type="primary"):
                    if camp_goal:
                        with st.spinner("🤖 AI müştəri datalarını və məqsədi analiz edir..."):
                            try:
                                import google.generativeai as genai
                                genai.configure(api_key=api_key)
                                valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                                chosen_model = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else 'models/gemini-pro')
                                model = genai.GenerativeModel(chosen_model)
                                
                                cust_stats = run_query("SELECT type, COUNT(*) as cnt FROM customers GROUP BY type")
                                stats_str = ", ".join([f"{r['type']}: {r['cnt']}" for _, r in cust_stats.iterrows()]) if not cust_stats.empty else "Məlumat yoxdur"
                                
                                prompt = f"Sən kofe şopun kreativ marketinq mütəxəssisisən. Mövcud müştəri bazamız: {stats_str}. Kampaniyanın məqsədi: '{camp_goal}'. Zəhmət olmasa, bu məqsədə uyğun 3 fərqli, cəlbedici marketinq mesajı (Instagram və ya SMS üçün) və 1 xüsusi endirim təklifi strategiyası yaz. Mətnlər qısa, səmimi və diqqətçəkici olsun."
                                
                                response = model.generate_content(prompt)
                                st.markdown(f"<div style='background: #1e2226; padding: 15px; border-left: 5px solid #007bff; border-radius:10px;'>{response.text}</div>", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Xəta: {e}")
                    else:
                        st.warning("Zəhmət olmasa kampaniyanın məqsədini yazın.")
        
        customers_df = run_query("SELECT * FROM customers ORDER BY created_at DESC")
        if not customers_df.empty:
            st.dataframe(customers_df, hide_index=True)

    with tab_app:
        st.markdown("### 📱 Müştəri Ekranı və Məlumatlar")
        st.info("Tezliklə App ayarları bura əlavə olunacaq.")

def render_database_page():
    st.subheader("💾 Baza İdarəetməsi (Backup & Restore)")
    if st.button("📦 Bütün Bazanı JSON kimi Yüklə"):
        try:
            tables = ['users', 'menu', 'sales', 'finance', 'customers', 'inventory', 'recipes', 'settings', 'logs', 'shift_handovers', 'admin_notes']
            backup_data = {}
            for t in tables:
                df = run_query(f"SELECT * FROM {t}")
                if not df.empty:
                    backup_data[t] = df.to_dict(orient='records')
            
            json_str = json.dumps(backup_data, indent=4, default=str)
            st.download_button("JSON Faylını Yüklə", data=json_str, file_name=f"backup_{get_baku_now().strftime('%Y%m%d_%H%M')}.json", mime="application/json")
        except Exception as e:
            st.error(f"Backup xətası: {e}")

    with st.expander("⚠️ Bazanı Bərpa Et (Restore)"):
        st.warning("DİQQƏT: Bu proses mövcud məlumatları silib yenisi ilə əvəz edəcək!")
        uploaded_json = st.file_uploader("JSON Backup faylını seçin", type="json")
        if st.button("Bazanı Fayldan Bərpa Et", type="primary", use_container_width=True) and uploaded_json:
            try:
                data = json.load(uploaded_json)
                with conn.session as s:
                    for tbl, recs in data.items():
                        if recs and tbl.isidentifier():
                            s.execute(text(f"TRUNCATE TABLE {tbl} CASCADE"))
                            for r in recs:
                                clean_keys = [k for k in r.keys() if k.isidentifier()]
                                cols = ", ".join(clean_keys)
                                vals = ":" + ", :".join(clean_keys)
                                safe_r = {k: r[k] for k in clean_keys}
                                s.execute(text(f"INSERT INTO {tbl} ({cols}) VALUES ({vals})"), safe_r)
                    s.commit()
                st.success("✅ Baza uğurla bərpa edildi!")
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Bərpa xətası (Rollback edildi): {e}")

def render_logs_page():
    st.subheader("🕵️‍♂️ Sistem Loqları")
    try:
        logs = run_query("SELECT * FROM logs ORDER BY created_at DESC LIMIT 500")
        if not logs.empty:
            st.dataframe(logs, use_container_width=True, hide_index=True)
        else:
            st.info("Loq tapılmadı.")
    except Exception as e:
        st.error(f"Loq oxuma xətası: {e}")

def render_notes_page():
    st.subheader("📝 Admin Qeydləri")
    run_action("CREATE TABLE IF NOT EXISTS admin_notes (id SERIAL PRIMARY KEY, title TEXT, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Başlıq")
        note = st.text_area("Qeyd")
        if st.form_submit_button("Yadda Saxla"):
            if title and note: 
                run_action("INSERT INTO admin_notes (title, note) VALUES (:t, :n)", {"t": title, "n": note})
                st.rerun()
                
    try:
        notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
        if not notes.empty:
            for _, n in notes.iterrows():
                with st.expander(f"{n['created_at']} - {n['title']}"):
                    st.write(n['note'])
                    if st.button("Sil", key=f"del_note_{n['id']}"):
                        run_action("DELETE FROM admin_notes WHERE id=:id", {"id": n['id']})
                        st.rerun()
    except Exception:
        pass
