import datetime
import io
import base64
import pytz
import streamlit as st
try:
    import qrcode
except ImportError:
    pass

from database import get_setting, run_action, run_query

# --- SİSTEM KONSTANTLARI (QORUNUR) ---
BRAND_NAME = "Emalatkhana POS AI Powered"
VERSION = "1.2 (Full Patch)"
DEFAULT_TERMS = "Bizi seçdiyiniz üçün təşəkkür edirik!"
APP_URL = "https://emalatxana.ironwaves.store" 

CARTOON_QUOTES = [
    "Qəhvəsiz bir gün, itirilmiş bir gündür!",
    "Füzulidə hər qurtum bir ilhamdır!",
    "Enerjini topla, günə başla!"
]

SUBJECTS = ["Təchizatçı", "İşçi", "Dövlət/Vergi", "İcarədar", "Digər"]
BONUS_RECIPIENTS = ["Hamısı", "Kassir", "Barista", "Xadimə", "Digər"]
ALLOWED_TABLES = [f"Masa {i}" for i in range(1, 16)] + ["Bar", "VIP", "Teras"]

PRESET_CATEGORIES = [
    "Kofe (Dənələr)", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", 
    "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", 
    "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", 
    "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar", "Digər"
]

CAT_ORDER_MAP = {cat: i for i, cat in enumerate([
    "Kofe (Dənələr)", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", 
    "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", 
    "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", 
    "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar"
])}

# --- KÖMƏKÇİ FUNKSİYALAR ---
def get_baku_now():
    offset_str = get_setting("utc_offset", "4")
    try: offset_hours = int(offset_str)
    except: offset_hours = 4
    utc_now = datetime.datetime.utcnow()
    return utc_now + datetime.timedelta(hours=offset_hours)

def get_shift_status():
    try:
        res = run_query("SELECT key, value FROM settings WHERE key IN ('current_shift_status', 'shift_open_time')")
        return {row['key']: row['value'] for _, row in res.iterrows()}
    except: return {'current_shift_status': 'Closed'}

def open_shift(user):
    now_str = get_baku_now().strftime("%Y-%m-%d %H:%M:%S")
    run_action("UPDATE settings SET value = 'Open' WHERE key = 'current_shift_status'")
    run_action("UPDATE settings SET value = :t WHERE key = 'shift_open_time'", {"t": now_str})
    log_system(user, f"NÖVBƏ AÇILDI: {now_str}")

def close_shift(user):
    run_action("UPDATE settings SET value = 'Closed' WHERE key = 'current_shift_status'")
    log_system(user, "NÖVBƏ BAĞLANDI")

def log_system(user, action):
    try:
        # Həm logs, həm də system_logs cədvəlinə yazırıq (təhlükəsizlik üçün)
        run_action("INSERT INTO system_logs (username, action) VALUES (:u, :a)", {"u": str(user), "a": str(action)})
    except: pass

def clean_qr_code(code):
    if not code: return ""
    if "id=" in str(code): return str(code).split("id=")[1].split("&")[0]
    return str(code).strip()

def verify_password(plain, hashed):
    if plain == hashed: return True
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except: return False
