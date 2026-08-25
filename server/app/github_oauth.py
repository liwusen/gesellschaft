import urllib.parse

import httpx

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user",
        "state": state,
    }
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


async def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> str | None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json().get("access_token")


async def fetch_user(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    return {"github_id": data["id"], "login": data["login"], "avatar_url": data.get("avatar_url", "")}
