"""Orchestration d'une analyse IP : validation, sources, comparaison, anonymat, cartes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from . import (
    anonymity_check,
    comparison as comparison_module,
    coord_validation,
    geolocation,
    local_db,
    maps,
    network_info,
    rdap as rdap_module,
    reverse_geocode as reverse_geocode_module,
)
from .http_client import ProviderError, ProviderResponseError, get_json, get_text
from .models import GeoResult, IPReport, NetworkInfo, STATUS_INDETERMINATE, STATUS_NO_INDICATOR
from .validation import InvalidIPError, classify_ip

LIMIT_GEO = (
    "La géolocalisation IP est approximative : elle ne correspond pas à une position GPS "
    "et ne permet pas de déterminer l'adresse exacte d'une personne."
)
LIMIT_INTERMEDIARY = (
    "La position estimée peut correspondre à un serveur intermédiaire (VPN, proxy, relais, hébergeur, "
    "passerelle du fournisseur d'accès) et non à l'appareil d'origine."
)
LIMIT_NOT_TRACKING = (
    "Une adresse IP ne permet pas de suivre des déplacements en temps réel ni de localiser un appareil par GPS."
)
LIMIT_NO_COORDS = "Coordonnées non fournies par la source : aucun lien cartographique généré."
LIMIT_NO_RADIUS = "Rayon d'incertitude non fourni par la source : précision inconnue."
LIMIT_CONTRADICTORY = (
    "Les sources se contredisent : aucune position unique n'est retenue et aucun lien cartographique "
    "principal n'est généré. Les estimations de chaque source sont affichées séparément."
)
LIMIT_ANONYMITY = (
    "Détection VPN/proxy/Tor/hébergement indicative : l'absence d'indicateur ne prouve pas l'absence de VPN."
)
LIMIT_ANONYMITY_INCOMPLETE = "Sources d'anonymat indisponibles ou incomplètes : résultat indéterminé."
LIMIT_OFFLINE = "Mode hors ligne : seules les bases locales sont utilisées, l'analyse d'anonymat n'est pas effectuée."

JsonFetcher = Callable[[str, float], dict[str, Any]]
TextFetcher = Callable[[str, float], str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _memoize(fetch: Callable[[str, float], Any]) -> Callable[[str, float], Any]:
    """Evite d'envoyer deux fois la meme requete pendant une analyse (succes ou echec)."""
    cache: dict[str, tuple[bool, Any]] = {}

    def wrapper(url: str, timeout: float) -> Any:
        if url not in cache:
            try:
                cache[url] = (True, fetch(url, timeout))
            except ProviderError as exc:
                cache[url] = (False, exc)
        ok, value = cache[url]
        if not ok:
            raise value
        return value

    return wrapper


def _merge_network(estimates: Sequence[GeoResult]) -> NetworkInfo:
    """Premiere valeur disponible pour chaque champ reseau, avec la source de chaque champ."""
    info = NetworkInfo()
    for field_name in ("isp", "organization", "asn", "domain", "timezone"):
        for estimate in estimates:
            value = getattr(estimate, field_name)
            if value is not None:
                setattr(info, field_name, value)
                info.sources[field_name] = estimate.source
                break
    return info


def _collect_online(
    ip: str | None,
    first: GeoResult | None,
    timeout: float,
    fetch_json: JsonFetcher,
    errors: list[str],
    exceptions: list[ProviderError],
) -> list[GeoResult]:
    results: list[GeoResult] = []
    if first is not None:
        results.append(first)
    elif ip is not None:
        try:
            results.append(geolocation.lookup(ip, timeout=timeout, fetch_json=fetch_json))
        except ProviderError as exc:
            errors.append(f"{geolocation.IPWHO_SOURCE} : {exc}")
            exceptions.append(exc)
    if ip is not None:
        try:
            results.append(geolocation.lookup_ipapi(ip, timeout=timeout, fetch_json=fetch_json))
        except ProviderError as exc:
            errors.append(str(exc) if str(exc).startswith(geolocation.IPAPI_SOURCE) else f"{geolocation.IPAPI_SOURCE} : {exc}")
            exceptions.append(exc)
    return results


def _collect_local(
    ip: str, databases: Sequence[local_db.LocalDatabase], errors: list[str], limitations: list[str]
) -> list[GeoResult]:
    results: list[GeoResult] = []
    for database in databases:
        try:
            found = local_db.lookup(database, ip)
        except local_db.LocalDBError as exc:
            errors.append(str(exc))
            continue
        if found is None:
            errors.append(f"{database.label} : adresse absente de la base.")
        else:
            results.append(found)
        note = local_db.staleness_note(database)
        if note:
            limitations.append(note)
    return results


