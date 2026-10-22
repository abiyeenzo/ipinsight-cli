import pytest

from src import coord_validation as cv
from src.models import GeoResult


def codes(issues):
    return {i.code for i in issues}


def test_valid_point():
    point, issues = cv.inspect_coordinates(48.8566, 2.3522)
    assert point == (48.8566, 2.3522) and issues == []


def test_signs_are_preserved():
    assert cv.inspect_coordinates(-33.87, -70.5)[0] == (-33.87, -70.5)


def test_missing_and_partial():
    point, issues = cv.inspect_coordinates(None, None)
    assert point is None and codes(issues) == {"coordinates_missing"}
    point, issues = cv.inspect_coordinates(10.0, None)
    assert point is None and codes(issues) == {"coordinates_partial"}
    assert cv.inspect_coordinates(None, 10.0)[0] is None


@pytest.mark.parametrize("lat,lon", [(91, 0.5), (-90.0001, 1), (0.5, 180.1), (0.5, -181), (200, 300)])
def test_out_of_range(lat, lon):
    point, issues = cv.inspect_coordinates(lat, lon)
    assert point is None and "coordinates_out_of_range" in codes(issues)


def test_swapped_values_are_detected_never_corrected():
    # 151.2 ne peut pas etre une latitude, mais est une longitude valide : inversion probable
    point, issues = cv.inspect_coordinates(151.2093, -33.8688)
    assert point is None
    assert codes(issues) == {"coordinates_out_of_range", "coordinates_swapped_suspected"}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, [1], {"a": 1}, "abc", ""])
def test_non_numeric(value):
    point, issues = cv.inspect_coordinates(value, 10.0)
    assert point is None and "coordinates_not_numeric" in codes(issues)


def test_decimal_comma_is_rejected_not_guessed():
    point, issues = cv.inspect_coordinates("48,8566", "2.3522")
    assert point is None and codes(issues) == {"coordinates_decimal_comma"}


def test_numeric_strings_with_dot_are_accepted():
    assert cv.inspect_coordinates("48.8566", " 2.3522 ")[0] == (48.8566, 2.3522)


def test_null_island_is_dropped():
    point, issues = cv.inspect_coordinates(0, 0)
    assert point is None and codes(issues) == {"coordinates_null_island"}
    assert cv.inspect_coordinates(0.0, 5.0)[0] == (0.0, 5.0)  # l'equateur reste valide


def _est(source, lat, lon):
    return GeoResult(ip="1.1.1.1", latitude=lat, longitude=lon, source=source)


def test_swap_between_sources_detected():
    good = _est("A", 48.8566, 2.3522)
    swapped = _est("B", 2.3522, 48.8566)
    found = cv.check_between_sources([good, swapped])
    assert codes(found) == {"swap_suspected_between_sources"}


def test_no_swap_flag_for_genuinely_different_places():
    assert cv.check_between_sources([_est("A", 48.8566, 2.3522), _est("B", -33.8688, 151.2093)]) == []
    assert cv.check_between_sources([_est("A", 48.8566, 2.3522), _est("B", 48.9, 2.4)]) == []


def test_validate_estimate_metadata_issues():
    estimate = GeoResult(ip="1.1.1.1", country_code="FRA", accuracy_radius_km=-5.0, city="Paris")
    assert codes(cv.validate_estimate(estimate)) == {
        "country_code_malformed", "radius_invalid", "place_without_coordinates"
    }


def test_declared_region_consistency():
    france_box = (41.0, 51.5, -5.5, 9.7)
    assert cv.point_in_declared_region((48.85, 2.35), *france_box)
    assert not cv.point_in_declared_region((40.7, -74.0), *france_box)
