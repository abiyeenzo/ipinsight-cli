"""Modeles de donnees partages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import maps

STATUS_INDICATORS = "indicators_found"
STATUS_NO_INDICATOR = "no_indicator_found"
STATUS_INDETERMINATE = "indeterminate"

TEXT_NO_INDICATOR = "Aucun indicateur trouvé dans la source consultée"
TEXT_INDETERMINATE = "Indéterminé : données insuffisantes"

# Familles de donnees : deux sources de meme famille ne sont jamais comptees
# comme deux confirmations independantes. Une famille "unverified" signifie que
# l'origine des donnees n'est pas documentee : aucune independance n'est supposee.
FAMILY_UNVERIFIED = "unverified"


def is_known_family(family: str) -> bool:
    return not family.startswith(FAMILY_UNVERIFIED)


@dataclass(frozen=True)
class Issue:
    """Probleme detecte sur une donnee (coordonnees invalides, incoherence...)."""

    code: str
    severity: str  # "error" | "warning" | "info"
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass
class GeoResult:
    """Estimation renvoyee par UNE source (``None`` = non fourni par la source)."""

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
    family: str = FAMILY_UNVERIFIED
    kind: str = "online"  # "online" | "local"
    database_date: str | None = None
    issues: list[Issue] = field(default_factory=list)

    @property
    def point(self) -> tuple[float, float] | None:
        if self.latitude is None or self.longitude is None:
            return None
        return (self.latitude, self.longitude)


@dataclass
class NetworkInfo:
    """Informations reseau, avec la source de chaque champ."""

    isp: str | None = None
    organization: str | None = None
    asn: int | None = None
    domain: str | None = None
    timezone: str | None = None
    sources: dict[str, str] = field(default_factory=dict)


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
    def has_indicator(self) -> bool:
        return any(flag is True for flag in (self.vpn, self.proxy, self.tor, self.hosting))

    @property
    def status(self) -> str:
        flags = (self.vpn, self.proxy, self.tor, self.hosting)
        if self.has_indicator:
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
class PairComparison:
    """Comparaison de deux estimations."""

    source_a: str
    source_b: str
    distance_km: float | None
    same_country: bool | None
    same_region: bool | None
    same_city: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_a": self.source_a,
            "source_b": self.source_b,
            "distance_km": None if self.distance_km is None else round(self.distance_km, 1),
            "same_country": self.same_country,
            "same_region": self.same_region,
            "same_city": self.same_city,
        }


@dataclass
class Confidence:
    """Niveau de confiance PRUDENT et qualitatif. Ce n'est PAS une probabilite calibree."""

    level: str  # none | low | medium | higher | undetermined
    label: str
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "label": self.label,
            "is_probability": False,
            "explanation": list(self.explanation),
            "method": "Regles qualitatives de prudence, non calibrees statistiquement "
            "(voir docs/GEOLOCATION_METHOD.md).",
        }


@dataclass
class Comparison:
    """Resultat de la comparaison des estimations."""

    status: str  # no_data | single_source | concordant | divergent | contradictory
    pairs: list[PairComparison] = field(default_factory=list)
    max_divergence_km: float | None = None
    known_families: list[str] = field(default_factory=list)
    unverified_sources: list[str] = field(default_factory=list)
    reference_source: str | None = None
    notes: list[str] = field(default_factory=list)
    confidence: Confidence = field(default_factory=lambda: Confidence("none", "aucune"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "max_divergence_km": None if self.max_divergence_km is None else round(self.max_divergence_km, 1),
            "independent_families": list(self.known_families),
            "unverified_provenance_sources": list(self.unverified_sources),
            "position_selected_from": self.reference_source,
            "pairs": [p.to_dict() for p in self.pairs],
            "notes": list(self.notes),
        }


@dataclass
class ReverseGeocode:
    """Contexte geographique autour d'un point ESTIME (jamais l'adresse d'une personne)."""

    source: str
    zoom: int
    country: str | None = None
    country_code: str | None = None
    state: str | None = None
    county: str | None = None
    city: str | None = None
    neighbourhood: str | None = None
    country_matches_estimate: bool | None = None
    attribution: str = "© OpenStreetMap contributors (ODbL)"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "zoom": self.zoom,
            "country": self.country,
            "country_code": self.country_code,
            "state": self.state,
            "county": self.county,
            "city": self.city,
            "neighbourhood": self.neighbourhood,
            "country_matches_estimate": self.country_matches_estimate,
            "attribution": self.attribution,
            "notes": list(self.notes),
        }


