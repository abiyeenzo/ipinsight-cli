"""Géolocalisation IP via ipwho.is (HTTPS, gratuit, sans clé API)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from .http_client import ProviderResponseError, get_json
from .maps import validate_coordinates
from .models import GeoResult

BASE_URL = "https://ipwho.is/"
SOURCE_NAME = "ipwho.is"

JsonFetcher = Callable[[str, float], dict[str, Any]]


def _clean_str(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _clean_asn(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        digits = value.upper().removeprefix("AS")
        return int(digits) if digits.isdigit() and int(digits) > 0 else None
    return None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_response(data: dict[str, Any], requested_ip: str | None) -> GeoResult:
    """Transforme la réponse du fournisseur en :class:`GeoResult`.

    Seules les valeurs réellement présentes et valides sont conservées ;
    rien n'est déduit ni inventé.
    """
    if data.get("success") is False:
        message = _clean_str(data.get("message")) or "requête refusée"
        raise ProviderResponseError(f"{SOURCE_NAME} : {message}.")
    ip = _clean_str(data.get("ip")) or requested_ip
    if not ip:
        raise ProviderResponseError(f"{SOURCE_NAME} : réponse sans adresse IP.")

    connection = _as_dict(data.get("connection"))
    tz = _as_dict(data.get("timezone"))
    coords = validate_coordinates(data.get("latitude"), data.get("longitude"))
    return GeoResult(
        ip=ip,
        country=_clean_str(data.get("country")),
        country_code=_clean_str(data.get("country_code")),
        region=_clean_str(data.get("region")),
        city=_clean_str(data.get("city")),
        latitude=coords[0] if coords else None,
        longitude=coords[1] if coords else None,
        accuracy_radius_km=None,  # ipwho.is ne fournit pas de rayon d'incertitude
        timezone=_clean_str(tz.get("id")),
        isp=_clean_str(connection.get("isp")),
        organization=_clean_str(connection.get("org")),
        asn=_clean_asn(connection.get("asn")),
        domain=_clean_str(connection.get("domain")),
        source=SOURCE_NAME,
    )


def lookup(ip: str | None, *, timeout: float = 8.0, fetch_json: JsonFetcher = get_json) -> GeoResult:
    """Interroge la source. ``ip=None`` analyse l'adresse publique de l'appelant.

    Données envoyées : l'adresse IP analysée (dans l'URL) ; pour ``None``,
    le fournisseur voit l'adresse source de la connexion.
    """
    url = BASE_URL if ip is None else BASE_URL + quote(ip, safe=":")
    return parse_response(fetch_json(url, timeout), ip)
