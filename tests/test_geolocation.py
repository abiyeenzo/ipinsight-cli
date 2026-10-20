import copy
import socket
import urllib.error

import pytest

from src import geolocation, http_client
from src.http_client import (
    NetworkUnavailableError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)


def test_complete_response(geo_payload):
    geo = geolocation.parse_response(geo_payload, "8.8.8.8")
    assert (geo.country, geo.country_code, geo.city) == ("United States", "US", "Mountain View")
    assert geo.asn == 15169 and geo.isp == "Google LLC" and geo.domain == "google.com"
    assert geo.timezone == "America/Los_Angeles"
    assert geo.latitude == pytest.approx(37.386, abs=1e-3)
    assert geo.accuracy_radius_km is None  # jamais inventé


def test_incomplete_response_keeps_none():
    geo = geolocation.parse_response({"ip": "8.8.8.8", "success": True, "country": "France"}, "8.8.8.8")
    assert geo.country == "France"
    assert geo.city is None and geo.latitude is None and geo.longitude is None
    assert geo.isp is None and geo.asn is None and geo.timezone is None


def test_invalid_coordinates_are_dropped(geo_payload):
    payload = copy.deepcopy(geo_payload)
    payload["latitude"], payload["longitude"] = 999, "abc"
    geo = geolocation.parse_response(payload, "8.8.8.8")
    assert geo.latitude is None and geo.longitude is None


def test_partial_coordinates_are_dropped(geo_payload):
    payload = copy.deepcopy(geo_payload)
    payload["longitude"] = None
    geo = geolocation.parse_response(payload, "8.8.8.8")
    assert geo.latitude is None and geo.longitude is None


def test_malformed_nested_blocks(geo_payload):
    payload = copy.deepcopy(geo_payload)
    payload["connection"] = "oops"
    payload["timezone"] = None
    geo = geolocation.parse_response(payload, "8.8.8.8")
    assert geo.asn is None and geo.timezone is None


def test_asn_formats():
    assert geolocation._clean_asn("AS15169") == 15169
    assert geolocation._clean_asn("15169") == 15169
    assert geolocation._clean_asn(0) is None
    assert geolocation._clean_asn(True) is None
    assert geolocation._clean_asn("abc") is None


def test_provider_failure_message():
    with pytest.raises(ProviderResponseError, match="Reserved range"):
        geolocation.parse_response({"success": False, "message": "Reserved range"}, "10.0.0.1")


def test_response_without_ip_or_request():
    with pytest.raises(ProviderResponseError):
        geolocation.parse_response({"success": True}, None)


def test_lookup_builds_expected_url(geo_payload):
    seen = []

    def fake(url, timeout):
        seen.append((url, timeout))
        return geo_payload

    geolocation.lookup("8.8.8.8", timeout=3, fetch_json=fake)
    geolocation.lookup(None, timeout=3, fetch_json=fake)
    assert seen[0] == ("https://ipwho.is/8.8.8.8", 3)
    assert seen[1][0] == "https://ipwho.is/"


def test_lookup_propagates_provider_errors():
    def boom(_url, _timeout):
        raise NetworkUnavailableError("hors ligne")

    with pytest.raises(NetworkUnavailableError):
        geolocation.lookup("8.8.8.8", fetch_json=boom)


# --- http_client : erreurs réseau simulées (aucune requête réelle) ---

class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, _n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _patch_urlopen(monkeypatch, behaviour):
    monkeypatch.setattr(http_client.urllib.request, "urlopen", behaviour)


def test_http_refuses_non_https():
    with pytest.raises(ProviderResponseError):
        http_client.get_text("http://ipwho.is/8.8.8.8", 1)


def test_http_timeout(monkeypatch):
    def fake(*_a, **_k):
        raise socket.timeout("timed out")

    _patch_urlopen(monkeypatch, fake)
    with pytest.raises(ProviderTimeoutError):
        http_client.get_text("https://example.com", 1)


def test_http_timeout_wrapped_in_urlerror(monkeypatch):
    def fake(*_a, **_k):
        raise urllib.error.URLError(socket.timeout("timed out"))

    _patch_urlopen(monkeypatch, fake)
    with pytest.raises(ProviderTimeoutError):
        http_client.get_text("https://example.com", 1)


def test_http_no_internet(monkeypatch):
    def fake(*_a, **_k):
        raise urllib.error.URLError(OSError("Network is unreachable"))

    _patch_urlopen(monkeypatch, fake)
    with pytest.raises(NetworkUnavailableError):
        http_client.get_json("https://example.com", 1)


def test_http_rate_limit_and_server_error(monkeypatch):
    def make(code):
        def fake(*_a, **_k):
            raise urllib.error.HTTPError("https://example.com", code, "x", {}, None)

        return fake

    _patch_urlopen(monkeypatch, make(429))
    with pytest.raises(ProviderRateLimitError):
        http_client.get_text("https://example.com", 1)
    _patch_urlopen(monkeypatch, make(503))
    with pytest.raises(ProviderResponseError, match="503"):
        http_client.get_text("https://example.com", 1)


def test_http_invalid_json_and_wrong_type(monkeypatch):
    _patch_urlopen(monkeypatch, lambda *_a, **_k: _FakeResponse(b"<html>"))
    with pytest.raises(ProviderResponseError):
        http_client.get_json("https://example.com", 1)
    _patch_urlopen(monkeypatch, lambda *_a, **_k: _FakeResponse(b"[1, 2]"))
    with pytest.raises(ProviderResponseError):
        http_client.get_json("https://example.com", 1)


def test_http_success(monkeypatch):
    _patch_urlopen(monkeypatch, lambda *_a, **_k: _FakeResponse(b'{"ok": true}'))
    assert http_client.get_json("https://example.com", 1) == {"ok": True}
