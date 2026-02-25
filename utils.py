import datetime
from database import get_setting, run_action

# Qlobal dəyişənlər
BRAND_NAME = "Füzuli"
SUBJECTS = ["Təchizatçı", "İşçi", "Dövlət/Vergi", "İcarədar", "Digər"]

# 1. HƏMİŞƏ DÜZGÜN SAAT (Serverdən asılı deyil, Ayarlara baxır)
def get_baku_now():
    offset_str = get_setting("utc_offset", "4")
    try:
        offset_hours = int(offset_str)
    except:
        offset_hours = 4
        
    utc_now = datetime.datetime.utcnow()
    real_local_time = utc_now + datetime.timedelta(hours=offset_hours)
    return real_local_time

# 2. MƏNTİQİ GÜN (Növbənin başlama saatına görə günü tapır)
def get_logical_date():
    now = get_baku_now()
    
    shift_start_str = get_setting("shift_start_time", "08:00")
    try:
        start_hour = int(shift_start_str.split(':')[0])
    except:
        start_hour = 8

    # Əgər saat 08:00-dan tezdirsə, deməli hələ dünənki növbə davam edir
    if now.hour < start_hour:
        return (now - datetime.timedelta(days=1)).date()
    return now.date()

# 3. NÖVBƏNİN TAM ARALIĞI (Z-Hesabat üçün)
def get_shift_range(logical_date=None):
    if not logical_date:
        logical_date = get_logical_date()
        
    shift_start_str = get_setting("shift_start_time", "08:00")
    try:
        start_hour, start_min = map(int, shift_start_str.split(':'))
    except:
        start_hour, start_min = 8, 0
        
    shift_start = datetime.datetime.combine(logical_date, datetime.time(start_hour, start_min))
    shift_end = shift_start + datetime.timedelta(days=1)
    
    return shift_start, shift_end

# Əlavə köməkçi funksiyalar (QR və Log)
def clean_qr_code(code):
    if not code: return ""
    return str(code).strip()

def log_system(user, action):
    try:
        run_action("INSERT INTO logs (user, action, created_at) VALUES (:u, :a, :t)", 
                   {"u": str(user), "a": str(action), "t": get_baku_now()})
    except:
        pass
