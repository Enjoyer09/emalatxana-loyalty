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

# --- SİSTEM KONSTANTLARI ---
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
def image_to_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception: return ""

def generate_styled_qr(data):
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(data); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO(); img.save(buf, format="PNG")
        return buf.getvalue()
    except: return None

# --- ZAMAN VƏ NÖVBƏ FUNKSİYALARI (BAKI VAXTI) ---
def get_baku_now():
    offset_str = get_setting("utc_offset", "4")
    try: offset_hours = int(offset_str)
    except: offset_hours = 4
    utc_now = datetime.datetime.utcnow()
    return utc_now + datetime.timedelta(hours=offset_hours)

def get_logical_date():
    now = get_baku_now()
    shift_start_str = get_setting("shift_start_time", "08:00")
    try: start_hour = int(shift_start_str.split(':')[0])
    except: start_hour = 8
    if now.hour < start_hour: return (now - datetime.timedelta(days=1)).date()
    return now.date()

def get_shift_range(logical_date=None):
    if not logical_date: logical_date = get_logical_date()
    shift_start_str = get_setting("shift_start_time", "08:00")
    shift_end_str = get_setting("shift_end_time", "23:59")
    try: s_h, s_m = map(int, shift_start_str.split(':'))
    except: s_h, s_m = 8, 0
    try: e_h, e_m = map(int, shift_end_str.split(':'))
    except: e_h, e_m = 23, 59
    shift_start = datetime.datetime.combine(logical_date, datetime.time(s_h, s_m))
    shift_end = datetime.datetime.combine(logical_date, datetime.time(e_h, e_m))
    if shift_end <= shift_start: shift_end += datetime.timedelta(days=1)
    return shift_start, shift_end

# --- YENİ SHIFT (NÖVBƏ) İDARƏETMƏ FUNKSİYALARI ---
def get_shift_status():
    try:
        shift = run_query("SELECT key, value FROM settings WHERE key IN ('current_shift_status', 'shift_open_time')")
        return {row['key']: row['value'] for _, row in shift.iterrows()}
    except: return {'current_shift_status': 'Closed'}

def open_shift(user):
    now_str = get_baku_now().strftime("%Y-%m-%d %H:%M:%S")
    run_action("UPDATE settings SET value = 'Open' WHERE key = 'current_shift_status'")
    run_action("UPDATE settings SET value = :t WHERE key = 'shift_open_time'", {"t": now_str})
    log_system(user, f"NÖVBƏ AÇILDI: {now_str}")

def close_shift(user):
    run_action("UPDATE settings SET value = 'Closed' WHERE key = 'current_shift_status'")
    log_system(user, "NÖVBƏ BAĞLANDI")

def clean_qr_code(code):
    if not code: return ""
    if "id=" in str(code): return str(code).split("id=")[1].split("&")[0]
    return str(code).strip()

def log_system(user, action):
    try:
        run_action("INSERT INTO system_logs (username, action) VALUES (:u, :a)", {"u": str(user), "a": str(action)})
    except: pass

def verify_password(plain, hashed):
    if plain == hashed: return True
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except: return False
