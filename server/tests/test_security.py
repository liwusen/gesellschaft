from app import security


def test_agent_token_format():
    t = security.new_agent_token()
    assert t.startswith("GLS-")
    assert len(t) == 44  # GLS- + 40 hex chars


def test_sign_verify_roundtrip():
    tok = security.sign_payload({"uid": 7, "kind": "account"}, "s3cret", 60)
    assert security.verify_payload(tok, "s3cret")["uid"] == 7


def test_verify_rejects_tamper_and_wrong_key():
    tok = security.sign_payload({"uid": 7}, "s3cret", 60)
    bad = tok[:-1] + ("A" if tok[-1] != "A" else "B")
    assert security.verify_payload(bad, "s3cret") is None
    assert security.verify_payload(tok, "other") is None


def test_verify_rejects_expired_and_wrong_prefix():
    expired = security.sign_payload({"uid": 1}, "k", -10)
    assert security.verify_payload(expired, "k") is None
    assert security.verify_payload("XXX-abc.def", "k") is None


def test_cookie_roundtrip():
    c = security.make_cookie("cli|9000|abc", "k", 60)
    assert security.read_cookie(c, "k") == "cli|9000|abc"
    assert security.read_cookie(c + "x", "k") is None


def test_limiter_sliding_window():
    lim = security.SlidingWindowLimiter(2, 3600)
    assert lim.allow("a")
    assert lim.allow("a")
    assert not lim.allow("a")
    assert lim.allow("b")


def test_sha256_hex_accepts_str_and_bytes():
    assert security.sha256_hex("abc") == security.sha256_hex(b"abc")
