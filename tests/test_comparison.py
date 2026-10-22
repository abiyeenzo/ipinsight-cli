import pytest

from src import comparison as cmp
from src.models import Confidence, GeoResult

PARIS = (48.8566, 2.3522)
LYON = (45.7640, 4.8357)        # environ 392 km de Paris
VERSAILLES = (48.8049, 2.1204)  # environ 18 km
LONDON = (51.5074, -0.1278)     # environ 344 km (au-dela du seuil de 300 km)
ROUEN = (49.4432, 1.0993)       # environ 110 km


def est(source, point, family="unverified", code="FR", **kw):
    lat, lon = point if point else (None, None)
    return GeoResult(ip="1.1.1.1", latitude=lat, longitude=lon, source=source, family=family,
                     country_code=code, country="X", **kw)


def test_no_estimates_and_no_coordinates():
    comparison, ref = cmp.compare([])
    assert comparison.status == "no_data" and ref is None and comparison.confidence.level == "none"
    comparison, ref = cmp.compare([est("A", None)])
    assert comparison.status == "no_data" and ref is None


def test_single_source_is_low_confidence():
    comparison, ref = cmp.compare([est("A", PARIS, family="dbip")])
    assert comparison.status == "single_source" and ref.source == "A"
    assert comparison.confidence.level == "low"
    assert any("Une seule source" in line for line in comparison.confidence.explanation)


def test_concordant_independent_families_give_medium():
    comparison, ref = cmp.compare([est("A", PARIS, "dbip"), est("B", VERSAILLES, "maxmind")])
    assert comparison.status == "concordant"
    assert comparison.known_families == ["dbip", "maxmind"]
    assert comparison.confidence.level == "medium"
    assert 10 < comparison.max_divergence_km < 30
    assert ref is not None


def test_three_independent_families_give_higher_but_never_certain():
    comparison, _ = cmp.compare([est("A", PARIS, "dbip"), est("B", VERSAILLES, "maxmind"), est("C", PARIS, "ipapi.is")])
    assert comparison.confidence.level == "higher"
    assert "jamais certaine" in comparison.confidence.label
    assert Confidence.to_dict(comparison.confidence)["is_probability"] is False


def test_same_family_is_not_independent_confirmation():
    comparison, _ = cmp.compare([est("A", PARIS, "maxmind"), est("B", PARIS, "maxmind"), est("C", PARIS, "maxmind")])
    assert comparison.known_families == ["maxmind"]
    assert comparison.confidence.level == "low"
    assert any("Indépendance non établie" in line for line in comparison.confidence.explanation)


def test_unverified_provenance_never_counts_as_independent():
    comparison, _ = cmp.compare([est("A", PARIS), est("B", VERSAILLES)])
    assert comparison.known_families == [] and comparison.confidence.level == "low"
    assert set(comparison.unverified_sources) == {"A", "B"}
    comparison, _ = cmp.compare([est("A", PARIS), est("B", VERSAILLES, "dbip")])
    assert comparison.confidence.level == "low"  # une seule famille documentee : pas assez


def test_moderate_divergence_is_flagged_and_low():
    comparison, ref = cmp.compare([est("A", PARIS, "dbip"), est("B", ROUEN, "maxmind", code="FR")])
    assert comparison.status == "divergent"
    assert comparison.confidence.level == "low"
    assert ref is not None


def test_distance_over_300km_is_contradictory_no_reference():
    comparison, ref = cmp.compare([est("A", PARIS, "dbip"), est("B", LYON, "maxmind")])
    assert comparison.status == "contradictory" and ref is None
    assert comparison.confidence.level == "undetermined"
    assert comparison.reference_source is None
    assert any("aucune position fiable" in line for line in comparison.confidence.explanation)


def test_344_km_exceeds_the_contradiction_threshold():
    comparison, ref = cmp.compare([est("A", PARIS, "dbip"), est("B", LONDON, "maxmind")])
    assert comparison.status == "contradictory" and ref is None


def test_different_countries_are_contradictory_even_when_close():
    comparison, ref = cmp.compare([est("A", PARIS, "dbip", code="FR"), est("B", VERSAILLES, "maxmind", code="BE")])
    assert comparison.status == "contradictory" and ref is None
    assert any("pays différents" in n for n in comparison.notes)


def test_country_codes_are_case_insensitive():
    comparison, _ = cmp.compare([est("A", PARIS, "dbip", code="fr"), est("B", VERSAILLES, "maxmind", code="FR")])
    assert comparison.status == "concordant"


def test_reference_is_a_real_point_the_most_central():
    comparison, ref = cmp.compare([
        est("A", PARIS, "dbip"), est("B", VERSAILLES, "maxmind"), est("C", (48.90, 2.40), "ipapi.is"),
    ])
    assert ref.point in {PARIS, VERSAILLES, (48.90, 2.40)}
    assert comparison.reference_source == ref.source


def test_tie_prefers_smaller_radius_then_order():
    a = est("A", PARIS, "dbip", accuracy_radius_km=50.0)
    b = est("B", VERSAILLES, "maxmind", accuracy_radius_km=5.0)
    comparison, ref = cmp.compare([a, b])
    assert ref.source == "B"
    assert any("arbitraire" in n for n in comparison.notes)
    _, ref = cmp.compare([est("A", PARIS, "dbip"), est("B", VERSAILLES, "maxmind")])
    assert ref.source == "A"


def test_pair_comparison_details():
    pair = cmp.compare_pair(
        GeoResult(ip="1.1.1.1", latitude=48.8566, longitude=2.3522, city="Paris", region="Île-de-France", country_code="FR"),
        GeoResult(ip="1.1.1.1", latitude=48.8049, longitude=2.1204, city="PARIS", region="Ile de France", country_code="FR"),
    )
    assert pair.same_city is True and pair.same_region is True and pair.same_country is True
    assert 15 < pair.distance_km < 25
    unknown = cmp.compare_pair(GeoResult(ip="1.1.1.1"), GeoResult(ip="1.1.1.1", city="Paris"))
    assert unknown.distance_km is None and unknown.same_city is None and unknown.same_country is None


def test_swap_note_appears_in_comparison():
    comparison, _ = cmp.compare([est("A", PARIS, "dbip"), est("B", (PARIS[1], PARIS[0]), "maxmind")])
    assert any("Inversion latitude/longitude suspectée" in n for n in comparison.notes)
    assert comparison.status == "contradictory"


def test_incomplete_estimate_alongside_usable_one():
    comparison, ref = cmp.compare([est("A", None, "dbip"), est("B", PARIS, "maxmind")])
    assert comparison.status == "single_source" and ref.source == "B"
    assert comparison.pairs[0].distance_km is None


@pytest.mark.parametrize("start", ["medium", "higher"])
def test_anonymity_caps_confidence(start):
    confidence = Confidence(start, "x", [])
    cmp.cap_confidence_for_anonymity(confidence, True)
    assert confidence.level == "low"
    assert any("serveur intermédiaire" in line for line in confidence.explanation)


def test_anonymity_cap_leaves_other_levels_and_no_indicator_alone():
    confidence = Confidence("medium", "x", [])
    cmp.cap_confidence_for_anonymity(confidence, False)
    assert confidence.level == "medium" and confidence.explanation == []
    undetermined = Confidence("undetermined", "x", [])
    cmp.cap_confidence_for_anonymity(undetermined, True)
    assert undetermined.level == "undetermined"
