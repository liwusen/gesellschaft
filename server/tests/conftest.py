import itertools
import sqlite3
import sys
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app import security  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

_gh_id = itertools.count(10001)


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        secret_key="test-secret-key",
        admin_token="test-admin-token",
        oauth_client_id="cid",
        oauth_client_secret="csec",
        public_base_url="http://testserver",
        agent_write_limit=3,
        agent_write_window=3600,
        publish_limit=5,
        publish_window=86400,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _db_file(client) -> str:
    return client.app.state.settings.db_path


def seed_user(client, login="alice", banned=0) -> int:
    conn = sqlite3.connect(_db_file(client))
    cur = conn.execute(
        "INSERT INTO users(github_id, login, avatar_url, banned) VALUES(?,?,?,?)",
        (next(_gh_id), login, "", banned),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def gla_headers(client, user_id: int) -> dict:
    token = security.sign_payload(
        {"uid": user_id, "kind": "account"},
        client.app.state.settings.secret_key,
        3600,
    )
    return {"Authorization": f"Bearer {token}"}


def make_agent(client, owner_id: int, name="bot", revoked=0):
    token = security.new_agent_token()
    conn = sqlite3.connect(_db_file(client))
    cur = conn.execute(
        "INSERT INTO agents(owner_id, name, persona, token_hash, revoked)"
        " VALUES(?,?,?,?,?)",
        (owner_id, name, "", security.sha256_hex(token), revoked),
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid, token


def gls_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def seed_thread(client, author_user_id: int, title="hello", content="world",
                category_slug="chat") -> int:
    conn = sqlite3.connect(_db_file(client))
    cat = conn.execute(
        "SELECT id FROM categories WHERE slug=?", (category_slug,)
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO threads(category_id, author_user_id, title, content)"
        " VALUES(?,?,?,?)",
        (cat, author_user_id, title, content),
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def seed_reply(client, author_user_id: int, thread_id: int, content="hi",
               parent_reply_id=None) -> int:
    conn = sqlite3.connect(_db_file(client))
    cur = conn.execute(
        "INSERT INTO replies(thread_id, parent_reply_id, author_user_id, content)"
        " VALUES(?,?,?,?)",
        (thread_id, parent_reply_id, author_user_id, content),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def set_flag(client, key: str, value: str) -> None:
    conn = sqlite3.connect(_db_file(client))
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?,?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def admin_login(client) -> None:
    resp = client.post("/admin/login", json={"token": "test-admin-token"})
    assert resp.status_code == 200
