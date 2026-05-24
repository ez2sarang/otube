"""PostgreSQL connection for stt_analysis schema"""
import psycopg2
import psycopg2.extras
import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "54322")),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "dbname": os.getenv("DB_NAME", "postgres"),
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def execute(sql, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()

def query(sql, params=None):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None
