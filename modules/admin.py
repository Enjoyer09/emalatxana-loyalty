# modules/admin.py — FINAL PATCHED v3.5 (+ Inventory Backup Fix)
import streamlit as st
import pandas as pd
import bcrypt
import time
import json
import datetime
import logging
from decimal import Decimal

from database import run_query, run_action, run_transaction, get_setting, set_setting, conn
from sqlalchemy import text
from utils import log_system, get_baku_now, safe_decimal

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# ============================================================
# SETTINGS PAGE
# ============================================================
def render_settings_page():
    st.subheader("⚙️ Ayarlar və İdarəetmə")

    tab_settings, tab_users, tab_crm, tab_happy, tab_app = st.tabs([
        "🍽️ Restoran Ayarları",
        "👥 İstifadəçilər",
        "📱 Müştəri CRM & QR",
        "⏰ Happy Hour",
        "📱 Müştəri Tətbiqi (App)"
    ])

    # ============================================================
    # RESTORAN AYARLARI
    # ============================================================
    with tab_settings:
        st.markdown("### 🍽️ Servis Haqqı Tənzimləməsi")
        current_fee = safe_decimal(get_setting("service_fee_percent", "0.0"))
        new_fee = st.number_input("Servis Haqqı (%)", min_value=0.0, max_value=100.0, step=1.0, value=float(current_fee))

        if st.button("Servis Haqqını Yenilə"):
            set_setting("service_fee_percent", str(Decimal(str(new_fee))))
            log_system(st.session_state.user, "SERVICE_FEE_UPDATE", {"percent": new_fee})
            st.success("Yeniləndi!")

        st.markdown("---")
        st.markdown("### 👁️ UI Vizuallıq Ayarları")

        staff_show_tables = get_setting("staff_show_tables", "TRUE") == "TRUE"
        manager_show_tables = get_setting("manager_show_tables", "TRUE") == "TRUE"
        staff_show_kitchen = get_setting("staff_show_kitchen", "TRUE") == "TRUE"

        c_ui1, c_ui2 = st.columns(2)
        with c_ui1:
            new_staff_tables = st.toggle("Staff (Kassir) 'Masalar'ı görsün", value=staff_show_tables)
            new_mgr_tables = st.toggle("Manager 'Masalar'ı görsün", value=manager_show_tables)
        with c_ui2:
            new_staff_kitchen = st.toggle("Staff (Kassir) 'Mətbəx'i görsün", value=staff_show_kitchen)

        if st.button("UI Ayarlarını Yadda Saxla", type="primary"):
            set_setting("staff_show_tables", "TRUE" if new_staff_tables else "FALSE")
            set_setting("manager_show_tables", "TRUE" if new_mgr_tables else "FALSE")
            set_setting("staff_show_kitchen", "TRUE" if new_staff_kitchen else "FALSE")
            log_system(
                st.session_state.user,
                "UI_SETTINGS_UPDATE",
                {
                    "staff_tables": new_staff_tables,
                    "mgr_tables": new_mgr_tables,
                    "staff_kitchen": new_staff_kitchen
                }
            )
            st.success("Görünüş ayarları yadda saxlanıldı!")
            time.sleep(1)
            st.rerun()

        st.markdown("---")
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
            log_system(
                st.session_state.user,
                "TIME_SETTINGS_UPDATE",
                {
                    "shift_start": new_start,
                    "shift_end": new_end,
                    "utc_offset": new_off
                }
            )
            st.success("Vaxt ayarları yeniləndi!")

        # ========================================================
        # RESEND / EMAIL REPORT SETTINGS
        # ========================================================
        st.markdown("---")
        st.markdown("### 📧 E-mail Hesabat Ayarları")

        resend_key = get_setting("resend_api_key", "")
        sender_email = get_setting("report_sender_email", "")
        recipient_emails = get_setting("report_recipient_emails", "")

        new_resend = st.text_input("Resend API Key", value=resend_key, type="password")
        new_sender = st.text_input("Göndərən E-mail", value=sender_email, placeholder="info@ironwaves.store")
        new_recipients = st.text_area("Alan E-mail-lər (vergüllə ayırın)", value=recipient_emails, placeholder="mail1@gmail.com,mail2@gmail.com")

        if st.button("E-mail Ayarlarını Yadda Saxla", type="primary"):
            set_setting("resend_api_key", new_resend)
            set_setting("report_sender_email", new_sender)
            set_setting("report_recipient_emails", new_recipients)
            log_system(
                st.session_state.user,
                "REPORT_EMAIL_SETTINGS_UPDATED",
                {
                    "sender": new_sender,
                    "recipients": new_recipients
                }
            )
            st.success("E-mail ayarları yadda saxlanıldı!")
            st.rerun()

    # ============================================================
    # USERS
    # ============================================================
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
                    if len(u_pass) < 4:
                        st.error("⚠️ Şifrə ən azı 4 simvol olmalıdır!")
                    else:
                        try:
                            p_hash = bcrypt.hashpw(u_pass.encode(), bcrypt.gensalt()).decode()
                            run_action(
                                "INSERT INTO users (username, password, role) VALUES (:u, :p, :r) "
                                "ON CONFLICT (username) DO UPDATE SET password=:p, role=:r",
                                {"u": u_name.strip(), "p": p_hash, "r": u_role}
                            )
                            log_system(
                                st.session_state.user,
                                "USER_UPSERT",
                                {"target_user": u_name.strip(), "role": u_role}
                            )
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
                        try:
                            actions = [
                                ("DELETE FROM active_sessions WHERE username=:u", {"u": del_user}),
                                ("DELETE FROM users WHERE username=:u", {"u": del_user})
                            ]
                            run_transaction(actions)
                            log_system(
                                st.session_state.user,
                                "USER_DELETE",
                                {"target_user": del_user}
                            )
                            st.success("Silindi!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Xəta: {e}")

    # ============================================================
    # CRM
    # ============================================================
    with tab_crm:
        st.markdown("### 📱 Müştəri QR və Loyallıq (CRM)")

        with st.form("add_customer"):
            card_id = st.text_input("Müştəri Kartı / QR ID (məs: 1001)")
            c_type = st.selectbox("Müştəri Tipi / Loyallıq Dərəcəsi", ["standard", "golden", "platinum", "elite", "thermos", "ikram", "telebe"])
            c_stars = st.number_input("Başlanğıc Ulduz Sayı", min_value=0, value=0, step=1)

            if st.form_submit_button("Müştərini Qeydiyyata Al"):
                if card_id.strip():
                    try:
                        run_action(
                            "INSERT INTO customers (card_id, type, stars) VALUES (:cid, :t, :s) "
                            "ON CONFLICT (card_id) DO UPDATE SET type=:t, stars=:s",
                            {"cid": card_id.strip(), "t": c_type, "s": c_stars}
                        )
                        log_system(
                            st.session_state.user,
                            "CUSTOMER_UPSERT",
                            {"card_id": card_id.strip(), "type": c_type, "stars": c_stars}
                        )
                        st.success(f"Müştəri ({card_id}) uğurla qeydiyyata alındı/yeniləndi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Xəta: {e}")
                else:
                    st.error("QR ID boş ola bilməz.")

        customers_df = run_query("SELECT * FROM customers ORDER BY created_at DESC")
        if not customers_df.empty:
            st.dataframe(customers_df, hide_index=True)

    # ============================================================
    # HAPPY HOUR
    # ============================================================
    with tab_happy:
        st.markdown("### ⏰ Happy Hour / Avtomatik Endirim")
        st.info("Müəyyən saatlarda avtomatik endirim tətbiq olunur.")

        hh_df = run_query("SELECT * FROM happy_hours ORDER BY start_time")

        if not hh_df.empty:
            for _, hh in hh_df.iterrows():
                status_icon = "🟢" if hh['is_active'] else "🔴"
                days = hh.get('days_of_week', '1,2,3,4,5,6,7')
                day_names = {'1': 'B.e', '2': 'Ç.a', '3': 'Ç', '4': 'C.a', '5': 'C', '6': 'Ş', '7': 'B'}
                day_display = " ".join([day_names.get(d.strip(), d) for d in str(days).split(',')])
                cats = hh.get('categories', 'ALL')
                cat_display = "Bütün menyu" if cats == 'ALL' else cats

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    c1.markdown(f"**{status_icon} {hh['name']}**")
                    c2.markdown(f"🕐 {hh['start_time']} — {hh['end_time']}")
                    c3.markdown(f"🏷️ **{hh['discount_percent']}%**")
                    if c4.button("🗑️", key=f"del_hh_{hh['id']}"):
                        run_action("DELETE FROM happy_hours WHERE id=:id", {"id": hh['id']})
                        log_system(
                            st.session_state.user,
                            "HAPPY_HOUR_DELETE",
                            {"id": int(hh['id']), "name": hh['name']}
                        )
                        st.rerun()
                    st.caption(f"📅 {day_display} | 📂 {cat_display}")

                    if hh['is_active']:
                        if st.button("⏸️ Deaktiv Et", key=f"deact_hh_{hh['id']}", use_container_width=True):
                            run_action("UPDATE happy_hours SET is_active=FALSE WHERE id=:id", {"id": hh['id']})
                            log_system(st.session_state.user, "HAPPY_HOUR_DEACTIVATE", {"id": int(hh['id']), "name": hh['name']})
                            st.rerun()
                    else:
                        if st.button("▶️ Aktivləşdir", key=f"act_hh_{hh['id']}", use_container_width=True):
                            run_action("UPDATE happy_hours SET is_active=TRUE WHERE id=:id", {"id": hh['id']})
                            log_system(st.session_state.user, "HAPPY_HOUR_ACTIVATE", {"id": int(hh['id']), "name": hh['name']})
                            st.rerun()
        else:
            st.warning("Heç bir Happy Hour yaradılmayıb.")

        st.markdown("---")
        st.markdown("#### ➕ Yeni Happy Hour Yarat")
        with st.form("new_hh_form", clear_on_submit=True):
            hh_c1, hh_c2 = st.columns(2)
            hh_name = hh_c1.text_input("Ad (Məs: Səhər Endirimi)")
            hh_discount = hh_c2.number_input("Endirim %", min_value=1, max_value=100, value=15)

            hh_c3, hh_c4 = st.columns(2)
            hh_start = hh_c3.time_input("Başlanğıc Saatı", value=datetime.time(14, 0))
            hh_end = hh_c4.time_input("Bitiş Saatı", value=datetime.time(16, 0))

            st.write("Hansı günlər aktiv olsun?")
            day_cols = st.columns(7)
            day_map = {'B.e': '1', 'Ç.a': '2', 'Ç': '3', 'C.a': '4', 'C': '5', 'Ş': '6', 'B': '7'}
            selected_days = []
            for i, (name, num) in enumerate(day_map.items()):
                if day_cols[i].checkbox(name, value=True, key=f"hh_day_{num}"):
                    selected_days.append(num)

            cat_mode = st.radio("Endirim nəyə tətbiq olunsun?", ["Bütün Menyu", "Yalnız Seçilmiş Kateqoriyalar"], horizontal=True)
            hh_cats = "ALL"
            if cat_mode == "Yalnız Seçilmiş Kateqoriyalar":
                try:
                    all_cats = run_query("SELECT DISTINCT category FROM menu WHERE is_active=TRUE")['category'].tolist()
                    selected_cats = st.multiselect("Kateqoriyalar", all_cats)
                    hh_cats = ",".join(selected_cats) if selected_cats else "ALL"
                except:
                    hh_cats = "ALL"

            if st.form_submit_button("✅ Happy Hour Yarat", type="primary"):
                if hh_name and selected_days:
                    try:
                        run_action(
                            "INSERT INTO happy_hours (name, start_time, end_time, discount_percent, days_of_week, categories, is_active, created_by, created_at) "
                            "VALUES (:n, :s, :e, :d, :days, :cats, TRUE, :u, :t)",
                            {
                                "n": hh_name.strip(),
                                "s": str(hh_start),
                                "e": str(hh_end),
                                "d": hh_discount,
                                "days": ",".join(selected_days),
                                "cats": hh_cats,
                                "u": st.session_state.user,
                                "t": get_baku_now()
                            }
                        )
                        log_system(
                            st.session_state.user,
                            "HAPPY_HOUR_CREATE",
                            {
                                "name": hh_name.strip(),
                                "discount_percent": hh_discount,
                                "start_time": str(hh_start),
                                "end_time": str(hh_end),
                                "days": selected_days,
                                "categories": hh_cats
                            }
                        )
                        st.success(f"'{hh_name}' yaradıldı!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Xəta: {e}")
                else:
                    st.error("Ad və ən azı 1 gün seçin!")

    # ============================================================
    # APP TAB
    # ============================================================
    with tab_app:
        st.markdown("### 📱 Müştəri Ekranı və Məlumatlar")
        st.info("Tezliklə App ayarları bura əlavə olunacaq.")


