"""Consultation FACULTATIVE des registres Internet regionaux via RDAP (RFC 7480 / RFC 9083).

Service utilise : bootstrap public HTTPS ``https://rdap.org/ip/<adresse>`` qui
redirige vers le registre regional competent (ARIN, RIPE NCC, APNIC, LACNIC ou
AFRINIC). Aucune cle requise.

Donnees extraites (uniquement lorsqu'elles figurent dans la reponse) :
  * identifiant du bloc (``handle``), nom du reseau (``name``), prefixe CIDR et plage ;
  * registre regional (RIR), titulaire declare et contact d'abus (``abuse_email``) ;
  * pays d'enregistrement administratif et dates d'allocation / mise a jour.

Le pays RDAP designe le siege administratif de l'organisation titulaire du bloc,
et non la localisation physique de l'equipement ou de l'utilisateur.
"""

from __future__ import annotations

import ipaddress
import threading
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from .http_client import ProviderError, ProviderResponseError, get_json
from .models import GeoResult, RDAPInfo
from .validation import InvalidIPError, classify_ip

RDAP_URL = "https://rdap.org/ip/"
SOURCE_NAME = "RDAP (registres RIR)"
MAX_ENTITY_DEPTH = 3

_REGISTRY_LABELS = {
    "arin": "ARIN",
    "ripencc": "RIPE NCC",
    "ripe": "RIPE NCC",
    "apnic": "APNIC",
    "lacnic": "LACNIC",
    "afrinic": "AFRINIC",
}

JsonFetcher = Callable[[str, float], dict[str, Any]]

