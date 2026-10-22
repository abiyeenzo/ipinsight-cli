"""Analyse multi-sources de bout en bout (reponses simulees, aucun reseau reel)."""

import json

import pytest

from src import analysis, cli, geolocation, local_db, reverse_geocode
from src.http_client import NetworkUnavailableError, ProviderError
from tests.mmdb_writer import build_mmdb, city_record

NO_FLAGS = {"is_vpn": False, "is_proxy": False, "is_tor": False, "is_datacenter": False}


def ipwho(lat, lon, code="FR", country="France", city="Paris"):
    return {"ip": "8.8.8.8", "success": True, "country": country, "country_code": code, "region": "Ile-de-France",
            "city": city, "latitude": lat, "longitude": lon,
            "connection": {"asn": 64500, "org": "Org", "isp": "FAI", "domain": "ex.test"},
            "timezone": {"id": "Europe/Paris"}}


def ipapi(lat, lon, code="FR", country="France", city="Paris", flags=NO_FLAGS):
    return {"ip": "8.8.8.8", **flags,
            "location": {"country": country, "country_code": code, "state": "Ile-de-France", "city": city,
                         "latitude": lat, "longitude": lon, "timezone": "Europe/Paris"},
            "company": {"name": "Org IPAPI", "domain": "ex.test"}, "asn": {"asn": 64500}}


def fetcher(who, api):
    def fetch(url, _t):
        if "ipwho.is" in url:
            if isinstance(who, Exception):
                raise who
            return who
        if isinstance(api, Exception):
            raise api
        return api
    return fetch


def run(who, api, **kw):
    return analysis.analyze("8.8.8.8", fetch_json=fetcher(who, api), fetch_text=lambda _u, _t: "1.2.3.4\n", **kw)


def test_two_online_sources_agree_but_independence_is_not_established():
    report = run(ipwho(48.8566, 2.3522), ipapi(48.8049, 2.1204))
    assert [e.source for e in report.estimates] == ["ipwho.is", "ipapi.is"]
    assert report.comparison.status == "concordant"
    assert report.comparison.known_families == ["ipapi.is"]
    assert "ipwho.is" in report.comparison.unverified_sources
    assert report.comparison.confidence.level == "low"


def test_adding_an_independent_local_database_raises_confidence(tmp_path):
    path = tmp_path / "c.mmdb"
    path.write_bytes(build_mmdb([("8.8.8.0/24", city_record(48.86, 2.35, country="France", iso="FR"))],
                                database_type="DBIP-City-Lite"))
    databases, _ = local_db.open_databases([path])
    try:
        report = run(ipwho(48.8566, 2.3522), ipapi(48.8049, 2.1204), databases=databases)
    finally:
        local_db.close_all(databases)
    assert report.comparison.known_families == ["dbip", "ipapi.is"]
    assert report.comparison.confidence.level == "medium"
    assert report.comparison.confidence.to_dict()["is_probability"] is False


def test_contradictory_sources_are_shown_separately_with_no_single_position():
    report = run(ipwho(48.8566, 2.3522), ipapi(45.7640, 4.8357, city="Lyon"))
    assert report.comparison.status == "contradictory"
    assert report.location is None and report.links is None and report.maps_url is None
    data = report.to_dict()
    assert data["latitude"] is None and data["maps_url"] is None and data["city"] is None
    assert data["position_status"] == "contradictory"
    assert data["confidence"]["level"] == "undetermined"
    assert len(data["estimates"]) == 2
    assert all(e["maps_url"] and e["osm_url"] for e in data["estimates"])  # chaque source garde son propre lien
    assert any("se contredisent" in item for item in data["limitations"])


def test_different_countries_contradict():
    report = run(ipwho(48.8566, 2.3522), ipapi(50.85, 4.35, code="BE", country="Belgium", city="Brussels"))
    assert report.comparison.status == "contradictory"


