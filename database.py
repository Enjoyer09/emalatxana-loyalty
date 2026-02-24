import streamlit as st
import pandas as pd
from sqlalchemy import text

# Verilənlər bazasına qoşulma
conn = st.connection("postgresql", type="sql")

def run_query(query, params=None):
    """Məlumat oxumaq üçün (SELECT)"""
    return conn.query(query, params=params if params else {}, ttl=0)

def run_action(query, params=None):
    """Məlumat yazmaq/silmək/dəyişmək üçün (INSERT, UPDATE, DELETE)"""
    with conn.session as s:
        s.execute(text(query), params if params else {})
        s.commit()

def ensure_schema():
    """Proqram açılanda bütün cədvəllərin varlığını yoxlayır və yoxdursa yaradır."""
    queries = [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS menu (
            id SERIAL PRIMARY KEY, item_name TEXT, price NUMERIC, category TEXT, is_active BOOLEAN, is_coffee BOOLEAN DEFAULT FALSE
        )""",
        """CREATE TABLE IF NOT EXISTS ingredients (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE, unit TEXT, unit_cost NUMERIC, stock_qty NUMERIC, category TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS recipes (
            id SERIAL PRIMARY KEY, menu_item_name TEXT, ingredient_name TEXT, quantity_required NUMERIC
        )""",
        """CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY, total_price NUMERIC, payment_method TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_by TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY, order_id INTEGER, item_name TEXT, quantity NUMERIC, price NUMERIC
        )""",
        """CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY, card_id TEXT UNIQUE, stars INTEGER DEFAULT 0, type TEXT, secret_token TEXT, email TEXT, phone TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS feedbacks (
            id SERIAL PRIMARY KEY, card_id TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY, card_id TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS promo_codes (
            id SERIAL PRIMARY KEY, code TEXT UNIQUE, discount_percent INTEGER, valid_until TIMESTAMP, assigned_user_id TEXT, is_used BOOLEAN DEFAULT FALSE
        )""",
        """CREATE TABLE IF NOT EXISTS customer_coupons (
            id SERIAL PRIMARY KEY, card_id TEXT, coupon_type TEXT, is_used BOOLEAN DEFAULT FALSE, expires_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS finance (
            id SERIAL PRIMARY KEY, type TEXT, category TEXT, amount NUMERIC, source TEXT, description TEXT, created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS z_reports (
            id SERIAL PRIMARY KEY, shift_start TIMESTAMP, shift_end TIMESTAMP, total_sales NUMERIC, cash_sales NUMERIC, card_sales NUMERIC, expected_cash NUMERIC, actual_cash NUMERIC, difference NUMERIC, generated_by TEXT
        )"""
    ]
    
    # Bütün cədvəlləri bir-bir bazaya yükləyirik
    with conn.session as s:
        for q in queries:
            s.execute(text(q))
        s.commit()
        
    # Əgər bazada heç bir admin yoxdursa, avtomatik 'admin' yaradırıq (şifrə: admin123)
    try:
        from auth import get_password_hash
        res = conn.query("SELECT * FROM users WHERE username='admin'", ttl=0)
        if res.empty:
            h = get_password_hash("admin123")
            with conn.session as s:
                s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin')"), {"p": h})
                s.commit()
    except Exception as e:
        pass

def get_setting(key, default=""):
    """Ayarları bazadan çəkmək üçün"""
    try:
        df = run_query("SELECT value FROM settings WHERE key=:k", {"k": key})
        if not df.empty: return df.iloc[0]['value']
    except: pass
    return default

def set_setting(key, value):
    """Ayarları bazaya yazmaq üçün (PostgreSQL uyğunlaşdırılmışdır)"""
    run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = :v", {"k": key, "v": value})
