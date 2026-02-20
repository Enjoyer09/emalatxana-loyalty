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

VERSION = "v1.0 (Füzuli)"
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
DEFAULT_TERMS = """<div style="background-color:#e8f5e9;padding:15px;border-radius:10px;border-left:5px solid #2E7D32;"><h4>📜 Qaydalar:</h4><ul><li>🔹 5% Endirim</li><li>🔹 9 ulduz = 1 Hədiyyə</li></ul></div>"""
ALLOWED_TABLES = ["users", "menu", "sales", "ingredients", "recipes", "customers", "notifications", "settings", "system_logs", "tables", "promo_codes", "customer_coupons", "expenses", "finance", "admin_notes", "bonuses"]

def get_baku_now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=4))).replace(tzinfo=None)
def get_logical_date(): return (get_baku_now() - datetime.timedelta(days=1)).date() if get_baku_now().hour < 8 else get_baku_now().date()
def get_shift_range(date_obj=None):
    if date_obj is None: date_obj = get_logical_date()
    start = datetime.datetime.combine(date_obj, datetime.time(8, 0, 0))
    end = start + datetime.timedelta(hours=24)
    return start, end
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

def get_receipt_html_string(cart, total):
    from database import get_setting
    store = get_setting("receipt_store_name", BRAND_NAME)
    addr = get_setting("receipt_address", "Baku")
    phone = get_setting("receipt_phone", "")
    header = get_setting("receipt_header", ""); footer = get_setting("receipt_footer", "Təşəkkürlər!")
    logo = get_setting("receipt_logo_base64")
    time_str = get_baku_now().strftime('%d/%m/%Y %H:%M')
    img_tag = f'<img src="data:image/png;base64,{logo}" style="width:80px; margin-bottom:10px; filter:grayscale(100%);">' if logo else ""
    rows = "".join([f"<tr><td style='border-bottom:1px dashed #000; padding:5px;'>{int(i['qty'])}</td><td style='border-bottom:1px dashed #000; padding:5px;'>{i['item_name']}</td><td style='border-bottom:1px dashed #000; padding:5px; text-align:right;'>{i['qty']*i['price']:.2f}</td></tr>" for i in cart])
    return f"""<html><head><style>body{{font-family:'Courier New',monospace;text-align:center;margin:0;padding:0}}.receipt-container{{width:300px;margin:0 auto;padding:10px;background:white}}table{{width:100%;text-align:left;border-collapse:collapse}}th{{border-bottom:1px dashed #000;padding:5px}}@media print{{body,html{{width:100%;height:100%;margin:0;padding:0}}body *{{visibility:hidden}}.receipt-container,.receipt-container *{{visibility:visible}}.receipt-container{{position:absolute;left:0;top:0;width:100%;margin:0;padding:0}}#print-btn{{display:none}}}}</style></head><body><div class="receipt-container">{img_tag}<h3 style="margin:5px 0;">{store}</h3><p style="margin:0;font-size:12px;">{addr}<br>{phone}</p><p style="margin:5px 0;font-weight:bold;">{header}</p><p style="font-size:12px;">{time_str}</p><br><table><tr><th>Say</th><th>Mal</th><th style='text-align:right;'>Məb</th></tr>{rows}</table><h3>YEKUN: {total:.2f} ₼</h3><p>{footer}</p><br><button id="print-btn" onclick="window.print()" style="background:#2E7D32;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">🖨️ ÇAP ET</button></div></body></html>"""
