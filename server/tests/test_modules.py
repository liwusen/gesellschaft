import hashlib

from conftest import gla_headers, set_flag, seed_user


def publish(client, uid, slug="demo-mod", version="", source=b"print('hi')\n",
            description="d", usage_text="u", no_announce="false"):
    data = {"slug": slug, "description": description,
            "usage_text": usage_text, "no_announce": no_announce}
    if version:
        data["version"] = version
    return client.post("/modules", data=data,
                       files={"file": ("m.py", source, "text/x-python")},
                       headers=gla_headers(client, uid))


def test_publish_creates_announce_thread(client):
    uid = seed_user(client, "pub")
    r = publish(client, uid)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["version"] == "1.0.0"
    assert j["announce_thread_id"] is not None
    th = client.get(f"/threads/{j['announce_thread_id']}").json()["thread"]
    assert th["title"].startswith("[模块] demo-mod")
    assert th["category"] == "module-release"


def test_no_announce_flag(client):
    uid = seed_user(client, "quiet")
    j = publish(client, uid, slug="silent-mod", no_announce="true").json()
    assert j["announce_thread_id"] is None


def test_auto_patch_bump_and_version_rules(client):
    uid = seed_user(client, "bump")
    first = publish(client, uid).json()
    assert first["version"] == "1.0.0"
    second = publish(client, uid, slug="demo-mod",
                     source=b"x = 2\n").json()
    assert second["version"] == "1.0.1"
    # 显式版本必须大于当前最新
    lower = publish(client, uid, slug="demo-mod", version="1.0.1")
    assert lower.status_code == 409
    higher = publish(client, uid, slug="demo-mod", version="2.0.0")
    assert higher.status_code == 201
    # 版本不可变:重复版本 409
    dup = publish(client, uid, slug="demo-mod", version="2.0.0")
    assert dup.status_code == 409


def test_only_owner_can_update_module(client):
    owner = seed_user(client, "owner")
    other = seed_user(client, "other")
    publish(client, owner)
    hijack = publish(client, other)
    assert hijack.status_code == 403


def test_slug_and_size_validation(client):
    uid = seed_user(client, "valid")
    bad_slug = publish(client, uid, slug="Bad_Slug!")
    assert bad_slug.status_code == 400
    big = publish(client, uid, slug="big-mod", source=b"a" * 131073)
    assert big.status_code == 400
    not_utf8 = publish(client, uid, slug="bin-mod", source=b"\xff\xfe\x00")
    assert not_utf8.status_code == 400


def test_source_download_and_sha_header(client):
    uid = seed_user(client, "sha")
    src = b"print('hello gesellschaft')\n"
    publish(client, uid, slug="sha-mod", source=src)
    resp = client.get("/modules/sha-mod/source")
    assert resp.status_code == 200
    assert resp.text == src.decode()
    expected_sha = hashlib.sha256(src).hexdigest()
    assert resp.headers["x-module-sha256"] == expected_sha
    meta = client.get("/modules/sha-mod").json()
    assert meta["module"]["download_count"] == 1


def test_find_search_and_mine(client):
    a = seed_user(client, "search-a")
    b = seed_user(client, "search-b")
    publish(client, a, slug="weather-tool", description="天气查询模块")
    publish(client, b, slug="rss-tool", description="RSS 阅读")
    hit = client.get("/modules?q=天气").json()
    assert [m["slug"] for m in hit["modules"]] == ["weather-tool"]
    mine = client.get("/modules?mine=true",
                      headers=gla_headers(client, a)).json()
    assert [m["slug"] for m in mine["modules"]] == ["weather-tool"]
    anon_mine = client.get("/modules?mine=true")
    assert anon_mine.status_code == 401
    txt = client.get("/modules?format=text").text
    assert "weather-tool" in txt and "rss-tool" in txt


def test_takedown_returns_410(client):
    from conftest import admin_login

    uid = seed_user(client, "down")
    publish(client, uid, slug="evil-mod")
    admin_login(client)
    r = client.post("/admin/api/modules/evil-mod/takedown",
                    json={"taken_down": True})
    assert r.status_code == 200
    assert client.get("/modules/evil-mod/source").status_code == 410
    listing = client.get("/modules").json()["modules"]
    assert "evil-mod" not in [m["slug"] for m in listing]


def test_registry_disabled_blocks_all(client):
    uid = seed_user(client, "regoff")
    set_flag(client, "registry_enabled", "0")
    assert publish(client, uid).status_code == 403
    assert client.get("/modules").status_code == 403
