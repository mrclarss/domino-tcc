import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    bio TEXT NOT NULL DEFAULT '',
    avatar TEXT NOT NULL DEFAULT 'rosa',
    avatar_ext TEXT,
    banner TEXT NOT NULL DEFAULT 'teal',
    email_verified INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    notify_on INTEGER NOT NULL DEFAULT 1,
    sound_on INTEGER NOT NULL DEFAULT 1,
    theme TEXT NOT NULL DEFAULT 'light',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_codes (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    purpose TEXT NOT NULL,
    code TEXT NOT NULL,
    payload TEXT,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    tries INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS friendships (
    id INTEGER PRIMARY KEY,
    requester_id INTEGER NOT NULL REFERENCES users(id),
    addressee_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (requester_id, addressee_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL,
    difficulty TEXT,
    hand_size INTEGER NOT NULL,
    status TEXT NOT NULL,
    room_code TEXT UNIQUE,
    player1_id INTEGER NOT NULL REFERENCES users(id),
    player2_id INTEGER REFERENCES users(id),
    state_json TEXT,
    stats_applied INTEGER NOT NULL DEFAULT 0,
    winner_slot INTEGER,
    p1_points INTEGER NOT NULL DEFAULT 0,
    p2_points INTEGER NOT NULL DEFAULT 0,
    p1_pips INTEGER NOT NULL DEFAULT 0,
    p2_pips INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id),
    player_slot INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id),
    player_slot INTEGER NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        os.makedirs(os.path.dirname(current_app.config["DATABASE"]), exist_ok=True)
        connection = sqlite3.connect(current_app.config["DATABASE"], timeout=8)
        connection.row_factory = sqlite3.Row
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 4000")
        g.db = connection
    return g.db


def close_db(_error=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@contextmanager
def transaction():
    connection = get_db()
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def init_db(app) -> None:
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["AVATARS"], exist_ok=True)
    with app.app_context():
        connection = get_db()
        connection.executescript(SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(email_codes)")}
        if "tries" not in columns:
            connection.execute("ALTER TABLE email_codes ADD COLUMN tries INTEGER NOT NULL DEFAULT 0")
        connection.commit()
        app.teardown_appcontext(close_db)