def render_database_page():
    st.subheader("💾 Baza İdarəetməsi (Backup & Restore)")
    st.info("Bütün sistemi və tranzaksiyaları JSON formatında yükləyin. Bu faylı istədiyiniz vaxt başqa sistemə köçürə bilərsiniz.")

    # YENİLƏNMİŞ, PANDAS İLƏ XƏTASIZ BACKUP MƏNTİQİ
    if st.button("📦 JSON Backup Hazırla", type="primary", use_container_width=True):
        with st.spinner("Məlumatlar toplanır... Zəhmət olmasa gözləyin."):
            try:
                tables_to_backup = [
                    "tables", "menu", "sales", "users", "active_sessions", "ingredients", 
                    "finance", "expenses", "recipes", "customers", "promo_codes", 
                    "customer_coupons", "notifications", "settings", "system_logs", 
                    "feedbacks", "admin_notes", "bonuses", "orders", "order_items", 
                    "z_reports", "logs", "coffee_fortunes", "happy_hours"
                ]
                backup_data = {}
                for t in tables_to_backup:
                    try:
                        df = run_query(f"SELECT * FROM {t}")
                        if not df.empty:
                            # Pandas to_json tarixi, onluq kəsrləri və mürəkkəb simvolları xətasız oxuyur!
                            json_str = df.to_json(orient="records", date_format="iso", force_ascii=False)
                            backup_data[t] = json.loads(json_str)
                        else:
                            backup_data[t] = []
                    except Exception as table_error:
                        logger.warning(f"Skipping table {t} during backup: {table_error}")
                        backup_data[t] = []

                final_json = json.dumps(backup_data, indent=4, ensure_ascii=False)
                st.session_state.backup_json = final_json
                st.session_state.backup_ready = True
                log_system(st.session_state.user, "DATABASE_BACKUP_CREATED", {"tables": list(backup_data.keys())})
            except Exception as e:
                st.error(f"Backup xətası: {e}")

    # EKRANDA YARANAN YÜKLƏMƏ DÜYMƏSİ (State-də qorunur)
    if st.session_state.get('backup_ready', False):
        st.download_button(
            label="📥 Hazır JSON Faylı Yüklə",
            data=st.session_state.backup_json,
            file_name=f"Emalatkhana_Backup_{get_baku_now().strftime('%d_%m_%Y_%H_%M')}.json",
            mime="application/json",
            use_container_width=True
        )
        st.success("✅ Backup faylı uğurla hazırlandı! Yuxarıdakı düyməyə basaraq yükləyə bilərsiniz.")

    st.markdown("---")

    with st.expander("⚠️ Bazanı Bərpa Et (Restore)"):
        st.warning("DİQQƏT: Bu proses mövcud məlumatları silib yenisi ilə əvəz edəcək!")
        uploaded_json = st.file_uploader("JSON Backup faylını seçin", type="json")
        if st.button("Bazanı Fayldan Bərpa Et", type="primary", use_container_width=True) and uploaded_json:
            try:
                data = json.load(uploaded_json)
                if not isinstance(data, dict):
                    st.error("⚠️ JSON formatı səhvdir!")
                    st.stop()

                allowed_tables = {
                    'users', 'menu', 'sales', 'finance', 'customers', 'ingredients', 'recipes',
                    'settings', 'logs', 'shift_handovers', 'admin_notes', 'refunds',
                    'kitchen_orders', 'happy_hours', 'notifications', 'promo_codes',
                    'customer_coupons', 'campaigns', 'tables', 'z_reports', 'active_sessions',
                    'expenses', 'system_logs', 'feedbacks', 'bonuses', 'orders', 'order_items', 'coffee_fortunes'
                }

                with conn.session as s:
                    for tbl, recs in data.items():
                        if tbl not in allowed_tables:
                            logger.warning(f"Skipping restore for unapproved table: {tbl}")
                            continue
                            
                        if recs and isinstance(recs, list):
                            try:
                                s.execute(text(f"TRUNCATE TABLE {tbl} CASCADE"))
                                for r in recs:
                                    if not isinstance(r, dict):
                                        continue
                                    clean_keys = [k for k in r.keys() if isinstance(k, str) and k.replace('_', '').isalnum()]
                                    if not clean_keys:
                                        continue
                                    cols = ", ".join(clean_keys)
                                    vals = ":" + ", :".join(clean_keys)
                                    safe_r = {k: r[k] for k in clean_keys}
                                    s.execute(text(f"INSERT INTO {tbl} ({cols}) VALUES ({vals})"), safe_r)
                                logger.info(f"Successfully restored table: {tbl}")
                            except Exception as table_restore_error:
                                logger.error(f"Failed to restore table {tbl}: {table_restore_error}")
                                raise table_restore_error 
                    s.commit()

                log_system(st.session_state.user, "DATABASE_RESTORE_COMPLETED")
                st.success("✅ Baza uğurla bərpa edildi!")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Bərpa xətası (Rollback edildi): {e}")


