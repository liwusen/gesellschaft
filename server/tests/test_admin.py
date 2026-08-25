from conftest import (admin_login, gla_headers, make_agent, seed_thread,
                      seed_user, set_flag)


def test_admin_endpoints_require_cookie(client):
    assert client.get("/admin/api/stats").status_code == 401
    bad = client.post("/admin/login", json={"token": "wrong"})
    assert bad.status_code == 401


def test_toggle_forum_via_settings(client):
    admin_login(client)
    current = client.get("/admin/api/settings").json()
    assert current == {"forum_enabled": True, "registry_enabled": True}
    patched = client.patch("/admin/api/settings",
                           json={"forum_enabled": False}).json()
    assert patched["forum_enabled"] is False
    uid = seed_user(client, "toggled")
    assert client.get("/threads").status_code == 403
    client.patch("/admin/api/settings", json={"forum_enabled": True})
    assert client.get("/threads").status_code == 200


def test_stats_counts(client):
    admin_login(client)
    uid = seed_user(client, "stats")
    _, _ = make_agent(client, uid)
    seed_thread(client, uid)
    stats = client.get("/admin/api/stats").json()
    assert stats["users"] >= 1
    assert stats["agents"] >= 1
    assert stats["threads"] >= 1


def test_soft_delete_thread_and_reply(client):
    admin_login(client)
    uid = seed_user(client, "del")
    tid = seed_thread(client, uid, "待删除")
    ok = client.delete(f"/admin/api/threads/{tid}")
    assert ok.status_code == 200
    assert client.get(f"/threads/{tid}").status_code == 404
    again = client.delete(f"/admin/api/threads/{tid}")
    assert again.status_code == 404


def test_ban_user_blocks_token_immediately(client):
    admin_login(client)
    uid = seed_user(client, "victim")
    headers = gla_headers(client, uid)
    write = client.post("/threads", json={"title": "t", "content": "c"},
                        headers=headers)
    assert write.status_code == 201
    ban = client.post(f"/admin/api/users/{uid}/ban", json={"banned": True})
    assert ban.status_code == 200
    blocked = client.post("/threads", json={"title": "t2", "content": "c"},
                          headers=headers)
    assert blocked.status_code == 403
    unban = client.post(f"/admin/api/users/{uid}/ban", json={"banned": False})
    assert unban.status_code == 200


def test_revoke_agent_kills_token(client):
    admin_login(client)
    uid = seed_user(client, "agentowner")
    aid, tok = make_agent(client, uid)
    assert client.post("/replies-x", headers={"Authorization":
                                              f"Bearer {tok}"}).status_code != 200
    rv = client.post(f"/admin/api/agents/{aid}/revoke")
    assert rv.status_code == 200
    # 吊销后写操作被拒(401)
    resp = client.post(
        "/threads",
        json={"title": "t", "content": "c"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 401


def test_category_crud(client):
    admin_login(client)
    add = client.post("/admin/api/categories",
                      json={"slug": "games", "name": "游戏", "sort": 5})
    assert add.status_code == 201
    dup = client.post("/admin/api/categories",
                      json={"slug": "games", "name": "重复", "sort": 6})
    assert dup.status_code == 409
    patch = client.patch("/admin/api/categories/games",
                         json={"sort": 1})
    assert patch.status_code == 200
    cats = client.get("/categories").json()["categories"]
    games = [c for c in cats if c["slug"] == "games"]
    assert games and games[0]["name"] == "游戏"


def test_users_listing(client):
    admin_login(client)
    seed_user(client, "listed")
    users = client.get("/admin/api/users").json()["users"]
    assert any(u["login"] == "listed" for u in users)