@dataclass
class RDAPInfo:
    """Donnees d'enregistrement issues des registres Internet regionaux (RDAP / RFC 9083)."""

    source: str
    handle: str | None = None
    name: str | None = None
    cidr: str | None = None
    range_text: str | None = None
    country: str | None = None
    registry: str | None = None
    registrant: str | None = None
    abuse_email: str | None = None
    allocation_type: str | None = None
    registration_date: str | None = None
    last_changed: str | None = None
    country_matches_estimate: bool | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "handle": self.handle,
            "name": self.name,
            "cidr": self.cidr,
            "range": self.range_text,
            "country": self.country,
            "registry": self.registry,
            "registrant": self.registrant,
            "abuse_email": self.abuse_email,
            "allocation_type": self.allocation_type,
            "registration_date": self.registration_date,
            "last_changed": self.last_changed,
            "country_matches_estimate": self.country_matches_estimate,
            "notes": list(self.notes),
        }



def _estimate_dict(estimate: GeoResult) -> dict[str, Any]:
    links = maps.build_links(
        estimate.latitude, estimate.longitude, zoom=maps.zoom_for_radius(estimate.accuracy_radius_km)
    )
    return {
        "source": estimate.source,
        "kind": estimate.kind,
        "family": estimate.family,
        "database_date": estimate.database_date,
        "country": estimate.country,
        "country_code": estimate.country_code,
        "region": estimate.region,
        "city": estimate.city,
        "latitude": estimate.latitude,
        "longitude": estimate.longitude,
        "accuracy_radius_km": estimate.accuracy_radius_km,
        "maps_url": links.google if links else None,
        "osm_url": links.osm if links else None,
        "issues": [issue.to_dict() for issue in estimate.issues],
    }


@dataclass
class IPReport:
    """Rapport complet pour une adresse IP."""

    ip: str
    scope: str
    scope_description: str
    timestamp: str
    geo: GeoResult | None = None  # premiere estimation obtenue (source principale)
    estimates: list[GeoResult] = field(default_factory=list)
    network: NetworkInfo | None = None
    comparison: Comparison | None = None
    location: GeoResult | None = None  # estimation retenue pour l'affichage (None si contradictoire)
    anonymity: AnonymityResult | None = None
    links: maps.MapLinks | None = None
    reverse_dns: str | None = None
    reverse_geocode: ReverseGeocode | None = None
    rdap: RDAPInfo | None = None
    source_errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    offline: bool = False

    @property
    def maps_url(self) -> str | None:
        return self.links.google if self.links else None

    @property
    def osm_url(self) -> str | None:
        return self.links.osm if self.links else None

    def to_dict(self) -> dict[str, Any]:
        loc = self.location
        net = self.network
        anon = self.anonymity
        comparison = self.comparison
        source_names = [e.source for e in self.estimates]
        return {
            "ip": self.ip,
            "ip_scope": self.scope,
            "country": loc.country if loc else None,
            "country_code": loc.country_code if loc else None,
            "region": loc.region if loc else None,
            "city": loc.city if loc else None,
            "latitude": loc.latitude if loc else None,
            "longitude": loc.longitude if loc else None,
            "accuracy_radius_km": loc.accuracy_radius_km if loc else None,
            "timezone": net.timezone if net else None,
            "isp": net.isp if net else None,
            "organization": net.organization if net else None,
            "asn": net.asn if net else None,
            "domain": net.domain if net else None,
            "reverse_dns": self.reverse_dns,
            "vpn_detected": anon.json_flag(anon.vpn) if anon else None,
            "proxy_detected": anon.json_flag(anon.proxy) if anon else None,
            "tor_detected": anon.json_flag(anon.tor) if anon else None,
            "hosting_detected": anon.json_flag(anon.hosting) if anon else None,
            "anonymity_status": anon.status if anon else STATUS_INDETERMINATE,
            "anonymity_errors": list(anon.errors) if anon else [],
            "maps_url": self.maps_url,
            "osm_url": self.osm_url,
            "position_status": comparison.status if comparison else "no_data",
            "confidence": comparison.confidence.to_dict() if comparison else Confidence("none", "aucune").to_dict(),
            "comparison": comparison.to_dict() if comparison else None,
            "estimates": [_estimate_dict(e) for e in self.estimates],
            "reverse_geocode": self.reverse_geocode.to_dict() if self.reverse_geocode else None,
            "rdap": self.rdap.to_dict() if self.rdap else None,
            "source": {
                "geolocation": source_names,
                "position_selected_from": comparison.reference_source if comparison else None,
                "network": dict(net.sources) if net else {},
                "anonymity": list(anon.sources) if anon else [],
            },
            "source_errors": list(self.source_errors),
            "offline": self.offline,
            "timestamp": self.timestamp,
            "limitations": list(self.limitations),
        }
