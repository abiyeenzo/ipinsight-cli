"""Orchestration d'une analyse IP : validation, géolocalisation, anonymat, cartes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from . import anonymity_check, geolocation, network_info
from .http_client import ProviderResponseError, get_json, get_text
from .maps import build_google_maps_url, build_osm_url
from .models import IPReport, STATUS_INDETERMINATE, STATUS_NO_INDICATOR
from .validation import InvalidIPError, classify_ip

LIMIT_GEO = (
    "La géolocalisation IP est approximative : elle ne correspond pas à une position GPS "
    "et ne permet pas de déterminer l'adresse exacte d'une personne."
)
LIMIT_NO_COORDS = "Coordonnées non fournies par la source : aucun lien cartographique généré."
LIMIT_NO_RADIUS = "Rayon d'incertitude non fourni par la source : précision inconnue."
LIMIT_ANONYMITY = (
    "Détection VPN/proxy/Tor/hébergement indicative : l'absence d'indicateur ne prouve pas l'absence de VPN."
)
LIMIT_ANONYMITY_INCOMPLETE = "Sources d'anonymat indisponibles ou incomplètes : résultat indéterminé."

JsonFetcher = Callable[[str, float], dict[str, Any]]
TextFetcher = Callable[[str, float], str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def analyze(
    target: str | None,
    *,
    timeout: float = 8.0,
    check_anonymity: bool = True,
    with_reverse_dns: bool = False,
    fetch_json: JsonFetcher = get_json,
    fetch_text: TextFetcher = get_text,
) -> IPReport:
    """Analyse ``target`` (IP) ou l'adresse publique de la machine si ``target`` vaut ``None``.

    Lève :class:`InvalidIPError` (entrée invalide) ou
    :class:`~src.http_client.ProviderError` (échec de la source de géolocalisation).
    """
    if target is not None:
        check = classify_ip(target)
        if not check.is_public:
            return IPReport(
                ip=check.address,
                scope=check.scope,
                scope_description=check.description,
                timestamp=_now(),
                limitations=[check.description, "Aucune requête externe effectuée."],
            )
        geo = geolocation.lookup(check.address, timeout=timeout, fetch_json=fetch_json)
    else:
        geo = geolocation.lookup(None, timeout=timeout, fetch_json=fetch_json)
        try:
            check = classify_ip(geo.ip)
        except InvalidIPError as exc:
            raise ProviderResponseError("La source a renvoyé une adresse IP invalide.") from exc

    report = IPReport(
        ip=check.address,
        scope=check.scope,
        scope_description=check.description,
        timestamp=_now(),
        geo=geo,
        maps_url=build_google_maps_url(geo.latitude, geo.longitude),
        osm_url=build_osm_url(geo.latitude, geo.longitude),
    )
    report.limitations.append(LIMIT_GEO)
    if report.maps_url is None:
        report.limitations.append(LIMIT_NO_COORDS)
    if geo.accuracy_radius_km is None:
        report.limitations.append(LIMIT_NO_RADIUS)

    if check_anonymity:
        report.anonymity = anonymity_check.check(
            check.address, timeout=timeout, fetch_json=fetch_json, fetch_text=fetch_text
        )
        report.limitations.append(LIMIT_ANONYMITY)
        if report.anonymity.status in (STATUS_INDETERMINATE, STATUS_NO_INDICATOR) and report.anonymity.errors:
            report.limitations.append(LIMIT_ANONYMITY_INCOMPLETE)
    if with_reverse_dns:
        report.reverse_dns = network_info.reverse_dns(check.address, timeout=timeout)
    return report
