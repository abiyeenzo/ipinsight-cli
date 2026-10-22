import math

import pytest

from src import geo_math

PARIS = (48.8566, 2.3522)
LONDON = (51.5074, -0.1278)
NEW_YORK = (40.7128, -74.0060)
SYDNEY = (-33.8688, 151.2093)


def test_haversine_known_distances():
    # Valeurs de reference usuelles (sphere de 6371 km) : tolerance 1 %
    assert geo_math.haversine_km(PARIS, LONDON) == pytest.approx(344, rel=0.01)
    assert geo_math.haversine_km(PARIS, NEW_YORK) == pytest.approx(5837, rel=0.01)
    assert geo_math.haversine_km(PARIS, SYDNEY) == pytest.approx(16960, rel=0.01)


def test_haversine_identity_symmetry_and_limits():
    assert geo_math.haversine_km(PARIS, PARIS) == 0.0
    assert geo_math.haversine_km(PARIS, LONDON) == pytest.approx(geo_math.haversine_km(LONDON, PARIS))
    # Points antipodaux : demi-circonference
    assert geo_math.haversine_km((0.0, 0.0), (0.0, 180.0)) == pytest.approx(math.pi * geo_math.EARTH_RADIUS_KM, rel=1e-9)
    # Un degre de latitude vaut environ 111,2 km
    assert geo_math.haversine_km((0.0, 10.0), (1.0, 10.0)) == pytest.approx(111.195, rel=1e-3)


def test_haversine_across_antimeridian_and_poles():
    assert geo_math.haversine_km((0.0, 179.5), (0.0, -179.5)) == pytest.approx(111.195, rel=1e-3)
    assert geo_math.haversine_km((90.0, 0.0), (90.0, 120.0)) == pytest.approx(0.0, abs=1e-6)


def test_swap_and_pairwise():
    assert geo_math.swap_lat_lon((1.5, 2.5)) == (2.5, 1.5)
    pairs = geo_math.pairwise_distances_km([PARIS, LONDON, NEW_YORK])
    assert [(i, j) for i, j, _ in pairs] == [(0, 1), (0, 2), (1, 2)]
    assert geo_math.max_pairwise_km([PARIS]) is None
    assert geo_math.max_pairwise_km([PARIS, LONDON, NEW_YORK]) == pytest.approx(5837, rel=0.01)


def test_medoid_returns_a_real_point_not_an_average():
    cluster = [(10.0, 10.0), (10.1, 10.0), (10.0, 10.1), (50.0, 50.0)]
    index = geo_math.medoid_index(cluster)
    assert index in (0, 1, 2) and cluster[index] in cluster
    assert geo_math.medoid_index([]) is None
    assert geo_math.medoid_index([PARIS]) == 0


def test_bounding_box_including_antimeridian():
    assert geo_math.in_bounding_box((48.0, 2.0), 41.0, 51.5, -5.0, 9.6)
    assert not geo_math.in_bounding_box((52.0, 2.0), 41.0, 51.5, -5.0, 9.6)
    # Boite chevauchant l'antimeridien (ouest 170 > est -170)
    assert geo_math.in_bounding_box((0.0, 179.0), -10, 10, 170.0, -170.0)
    assert geo_math.in_bounding_box((0.0, -179.0), -10, 10, 170.0, -170.0)
    assert not geo_math.in_bounding_box((0.0, 0.0), -10, 10, 170.0, -170.0)


def test_within_radius():
    assert geo_math.within_radius_km(PARIS, LONDON, 400)
    assert not geo_math.within_radius_km(PARIS, LONDON, 300)
