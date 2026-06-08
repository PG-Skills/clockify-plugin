"""Helper HTTP JSON sobre urllib (stdlib) — substitui httpx do servidor.

`request_json` faz GET/POST com header X-Api-Key, querystring opcional e corpo JSON,
e levanta `HttpError(status)` em respostas >= 400 (equivalente ao raise_for_status)."""

import json
import urllib.error
import urllib.parse
from urllib.request import Request, urlopen  # urlopen é patchado nos testes


class HttpError(Exception):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def request_json(method, url, *, api_key, params=None, body=None, timeout=30.0):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {"X-Api-Key": api_key}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise HttpError(e.code, detail) from e
