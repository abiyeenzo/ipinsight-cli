"""Modèles de données partagés."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STATUS_INDICATORS = "indicators_found"
STATUS_NO_INDICATOR = "no_indicator_found"
STATUS_INDETERMINATE = "indeterminate"

TEXT_NO_INDICATOR = "Aucun indicateur trouvé dans la source consultée"
TEXT_INDETERMINATE = "Indéterminé : données insuffisantes"


@dataclass
class GeoResult:
    """Données renvoyées par la source de géolocalisation (``None`` = non fourni)."""

    ip: str
    country: str | None = None
    country_code: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy_radius_km: float | None = None
    timezone: str | None = None
    isp: str | None = None
    organization: str | None = None
    asn: int | None = None
    domain: str | None = None
    source: str = "ipwho.is"


@dataclass
class AnonymityResult:
    """Indicateurs d'anonymisation. ``True`` = indicateur, ``False`` = rien dans la source, ``None`` = inconnu."""

    vpn: bool | None = None
    proxy: bool | None = None
    tor: bool | None = None
    hosting: bool | None = None
    sources: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        flags = (self.vpn, self.proxy, self.tor, self.hosting)
        if any(flag is True for flag in flags):
            return STATUS_INDICATORS
        if self.sources and any(flag is False for flag in flags):
            return STATUS_NO_INDICATOR
        return STATUS_INDETERMINATE

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self.vpn:
            lines.append("VPN : probablement détecté")
        if self.proxy:
            lines.append("Proxy : probablement détecté")
        if self.tor:
            lines.append("Tor : indicateur détecté")
        if self.hosting:
            lines.append("Hébergement : indicateur détecté")
        if lines:
            return lines
        if self.status == STATUS_NO_INDICATOR:
            return [TEXT_NO_INDICATOR]
        return [TEXT_INDETERMINATE]

    def json_flag(self, value: bool | None) -> bool | None:
        """Renvoie ``True`` pour un indicateur, sinon ``None`` (jamais ``False``).

        Une absence d'indicateur ne prouve pas l'absence de VPN, proxy ou Tor.
        """
        return True if value is True else None


@dataclass
class IPReport:
    """Rapport complet pour une adresse IP."""

    ip: str
    scope: str
    scope_description: str
    timestamp: str
    geo: GeoResult | None = None
    anonymity: AnonymityResult | None = None
    maps_url: str | None = None
    osm_url: str | None = None
    reverse_dns: str | None = None
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        geo = self.geo
        anon = self.anonymity
        return {
            "ip": self.ip,
            "ip_scope": self.scope,
            "country": geo.country if geo else None,
            "country_code": geo.country_code if geo else None,
            "region": geo.region if geo else None,
            "city": geo.city if geo else None,
            "latitude": geo.latitude if geo else None,
            "longitude": geo.longitude if geo else None,
            "accuracy_radius_km": geo.accuracy_radius_km if geo else None,
            "timezone": geo.timezone if geo else None,
            "isp": geo.isp if geo else None,
            "organization": geo.organization if geo else None,
            "asn": geo.asn if geo else None,
            "domain": geo.domain if geo else None,
            "reverse_dns": self.reverse_dns,
            "vpn_detected": anon.json_flag(anon.vpn) if anon else None,
            "proxy_detected": anon.json_flag(anon.proxy) if anon else None,
            "tor_detected": anon.json_flag(anon.tor) if anon else None,
            "hosting_detected": anon.json_flag(anon.hosting) if anon else None,
            "anonymity_status": anon.status if anon else STATUS_INDETERMINATE,
            "anonymity_errors": list(anon.errors) if anon else [],
            "maps_url": self.maps_url,
            "osm_url": self.osm_url,
            "source": {
                "geolocation": geo.source if geo else None,
                "anonymity": list(anon.sources) if anon else [],
            },
            "timestamp": self.timestamp,
            "limitations": list(self.limitations),
        }
