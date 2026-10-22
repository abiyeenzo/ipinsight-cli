import pytest

from src import reverse_geocode as rg
from src.http_client import NetworkUnavailableError, ProviderError, ProviderResponseError
from src.models import GeoResult

PARIS = {
    "address": {
        "city": "Paris", "county": "Paris", "state": "Ile-de-France", "country": "France", "country_code": "fr",
        "suburb": "Quartier du Louvre", "neighbourhood": "Les Halles",
    }
}


@pytest.fixture(autouse=True)
def fresh_cache():
    rg.clear_cache()


def estimate(radius=None, code="FR"):
    return GeoResult(ip="1.1.1.1", latitude=48.8566, longitude=2.3522, country_code=code, accuracy_radius_km=radius)


def test_city_level_by_default_and_no_neighbourhood():
    seen = []

    def fetch(url, _t):
        seen.append(url)
        return PARIS

    result = rg.lookup(estimate(), fetch_json=fetch, throttle=False)
    assert "zoom=10" in seen[0] and "lat=48.856600&lon=2.352200" in seen[0]
    assert result.city == "Paris" and result.country_code == "FR" and result.state == "Ile-de-France"
    assert result.neighbourhood is None
    assert any("Quartier non affiché" in n for n in result.notes)
    assert result.country_matches_estimate is True
    assert "OpenStreetMap" in result.attribution


def test_neighbourhood_only_when_radius_is_small_and_source_provides_it():
    result = rg.lookup(estimate(radius=1.0), fetch_json=lambda *_: PARIS, throttle=False)
    assert result.neighbourhood == "Les Halles" and result.zoom == 14
    assert rg.lookup(estimate(radius=3.5), fetch_json=lambda *_: PARIS, throttle=False).neighbourhood is None


def test_small_radius_but_no_neighbourhood_in_response():
    payload = {"address": {"city": "Paris", "country_code": "fr"}}
    result = rg.lookup(estimate(radius=1.0), fetch_json=lambda *_: payload, throttle=False)
    assert result.neighbourhood is None
    assert any("Aucun quartier fourni" in n for n in result.notes)


def test_never_exposes_street_or_house_number():
    payload = {"address": {**PARIS["address"], "road": "Rue de Rivoli", "house_number": "12"}}
    data = rg.lookup(estimate(radius=1.0), fetch_json=lambda *_: payload, throttle=False).to_dict()
    assert "Rivoli" not in str(data) and "house" not in str(data)


def test_country_mismatch_is_reported():
    result = rg.lookup(estimate(code="DE"), fetch_json=lambda *_: PARIS, throttle=False)
    assert result.country_matches_estimate is False
    assert any("Incohérence" in n for n in result.notes)


def test_town_village_fallback_for_city():
    payload = {"address": {"village": "Petitville", "country_code": "fr"}}
    assert rg.lookup(estimate(), fetch_json=lambda *_: payload, throttle=False).city == "Petitville"


def test_results_are_cached_so_same_point_is_not_requested_twice():
    calls = []

    def fetch(url, _t):
        calls.append(url)
        return PARIS

    rg.lookup(estimate(), fetch_json=fetch, throttle=False)
    rg.lookup(estimate(), fetch_json=fetch, throttle=False)
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{"error": "Unable to geocode"}, {}, {"address": "oops"}])
def test_provider_refusals_and_incomplete_responses(payload):
    with pytest.raises(ProviderResponseError):
        rg.lookup(estimate(), fetch_json=lambda *_: payload, throttle=False)


def test_connection_errors_propagate():
    def failing(*_):
        raise NetworkUnavailableError("hors ligne")

    with pytest.raises(NetworkUnavailableError):
        rg.lookup(estimate(), fetch_json=failing, throttle=False)


def test_no_coordinates_means_no_request():
    with pytest.raises(ProviderError):
        rg.lookup(GeoResult(ip="1.1.1.1"), fetch_json=lambda *_: pytest.fail("requete inattendue"), throttle=False)


def test_throttle_waits_between_requests(monkeypatch):
    sleeps = []
    clock = [100.0]
    monkeypatch.setattr(rg.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(rg.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(rg, "_last_call", 99.9)
    rg.lookup(estimate(), fetch_json=lambda *_: PARIS)
    assert sleeps and sleeps[0] == pytest.approx(rg.MIN_INTERVAL_SECONDS - 0.1)
