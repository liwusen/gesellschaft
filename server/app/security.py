import base64
import hashlib
import hmac
import json
import secrets
import time


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def new_agent_token() -> str:
    return "GLS-" + secrets.token_hex(20)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_payload(payload: dict, secret: str, ttl_seconds: int) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl_seconds
    raw = _b64e(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(secret.encode("utf-8"), raw.encode(), hashlib.sha256).digest())
    return f"GLA-{raw}.{sig}"


def verify_payload(token: str, secret: str) -> dict | None:
    try:
        if not token.startswith("GLA-"):
            return None
        raw, sig = token[len("GLA-"):].split(".", 1)
        expect = _b64e(hmac.new(secret.encode("utf-8"), raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expect):
            return None
        payload = json.loads(_b64d(raw))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def make_cookie(value: str, secret: str, ttl_seconds: int) -> str:
    """签名的 cookie/state 值(与账号 Token 同构,去前缀)。"""
    return sign_payload({"v": value}, secret, ttl_seconds)[len("GLA-"):]


def read_cookie(cookie: str, secret: str) -> str | None:
    payload = verify_payload(f"GLA-{cookie}", secret)
    return payload.get("v") if payload else None


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        recent = [t for t in self._hits.get(key, []) if now - t < self.window]
        if len(recent) >= self.max_events:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True
