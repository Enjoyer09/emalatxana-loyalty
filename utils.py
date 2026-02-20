import streamlit as st
import datetime
import bcrypt
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from io import BytesIO
import base64
import requests
import re
import os

VERSION = "v1.0 (Xanış Modular)"
BRAND_NAME = "Emalatxana POS by iRonwaves"
ADMIN_DEFAULT_PASS = os.environ.get("ADMIN_PASS", "admin123") 
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DEFAULT_SENDER_EMAIL = "info@ironwaves.store"
APP_URL = "https://no1.ironwaves.store" 

SUBJECTS = ["Admin", "Abbas (Manager)", "Nicat (Investor)", "Elvin (Investor)", "Bank Kartı (Şirkət)", "Təchizatçı", "Digər"]
PRESET_CATEGORIES = ["Kofe (Dənələr)", "Süd Məhsulları", "Bar Məhsulları (Su/Buz)", "Siroplar", "Soslar və Pastalar", "Qablaşdırma (Stəkan/Qapaq)", "Şirniyyat (Hazır)", "İçkilər (Hazır)", "Meyvə-Tərəvəz", "Təsərrüfat/Təmizlik", "Mətbəə / Kartlar"]
CAT_ORDER_MAP = {cat: i for i, cat in enumerate(PRESET_CATEGORIES)}
BONUS_RECIPIENTS = ["Sabina", "Samir"]
CARTOON_QUOTES = ["Bu gün sənin günündür! 🚀", "Qəhrəman kimi parılda! ⭐", "Bir fincan kofe = Xoşbəxtlik! ☕", "Enerjini topla, dünyanı fəth et! 🌍"]

DEFAULT_TERMS = """
<div style="font-family: 'Arial', sans-serif; color: #333; line-height: 1.6; font-size: 14px; background-color: #e8f5e9; padding: 15px; border-radius: 10px; border-left: 5px solid #2E7D32;">
    <h4 style="color: #2E7D32; margin-top: 0;">📜 Xoş Gəldiniz! Qaydalar:</h4>
    <ul style="padding-left: 20px; margin-bottom: 0;">
        <li>🔹 <strong>5% Endirim:</strong> Bütün kofe və içkilərə.</li>
        <li>🔹 <strong>Hədiyyə Kofe:</strong> 9 ulduz yığanda 10-cu kofe bizdən Hədiyyə! 🎁</li>
    </ul>
</div>
"""
ALLOWED_TABLES = ["users", "menu", "sales", "ingredients", "recipes", "customers", "notifications", "settings", "system_logs", "tables", "promo_codes", "customer_coupons", "expenses", "finance", "admin_notes", "bonuses"]

def get_baku_now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=4))).replace(tzinfo=None)
def get_logical_date(): return (get_baku_now() - datetime.timedelta(days=1)).date() if get_baku_now().hour < 8 else get_baku_now().date()
def get_shift_range(date_obj=None):
    if date_obj is None: date_obj = get_logical_date()
    start = datetime.datetime.combine(date_obj, datetime.time(8, 0, 0))
    return start, start + datetime.timedelta(hours=24)
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): 
    try: return bcrypt.checkpw(p.encode(), h.encode()) if h.startswith('$2b$') else p == h
    except: return False
def clean_qr_code(raw_code): return re.sub(r'[^a-zA-Z0-9]', '', raw_code.split("id=")[1].split("&")[0]) if "id=" in raw_code else re.sub(r'[^a-zA-Z0-9]', '', raw_code.strip()) if raw_code else ""
def generate_styled_qr(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(image_factory=StyledPilImage, module_drawer=SquareModuleDrawer(), color_mask=SolidFillColorMask(front_color=(0, 128, 0, 255), back_color=(255, 255, 255, 0)))
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
def image_to_base64(image_file): return base64.b64encode(image_file.getvalue()).decode()
def send_email(to_email, subject, body):
    if not RESEND_API_KEY: return "API_KEY_MISSING"
    try: requests.post("https://api.resend.com/emails", json={"from": f"{BRAND_NAME} <{DEFAULT_SENDER_EMAIL}>", "to": [to_email], "subject": subject, "html": body}, headers={"Authorization": f"Bearer {RESEND_API_KEY}"}); return "OK"
    except: return "Error"
def log_system(user, action, cid=None):
    from database import run_action 
    try: run_action("INSERT INTO system_logs (username, action, customer_id, created_at) VALUES (:u, :a, :c, :t)", {"u":user, "a":action, "c":cid, "t":get_baku_now()})
    except: pass
