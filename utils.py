# utils.py — PATCHED v3.0 (+ Happy Hour)
import datetime
import io
import base64
import logging
import os
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        ZoneInfo = None

from database import get_setting, run_action, run_query

# ============================================================
# CONSTANTS
# ============================================================
BRAND_NAME = "Emalatkhana POS AI Powered"
VERSION = "3.0"
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

CAT_ORDER_MAP = {cat: i for i, cat in enumerate(PRESET_CATEGORIES)}

SK_SHIFT_STATUS = "current_shift_status"
SK_SHIFT_OPEN_TIME = "shift_open_time"
SK_UTC_OFFSET = "utc_offset"
SK_TIMEZONE = "timezone"
SK_SHIFT_START = "shift_start_time"
SK_SHIFT_END = "shift_end_time"
SK_CASH_LIMIT = "cash_limit"

# ============================================================
# DECIMAL HELPERS
# ============================================================
def safe_decimal(val, default="0"):
    import pandas as pd_check
    if val is None or (isinstance(val, float) and (pd_check.isna(val) or val != val)):
        return Decimal(default)
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def format_money(val):
    if isinstance(val, Decimal):
        return f"{val:.2f}"
    return f"{Decimal(str(val)):.2f}"

# ============================================================
# TIME FUNCTIONS
# ============================================================
def get_baku_now():
    tz_name = get_setting(SK_TIMEZONE, "Asia/Baku")
    if ZoneInfo:
        try:
            zone = ZoneInfo(tz_name)
            return datetime.datetime.now(zone)
        except:
            pass
    # Fallback
    offset_str = get_setting(SK_UTC_OFFSET, "4")
    try:
        offset_hours = int(offset_str)
    except:
        offset_hours = 4
    utc_now = datetime.datetime.utcnow()
    return utc_now + datetime.timedelta(hours=offset_hours)

def get_logical_date():
    now = get_baku_now()
    shift_start_str = get_setting(SK_SHIFT_START, "08:00")
    try:
        start_hour = int(shift_start_str.split(':')[0])
    except:
        start_hour = 8
    if now.hour < start_hour:
        return (now - datetime.timedelta(days=1)).date()
    return now.date()

def get_shift_range(logical_date=None):
    if not logical_date:
        logical_date = get_logical_date()
    shift_start_str = get_setting(SK_SHIFT_START, "08:00")
    shift_end_str = get_setting(SK_SHIFT_END, "23:59")
    try:
        start_hour, start_min = map(int, shift_start_str.split(':'))
    except:
        start_hour, start_min = 8, 0
    try:
        end_hour, end_min = map(int, shift_end_str.split(':'))
    except:
        end_hour, end_min = 23, 59
    shift_start = datetime.datetime.combine(logical_date, datetime.time(start_hour, start_min))
    shift_end = datetime.datetime.combine(logical_date, datetime.time(end_hour, end_min))
    if shift_end <= shift_start:
        shift_end += datetime.timedelta(days=1)
    return shift_start, shift_end

# ============================================================
# QR / IMAGE
# ============================================================
def clean_qr_code(code):
    if not code:
        return ""
    return str(code).strip()

def image_to_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        logger.error(f"Error reading image: {e}")
        return ""

def generate_styled_qr(data):
    if qrcode is None:
        return None
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Error generating QR: {e}")
        return None

# ============================================================
# LOGGING
# ============================================================
def log_system(user, action, details=None):
    try:
        run_action(
            'INSERT INTO logs ("user", action, details, created_at) VALUES (:u, :a, :d, :t)',
            {"u": str(user), "a": str(action), "d": str(details) if details else None, "t": get_baku_now()}
        )
    except Exception as e:
        logger.error(f"System log error: {e}")

# ============================================================
# PASSWORD
# ============================================================
def hash_password(password):
    import bcrypt
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    if not plain_password or not hashed_password:
        return False
    if str(hashed_password).startswith("pbkdf2:"):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(hashed_password, plain_password)
        except:
            return False
    try:
        import bcrypt
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False

# ============================================================
# SHIFT
# ============================================================
def get_shift_status():
    try:
        res = run_query("SELECT key, value FROM settings WHERE key IN ('current_shift_status', 'shift_open_time')")
        return {row['key']: row['value'] for _, row in res.iterrows()}
    except:
        return {'current_shift_status': 'Closed'}

def open_shift(user):
    now_str = get_baku_now().strftime("%Y-%m-%d %H:%M:%S")
    current = get_shift_status()
    if current.get('current_shift_status') == 'Open':
        return False
    run_action("UPDATE settings SET value = 'Open' WHERE key = 'current_shift_status'")
    run_action("UPDATE settings SET value = :t WHERE key = 'shift_open_time'", {"t": now_str})
    log_system(user, f"NÖVBƏ AÇILDI: {now_str}")
    return True

def close_shift(user):
    run_action("UPDATE settings SET value = 'Closed' WHERE key = 'current_shift_status'")
    log_system(user, "NÖVBƏ BAĞLANDI")
    return True

# ============================================================
# HAPPY HOUR CHECK (YENİ)
# ============================================================
def get_active_happy_hour():
    """Hazırda aktiv happy hour varsa qaytarır, yoxsa None"""
    try:
        now = get_baku_now()
        current_time = now.strftime("%H:%M:%S")
        current_day = str(now.isoweekday())

        hh_df = run_query("SELECT * FROM happy_hours WHERE is_active=TRUE")

        if hh_df.empty:
            return None

        for _, hh in hh_df.iterrows():
            days = str(hh.get('days_of_week', '1,2,3,4,5,6,7')).split(',')
            if current_day not in [d.strip() for d in days]:
                continue
            start = str(hh['start_time'])
            end = str(hh['end_time'])
            if start <= current_time <= end:
                return {
                    'name': hh['name'],
                    'discount_percent': int(hh['discount_percent']),
                    'categories': str(hh.get('categories', 'ALL')),
                    'start_time': start,
                    'end_time': end
                }
        return None
    except Exception as e:
        logger.error(f"Happy hour check failed: {e}")
        return None
