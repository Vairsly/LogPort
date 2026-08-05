import sqlite3
from datetime import datetime, timezone

from flask import current_app, g
from argon2 import PasswordHasher


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS servers (
 id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL DEFAULT 22,
 username TEXT NOT NULL, auth_type TEXT NOT NULL CHECK(auth_type IN ('password','private_key')),
 secret_encrypted TEXT NOT NULL, key_passphrase_encrypted TEXT, host_fingerprint TEXT,
 containers TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS export_tasks (
 id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE RESTRICT,
 server_name TEXT NOT NULL, container TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','expired','cancelled')),
 file_path TEXT, file_size INTEGER, error TEXT, created_at TEXT NOT NULL, started_at TEXT,
 finished_at TEXT, expires_at TEXT, worker_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON export_tasks(status, created_at);
"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=30, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    username = current_app.config["ADMIN_USERNAME"]
    password = current_app.config["ADMIN_PASSWORD"]
    if password and not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        db.execute(
            "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
            (username, PasswordHasher().hash(password), utcnow()),
        )
