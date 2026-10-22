"""Comparaison independante des estimations de plusieurs sources.

Regles (heuristiques de prudence, NON calibrees statistiquement) :
  * deux sources de la meme famille de donnees comptent pour UNE seule ;
  * une source dont l'origine des donnees n'est pas documentee ne compte jamais
    comme confirmation independante ;
  * des pays differents, ou plus de 300 km d'ecart, rendent la position
    contradictoire : aucune position unique n'est retenue ;
  * le niveau de confiance est qualitatif et n'est jamais une probabilite.
"""

from __future__ import annotations

import re
import unicodedata

from . import coord_validation, geo_math
from .models import (
    Comparison,
    Confidence,
    GeoResult,
    PairComparison,
    is_known_family,
)

CONCORDANT_KM = 50.0
CONTRADICTORY_KM = 300.0

LABELS = {
    "none": "aucune",
    "low": "faible",
    "medium": "moyenne",
    "higher": "plus élevée (jamais certaine)",
    "undetermined": "non déterminable",
}


def _normalize(text: str | None) -> str | None:
    if not text:
        return None
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-z0-9]+", " ", stripped.casefold()).strip()
    return cleaned or None


def _same(a: str | None, b: str | None) -> bool | None:
    na, nb = _normalize(a), _normalize(b)
    if na is None or nb is None:
        return None
    return na == nb


def _same_country(a: GeoResult, b: GeoResult) -> bool | None:
    if a.country_code and b.country_code:
        return a.country_code.upper() == b.country_code.upper()
    return _same(a.country, b.country)


def compare_pair(a: GeoResult, b: GeoResult) -> PairComparison:
    pa, pb = a.point, b.point
    distance = geo_math.haversine_km(pa, pb) if pa and pb else None
    return PairComparison(
        source_a=a.source,
        source_b=b.source,
        distance_km=distance,
        same_country=_same_country(a, b),
        same_region=_same(a.region, b.region),
        same_city=_same(a.city, b.city),
    )


def _reference_index(usable: list[GeoResult]) -> int:
    """Indice du point le plus central ; a egalite, le rayon d'incertitude le plus petit, puis l'ordre des sources."""
    points = [e.point for e in usable]
    assert all(p is not None for p in points)
    typed = [p for p in points if p is not None]
    totals = [sum(geo_math.haversine_km(p, q) for q in typed) for p in typed]
    best_total = min(totals)
    candidates = [i for i, t in enumerate(totals) if t <= best_total + 1e-9]
    candidates.sort(key=lambda i: (usable[i].accuracy_radius_km is None, usable[i].accuracy_radius_km or 0.0, i))
    return candidates[0]


def _confidence(
    status: str,
    known: list[str],
    unverified: list[str],
    usable_count: int,
    max_km: float | None,
) -> Confidence:
    explanation: list[str] = []
    if status == "no_data":
        explanation.append("Aucune source n'a fourni de coordonnées valides.")
        return Confidence("none", LABELS["none"], explanation)
    if status == "contradictory":
        explanation.append(
            "Les sources se contredisent (pays différents ou écart supérieur à "
            f"{CONTRADICTORY_KM:.0f} km) : aucune position fiable ne peut être choisie."
        )
        return Confidence("undetermined", LABELS["undetermined"], explanation)

    if status == "single_source":
        explanation.append("Une seule source exploitable : aucune comparaison possible.")
        level = "low"
    else:
        shown = f"{max_km:.1f}" if max_km is not None else "?"
        explanation.append(f"{usable_count} sources comparées, écart maximal {shown} km.")
        if status == "divergent":
            explanation.append(
                f"Écart entre {CONCORDANT_KM:.0f} et {CONTRADICTORY_KM:.0f} km : divergence notable."
            )
            level = "low"
        elif len(known) >= 3:
            explanation.append(f"{len(known)} familles de données indépendantes concordent.")
            level = "higher"
        elif len(known) == 2:
            explanation.append("2 familles de données indépendantes concordent.")
            level = "medium"
        else:
            level = "low"

    if len(known) < 2 and status in ("concordant", "divergent"):
        explanation.append(
            "Indépendance non établie : moins de deux familles de données documentées parmi les sources "
            "(ajouter une base locale d'une autre famille améliore la vérification croisée)."
        )
    if unverified:
        explanation.append(
            "Origine des données non documentée, donc jamais comptée comme confirmation indépendante : "
            + ", ".join(unverified) + "."
        )
    explanation.append("Niveau qualitatif prudent, ce n'est pas une probabilité statistique calibrée.")
    return Confidence(level, LABELS[level], explanation)


def compare(estimates: list[GeoResult]) -> tuple[Comparison, GeoResult | None]:
    """Compare les estimations ; renvoie ``(comparaison, estimation retenue ou None)``.

    L'estimation retenue est toujours l'une des estimations reelles (le point le
    plus central), jamais une moyenne fabriquee. Elle vaut ``None`` si les sources
    se contredisent ou si aucune coordonnee n'est exploitable.
    """
    usable = [e for e in estimates if e.point is not None]
    known = sorted({e.family for e in estimates if e.point is not None and is_known_family(e.family)})
    unverified = [e.source for e in usable if not is_known_family(e.family)]
    comparison = Comparison(status="no_data", known_families=known, unverified_sources=unverified)

    for i, first in enumerate(estimates):
        for second in estimates[i + 1:]:
            comparison.pairs.append(compare_pair(first, second))

    distances = [p.distance_km for p in comparison.pairs if p.distance_km is not None]
    comparison.max_divergence_km = max(distances) if distances else None
    country_conflict = any(p.same_country is False for p in comparison.pairs)

    for issue in coord_validation.check_between_sources(estimates):
        comparison.notes.append(issue.message)

    if country_conflict:
        comparison.status = "contradictory"
        comparison.notes.append("Les sources désignent des pays différents.")
    elif not usable:
        comparison.status = "no_data"
    elif len(usable) == 1:
        comparison.status = "single_source"
    else:
        km = comparison.max_divergence_km or 0.0
        comparison.status = (
            "contradictory" if km > CONTRADICTORY_KM else "divergent" if km > CONCORDANT_KM else "concordant"
        )

    reference: GeoResult | None = None
    if usable and comparison.status != "contradictory":
        reference = usable[_reference_index(usable)]
        comparison.reference_source = reference.source
        if len(usable) == 2 and comparison.status != "single_source":
            comparison.notes.append(
                "Avec deux sources seulement, le choix de l'une des deux est arbitraire : les deux restent affichées."
            )
    comparison.confidence = _confidence(
        comparison.status, known, unverified, len(usable), comparison.max_divergence_km
    )
    return comparison, reference


def cap_confidence_for_anonymity(confidence: Confidence, indicator_found: bool) -> Confidence:
    """Plafonne la confiance a « faible » si un VPN, proxy, Tor ou hebergeur est signale."""
    if not indicator_found or confidence.level in ("none", "undetermined", "low"):
        if indicator_found:
            confidence.explanation.append(
                "Un indicateur VPN/proxy/Tor/hébergement est signalé : la position peut être celle d'un serveur intermédiaire."
            )
        return confidence
    confidence.level = "low"
    confidence.label = LABELS["low"]
    confidence.explanation.append(
        "Confiance plafonnée à « faible » : un indicateur VPN/proxy/Tor/hébergement est signalé, "
        "la position peut être celle d'un serveur intermédiaire et non celle de l'appareil d'origine."
    )
    return confidence