_cache: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _text(value: object) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _iso_date(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    date_part = text[:10]
    if len(date_part) == 10 and date_part[4] == "-" and date_part[7] == "-":
        return date_part
    return text


def _registry_name(data: dict[str, Any]) -> str | None:
    port43 = (_text(data.get("port43")) or "").lower()
    for token, label in _REGISTRY_LABELS.items():
        if token in port43:
            return label
    return _text(data.get("port43"))


def _extract_cidrs(data: dict[str, Any], start: str | None, end: str | None) -> str | None:
    raw_cidrs = data.get("cidr0_cidrs")
    prefixes: list[str] = []
    if isinstance(raw_cidrs, list):
        for entry in raw_cidrs:
            if not isinstance(entry, dict):
                continue
            prefix = _text(entry.get("v4prefix")) or _text(entry.get("v6prefix"))
            length = entry.get("length")
            if prefix and isinstance(length, int) and not isinstance(length, bool) and length >= 0:
                try:
                    net = ipaddress.ip_network(f"{prefix}/{length}", strict=False)
                    prefixes.append(str(net))
                except ValueError:
                    continue
    if prefixes:
        return ", ".join(prefixes)
    if start and end:
        try:
            a, b = ipaddress.ip_address(start), ipaddress.ip_address(end)
            if a.version == b.version and int(a) <= int(b):
                summarized = list(ipaddress.summarize_address_range(a, b))
                if 1 <= len(summarized) <= 4:
                    return ", ".join(str(net) for net in summarized)
        except ValueError:
            pass
    return None


def _vcard_fields(entity: dict[str, Any]) -> tuple[str | None, str | None]:
    """Renvoie ``(fn, email)`` extraits d'un ``vcardArray`` RFC 7095."""
    vcard = entity.get("vcardArray")
    if not (isinstance(vcard, list) and len(vcard) == 2 and isinstance(vcard[1], list)):
        return None, None
    fn: str | None = None
    email: str | None = None
    for prop in vcard[1]:
        if not (isinstance(prop, list) and len(prop) >= 4 and isinstance(prop[0], str)):
            continue
        name = prop[0].lower()
        value = _text(prop[3])
        if name == "fn" and value and fn is None:
            fn = value
        elif name == "email" and value and "@" in value and email is None:
            email = value
    return fn, email


def _walk_entities(entities: object, depth: int = 0) -> tuple[str | None, str | None]:
    """Parcourt les entites RDAP (jusqu'a ``MAX_ENTITY_DEPTH``) pour extraire titulaire et contact d'abus."""
    if depth > MAX_ENTITY_DEPTH or not isinstance(entities, list):
        return None, None
    registrant: str | None = None
    abuse_email: str | None = None
    fallback_org: str | None = None

    for item in entities:
        if not isinstance(item, dict):
            continue
        roles_raw = item.get("roles")
        roles = {r.lower() for r in roles_raw if isinstance(r, str)} if isinstance(roles_raw, list) else set()
        fn, email = _vcard_fields(item)
        if "registrant" in roles and fn and registrant is None:
            registrant = fn
        elif fn and fallback_org is None and ("administrative" in roles or not roles):
            fallback_org = fn
        if "abuse" in roles and email and abuse_email is None:
            abuse_email = email
        sub_reg, sub_abuse = _walk_entities(item.get("entities"), depth + 1)
        if registrant is None and sub_reg is not None:
            registrant = sub_reg
        if abuse_email is None and sub_abuse is not None:
            abuse_email = sub_abuse

    return registrant or fallback_org, abuse_email


def _extract_events(events: object) -> tuple[str | None, str | None]:
    if not isinstance(events, list):
        return None, None
    registered: str | None = None
    changed: str | None = None
    for event in events:
        if not isinstance(event, dict):
            continue
        action = (_text(event.get("eventAction")) or "").lower()
        date = _iso_date(event.get("eventDate"))
        if not date:
            continue
        if action == "registration" and registered is None:
            registered = date
        elif action in ("last changed", "last update of rdap database") and changed is None:
            changed = date
    return registered, changed


def parse_response(data: dict[str, Any], estimate: GeoResult | None = None) -> RDAPInfo:
    """Transforme un objet reseau RDAP (RFC 9083) en :class:`RDAPInfo`."""
    if "errorCode" in data:
        title = _text(data.get("title")) or f"erreur {data.get('errorCode')}"
        raise ProviderResponseError(f"{SOURCE_NAME} : {title}.")

    handle = _text(data.get("handle"))
    name = _text(data.get("name"))
    start = _text(data.get("startAddress"))
    end = _text(data.get("endAddress"))
    range_text = f"{start} - {end}" if start and end else None
    cidr = _extract_cidrs(data, start, end)
    raw_country = _text(data.get("country"))
    country = raw_country.upper() if raw_country and len(raw_country) == 2 and raw_country.isalpha() else None
    registry = _registry_name(data)
    allocation_type = _text(data.get("type"))
    registrant, abuse_email = _walk_entities(data.get("entities"))
    registered, changed = _extract_events(data.get("events"))

    if not any((handle, name, cidr, range_text, country, registrant, abuse_email)):
        raise ProviderResponseError(f"{SOURCE_NAME} : réponse RDAP incomplète ou non reconnue.")

    notes = [
        "Le registre RDAP indique l'entité administrative titulaire du bloc d'adresses, "
        "pas la position physique d'un appareil."
    ]
    matches: bool | None = None
    if country and estimate is not None and estimate.country_code:
        geo_code = estimate.country_code.upper()
        matches = country == geo_code
        if not matches:
            notes.append(
                f"Écart administratif : bloc enregistré en {country} mais géolocalisé en {geo_code} "
                "(fréquent pour un opérateur international ou du routage anycast)."
            )

    return RDAPInfo(
        source=SOURCE_NAME,
        handle=handle,
        name=name,
        cidr=cidr,
        range_text=range_text,
        country=country,
        registry=registry,
        registrant=registrant,
        abuse_email=abuse_email,
        allocation_type=allocation_type,
        registration_date=registered,
        last_changed=changed,
        country_matches_estimate=matches,
        notes=notes,
    )


def lookup(
    ip: str,
    *,
    estimate: GeoResult | None = None,
    timeout: float = 8.0,
    fetch_json: JsonFetcher = get_json,
) -> RDAPInfo:
    """Interroge RDAP pour une adresse IP publique. Leve ``ProviderError`` en cas d'echec."""
    try:
        check = classify_ip(ip)
    except InvalidIPError as exc:
        raise ProviderError(str(exc)) from exc
    if not check.is_public:
        raise ProviderError("Consultation RDAP réservée aux adresses IP publiques.")

    with _lock:
        payload = _cache.get(check.address)
    if payload is None:
        url = RDAP_URL + quote(check.address, safe=":")
        payload = fetch_json(url, timeout)
        with _lock:
            _cache[check.address] = payload
    return parse_response(payload, estimate)
