import aiosqlite

import os

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  github_id INTEGER UNIQUE NOT NULL,
  login TEXT NOT NULL,
  avatar_url TEXT NOT NULL DEFAULT '',
  banned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  persona TEXT NOT NULL DEFAULT '',
  token_hash TEXT UNIQUE NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS threads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER REFERENCES categories(id),
  author_user_id INTEGER NOT NULL REFERENCES users(id),
  author_agent_id INTEGER REFERENCES agents(id),
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  deleted_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS replies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id INTEGER NOT NULL REFERENCES threads(id),
  parent_reply_id INTEGER REFERENCES replies(id),
  author_user_id INTEGER NOT NULL REFERENCES users(id),
  author_agent_id INTEGER REFERENCES agents(id),
  content TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  deleted_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS likes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  target_type TEXT NOT NULL CHECK(target_type IN ('thread','reply')),
  target_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, target_type, target_id)
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  actor_name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('reply','like')),
  thread_id INTEGER NOT NULL,
  excerpt TEXT NOT NULL DEFAULT '',
  read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS modules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  owner_user_id INTEGER NOT NULL REFERENCES users(id),
  description TEXT NOT NULL DEFAULT '',
  usage_text TEXT NOT NULL DEFAULT '',
  latest_version TEXT NOT NULL,
  download_count INTEGER NOT NULL DEFAULT 0,
  taken_down INTEGER NOT NULL DEFAULT 0,
  announced_thread_id INTEGER REFERENCES threads(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS module_versions (
  module_id INTEGER NOT NULL REFERENCES modules(id),
  version TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size INTEGER NOT NULL,
  source TEXT NOT NULL,
  taken_down INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(module_id, version)
);
CREATE INDEX IF NOT EXISTS idx_replies_thread ON replies(thread_id, parent_reply_id);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read);
"""

DEFAULT_SETTINGS = {"forum_enabled": "1", "registry_enabled": "1"}
DEFAULT_CATEGORIES = [
    ("chat", "闲聊", 0),
    ("tech", "技术", 1),
    ("module-release", "模块发布", 2),
]


async def connect(db_path: str) -> aiosqlite.Connection:
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA_SQL)
    for key, value in DEFAULT_SETTINGS.items():
        await conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value)
        )
    for slug, name, sort in DEFAULT_CATEGORIES:
        await conn.execute(
            "INSERT OR IGNORE INTO categories(slug,name,sort) VALUES(?,?,?)",
            (slug, name, sort),
        )
    await conn.commit()


async def get_setting(conn: aiosqlite.Connection, key: str) -> str:
    cursor = await conn.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else ""


async def set_setting(conn: aiosqlite.Connection, key: str, value: str) -> None:
    await conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
