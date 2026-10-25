import pytest

from src import analysis, rdap
from src.http_client import NetworkUnavailableError, ProviderError, ProviderResponseError
from src.models import GeoResult

SAMPLE_RDAP = {
    "objectClassName": "ip network",
    "handle": "NET-8-8-8-0-2",
    "startAddress": "8.8.8.0",
    "endAddress": "8.8.8.255",
    "ipVersion": "v4",
    "name": "GOGL",
    "type": "DIRECT ALLOCATION",
    "country": "us",
    "port43": "whois.arin.net",
    "cidr0_cidrs": [{"v4prefix": "8.8.8.0", "length": 24}],
    "events": [
        {"eventAction": "registration", "eventDate": "2014-03-14T16:52:05Z"},
        {"eventAction": "last changed", "eventDate": "2023-12-28T17:24:56Z"},
    ],
    "entities": [
        {
            "objectClassName": "entity",
            "handle": "GOGL",
            "roles": ["registrant"],
            "vcardArray": [
                "vcard",
                [
                    ["version", {}, "text", "4.0"],
                    ["fn", {}, "text", "Google LLC"],
                ],
            ],
            "entities": [
                {
                    "objectClassName": "entity",
                    "handle": "ABUSE5250-ARIN",
                    "roles": ["abuse", "technical"],
                    "vcardArray": [
                        "vcard",
                        [
                            ["version", {}, "text", "4.0"],
                            ["fn", {}, "text", "Abuse"],
                            ["email", {}, "text", "network-abuse@google.com"],
                        ],
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def fresh_rdap_cache():
    rdap.clear_cache()


def test_parse_complete_rdap_payload():
    estimate = GeoResult(ip="8.8.8.8", country_code="US")
    info = rdap.parse_response(SAMPLE_RDAP, estimate)
    assert info.handle == "NET-8-8-8-0-2"
    assert info.name == "GOGL"
    assert info.cidr == "8.8.8.0/24"
    assert info.range_text == "8.8.8.0 - 8.8.8.255"
    assert info.country == "US"
    assert info.registry == "ARIN"
    assert info.registrant == "Google LLC"
    assert info.abuse_email == "network-abuse@google.com"
    assert info.allocation_type == "DIRECT ALLOCATION"
    assert info.registration_date == "2014-03-14"
    assert info.last_changed == "2023-12-28"
    assert info.country_matches_estimate is True
    assert any("entité administrative" in note for note in info.notes)


def test_country_mismatch_adds_administrative_note():
    estimate = GeoResult(ip="8.8.8.8", country_code="FR")
    info = rdap.parse_response(SAMPLE_RDAP, estimate)
    assert info.country_matches_estimate is False
    assert any("Écart administratif" in note for note in info.notes)


def test_cidr_fallback_from_start_and_end_addresses():
    payload = {
        "handle": "RIPE-BLOCK",
        "startAddress": "193.0.0.0",
        "endAddress": "193.0.7.255",
        "country": "NL",
        "port43": "whois.ripe.net",
    }
    info = rdap.parse_response(payload)
    assert info.cidr == "193.0.0.0/21"
    assert info.registry == "RIPE NCC"
    assert info.country == "NL"


@pytest.mark.parametrize(
    "port43,expected",
    [
        ("whois.arin.net", "ARIN"),
        ("whois.ripe.net", "RIPE NCC"),
        ("whois.apnic.net", "APNIC"),
        ("whois.lacnic.net", "LACNIC"),
        ("whois.afrinic.net", "AFRINIC"),
    ],
)
def test_registry_labels(port43, expected):
    info = rdap.parse_response({"handle": "H1", "port43": port43})
    assert info.registry == expected


def test_lookup_caches_response_for_same_ip():
    calls = []

    def fetch(url, _t):
        calls.append(url)
        return SAMPLE_RDAP

    rdap.lookup("8.8.8.8", fetch_json=fetch)
    rdap.lookup("8.8.8.8", fetch_json=fetch)
    assert len(calls) == 1
    assert calls[0] == "https://rdap.org/ip/8.8.8.8"


def test_lookup_refuses_non_public_and_invalid_ip(no_network):
    with pytest.raises(ProviderError):
        rdap.lookup("192.168.1.1", fetch_json=no_network)
    with pytest.raises(ProviderError):
        rdap.lookup("not-an-ip", fetch_json=no_network)


@pytest.mark.parametrize("payload", [{"errorCode": 404, "title": "Not Found"}, {}, {"objectClassName": "ip network"}])
def test_invalid_or_error_rdap_payloads_rejected(payload):
    with pytest.raises(ProviderResponseError):
        rdap.parse_response(payload)


def test_analysis_with_rdap_and_non_fatal_failure(geo_payload):
    def fetch(url, _t):
        if "rdap.org" in url:
            return SAMPLE_RDAP
        if "ipwho.is" in url:
            return geo_payload
        return {"is_vpn": False, "is_proxy": False, "is_tor": False, "is_datacenter": False}

    report = analysis.analyze("8.8.8.8", with_rdap=True, fetch_json=fetch, fetch_text=lambda _u, _t: "")
    assert report.rdap is not None
    assert report.rdap.cidr == "8.8.8.0/24"
    assert report.to_dict()["rdap"]["abuse_email"] == "network-abuse@google.com"

    def fetch_failing_rdap(url, _t):
        if "rdap.org" in url:
            raise NetworkUnavailableError("rdap indisponible")
        return fetch(url, _t)

    rdap.clear_cache()
    report_fail = analysis.analyze("8.8.8.8", with_rdap=True, fetch_json=fetch_failing_rdap, fetch_text=lambda _u, _t: "")
    assert report_fail.rdap is None
    assert any(e.startswith("RDAP :") for e in report_fail.source_errors)
