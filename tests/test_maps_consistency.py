"""Demontre que Google Maps et OpenStreetMap recoivent exactement le meme couple de coordonnees."""

import io
import re

import pytest
from rich.console import Console

from src import analysis, geo_math, maps, output

SAMPLES = [
    (37.3860517, -122.0838511),   # hemisphere nord, longitude negative
    (-33.8688, 151.2093),         # latitude negative
    (-1.5, -70.25),               # deux signes negatifs
    (4.0511, 9.7679),
    (48.8566, 2.3522),
    (0.000001, -0.000001),        # tres proche de zero, signes conserves
    (89.999999, 179.999999),      # limites
    (-90.0, -180.0),
]


@pytest.mark.parametrize("lat,lon", SAMPLES)
def test_both_urls_carry_the_same_numeric_pair(lat, lon):
    links = maps.build_links(lat, lon)
    assert links is not None
    google = maps.extract_coordinates(links.google)
    osm = maps.extract_coordinates(links.osm)
    assert google == osm == (float(links.lat_text), float(links.lon_text))
    assert maps.links_are_consistent(links)
    # Aucun arrondi significatif : moins de 1 m par rapport a la valeur d'origine
    assert geo_math.haversine_km((lat, lon), google) < 0.001


@pytest.mark.parametrize("lat,lon", SAMPLES)
def test_same_text_values_and_zoom_in_both_urls(lat, lon):
    links = maps.build_links(lat, lon, zoom=12)
    assert f"q={links.lat_text},{links.lon_text}" in links.google
    assert f"mlat={links.lat_text}&mlon={links.lon_text}" in links.osm
    assert links.osm.endswith(f"#map=12/{links.lat_text}/{links.lon_text}")
    assert links.google.endswith("&z=12")


def test_latitude_is_first_in_both_urls_never_swapped():
    links = maps.build_links(48.8566, 2.3522)  # lat != lon, lat dans les limites
    assert maps.extract_coordinates(links.google) == (48.8566, 2.3522)
    assert maps.extract_coordinates(links.osm) == (48.8566, 2.3522)


def test_signs_and_decimal_point_are_preserved():
    links = maps.build_links(-33.8688, -70.5)
    assert "q=-33.868800,-70.500000" in links.google
    assert "mlat=-33.868800&mlon=-70.500000" in links.osm
    assert "," not in links.lat_text and "," not in links.lon_text


def test_negative_zero_is_not_rendered():
    assert maps.format_coordinate(-0.0) == "0.000000"
    assert maps.format_coordinate(-0.0000001) == "0.000000"


def test_urls_need_no_encoding_and_hosts_are_fixed():
    links = maps.build_links(-12.5, -45.25)
    for url in (links.google, links.osm):
        assert re.fullmatch(r"https://[a-z.]+/[A-Za-z0-9?=&#,./\-_]*", url)
    assert links.google.startswith("https://www.google.com/maps?q=")
    assert links.osm.startswith("https://www.openstreetmap.org/?mlat=")


def test_inconsistent_links_are_detected():
    links = maps.build_links(10.0, 20.0)
    tampered = "https://www.openstreetmap.org/?mlat=10.000000&mlon=20.000000#map=10/10.000000/21.000000"
    assert maps.extract_coordinates(tampered) is None  # marqueur et centre divergent
    assert maps.extract_coordinates("https://example.com/?q=1,2") is None
    assert maps.extract_coordinates("https://www.google.com/maps?q=abc") is None
    assert maps.links_are_consistent(links)


@pytest.mark.parametrize("lat,lon", [(91, 0), (0, 181), (None, 1), (1, None), (float("nan"), 1), ("1", "2")])
def test_no_link_for_invalid_coordinates(lat, lon):
    assert maps.build_links(lat, lon) is None


def test_zoom_depends_on_radius_and_is_identical_for_both_maps():
    assert maps.zoom_for_radius(None) == maps.DEFAULT_ZOOM
    assert maps.zoom_for_radius(0.5) == 14
    assert maps.zoom_for_radius(20) == 11
    assert maps.zoom_for_radius(500) == 7
    assert maps.zoom_for_radius(-3) == maps.DEFAULT_ZOOM
    links = maps.build_links(1.0, 2.0, zoom=maps.zoom_for_radius(20))
    assert "&z=11" in links.google and "#map=11/" in links.osm


def test_report_exposes_same_pair_in_json_and_terminal(geo_payload):
    report = analysis.analyze(
        "8.8.8.8",
        fetch_json=lambda url, _t: geo_payload if "ipwho.is" in url else {},
        fetch_text=lambda _u, _t: "",
    )
    assert maps.links_are_consistent(report.links)
    data = report.to_dict()
    assert maps.extract_coordinates(data["maps_url"]) == maps.extract_coordinates(data["osm_url"])
    for estimate in data["estimates"]:
        assert maps.extract_coordinates(estimate["maps_url"]) == maps.extract_coordinates(estimate["osm_url"])


@pytest.mark.parametrize("width", [200, 120, 100, 80, 60, 50, 40, 30])
def test_terminal_never_folds_the_urls(geo_payload, width):
    """Regression : a 80 colonnes l'URL OSM etait tronquee (longitude fausse), a 60 elle perdait la longitude."""
    report = analysis.analyze(
        "8.8.8.8",
        fetch_json=lambda url, _t: geo_payload if "ipwho.is" in url else {},
        fetch_text=lambda _u, _t: "",
    )
    buffer = io.StringIO()
    console = Console(file=buffer, no_color=True, color_system=None, width=width, highlight=False)
    output.render_report(console, report)
    lines = buffer.getvalue().splitlines()
    assert report.links.google in [line.strip() for line in lines]
    assert report.links.osm in [line.strip() for line in lines]