def test_source_failure_is_reported_but_result_still_produced():
    report = run(NetworkUnavailableError("hors ligne"), ipapi(48.8566, 2.3522))
    assert [e.source for e in report.estimates] == ["ipapi.is"]
    assert any(e.startswith("ipwho.is") for e in report.source_errors)
    assert report.location.city == "Paris" and report.comparison.status == "single_source"


def test_all_sources_failing_raises_instead_of_inventing():
    with pytest.raises(ProviderError):
        run(NetworkUnavailableError("a"), NetworkUnavailableError("b"))


def test_incomplete_response_keeps_nulls():
    report = run({"ip": "8.8.8.8", "success": True, "country": "France", "country_code": "FR"}, ipapi(None, None, city=None))
    data = report.to_dict()
    assert data["latitude"] is None and data["maps_url"] is None and data["position_status"] == "no_data"
    assert data["country"] == "France"
    assert any("Coordonnées non fournies" in item for item in data["limitations"])


def test_invalid_coordinates_from_a_source_are_dropped_and_flagged():
    report = run(ipwho(999.0, 2.3522), ipapi(48.8566, 2.3522))
    bad = report.estimates[0]
    assert bad.point is None
    assert any(i.code == "coordinates_out_of_range" for i in bad.issues)
    data = report.to_dict()
    assert data["estimates"][0]["issues"][0]["code"] == "coordinates_out_of_range"
    assert data["estimates"][0]["latitude"] is None


def test_swapped_values_from_a_source_are_flagged_not_fixed():
    report = run(ipwho(2.3522, 48.8566), ipapi(48.8566, 2.3522))
    assert report.comparison.status == "contradictory"
    assert any("Inversion" in n for n in report.comparison.notes)
    assert report.estimates[0].latitude == 2.3522  # jamais corrige automatiquement


def test_vpn_indicator_caps_confidence_and_mentions_intermediary_server(tmp_path):
    path = tmp_path / "c.mmdb"
    path.write_bytes(build_mmdb([("8.8.8.0/24", city_record(48.86, 2.35, iso="FR"))], database_type="GeoLite2-City"))
    databases, _ = local_db.open_databases([path])
    try:
        report = run(ipwho(48.8566, 2.3522), ipapi(48.8049, 2.1204, flags={**NO_FLAGS, "is_vpn": True}), databases=databases)
    finally:
        local_db.close_all(databases)
    assert report.comparison.confidence.level == "low"
    assert report.anonymity.vpn is True
    assert any("serveur intermédiaire" in line for line in report.comparison.confidence.explanation)
    assert any("serveur intermédiaire" in item for item in report.limitations)  # toujours present


def test_limitations_always_state_no_realtime_tracking_and_intermediary():
    report = run(ipwho(48.8566, 2.3522), ipapi(48.8566, 2.3522))
    joined = " ".join(report.limitations)
    assert "serveur intermédiaire" in joined and "temps réel" in joined and "GPS" in joined


def test_ipapi_requests_are_not_duplicated():
    urls = []

    def fetch(url, _t):
        urls.append(url)
        return ipwho(48.8566, 2.3522) if "ipwho.is" in url else ipapi(48.8566, 2.3522)

    analysis.analyze("8.8.8.8", fetch_json=fetch, fetch_text=lambda _u, _t: "")
    assert sum("ipapi.is" in u for u in urls) == 1 and sum("ipwho.is" in u for u in urls) == 1


def test_network_fields_come_with_their_source():
    report = run(ipwho(48.8566, 2.3522), ipapi(48.8566, 2.3522))
    assert report.network.isp == "FAI" and report.network.sources["isp"] == "ipwho.is"
    data = report.to_dict()
    assert data["source"]["network"]["asn"] == "ipwho.is"


def test_ipapi_key_is_optional_and_only_added_to_the_url(monkeypatch):
    monkeypatch.delenv(geolocation.IPAPI_KEY_ENV, raising=False)
    assert "key=" not in geolocation.ipapi_url("8.8.8.8")
    monkeypatch.setenv(geolocation.IPAPI_KEY_ENV, "SECRET123")
    assert geolocation.ipapi_url("8.8.8.8").endswith("&key=SECRET123")


