"""Moteur de validation des coordonnees et des metadonnees geographiques.

Principe : detecter et SIGNALER, ne jamais corriger silencieusement. Une valeur
invalide est ecartee (jamais « reparee »), et le probleme est consigne dans une
liste d'``Issue`` visible dans le rapport.
"""

from __future__ import annotations

import math

from . import geo_math
from .models import GeoResult, Issue

Point = tuple[float, float]

SWAP_MIN_DISTANCE_KM = 500.0  # ecart minimal entre deux sources pour suspecter une inversion
SWAP_MAX_RESIDUAL_KM = 100.0  # une fois permute, le point doit retomber pres de l'autre source


def _issue(code: str, severity: str, message: str) -> Issue:
    return Issue(code, severity, message)


def _to_number(value: object) -> tuple[float | None, Issue | None]:
    """Convertit une valeur en nombre. Les chaines a virgule decimale sont refusees."""
    if isinstance(value, bool):
        return None, _issue("coordinates_not_numeric", "error", "Valeur booléenne à la place d'un nombre.")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if "," in text:
            return None, _issue(
                "coordinates_decimal_comma", "error", f"Séparateur décimal ambigu (virgule) : {text!r}."
            )
        try:
            number = float(text)
        except ValueError:
            return None, _issue("coordinates_not_numeric", "error", f"Valeur non numérique : {text!r}.")
    else:
        return None, _issue("coordinates_not_numeric", "error", f"Type inattendu : {type(value).__name__}.")
    if not math.isfinite(number):
        return None, _issue("coordinates_not_numeric", "error", "Valeur non finie (NaN ou infini).")
    return number, None


def inspect_coordinates(latitude: object, longitude: object) -> tuple[Point | None, list[Issue]]:
    """Valide ``(latitude, longitude)`` WGS84 en degres decimaux.

    Renvoie ``(point, issues)``. ``point`` vaut ``None`` si les coordonnees sont
    absentes ou invalides. Cas traites : absence, valeur partielle, non numerique,
    virgule decimale, hors limites, inversion probable, point (0, 0).
    """
    if latitude is None and longitude is None:
        return None, [_issue("coordinates_missing", "info", "Coordonnées non fournies par la source.")]
    if latitude is None or longitude is None:
        return None, [_issue("coordinates_partial", "error", "Une seule des deux coordonnées est fournie : ignorées.")]

    issues: list[Issue] = []
    lat, lat_issue = _to_number(latitude)
    lon, lon_issue = _to_number(longitude)
    issues.extend(i for i in (lat_issue, lon_issue) if i is not None)
    if lat is None or lon is None:
        return None, issues

    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        issues.append(_issue(
            "coordinates_out_of_range", "error",
            f"Coordonnées hors limites WGS84 : latitude {lat}, longitude {lon}.",
        ))
        if not -90.0 <= lat <= 90.0 and -180.0 <= lat <= 180.0 and -90.0 <= lon <= 90.0:
            issues.append(_issue(
                "coordinates_swapped_suspected", "warning",
                f"La valeur {lat} est impossible comme latitude mais valide comme longitude : "
                "inversion possible. Aucune correction automatique n'est appliquée.",
            ))
        return None, issues

    if lat == 0.0 and lon == 0.0:
        issues.append(_issue(
            "coordinates_null_island", "warning",
            "Point (0, 0) : valeur de remplacement très probable (« Null Island »), ignoré.",
        ))
        return None, issues
    return (lat, lon), issues


def check_between_sources(estimates: list[GeoResult]) -> list[Issue]:
    """Detecte une inversion latitude/longitude probable entre deux sources.

    Si A est tres loin de B, mais que A permute (lat <-> lon) retombe pres de B
    (ou l'inverse), une inversion est SUSPECTEE. Rien n'est corrige.
    """
    issues: list[Issue] = []
    usable = [e for e in estimates if e.point is not None]
    for i, first in enumerate(usable):
        for second in usable[i + 1:]:
            a, b = first.point, second.point
            assert a is not None and b is not None
            if geo_math.haversine_km(a, b) < SWAP_MIN_DISTANCE_KM:
                continue
            for name, p, other in ((first.source, a, b), (second.source, b, a)):
                swapped = geo_math.swap_lat_lon(p)
                if -90.0 <= swapped[0] <= 90.0 and geo_math.haversine_km(swapped, other) <= SWAP_MAX_RESIDUAL_KM:
                    issues.append(_issue(
                        "swap_suspected_between_sources", "warning",
                        f"Inversion latitude/longitude suspectée pour {name} : le point permuté coïncide "
                        "avec l'autre source. Aucune correction automatique.",
                    ))
    return issues


def point_in_declared_region(
    point: Point, south: float, north: float, west: float, east: float
) -> bool:
    """Coherence avec une region declaree decrite par une boite englobante (gere l'antimeridien)."""
    return geo_math.in_bounding_box(point, south, north, west, east)


def validate_estimate(estimate: GeoResult) -> list[Issue]:
    """Verifie la coherence interne d'une estimation (hors comparaison entre sources)."""
    issues = list(estimate.issues)
    code = estimate.country_code
    if code is not None and not (len(code) == 2 and code.isalpha()):
        issues.append(_issue("country_code_malformed", "warning", f"Code pays inattendu : {code!r}."))
    if estimate.accuracy_radius_km is not None and (
        not isinstance(estimate.accuracy_radius_km, (int, float)) or estimate.accuracy_radius_km < 0
    ):
        issues.append(_issue("radius_invalid", "warning", "Rayon d'incertitude invalide : ignoré."))
    if estimate.point is None and (estimate.city or estimate.region):
        issues.append(_issue(
            "place_without_coordinates", "info",
            "Ville ou région fournie sans coordonnées : aucune position cartographique n'est déduite.",
        ))
    return issues
