import json

import pytest

import iotclient
from iotclient import IotClient


class _FakeResp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return json.loads(self._body)

    @property
    def text(self):
        return self._body


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    #skip the backoff waits so tests run instantly
    monkeypatch.setattr(iotclient, "sleep", lambda s: None)


def _install_responses(monkeypatch, responses):
    """Make requests.post return each item of `responses` in turn.

    An item may be a _FakeResp (returned) or an Exception subclass instance
    (raised) to simulate a network error. Records the call count.
    """
    state = {"n": 0}

    def fake_post(url, data=None, headers=None, timeout=None):
        i = state["n"]
        state["n"] += 1
        item = responses[i]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(iotclient.requests, "post", fake_post)
    return state


def test_get_token_success_first_try(monkeypatch):
    state = _install_responses(monkeypatch, [
        _FakeResp(200, '{"access_token": "tok123", "expires_in": 300}'),
    ])
    c = IotClient("id", "secret", "")
    token = c.get_token()
    assert token["access_token"] == "tok123"
    assert state["n"] == 1


def test_get_token_is_cached(monkeypatch):
    state = _install_responses(monkeypatch, [
        _FakeResp(200, '{"access_token": "tok123", "expires_in": 300}'),
    ])
    c = IotClient("id", "secret", "")
    c.get_token()
    #second call must reuse the cached token, not hit the network again
    c.get_token()
    assert state["n"] == 1


def test_get_token_401_fast_fails(monkeypatch):
    #a bad key won't fix itself by retrying, so we must stop after one attempt
    state = _install_responses(monkeypatch, [
        _FakeResp(401, '{"error": "invalid_client"}'),
    ] * iotclient.TOKEN_MAX_ATTEMPTS)
    c = IotClient("id", "secret", "")
    with pytest.raises(RuntimeError):
        c.get_token()
    assert state["n"] == 1


def test_get_token_retries_429_then_succeeds(monkeypatch):
    state = _install_responses(monkeypatch, [
        _FakeResp(429, '{"error": "rate"}'),
        _FakeResp(429, '{"error": "rate"}'),
        _FakeResp(200, '{"access_token": "ok", "expires_in": 300}'),
    ])
    c = IotClient("id", "secret", "")
    token = c.get_token()
    assert token["access_token"] == "ok"
    assert state["n"] == 3


def test_get_token_exhausts_on_persistent_5xx(monkeypatch):
    state = _install_responses(monkeypatch, [
        _FakeResp(500, '{"error": "boom"}'),
    ] * iotclient.TOKEN_MAX_ATTEMPTS)
    c = IotClient("id", "secret", "")
    with pytest.raises(RuntimeError):
        c.get_token()
    assert state["n"] == iotclient.TOKEN_MAX_ATTEMPTS


def test_get_token_retries_network_error(monkeypatch):
    state = _install_responses(monkeypatch, [
        iotclient.requests.RequestException("conn reset"),
        _FakeResp(200, '{"access_token": "net", "expires_in": 300}'),
    ])
    c = IotClient("id", "secret", "")
    token = c.get_token()
    assert token["access_token"] == "net"
    assert state["n"] == 2


def test_get_token_200_without_access_token_is_retried(monkeypatch):
    #a 200 with no access_token is treated as retryable, then raises if it never appears
    state = _install_responses(monkeypatch, [
        _FakeResp(200, '{"expires_in": 300}'),
    ] * iotclient.TOKEN_MAX_ATTEMPTS)
    c = IotClient("id", "secret", "")
    with pytest.raises(RuntimeError):
        c.get_token()
    assert state["n"] == iotclient.TOKEN_MAX_ATTEMPTS
