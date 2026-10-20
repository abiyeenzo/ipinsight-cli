"""Indicateurs d'anonymisation réseau (VPN, proxy, Tor, hébergement) — résultats indicatifs.

Sources gratuites, sans clé obligatoire :
  * ipapi.is (champs is_vpn / is_proxy / is_tor / is_datacenter) ;
  * liste publique des nœuds de sortie Tor du Tor Project.

Ce module ne cherche ni à contourner un VPN, ni à retrouver une IP d'origine.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from .http_client import ProviderError, get_json, get_text
from .models import AnonymityResult

IPAPI_IS_URL = "https://api.ipapi.is/?q="
TOR_EXIT_LIST_URL = "https://check.torproject.org/torbulkexitlist"

JsonFetcher = Callable[[str, float], dict[str, Any]]
TextFetcher = Callable[[str, float], str]


def _flag(data: dict[str, Any], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None


def _merge(*values: bool | None) -> bool | None:
    """True si au moins un indicateur ; False si une source n'en voit aucun ; sinon None."""
    if any(v is True for v in values):
        return True
    if any(v is False for v in values):
        return False
    return None


def parse_tor_exit_list(text: str) -> set[str]:
    addresses: set[str] = set()
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        try:
            addresses.add(str(ipaddress.ip_address(candidate)))
        except ValueError:
            continue
    return addresses


def check(
    ip: str,
    *,
    timeout: float = 8.0,
    fetch_json: JsonFetcher = get_json,
    fetch_text: TextFetcher = get_text,
) -> AnonymityResult:
    """Interroge les sources ; ne lève jamais d'erreur de fournisseur (elles sont consignées)."""
    result = AnonymityResult()
    normalized = str(ipaddress.ip_address(ip))

    api_vpn = api_proxy = api_tor = api_hosting = None
    try:
        data = fetch_json(IPAPI_IS_URL + quote(normalized, safe=":"), timeout)
        if "error" in data:
            raise ProviderError(str(data["error"]))
        api_vpn = _flag(data, "is_vpn")
        api_proxy = _flag(data, "is_proxy")
        api_tor = _flag(data, "is_tor")
        api_hosting = _flag(data, "is_datacenter")
        if any(v is not None for v in (api_vpn, api_proxy, api_tor, api_hosting)):
            result.sources.append("ipapi.is")
        else:
            result.errors.append("ipapi.is : réponse sans indicateurs exploitables.")
    except ProviderError as exc:
        result.errors.append(f"ipapi.is : {exc}")

    tor_list_value: bool | None = None
    try:
        exit_nodes = parse_tor_exit_list(fetch_text(TOR_EXIT_LIST_URL, timeout))
        if exit_nodes:
            tor_list_value = normalized in exit_nodes
            result.sources.append("Tor Project (liste des nœuds de sortie)")
        else:
            result.errors.append("Tor Project : liste vide ou illisible.")
    except ProviderError as exc:
        result.errors.append(f"Tor Project : {exc}")

    result.vpn = _merge(api_vpn)
    result.proxy = _merge(api_proxy)
    result.tor = _merge(api_tor, tor_list_value)
    result.hosting = _merge(api_hosting)
    return result
