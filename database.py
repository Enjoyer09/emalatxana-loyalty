import streamlit as st
from sqlalchemy import text
import os
import pandas as pd
import bcrypt

def get_connection():
    try:
        db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL") or os.environ.get("DATABASE_URL")
        if not db_url: return None
        if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        return st.connection("neon", type="sql", url=db_url, pool_pre_ping=True, pool_size=20, max_overflow=30)
    except Exception as e: 
        st.error(f"DB Error: {e}")
        return None

conn = get_connection()

def run_query(q, p=None): 
    if not conn: return pd.DataFrame()
    return conn.query(q, params=p if p else {}, ttl=0)

def run_action(q, p=None): 
    if not conn: return False
    with conn.session as s: 
        s.execute(text(q), p if p else {})
        s.commit()
    return True

def get_setting(key, default=""):
    try: 
        res = run_query("SELECT value FROM settings WHERE key=:k", {"k":key})
        return res.iloc[0]['value'] if not res.empty else default
    except: return default

def set_setting(key, value): 
    run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v", {"k":key, "v":value})

@st.cache_resource
def ensure_schema():
    if not conn: return False
    with conn.session as s:
        # --- ƏSAS CƏDVƏLLƏR ---
        s.execute(text("CREATE TABLE IF NOT EXISTS tables (id SERIAL PRIMARY KEY, label TEXT, is_occupied BOOLEAN DEFAULT FALSE, items TEXT, total DECIMAL(10,2) DEFAULT 0, opened_at TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_active BOOLEAN DEFAULT FALSE, is_coffee BOOLEAN DEFAULT FALSE, printer_target TEXT DEFAULT 'kitchen', price_half DECIMAL(10,2));"))
        
        # Sales cədvəli (Net gəlir üçün sütunlar əlavə edilə bilər)
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, 
                cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                customer_card_id TEXT, original_total DECIMAL(10,2) DEFAULT 0, 
                discount_amount DECIMAL(10,2) DEFAULT 0, note TEXT, 
                tip_amount DECIMAL(10,2) DEFAULT 0, is_test BOOLEAN DEFAULT FALSE
            );
        """))
        
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP, failed_attempts INTEGER DEFAULT 0, locked_until TIMESTAMP);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_activity TIMESTAMP);"))
        
        # Finance cədvəli (Maliyyə hərəkətləri)
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS finance (
                id SERIAL PRIMARY KEY, type TEXT, category TEXT, amount DECIMAL(10,2), 
                source TEXT, description TEXT, created_by TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, subject TEXT, is_test BOOLEAN DEFAULT FALSE
            );
        """))
        
        s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, \"user\" TEXT, action TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))

        # --- YENİLƏMƏLƏR (PATCHES) ---
        # Sütun yoxlamaları (Xəta verməməsi üçün try-except daxilində)
        columns_to_add = [
            ("sales", "is_test", "BOOLEAN DEFAULT FALSE"),
            ("finance", "is_test", "BOOLEAN DEFAULT FALSE"),
            ("sales", "bank_fee", "DECIMAL(10,2) DEFAULT 0"), # Bank komissiyasını Analitika üçün saxlamaq
            ("sales", "net_total", "DECIMAL(10,2) DEFAULT 0") # Xalis məbləği Analitika üçün saxlamaq
        ]

        for table, col, dtype in columns_to_add:
            try:
                with s.begin_nested():
                    s.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {dtype};"))
            except:
                pass

        # İlkin tənzimləmələr
        s.execute(text("INSERT INTO settings (key, value) VALUES ('current_shift_status', 'Closed') ON CONFLICT DO NOTHING;"))

        # Admin istifadəçisi yarat
        try:
            with s.begin_nested():
                p_hash = bcrypt.hashpw(os.environ.get("ADMIN_PASS", "admin123").encode(), bcrypt.gensalt()).decode()
                s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin') ON CONFLICT (username) DO NOTHING"), {"p": p_hash})
        except: 
            pass
            
        s.commit()
    return True
