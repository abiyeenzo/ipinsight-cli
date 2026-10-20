"""Validation et classification des adresses IP (IPv4 / IPv6)."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

MAX_IP_TEXT_LENGTH = 45  # longueur maximale d'une IPv6 textuelle (IPv4 mappée incluse)

_SCOPE_DESCRIPTIONS = {
    "public": "Adresse IP publique routable.",
    "private": "Adresse privée ou réservée à la documentation : non routable sur Internet.",
    "loopback": "Adresse de bouclage (loopback) : machine locale uniquement.",
    "link_local": "Adresse locale au lien (link-local) : non routable.",
    "multicast": "Adresse multicast : ne désigne pas un hôte unique.",
    "unspecified": "Adresse non spécifiée (0.0.0.0 ou ::).",
    "reserved": "Adresse réservée par l'IANA : non routable.",
    "non_routable": "Adresse non globalement routable (ex. espace partagé CGNAT).",
}


class InvalidIPError(ValueError):
    """Levée lorsque le texte fourni n'est pas une adresse IP valide."""


@dataclass(frozen=True)
class IPCheck:
    """Résultat de la classification d'une adresse IP."""

    address: str
    version: int
    scope: str
    description: str

    @property
    def is_public(self) -> bool:
        return self.scope == "public"


def _scope_of(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    if addr.is_unspecified:
        return "unspecified"
    if addr.is_loopback:
        return "loopback"
    if addr.is_link_local:
        return "link_local"
    if addr.is_multicast:
        return "multicast"
    if addr.is_private:
        return "private"
    if addr.is_reserved:
        return "reserved"
    if not addr.is_global:
        return "non_routable"
    return "public"


def classify_ip(text: str) -> IPCheck:
    """Valide ``text`` et renvoie sa classification.

    Lève :class:`InvalidIPError` si l'adresse est mal formée.
    """
    cleaned = text.strip() if isinstance(text, str) else ""
    if not cleaned:
        raise InvalidIPError("Adresse IP vide.")
    if len(cleaned) > MAX_IP_TEXT_LENGTH:
        raise InvalidIPError("Adresse IP trop longue.")
    if "%" in cleaned or "/" in cleaned:
        raise InvalidIPError("Les identifiants de zone et les préfixes CIDR ne sont pas acceptés.")
    try:
        addr = ipaddress.ip_address(cleaned)
    except ValueError as exc:
        raise InvalidIPError(f"Adresse IP mal formée : {cleaned!r}.") from exc
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    scope = _scope_of(addr)
    return IPCheck(
        address=str(addr),
        version=addr.version,
        scope=scope,
        description=_SCOPE_DESCRIPTIONS[scope],
    )
