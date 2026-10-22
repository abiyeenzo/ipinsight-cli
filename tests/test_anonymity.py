from src import anonymity_check
from src.http_client import NetworkUnavailableError, ProviderTimeoutError
from src.models import (
    STATUS_INDETERMINATE,
    STATUS_INDICATORS,
    STATUS_NO_INDICATOR,
    TEXT_INDETERMINATE,
    TEXT_NO_INDICATOR,
)

TOR_LIST = "# commentaire\n185.220.101.1\n2001:db8::1\nnot-an-ip\n\n"


def _json(payload):
    return lambda _url, _t: payload


def _text(body):
    return lambda _url, _t: body


def _fail(exc):
    def raiser(_url, _t):
        raise exc

    return raiser


def test_vpn_and_hosting_indicators():
    payload = {"is_vpn": True, "is_proxy": False, "is_tor": False, "is_datacenter": True}
    result = anonymity_check.check("8.8.8.8", fetch_json=_json(payload), fetch_text=_text(TOR_LIST))
    assert result.status == STATUS_INDICATORS
    lines = result.summary_lines()
    assert "VPN : probablement détecté" in lines
    assert "Hébergement : indicateur détecté" in lines
    assert not any("Proxy" in line for line in lines)


def test_proxy_indicator():
    payload = {"is_vpn": False, "is_proxy": True, "is_tor": False, "is_datacenter": False}
    result = anonymity_check.check("8.8.8.8", fetch_json=_json(payload), fetch_text=_text(TOR_LIST))
    assert result.summary_lines() == ["Proxy : probablement détecté"]


def test_tor_detected_from_exit_list_only():
    result = anonymity_check.check("185.220.101.1", fetch_json=_fail(NetworkUnavailableError("x")), fetch_text=_text(TOR_LIST))
    assert result.tor is True
    assert result.summary_lines() == ["Tor : indicateur détecté"]
    assert result.errors and "ipapi.is" in result.errors[0]


def test_tor_ipv6_normalisation():
    result = anonymity_check.check("2001:0db8:0:0:0:0:0:1", fetch_json=_fail(NetworkUnavailableError("x")), fetch_text=_text(TOR_LIST))
    assert result.tor is True


def test_no_indicator_wording():
    payload = {"is_vpn": False, "is_proxy": False, "is_tor": False, "is_datacenter": False}
    result = anonymity_check.check("8.8.8.8", fetch_json=_json(payload), fetch_text=_text(TOR_LIST))
    assert result.status == STATUS_NO_INDICATOR
    assert result.summary_lines() == [TEXT_NO_INDICATOR]
    # jamais présenté comme une absence prouvée dans le JSON
    assert result.json_flag(result.vpn) is None


def test_all_sources_down_is_indeterminate():
    result = anonymity_check.check(
        "8.8.8.8", fetch_json=_fail(ProviderTimeoutError("lent")), fetch_text=_fail(NetworkUnavailableError("off"))
    )
    assert result.status == STATUS_INDETERMINATE
    assert result.summary_lines() == [TEXT_INDETERMINATE]
    assert len(result.errors) == 2
    assert result.vpn is None and result.tor is None


def test_response_without_flags_is_indeterminate():
    result = anonymity_check.check("8.8.8.8", fetch_json=_json({"ip": "8.8.8.8"}), fetch_text=_fail(NetworkUnavailableError("off")))
    assert result.status == STATUS_INDETERMINATE
    assert any("indicateurs VPN" in e for e in result.errors)


def test_provider_error_field():
    result = anonymity_check.check("8.8.8.8", fetch_json=_json({"error": "quota"}), fetch_text=_text("\n"))
    assert result.status == STATUS_INDETERMINATE
    assert any("quota" in e for e in result.errors)


def test_parse_tor_exit_list_ignores_garbage():
    assert anonymity_check.parse_tor_exit_list(TOR_LIST) == {"185.220.101.1", "2001:db8::1"}
