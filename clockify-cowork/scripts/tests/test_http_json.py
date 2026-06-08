import io
import json

import pytest

import http_json


class _FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._raw = json.dumps(payload).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_request_json_get_ok(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["api_key"] = req.headers.get("X-api-key")
        return _FakeResp(200, {"name": "Ana"})

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    data = http_json.request_json(
        "GET", "https://api.clockify.me/api/v1/user", api_key="KEY"
    )
    assert data == {"name": "Ana"}
    assert captured["method"] == "GET"
    assert captured["api_key"] == "KEY"


def test_request_json_params_in_querystring(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResp(200, [])

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    http_json.request_json(
        "GET",
        "https://x/y",
        api_key="K",
        params={"name": "Proj X", "strict-name-search": "true"},
    )
    assert (
        "name=Proj+X" in captured["url"]
        and "strict-name-search=true" in captured["url"]
    )


def test_request_json_post_sends_body(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = req.data
        captured["ct"] = req.headers.get("Content-type")
        return _FakeResp(201, {"id": "e1"})

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    out = http_json.request_json("POST", "https://x/y", api_key="K", body={"a": 1})
    assert out == {"id": "e1"}
    assert json.loads(captured["body"]) == {"a": 1}
    assert captured["ct"] == "application/json"


def test_request_json_raises_httperror_on_4xx(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"")
        )

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    with pytest.raises(http_json.HttpError) as ei:
        http_json.request_json("GET", "https://x/y", api_key="K")
    assert ei.value.status == 401
