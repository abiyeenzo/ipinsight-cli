"""Bases de geolocalisation locales (.mmdb) : fonctionnement hors ligne.

Aucune base n'est incluse dans le projet (licences). L'utilisateur fournit ses
propres fichiers, par exemple DB-IP Lite (CC BY 4.0, attribution requise) ou
GeoLite2 (compte MaxMind et EULA). Voir docs/DATA_SOURCES.md.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import coord_validation
from .mmdb import MMDBError, MMDBReader
from .models import FAMILY_UNVERIFIED, GeoResult

ENV_VAR = "IPINSIGHT_MMDB"
STALE_AFTER_DAYS = 120


class LocalDBError(Exception):
    """Base locale inutilisable."""


def detect_family(database_type: str) -> str:
    """Deduit la famille de donnees d'apres le type declare par la base (jamais d'apres le nom du fichier)."""
    lowered = database_type.lower().replace("_", "-")
    if "geolite2" in lowered or "geoip2" in lowered:
        return "maxmind"
    if "dbip" in lowered or "db-ip" in lowered:
        return "dbip"
    return f"{FAMILY_UNVERIFIED}:{database_type or 'inconnue'}"


def _names(node: object) -> str | None:
    if isinstance(node, dict):
        names = node.get("names")
        if isinstance(names, dict):
            value = names.get("en")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _text(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


@dataclass
class LocalDatabase:
    """Base locale ouverte."""

    path: Path
    reader: MMDBReader
    family: str
    database_type: str
    build_date: str | None

    @property
    def label(self) -> str:
        return f"base locale {self.path.name}"

    def age_days(self, now: datetime | None = None) -> int | None:
        epoch = self.reader.build_epoch
        if epoch is None:
            return None
        built = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return ((now or datetime.now(timezone.utc)) - built).days

    def close(self) -> None:
        self.reader.close()


def open_database(path: str | Path) -> LocalDatabase:
    try:
        reader = MMDBReader(path)
    except MMDBError as exc:
        raise LocalDBError(str(exc)) from exc
    epoch = reader.build_epoch
    build_date = datetime.fromtimestamp(epoch, tz=timezone.utc).date().isoformat() if epoch else None
    return LocalDatabase(
        path=Path(path),
        reader=reader,
        family=detect_family(reader.database_type),
        database_type=reader.database_type,
        build_date=build_date,
    )


def paths_from_environment() -> list[str]:
    raw = os.environ.get(ENV_VAR, "")
    return [part for part in raw.split(os.pathsep) if part.strip()]


def open_databases(paths: Iterable[str | Path]) -> tuple[list[LocalDatabase], list[str]]:
    """Ouvre les bases ; renvoie ``(bases, erreurs)`` sans interrompre sur une base defectueuse."""
    databases: list[LocalDatabase] = []
    errors: list[str] = []
    for path in paths:
        try:
            databases.append(open_database(path))
        except LocalDBError as exc:
            errors.append(f"{Path(path).name} : {exc}")
    return databases, errors


def lookup(database: LocalDatabase, ip: str) -> GeoResult | None:
    """Interroge une base locale ; ``None`` si l'adresse n'y figure pas."""
    try:
        record = database.reader.get(ip)
    except MMDBError as exc:
        raise LocalDBError(f"{database.path.name} : {exc}") from exc
    if record is None:
        return None
    return parse_record(record, ip, database)


def parse_record(record: dict[str, Any], ip: str, database: LocalDatabase) -> GeoResult:
    location = record.get("location") if isinstance(record.get("location"), dict) else {}
    point, issues = coord_validation.inspect_coordinates(location.get("latitude"), location.get("longitude"))
    country = record.get("country") if isinstance(record.get("country"), dict) else {}
    subdivisions = record.get("subdivisions")
    first_subdivision = subdivisions[0] if isinstance(subdivisions, list) and subdivisions else None
    radius = location.get("accuracy_radius")
    asn = record.get("autonomous_system_number")
    return GeoResult(
        ip=ip,
        country=_names(country),
        country_code=_text(country.get("iso_code")),
        region=_names(first_subdivision),
        city=_names(record.get("city")),
        latitude=point[0] if point else None,
        longitude=point[1] if point else None,
        accuracy_radius_km=float(radius) if isinstance(radius, (int, float)) and not isinstance(radius, bool) and radius >= 0 else None,
        timezone=_text(location.get("time_zone")),
        organization=_text(record.get("autonomous_system_organization")),
        asn=asn if isinstance(asn, int) and not isinstance(asn, bool) and asn > 0 else None,
        source=database.label,
        family=database.family,
        kind="local",
        database_date=database.build_date,
        issues=issues,
    )


def staleness_note(database: LocalDatabase) -> str | None:
    age = database.age_days()
    if age is not None and age > STALE_AFTER_DAYS:
        return f"{database.path.name} date de {age} jours : les estimations peuvent être périmées."
    return None


def close_all(databases: Sequence[LocalDatabase]) -> None:
    for database in databases:
        database.close()