def analyze(
    target: str | None,
    *,
    timeout: float = 8.0,
    check_anonymity: bool = True,
    with_reverse_dns: bool = False,
    with_rdap: bool = False,
    reverse_geocode: bool = False,
    databases: Sequence[local_db.LocalDatabase] = (),
    offline: bool = False,
    fetch_json: JsonFetcher = get_json,
    fetch_text: TextFetcher = get_text,
) -> IPReport:
    """Analyse ``target`` (IP) ou l'adresse publique de la machine si ``target`` vaut ``None``.

    Leve :class:`InvalidIPError` (entree invalide) ou
    :class:`~src.http_client.ProviderError` (aucune source n'a repondu).
    """
    fetch_json = _memoize(fetch_json)
    fetch_text = _memoize(fetch_text)
    first: GeoResult | None = None

    if target is not None:
        check = classify_ip(target)
        if not check.is_public:
            return IPReport(
                ip=check.address,
                scope=check.scope,
                scope_description=check.description,
                timestamp=_now(),
                limitations=[check.description, "Aucune requête externe effectuée."],
                offline=offline,
            )
    else:
        if offline:
            raise ProviderResponseError("--self nécessite le réseau : incompatible avec --offline.")
        first = geolocation.lookup(None, timeout=timeout, fetch_json=fetch_json)
        try:
            check = classify_ip(first.ip)
        except InvalidIPError as exc:
            raise ProviderResponseError("La source a renvoyé une adresse IP invalide.") from exc
        if not check.is_public:
            raise ProviderResponseError("La source a renvoyé une adresse non publique.")

    errors: list[str] = []
    exceptions: list[ProviderError] = []
    limitations: list[str] = [LIMIT_GEO, LIMIT_INTERMEDIARY, LIMIT_NOT_TRACKING]

    estimates: list[GeoResult] = []
    if not offline:
        estimates.extend(_collect_online(check.address, first, timeout, fetch_json, errors, exceptions))
    estimates.extend(_collect_local(check.address, databases, errors, limitations))

    if not estimates and exceptions:
        raise exceptions[0]
    for estimate in estimates:
        estimate.issues = coord_validation.validate_estimate(estimate)

    comparison, reference = comparison_module.compare(estimates)
    primary = estimates[0] if estimates else None
    location = reference or (primary if comparison.status != "contradictory" else None)

    report = IPReport(
        ip=check.address,
        scope=check.scope,
        scope_description=check.description,
        timestamp=_now(),
        geo=primary,
        estimates=estimates,
        network=_merge_network(estimates) if estimates else None,
        comparison=comparison,
        location=location,
        source_errors=errors,
        limitations=limitations,
        offline=offline,
    )
    if reference is not None:
        report.links = maps.build_links(
            reference.latitude, reference.longitude, zoom=maps.zoom_for_radius(reference.accuracy_radius_km)
        )
    if not estimates:
        limitations.append("Adresse absente des bases locales : aucune estimation disponible.")
    elif comparison.status == "contradictory":
        limitations.append(LIMIT_CONTRADICTORY)
    elif report.links is None:
        limitations.append(LIMIT_NO_COORDS)
    if reference is not None and reference.accuracy_radius_km is None:
        limitations.append(LIMIT_NO_RADIUS)

    if offline:
        limitations.append(LIMIT_OFFLINE)
    elif check_anonymity:
        report.anonymity = anonymity_check.check(
            check.address, timeout=timeout, fetch_json=fetch_json, fetch_text=fetch_text
        )
        limitations.append(LIMIT_ANONYMITY)
        if report.anonymity.status in (STATUS_INDETERMINATE, STATUS_NO_INDICATOR) and report.anonymity.errors:
            limitations.append(LIMIT_ANONYMITY_INCOMPLETE)
        comparison_module.cap_confidence_for_anonymity(comparison.confidence, report.anonymity.has_indicator)

    if reverse_geocode and reference is not None and not offline:
        try:
            report.reverse_geocode = reverse_geocode_module.lookup(reference, timeout=timeout, fetch_json=fetch_json)
        except ProviderError as exc:
            errors.append(f"Géocodage inverse : {exc}")
    if with_rdap and not offline:
        try:
            report.rdap = rdap_module.lookup(
                check.address, estimate=location or primary, timeout=timeout, fetch_json=fetch_json
            )
        except ProviderError as exc:
            errors.append(f"RDAP : {exc}")
    if with_reverse_dns and not offline:
        report.reverse_dns = network_info.reverse_dns(check.address, timeout=timeout)
    return report
