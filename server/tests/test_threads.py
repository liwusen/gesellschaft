from conftest import (gla_headers, gls_headers, make_agent, seed_reply,
                      seed_thread, seed_user, set_flag)


def test_categories_seeded(client):
    rows = client.get("/categories").json()["categories"]
    slugs = [r["slug"] for r in rows]
    assert {"chat", "tech", "module-release"} <= set(slugs)


def test_list_threads_json_and_text(client):
    uid = seed_user(client, "carol")
    seed_thread(client, uid, "第一帖")
    seed_thread(client, uid, "第二帖")
    js = client.get("/threads").json()
    assert js["total"] >= 2
    assert js["threads"][0]["title"] == "第二帖"
    txt = client.get("/threads?format=text").text
    assert "第一帖" in txt and "第二帖" in txt


def test_list_filter_category(client):
    uid = seed_user(client, "carl")
    seed_thread(client, uid, "技术帖", category_slug="tech")
    seed_thread(client, uid, "闲聊帖", category_slug="chat")
    js = client.get("/threads?category=tech").json()
    titles = [t["title"] for t in js["threads"]]
    assert titles == ["技术帖"]


def test_detail_nesting_and_pagination(client):
    uid = seed_user(client, "dave")
    tid = seed_thread(client, uid)
    top = seed_reply(client, uid, tid, "顶层楼")
    seed_reply(client, uid, tid, "子楼", parent_reply_id=top)
    d = client.get(f"/threads/{tid}").json()
    assert len(d["replies"]) == 1
    assert d["replies"][0]["content"] == "顶层楼"
    assert d["replies"][0]["children"][0]["content"] == "子楼"
    txt = client.get(f"/threads/{tid}?format=text").text
    assert "顶层楼" in txt


def test_detail_404(client):
    assert client.get("/threads/999").status_code == 404


def test_create_thread_with_account_and_agent(client):
    uid = seed_user(client, "erin")
    r = client.post("/threads",
                    json={"title": "T", "content": "C", "category": "tech"},
                    headers=gla_headers(client, uid))
    assert r.status_code == 201
    assert r.json()["author"] == "@erin"

    _, tok = make_agent(client, uid, name="faust-bot")
    r2 = client.post("/threads",
                     json={"title": "T2", "content": "C2", "category": "chat"},
                     headers=gls_headers(tok))
    assert r2.status_code == 201
    listing = client.get("/threads").json()["threads"]
    by_title = {t["title"]: t for t in listing}
    assert by_title["T2"]["author"] == "faust-bot(@erin)"


def test_create_thread_requires_auth_and_valid_category(client):
    assert client.post(
        "/threads", json={"title": "x", "content": "y"}
    ).status_code == 401
    uid = seed_user(client, "frank")
    bad = client.post("/threads",
                      json={"title": "x", "content": "y", "category": "nope"},
                      headers=gla_headers(client, uid))
    assert bad.status_code == 400


def test_write_rate_limit(client):
    uid = seed_user(client, "grace")
    headers = gla_headers(client, uid)
    for i in range(3):  # fixture limit = 3
        ok = client.post("/threads",
                         json={"title": f"t{i}", "content": "c"},
                         headers=headers)
        assert ok.status_code == 201
    blocked = client.post("/threads",
                          json={"title": "t9", "content": "c"}, headers=headers)
    assert blocked.status_code == 429


def test_reply_notifies_author(client):
    anna = seed_user(client, "anna")
    ben = seed_user(client, "ben")
    tid = seed_thread(client, anna, "求帮助")
    r = client.post(f"/threads/{tid}/replies", json={"content": "我来帮你"},
                    headers=gla_headers(client, ben))
    assert r.status_code == 201
    notes = client.get("/me/notifications",
                       headers=gla_headers(client, anna)).json()["items"]
    assert notes[0]["type"] == "reply"
    assert notes[0]["actor_name"] == "@ben"
    assert notes[0]["excerpt"] == "我来帮你"
    # 自己回复自己不产生通知
    client.post(f"/threads/{tid}/replies", json={"content": "self"},
                headers=gla_headers(client, anna))
    notes = client.get("/me/notifications",
                       headers=gla_headers(client, anna)).json()["items"]
    assert len(notes) == 1


def test_nested_depth_limited(client):
    uid = seed_user(client, "heidi")
    tid = seed_thread(client, uid)
    top = seed_reply(client, uid, tid, "top")
    child = seed_reply(client, uid, tid, "child", parent_reply_id=top)
    deep = client.post(f"/threads/{tid}/replies",
                       json={"content": "too deep", "parent_reply_id": child},
                       headers=gla_headers(client, uid))
    assert deep.status_code == 400


def test_like_toggle_and_notification(client):
    a = seed_user(client, "ivan")
    b = seed_user(client, "judy")
    tid = seed_thread(client, a)
    h = gla_headers(client, b)
    first = client.post(f"/threads/{tid}/like", headers=h)
    assert first.json() == {"liked": True, "likes": 1}
    second = client.post(f"/threads/{tid}/like", headers=h)
    assert second.json() == {"liked": False, "likes": 0}
    rid = seed_reply(client, a, tid, "r1")
    rl = client.post(f"/replies/{rid}/like", headers=h).json()
    assert rl == {"liked": True, "likes": 1}
    notes = client.get("/me/notifications",
                       headers=gla_headers(client, a)).json()["items"]
    assert any(n["type"] == "like" for n in notes)


def test_forum_disabled_blocks_reads_and_writes(client):
    uid = seed_user(client, "ken")
    set_flag(client, "forum_enabled", "0")
    assert client.get("/threads").status_code == 403
    assert client.get("/categories").json()  # categories 不受闸门限制
    w = client.post("/threads", json={"title": "t", "content": "c"},
                    headers=gla_headers(client, uid))
    assert w.status_code == 403
