"""Sources de geolocalisation en ligne : ipwho.is et ipapi.is (HTTPS, gratuites).

Chaque fonction renvoie UNE estimation, sans rien deduire ni completer.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from . import coord_validation
from .http_client import ProviderResponseError, get_json
from .models import FAMILY_UNVERIFIED, GeoResult

IPWHO_URL = "https://ipwho.is/"
IPWHO_SOURCE = "ipwho.is"
IPAPI_URL = "https://api.ipapi.is/"
IPAPI_SOURCE = "ipapi.is"
# Selon la documentation du fournisseur, la geolocalisation provient de sa base propre.
IPAPI_FAMILY = "ipapi.is"
IPAPI_KEY_ENV = "IPINSIGHT_IPAPI_KEY"

BASE_URL = IPWHO_URL
SOURCE_NAME = IPWHO_SOURCE

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


def ipapi_url(ip: str | None) -> str:
    """URL ipapi.is. La cle API OPTIONNELLE (variable d'environnement) n'est jamais affichee ni stockee."""
    url = IPAPI_URL + "?q=" + quote(ip, safe=":") if ip else IPAPI_URL
    key = os.environ.get(IPAPI_KEY_ENV, "").strip()
    if key:
        url += ("&" if "?" in url else "?") + "key=" + quote(key, safe="")
    return url


def parse_response(data: dict[str, Any], requested_ip: str | None) -> GeoResult:
    """Transforme la reponse d'ipwho.is en :class:`GeoResult`.

    Seules les valeurs reellement presentes et valides sont conservees ;
    rien n'est deduit ni invente. Les coordonnees invalides sont ecartees
    et signalees dans ``issues``.
    """
    if data.get("success") is False:
        message = _clean_str(data.get("message")) or "requête refusée"
        raise ProviderResponseError(f"{IPWHO_SOURCE} : {message}.")
    ip = _clean_str(data.get("ip")) or requested_ip
    if not ip:
        raise ProviderResponseError(f"{IPWHO_SOURCE} : réponse sans adresse IP.")

    connection = _as_dict(data.get("connection"))
    tz = _as_dict(data.get("timezone"))
    point, issues = coord_validation.inspect_coordinates(data.get("latitude"), data.get("longitude"))
    return GeoResult(
        ip=ip,
        country=_clean_str(data.get("country")),
        country_code=_clean_str(data.get("country_code")),
        region=_clean_str(data.get("region")),
        city=_clean_str(data.get("city")),
        latitude=point[0] if point else None,
        longitude=point[1] if point else None,
        accuracy_radius_km=None,  # ipwho.is ne fournit pas de rayon d'incertitude
        timezone=_clean_str(tz.get("id")),
        isp=_clean_str(connection.get("isp")),
        organization=_clean_str(connection.get("org")),
        asn=_clean_asn(connection.get("asn")),
        domain=_clean_str(connection.get("domain")),
        source=IPWHO_SOURCE,
        family=FAMILY_UNVERIFIED,
        issues=issues,
    )


def parse_ipapi_response(data: dict[str, Any], requested_ip: str | None) -> GeoResult:
    """Transforme la reponse d'ipapi.is en :class:`GeoResult` (bloc ``location``)."""
    if "error" in data:
        raise ProviderResponseError(f"{IPAPI_SOURCE} : {_clean_str(data.get('error')) or 'requête refusée'}.")
    location = data.get("location")
    if not isinstance(location, dict):
        raise ProviderResponseError(f"{IPAPI_SOURCE} : aucune localisation dans la réponse.")
    ip = _clean_str(data.get("ip")) or requested_ip
    if not ip:
        raise ProviderResponseError(f"{IPAPI_SOURCE} : réponse sans adresse IP.")
    asn_block = _as_dict(data.get("asn"))
    company = _as_dict(data.get("company"))
    point, issues = coord_validation.inspect_coordinates(location.get("latitude"), location.get("longitude"))
    return GeoResult(
        ip=ip,
        country=_clean_str(location.get("country")),
        country_code=_clean_str(location.get("country_code")),
        region=_clean_str(location.get("state")),
        city=_clean_str(location.get("city")),
        latitude=point[0] if point else None,
        longitude=point[1] if point else None,
        accuracy_radius_km=None,  # non fourni
        timezone=_clean_str(location.get("timezone")),
        organization=_clean_str(company.get("name")) or _clean_str(asn_block.get("org")),
        asn=_clean_asn(asn_block.get("asn")),
        domain=_clean_str(company.get("domain")) or _clean_str(asn_block.get("domain")),
        source=IPAPI_SOURCE,
        family=IPAPI_FAMILY,
        issues=issues,
    )


def lookup(ip: str | None, *, timeout: float = 8.0, fetch_json: JsonFetcher = get_json) -> GeoResult:
    """Interroge ipwho.is. ``ip=None`` analyse l'adresse publique de l'appelant.

    Donnees envoyees : l'adresse IP analysee (dans l'URL) ; pour ``None``,
    le fournisseur voit l'adresse source de la connexion.
    """
    url = IPWHO_URL if ip is None else IPWHO_URL + quote(ip, safe=":")
    return parse_response(fetch_json(url, timeout), ip)


def lookup_ipapi(ip: str, *, timeout: float = 8.0, fetch_json: JsonFetcher = get_json) -> GeoResult:
    """Interroge ipapi.is pour ``ip`` (adresse IP envoyee dans l'URL)."""
    return parse_ipapi_response(fetch_json(ipapi_url(ip), timeout), ip)
