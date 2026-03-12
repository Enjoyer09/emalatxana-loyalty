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
    try:
        return conn.query(q, params=p if p else {}, ttl=0)
    except Exception as e:
        print(f"DB Query Error: {e}")
        return pd.DataFrame()

def run_action(q, p=None): 
    if not conn: return False
    try:
        with conn.session as s: 
            s.execute(text(q), p if p else {})
            s.commit()
        return True
    except Exception as e:
        print(f"DB Action Error: {e}")
        return False

def get_setting(key, default=""):
    try: 
        res = run_query("SELECT value FROM settings WHERE key=:k", {"k":key})
        return res.iloc[0]['value'] if not res.empty else default
    except Exception as e: 
        print(f"DB Get Setting Error: {e}")
        return default

def set_setting(key, value): 
    run_action("INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v", {"k":key, "v":value})

@st.cache_resource
def ensure_schema():
    if not conn: return False
    try:
        with conn.session as s:
            s.execute(text("CREATE TABLE IF NOT EXISTS tables (id SERIAL PRIMARY KEY, label TEXT, is_occupied BOOLEAN DEFAULT FALSE, items TEXT, total DECIMAL(10,2) DEFAULT 0, opened_at TIMESTAMP);"))
            s.execute(text("CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, item_name TEXT, price DECIMAL(10,2), category TEXT, is_active BOOLEAN DEFAULT FALSE, is_coffee BOOLEAN DEFAULT FALSE, printer_target TEXT DEFAULT 'kitchen', price_half DECIMAL(10,2));"))
            
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS sales (
                    id SERIAL PRIMARY KEY, items TEXT, total DECIMAL(10,2), payment_method TEXT, 
                    cashier TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                    customer_card_id TEXT, original_total DECIMAL(10,2) DEFAULT 0, 
                    discount_amount DECIMAL(10,2) DEFAULT 0, note TEXT, 
                    tip_amount DECIMAL(10,2) DEFAULT 0, is_test BOOLEAN DEFAULT FALSE,
                    cogs DECIMAL(10,2) DEFAULT 0
                );
            """))
            
            s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, last_seen TIMESTAMP, failed_attempts INTEGER DEFAULT 0, locked_until TIMESTAMP);"))
            s.execute(text("CREATE TABLE IF NOT EXISTS active_sessions (token TEXT PRIMARY KEY, username TEXT, role TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_activity TIMESTAMP);"))
            
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS finance (
                    id SERIAL PRIMARY KEY, type TEXT, category TEXT, amount DECIMAL(10,2), 
                    source TEXT, description TEXT, created_by TEXT, 
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, subject TEXT, is_test BOOLEAN DEFAULT FALSE
                );
            """))
            
            s.execute(text("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"))
            s.execute(text("CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, \"user\" TEXT, action TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))
            s.execute(text("CREATE TABLE IF NOT EXISTS z_reports (id SERIAL PRIMARY KEY, total_sales DECIMAL(10,2), cash_sales DECIMAL(10,2), card_sales DECIMAL(10,2), total_cogs DECIMAL(10,2), actual_cash DECIMAL(10,2), generated_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"))

            columns_to_add = [
                ("sales", "is_test", "BOOLEAN DEFAULT FALSE"),
                ("finance", "is_test", "BOOLEAN DEFAULT FALSE"),
                ("sales", "bank_fee", "DECIMAL(10,2) DEFAULT 0"),
                ("sales", "net_total", "DECIMAL(10,2) DEFAULT 0"),
                ("sales", "cogs", "DECIMAL(10,2) DEFAULT 0")
            ]

            for table, col, dtype in columns_to_add:
                try:
                    with s.begin_nested():
                        s.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {dtype};"))
                except Exception as e:
                    pass

            s.execute(text("INSERT INTO settings (key, value) VALUES ('current_shift_status', 'Closed') ON CONFLICT DO NOTHING;"))

            try:
                with s.begin_nested():
                    admin_pass = os.environ.get("ADMIN_PASS")
                    if not admin_pass:
                        import secrets
                        admin_pass = secrets.token_urlsafe(16)
                        print(f"WARNING: ADMIN_PASS is not set. Generated temporary password: {admin_pass}")
                    p_hash = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
                    s.execute(text("INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin') ON CONFLICT (username) DO NOTHING"), {"p": p_hash})
            except Exception as e: 
                print(f"Error creating admin user: {e}")
                
            s.commit()
        return True
    except Exception as e:
        print(f"Ensure schema fatal error: {e}")
        return False
