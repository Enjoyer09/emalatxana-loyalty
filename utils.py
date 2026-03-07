import datetime
import io
import base64
try:
    import qrcode
except ImportError:
    pass

from database import get_setting, run_action

# --- SİSTEM KONSTANTLARI ---
BRAND_NAME = "Emalatkhana POS AI Powered"
VERSION = "1.0 RC"
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
    except Exception:
        return ""

def generate_styled_qr(data):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except:
        return None

# --- ZAMAN VƏ NÖVBƏ FUNKSİYALARI (YENİLƏNİB) ---

def get_baku_now():
    offset_str = get_setting("utc_offset", "4")
    try:
        offset_hours = int(offset_str)
    except:
        offset_hours = 4
        
    utc_now = datetime.datetime.utcnow()
    real_local_time = utc_now + datetime.timedelta(hours=offset_hours)
    return real_local_time

def get_logical_date():
    now = get_baku_now()
    
    shift_start_str = get_setting("shift_start_time", "08:00")
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
        
    shift_start_str = get_setting("shift_start_time", "08:00")
    shift_end_str = get_setting("shift_end_time", "23:59")
    
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
    
    # Məntiq: Qapanış saatı açılışdan kiçikdirsə (məs: gecə 02:00-da qapanış), deməli gün ertəsi günə keçir
    if shift_end <= shift_start:
        shift_end += datetime.timedelta(days=1)
    
    return shift_start, shift_end

def clean_qr_code(code):
    if not code: return ""
    return str(code).strip()

def log_system(user, action):
    try:
        run_action("INSERT INTO logs (user, action, created_at) VALUES (:u, :a, :t)", 
                   {"u": str(user), "a": str(action), "t": get_baku_now()})
    except:
        pass

# --- ŞİFRƏLƏMƏ (AUTH) ---

def hash_password(password):
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)
    except:
        return password

def verify_password(plain_password, hashed_password):
    if plain_password == hashed_password:
        return True
    
    if str(hashed_password).startswith("pbkdf2:"):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(hashed_password, plain_password)
        except:
            pass
            
    try:
        import bcrypt
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        pass
        
    return False
