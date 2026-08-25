"""浏览器冒烟:造数据后逐页截图验证。"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

settings = Settings(
    db_path="data/gesellschaft.db",
    secret_key="smoke-secret",
    admin_token="dev-admin-token",
    oauth_client_id="cid",
    oauth_client_secret="csec",
)
app = create_app(settings)

# 直接往同一个 SQLite 里造种子数据(服务器进程持有 WAL 连接,可并发写)
conn = sqlite3.connect("data/gesellschaft.db")
cur = conn.execute(
    "INSERT OR IGNORE INTO users(github_id, login) VALUES(90001, 'allenlee')")
uid = cur.lastrowid or 1
conn.commit()
row = conn.execute("SELECT id FROM users WHERE github_id=90001").fetchone()
uid = row[0]
cat = conn.execute("SELECT id FROM categories WHERE slug='tech'").fetchone()[0]
for i in range(3):
    conn.execute(
        "INSERT INTO threads(category_id, author_user_id, title, content)"
        " VALUES(?,?,?,?)",
        (cat, uid, f"冒烟测试帖子 {i+1}",
         "这是 Gesellschaft 冒烟测试的正文内容。"))
conn.commit()
conn.close()

with TestClient(app) as c:
    print("threads:", c.get("/threads").json()["total"])
