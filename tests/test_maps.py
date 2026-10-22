import pytest

from src import maps


def test_google_maps_url_format():
    assert maps.build_google_maps_url(37.386, -122.0838) == "https://www.google.com/maps?q=37.386000,-122.083800&z=10"


def test_osm_url_format():
    url = maps.build_osm_url(48.8566, 2.3522)
    assert url.startswith("https://www.openstreetmap.org/?mlat=48.856600&mlon=2.352200")


@pytest.mark.parametrize(
    "lat,lon",
    [(None, 1.0), (1.0, None), (91, 0), (0, 181), (-90.1, 0), (float("nan"), 0), (float("inf"), 0), ("1", "2"), (True, False)],
)
def test_invalid_coordinates_give_no_link(lat, lon):
    assert maps.validate_coordinates(lat, lon) is None
    assert maps.build_google_maps_url(lat, lon) is None
    assert maps.build_osm_url(lat, lon) is None


def test_boundary_coordinates_accepted():
    assert maps.validate_coordinates(90, 180) == (90.0, 180.0)
    assert maps.validate_coordinates(-90, -180) == (-90.0, -180.0)


def test_open_in_browser_refuses_unknown_hosts(monkeypatch):
    called = []
    monkeypatch.setattr(maps.webbrowser, "open", lambda url: called.append(url) or True)
    assert maps.open_in_browser("https://evil.example/maps?q=1,2") is False
    assert maps.open_in_browser("http://www.google.com/maps?q=1,2") is False
    assert called == []
    assert maps.open_in_browser("https://www.google.com/maps?q=1,2") is True


def test_copy_to_clipboard_without_tool(monkeypatch):
    monkeypatch.setattr(maps.shutil, "which", lambda _name: None)
    assert maps.copy_to_clipboard("https://www.google.com/maps?q=1,2") is False


def test_disclaimer_mentions_estimation():
    assert "estimées" in maps.MAPS_DISCLAIMER
    assert "non nécessairement" in maps.MAPS_DISCLAIMER
