# database.py — FIX PACKAGE A FINAL
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
        st.error("❌ DATABASE_URL konfiqurasiya edilməyib!")
        st.stop()

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

    try:
        return st.connection(
            "neon",
            type="sql",
            url=db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=300
        )
    except Exception as e:
        st.error(f"❌ DB bağlantı xətası: {e}")
        logger.critical(f"DB connection failed: {e}", exc_info=True)
        st.stop()


conn = get_connection()


# ============================================================
# QUERY HELPERS
# ============================================================
def run_query(q, p=None):
    return conn.query(q, params=p if p else {}, ttl=0)


def run_query_cached(q, p=None, ttl=60):
    return conn.query(q, params=p if p else {}, ttl=ttl)


def run_action(q, p=None, session=None):
    if session:
        session.execute(text(q), p if p else {})
        return True

    with conn.session as s:
        s.execute(text(q), p if p else {})
        s.commit()
    return True


def run_transaction(actions: list):
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
        "INSERT INTO settings (key, value) VALUES (:k, :v) "
        "ON CONFLICT (key) DO UPDATE SET value=:v",
        {"k": key, "v": value}
    )


# ============================================================
# SCHEMA
# ============================================================
@st.cache_resource
def ensure_schema():
    with conn.session as s:
        # SETTINGS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """))

        # USERS
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

        # ACTIVE SESSIONS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                token TEXT PRIMARY KEY,
                username TEXT,
                role TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP
            );
        """))

        # TABLES
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

        # MENU
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

        # SALES
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
                net_total DECIMAL(10,2) DEFAULT 0,
                status TEXT DEFAULT 'COMPLETED'
            );
        """))

        # FINANCE
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
                deleted_at TIMESTAMP,
                sale_id INTEGER
            );
        """))

        # FINANCE AUDIT LOG
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

        # LOGS
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

        # Z REPORTS
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

        # SHIFT HANDOVERS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS shift_handovers (
                id SERIAL PRIMARY KEY,
                handed_by TEXT,
                expected_cash DECIMAL(10,2),
                actual_cash DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # CORRECTION REQUESTS
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

        # REFUNDS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS refunds (
                id SERIAL PRIMARY KEY,
                original_sale_id INTEGER NOT NULL,
                refund_amount DECIMAL(10,2) NOT NULL,
                reason TEXT NOT NULL,
                refund_type TEXT DEFAULT 'VOID',
                items_returned_to_stock BOOLEAN DEFAULT FALSE,
                created_by TEXT,
                approved_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # KITCHEN ORDERS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS kitchen_orders (
                id SERIAL PRIMARY KEY,
                sale_source TEXT DEFAULT 'POS',
                table_label TEXT,
                items TEXT NOT NULL,
                status TEXT DEFAULT 'NEW',
                priority TEXT DEFAULT 'NORMAL',
                notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                completed_at TIMESTAMP,
                completed_by TEXT
            );
        """))

        # HAPPY HOURS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS happy_hours (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                discount_percent INTEGER NOT NULL DEFAULT 10,
                days_of_week TEXT DEFAULT '1,2,3,4,5,6,7',
                categories TEXT DEFAULT 'ALL',
                is_active BOOLEAN DEFAULT TRUE,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # NOTIFICATIONS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                card_id TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # PROMO CODES
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE,
                discount_percent INTEGER,
                valid_until TIMESTAMP,
                assigned_user_id TEXT,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # CUSTOMER COUPONS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS customer_coupons (
                id SERIAL PRIMARY KEY,
                card_id TEXT,
                coupon_type TEXT,
                expires_at TIMESTAMP,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # CAMPAIGNS
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                badge TEXT,
                img_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # SAFE COLUMN ADDITIONS
        columns_to_add = [
            ("sales", "is_test", "BOOLEAN DEFAULT FALSE"),
            ("sales", "bank_fee", "DECIMAL(10,2) DEFAULT 0"),
            ("sales", "net_total", "DECIMAL(10,2) DEFAULT 0"),
            ("sales", "cogs", "DECIMAL(10,2) DEFAULT 0"),
            ("sales", "status", "TEXT DEFAULT 'COMPLETED'"),

            ("finance", "is_test", "BOOLEAN DEFAULT FALSE"),
            ("finance", "is_deleted", "BOOLEAN DEFAULT FALSE"),
            ("finance", "deleted_by", "TEXT"),
            ("finance", "deleted_at", "TIMESTAMP"),
            ("finance", "subject", "TEXT"),
            ("finance", "sale_id", "INTEGER"),

            ("logs", "details", "TEXT"),
            ("logs", "ip", "TEXT"),
            ("notifications", "is_read", "BOOLEAN DEFAULT FALSE"),
            ("promo_codes", "is_used", "BOOLEAN DEFAULT FALSE"),
            ("customer_coupons", "is_used", "BOOLEAN DEFAULT FALSE"),
            ("z_reports", "total_cogs", "DECIMAL(10,2) DEFAULT 0"),
        ]

        for tbl, col, dtype in columns_to_add:
            exists = s.execute(text("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_name=:t AND column_name=:c
            """), {"t": tbl, "c": col}).fetchone()

            if not exists:
                try:
                    s.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {dtype}"))
                    logger.info(f"Added column {tbl}.{col}")
                except Exception as e:
                    logger.warning(f"Column add {tbl}.{col} failed: {e}")

        # DEFAULT SETTINGS
        s.execute(text("""
            INSERT INTO settings (key, value)
            VALUES ('current_shift_status', 'Closed')
            ON CONFLICT DO NOTHING
        """))

        # DEFAULT ADMIN
        existing_admin = s.execute(text("SELECT 1 FROM users WHERE username='admin'")).fetchone()
        if not existing_admin:
            import bcrypt
            admin_pass = os.environ.get("ADMIN_PASS", "admin123")
            p_hash = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
            s.execute(text("""
                INSERT INTO users (username, password, role)
                VALUES ('admin', :p, 'admin')
            """), {"p": p_hash})

        s.commit()

    return True
