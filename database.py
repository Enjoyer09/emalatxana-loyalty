# database.py — PATCHED v2.0
import streamlit as st
from sqlalchemy import text
import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CONNECTION
# ============================================================
def get_connection():
    db_url = os.environ.get("STREAMLIT_CONNECTIONS_NEON_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        st.error("❌ DATABASE_URL konfiqurasiya edilməyib! Sistem işləyə bilməz.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    try:
        return st.connection(
            "neon", type="sql", url=db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=300
        )
    except Exception as e:
        st.error(f"❌ Verilənlər bazasına qoşulmaq mümkün deyil: {e}")
        logger.critical(f"DB Connection failed: {e}", exc_info=True)
        st.stop()

conn = get_connection()

# ============================================================
# QUERY HELPERS
# ============================================================
def run_query(q, p=None):
    """Real-time data üçün (caching yoxdur)"""
    return conn.query(q, params=p if p else {}, ttl=0)

def run_query_cached(q, p=None, ttl=60):
    """Təkrarlanan read-only sorğular üçün (menu, users list)"""
    return conn.query(q, params=p if p else {}, ttl=ttl)

def run_action(q, p=None, session=None):
    """Tək əməliyyat. session verilərsə xarici transaction-a qoşulur."""
    if session:
        session.execute(text(q), p if p else {})
        return True
    with conn.session as s:
        s.execute(text(q), p if p else {})
        s.commit()
    return True

def run_transaction(actions: list):
    """
    Atomik multi-step əməliyyat.
    actions = [(sql_string, params_dict), ...]
    Hamısı uğurlu → commit, biri uğursuz → rollback.
    """
    with conn.session as s:
        try:
            for q, p in actions:
                s.execute(text(q), p if p else {})
            s.commit()
            return True
        except Exception as e:
            s.rollback()
            logger.error(f"Transaction failed: {e}", exc_info=True)
            raise e

# ============================================================
# SETTINGS HELPERS
# ============================================================
def get_setting(key, default=""):
    try:
        res = run_query("SELECT value FROM settings WHERE key=:k", {"k": key})
        return res.iloc[0]['value'] if not res.empty else default
    except Exception as e:
        logger.error(f"get_setting('{key}') failed: {e}")
        return default

def set_setting(key, value):
    run_action(
        "INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value=:v",
        {"k": key, "v": value}
    )

# ============================================================
# SCHEMA MANAGEMENT (Versioned)
# ============================================================
@st.cache_resource
def ensure_schema():
    with conn.session as s:
        # ---- Core Tables ----
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, 
                value TEXT
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, 
                password TEXT, 
                role TEXT, 
                last_seen TIMESTAMP, 
                failed_attempts INTEGER DEFAULT 0, 
                locked_until TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                token TEXT PRIMARY KEY, 
                username TEXT, 
                role TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                last_activity TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS tables (
                id SERIAL PRIMARY KEY, 
                label TEXT, 
                is_occupied BOOLEAN DEFAULT FALSE, 
                items TEXT, 
                total DECIMAL(10,2) DEFAULT 0, 
                opened_at TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS menu (
                id SERIAL PRIMARY KEY, 
                item_name TEXT, 
                price DECIMAL(10,2), 
                category TEXT, 
                is_active BOOLEAN DEFAULT FALSE, 
                is_coffee BOOLEAN DEFAULT FALSE, 
                printer_target TEXT DEFAULT 'kitchen', 
                price_half DECIMAL(10,2)
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY, 
                items TEXT, 
                total DECIMAL(10,2), 
                payment_method TEXT,
                cashier TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                customer_card_id TEXT, 
                original_total DECIMAL(10,2) DEFAULT 0,
                discount_amount DECIMAL(10,2) DEFAULT 0, 
                note TEXT,
                tip_amount DECIMAL(10,2) DEFAULT 0, 
                is_test BOOLEAN DEFAULT FALSE,
                cogs DECIMAL(10,2) DEFAULT 0,
                bank_fee DECIMAL(10,2) DEFAULT 0,
                net_total DECIMAL(10,2) DEFAULT 0
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS finance (
                id SERIAL PRIMARY KEY, 
                type TEXT, 
                category TEXT, 
                amount DECIMAL(10,2),
                source TEXT, 
                description TEXT, 
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                subject TEXT, 
                is_test BOOLEAN DEFAULT FALSE,
                is_deleted BOOLEAN DEFAULT FALSE,
                deleted_by TEXT,
                deleted_at TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS finance_audit_log (
                id SERIAL PRIMARY KEY,
                original_id INTEGER,
                action TEXT,
                original_data TEXT,
                new_data TEXT,
                performed_by TEXT,
                reason TEXT,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY, 
                "user" TEXT, 
                action TEXT, 
                details TEXT,
                ip TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS z_reports (
                id SERIAL PRIMARY KEY, 
                total_sales DECIMAL(10,2), 
                cash_sales DECIMAL(10,2), 
                card_sales DECIMAL(10,2), 
                total_cogs DECIMAL(10,2), 
                actual_cash DECIMAL(10,2), 
                generated_by TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS shift_handovers (
                id SERIAL PRIMARY KEY,
                handed_by TEXT,
                expected_cash DECIMAL(10,2),
                actual_cash DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS correction_requests (
                id SERIAL PRIMARY KEY,
                requested_by TEXT,
                cash_diff DECIMAL(10,2),
                card_diff DECIMAL(10,2),
                reason TEXT,
                status TEXT DEFAULT 'PENDING',
                approved_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # ---- Safe column additions ----
        columns_to_add = [
            ("sales", "is_test", "BOOLEAN DEFAULT FALSE"),
            ("finance", "is_test", "BOOLEAN DEFAULT FALSE"),
            ("sales", "bank_fee", "DECIMAL(10,2) DEFAULT 0"),
            ("sales", "net_total", "DECIMAL(10,2) DEFAULT 0"),
            ("sales", "cogs", "DECIMAL(10,2) DEFAULT 0"),
            ("finance", "is_deleted", "BOOLEAN DEFAULT FALSE"),
            ("finance", "deleted_by", "TEXT"),
            ("finance", "deleted_at", "TIMESTAMP"),
        ]

        for tbl, col, dtype in columns_to_add:
            exists = s.execute(text(
                "SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"
            ), {"t": tbl, "c": col}).fetchone()
            if not exists:
                try:
                    s.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {dtype}"))
                except Exception as e:
                    logger.warning(f"Column add {tbl}.{col} failed: {e}")

        # ---- Default settings ----
        s.execute(text(
            "INSERT INTO settings (key, value) VALUES ('current_shift_status', 'Closed') ON CONFLICT DO NOTHING"
        ))

        # ---- Default admin user ----
        admin_pass = os.environ.get("ADMIN_PASS")
        if not admin_pass:
            logger.critical("ADMIN_PASS environment variable is not set! Using fallback.")
            admin_pass = "admin123"

        existing_admin = s.execute(text("SELECT 1 FROM users WHERE username='admin'")).fetchone()
        if not existing_admin:
            import bcrypt
            p_hash = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
            s.execute(text(
                "INSERT INTO users (username, password, role) VALUES ('admin', :p, 'admin')"
            ), {"p": p_hash})

        s.commit()
    return True
