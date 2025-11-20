import sqlite3
import os


def init_db():
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect("db/users.db", check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            admin BOOLEAN NOT NULL,
            access_token TEXT,
            refresh_token TEXT,
            access_exp INTEGER,
            refresh_exp INTEGER
        )"""
    )
    conn.commit()
    return conn
