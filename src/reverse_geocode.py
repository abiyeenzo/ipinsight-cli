"""Geocodage inverse FACULTATIF via Nominatim (OpenStreetMap).

Respect de la politique d'usage de Nominatim (operations.osmfoundation.org) :
  * 1 requete par seconde au maximum (ce module en attend 1,1) ;
  * User-Agent identifiant l'application (jamais celui, generique, d'une bibliotheque) ;
  * cache en memoire : un meme point n'est jamais redemande ;
  * attribution « © OpenStreetMap contributors » affichee avec le resultat ;
  * desactive par defaut (option ``--reverse-geocode``), aucune requete en grille.

Le point interroge est une ESTIMATION issue d'une adresse IP. Le resultat decrit
la zone autour de ce point, jamais l'adresse d'une personne. Le niveau de detail
demande reste celui d'une ville (zoom 10) ; un quartier n'est affiche que si
l'incertitude declaree par la source est inferieure a 3 km ET si Nominatim
renvoie lui-meme un quartier.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from . import maps
from .http_client import ProviderError, ProviderResponseError, get_json
from .models import GeoResult, ReverseGeocode

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
SOURCE_NAME = "Nominatim (OpenStreetMap)"
CITY_ZOOM = 10
NEIGHBOURHOOD_ZOOM = 14
NEIGHBOURHOOD_MAX_RADIUS_KM = 3.0
MIN_INTERVAL_SECONDS = 1.1

JsonFetcher = Callable[[str, float], dict[str, Any]]

_cache: dict[tuple[str, str, int], ReverseGeocode] = {}
_lock = threading.Lock()
_last_call = 0.0


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _wait_turn() -> None:
    global _last_call
    with _lock:
        pause = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call)
        if pause > 0:
            time.sleep(pause)
        _last_call = time.monotonic()


def zoom_for(estimate: GeoResult) -> int:
    """Zoom de ville par defaut ; zoom de quartier seulement si l'incertitude declaree est faible."""
    radius = estimate.accuracy_radius_km
    if radius is not None and radius <= NEIGHBOURHOOD_MAX_RADIUS_KM:
        return NEIGHBOURHOOD_ZOOM
    return CITY_ZOOM


def _text(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def parse_response(data: dict[str, Any], estimate: GeoResult, zoom: int) -> ReverseGeocode:
    if "error" in data:
        raise ProviderResponseError(f"{SOURCE_NAME} : {_text(data.get('error')) or 'aucun résultat'}.")
    address = data.get("address")
    if not isinstance(address, dict):
        raise ProviderResponseError(f"{SOURCE_NAME} : réponse sans adresse.")

    code = _text(address.get("country_code"))
    code = code.upper() if code else None
    city = next((_text(address.get(k)) for k in ("city", "town", "village", "municipality") if _text(address.get(k))), None)
    neighbourhood = None
    notes = ["Zone autour du point estimé : ne désigne pas l'adresse d'une personne."]
    radius = estimate.accuracy_radius_km
    if radius is not None and radius <= NEIGHBOURHOOD_MAX_RADIUS_KM:
        neighbourhood = next(
            (_text(address.get(k)) for k in ("neighbourhood", "suburb", "quarter") if _text(address.get(k))), None
        )
        if neighbourhood is None:
            notes.append("Aucun quartier fourni par la source.")
    else:
        notes.append("Quartier non affiché : l'estimation IP n'est pas assez précise pour le justifier.")

    matches: bool | None = None
    if code and estimate.country_code:
        matches = code == estimate.country_code.upper()
        if not matches:
            notes.append(
                f"Incohérence : le point estimé se situe en {code} alors que la source déclare {estimate.country_code.upper()}."
            )
    return ReverseGeocode(
        source=SOURCE_NAME,
        zoom=zoom,
        country=_text(address.get("country")),
        country_code=code,
        state=_text(address.get("state")) or _text(address.get("region")),
        county=_text(address.get("county")),
        city=city,
        neighbourhood=neighbourhood,
        country_matches_estimate=matches,
        notes=notes,
    )


def lookup(
    estimate: GeoResult,
    *,
    timeout: float = 8.0,
    fetch_json: JsonFetcher = get_json,
    throttle: bool = True,
) -> ReverseGeocode:
    """Geocodage inverse du point estime. Leve ``ProviderError`` en cas d'echec."""
    links = maps.build_links(estimate.latitude, estimate.longitude)
    if links is None:
        raise ProviderError("Aucune coordonnée valide à géocoder.")
    zoom = zoom_for(estimate)
    key = (links.lat_text, links.lon_text, zoom)
    with _lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    url = (
        f"{NOMINATIM_URL}?format=jsonv2&lat={links.lat_text}&lon={links.lon_text}"
        f"&zoom={zoom}&addressdetails=1&accept-language=en"
    )
    if throttle:
        _wait_turn()
    result = parse_response(fetch_json(url, timeout), estimate, zoom)
    with _lock:
        _cache[key] = result
    return result