def test_ipapi_key_never_leaks_into_report_or_errors(monkeypatch):
    monkeypatch.setenv(geolocation.IPAPI_KEY_ENV, "SECRET123")

    def fetch(url, _t):
        if "ipwho.is" in url:
            return ipwho(48.8566, 2.3522)
        raise NetworkUnavailableError("echec")

    report = analysis.analyze("8.8.8.8", fetch_json=fetch, fetch_text=lambda _u, _t: "")
    assert "SECRET123" not in json.dumps(report.to_dict())


def test_reverse_geocode_option(monkeypatch):
    reverse_geocode.clear_cache()
    payload = {"address": {"city": "Paris", "country": "France", "country_code": "fr"}}

    def fetch(url, _t):
        if "nominatim" in url:
            return payload
        return ipwho(48.8566, 2.3522) if "ipwho.is" in url else ipapi(48.8566, 2.3522)

    monkeypatch.setattr(reverse_geocode, "MIN_INTERVAL_SECONDS", 0.0)
    report = analysis.analyze("8.8.8.8", fetch_json=fetch, fetch_text=lambda _u, _t: "", reverse_geocode=True)
    assert report.reverse_geocode.city == "Paris" and report.reverse_geocode.neighbourhood is None
    assert report.to_dict()["reverse_geocode"]["attribution"].startswith("©")


def test_reverse_geocode_not_attempted_when_sources_contradict():
    called = []

    def fetch(url, _t):
        called.append(url)
        return ipwho(48.8566, 2.3522) if "ipwho.is" in url else ipapi(45.76, 4.83, city="Lyon")

    report = analysis.analyze("8.8.8.8", fetch_json=fetch, fetch_text=lambda _u, _t: "", reverse_geocode=True)
    assert report.reverse_geocode is None and not any("nominatim" in u for u in called)


def test_reverse_geocode_failure_is_non_fatal():
    reverse_geocode.clear_cache()

    def fetch(url, _t):
        if "nominatim" in url:
            raise NetworkUnavailableError("nominatim hors ligne")
        return ipwho(48.8566, 2.3522) if "ipwho.is" in url else ipapi(48.8566, 2.3522)

    report = analysis.analyze("8.8.8.8", fetch_json=fetch, fetch_text=lambda _u, _t: "", reverse_geocode=True)
    assert report.reverse_geocode is None
    assert any(e.startswith("Géocodage inverse") for e in report.source_errors)


def test_cli_json_exposes_comparison(monkeypatch, capsys):
    original = analysis.analyze
    monkeypatch.setattr(cli.analysis, "analyze", lambda t, **kw: original(
        t, fetch_json=fetcher(ipwho(48.8566, 2.3522), ipapi(48.8049, 2.1204)), fetch_text=lambda _u, _t: "", **kw))
    assert cli.main(["--ip", "8.8.8.8", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["comparison"]["status"] == "concordant"
    assert data["confidence"]["is_probability"] is False
    assert data["comparison"]["pairs"][0]["distance_km"] == pytest.approx(18.2, abs=1.0)


def test_contradictory_terminal_shows_one_intact_link_pair_per_source():
    import io

    from rich.console import Console

    from src import output

    report = run(ipwho(48.8566, 2.3522), ipapi(45.7640, 4.8357, city="Lyon"))
    buffer = io.StringIO()
    output.render_report(Console(file=buffer, no_color=True, color_system=None, width=40, highlight=False), report)
    lines = [line.strip() for line in buffer.getvalue().splitlines()]
    assert "Aucun lien cartographique principal" in buffer.getvalue()
    for estimate in report.estimates:
        data = [e for e in report.to_dict()["estimates"] if e["source"] == estimate.source][0]
        assert data["maps_url"] in lines and data["osm_url"] in lines