def render_logs_page():
    st.subheader("🕵️‍♂️ Sistem Loqları")

    c1, c2 = st.columns([1, 1])

    if c1.button("🧪 Test Structured Log"):
        log_system(
            st.session_state.get('user', 'admin'),
            "TEST_LOG",
            {
                "message": "Bu structured test logudur",
                "page": "logs",
                "time": str(get_baku_now())
            }
        )
        st.success("Structured test log yazıldı!")
        st.rerun()

    limit = c2.selectbox("Limit", [100, 250, 500, 1000], index=2)

    try:
        logs = run_query(f'SELECT * FROM logs ORDER BY created_at DESC LIMIT {int(limit)}')
        if not logs.empty:
            if 'created_at' in logs.columns:
                try:
                    logs['created_at'] = pd.to_datetime(logs['created_at']).dt.strftime('%d.%m.%Y %H:%M:%S')
                except:
                    pass

            if '"user"' in logs.columns and 'user' not in logs.columns:
                logs['user'] = logs['"user"']

            if 'details' in logs.columns:
                def pretty_details(x):
                    if pd.isna(x) or x is None or str(x).strip() == "":
                        return ""
                    try:
                        parsed = json.loads(x)
                        if isinstance(parsed, dict):
                            return " | ".join([f"{k}: {v}" for k, v in parsed.items()])
                        return str(parsed)
                    except:
                        return str(x)

                logs['details_preview'] = logs['details'].apply(pretty_details)

            display_cols = [c for c in ['created_at', 'user', 'action', 'details_preview'] if c in logs.columns]

            st.dataframe(
                logs[display_cols] if display_cols else logs,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "created_at": "Tarix",
                    "user": "İstifadəçi",
                    "action": "Event",
                    "details_preview": "Detallar"
                }
            )

            with st.expander("📜 Raw Log Məlumatları"):
                for _, row in logs.iterrows():
                    st.markdown(f"### {row.get('action', '-')}")
                    st.write(f"**Tarix:** {row.get('created_at', '-')}")
                    st.write(f"**User:** {row.get('user', '-')}")
                    if 'details' in row and row['details']:
                        try:
                            parsed = json.loads(row['details'])
                            st.json(parsed)
                        except:
                            st.code(str(row['details']))
                    st.markdown("---")

            st.caption(f"Toplam göstərilən log sayı: {len(logs)}")
        else:
            st.info("Loq tapılmadı.")
    except Exception as e:
        st.error(f"Loq oxuma xətası: {e}")


def render_notes_page():
    st.subheader("📝 Admin Qeydləri")
    try:
        run_action("CREATE TABLE IF NOT EXISTS admin_notes (id SERIAL PRIMARY KEY, title TEXT, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    except:
        pass

    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Başlıq")
        note = st.text_area("Qeyd")
        if st.form_submit_button("Yadda Saxla"):
            if title.strip() and note.strip():
                run_action("INSERT INTO admin_notes (title, note) VALUES (:t, :n)", {"t": title.strip(), "n": note.strip()})
                log_system(st.session_state.user, "NOTE_CREATED", {"title": title[:50]})
                st.rerun()

    try:
        notes = run_query("SELECT * FROM admin_notes ORDER BY created_at DESC")
        if not notes.empty:
            for _, n in notes.iterrows():
                with st.expander(f"{n['created_at']} - {n['title']}"):
                    st.write(n['note'])
                    if st.button("Sil", key=f"del_note_{n['id']}"):
                        run_action("DELETE FROM admin_notes WHERE id=:id", {"id": n['id']})
                        log_system(st.session_state.user, "NOTE_DELETED", {"title": str(n['title'])[:50], "id": int(n['id'])})
                        st.rerun()
    except Exception:
        pass
