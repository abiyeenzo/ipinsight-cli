"""Rendu terminal (Rich) et sérialisation JSON."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import SIGNATURE, __version__
from .disclaimer import WARNING_TEXT
from .maps import MAPS_DISCLAIMER
from .models import (
    STATUS_INDICATORS,
    STATUS_INDETERMINATE,
    STATUS_NO_INDICATOR,
    IPReport,
)

BANNER = r"""
 ___ ____ ___           _       _     _
|_ _|  _ \_ _|_ __  ___(_) __ _| |__ | |_
 | || |_) | || '_ \/ __| |/ _` | '_ \| __|
 | ||  __/| || | | \__ \ | (_| | | | | |_
|___|_|  |___|_| |_|___/_|\__, |_| |_|\__|
                          |___/
"""

NOT_AVAILABLE = "non disponible"


def make_console(no_color: bool = False, stderr: bool = False) -> Console:
    """Crée une console ; ``no_color`` désactive couleurs et styles."""
    if no_color:
        return Console(no_color=True, color_system=None, highlight=False, stderr=stderr)
    return Console(highlight=False, stderr=stderr)


def _symbols(console: Console) -> dict[str, str]:
    if (console.encoding or "").lower().startswith("utf"):
        return {"ok": "✔", "warn": "⚠", "err": "✖"}
    return {"ok": "[OK]", "warn": "[!]", "err": "[x]"}


def print_banner(console: Console) -> None:
    console.print(BANNER, style="bold cyan", markup=False)
    console.print(f"  v{__version__}", style="bold", markup=False)
    console.print(f"  {SIGNATURE}\n", style="dim", markup=False)


def print_warning_text(console: Console) -> None:
    console.print(Panel(WARNING_TEXT, title="Avertissement d'usage", border_style="yellow"))


def print_status(console: Console, kind: str, message: str) -> None:
    style = {"ok": "green", "warn": "yellow", "err": "red"}[kind]
    console.print(f"{_symbols(console)[kind]} {message}", style=style, markup=False)


def _value(value: object) -> str:
    return NOT_AVAILABLE if value is None else str(value)


def _section(title: str, rows: list[tuple[str, object]]) -> Table:
    table = Table(title=title, title_justify="left", show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold", no_wrap=True)
    table.add_column(overflow="fold")
    for label, value in rows:
        table.add_row(label, _value(value))
    return table


def render_report(console: Console, report: IPReport) -> None:
    """Affiche le rapport organisé par catégories."""
    console.print(_section("Adresse", [("IP", report.ip), ("Type", report.scope_description)]))
    geo = report.geo
    if geo is None:
        print_status(console, "warn", "Aucune géolocalisation : adresse non publique, aucune requête effectuée.")
        _render_limitations(console, report)
        return

    place = [
        ("Pays", f"{geo.country} ({geo.country_code})" if geo.country and geo.country_code else geo.country),
        ("Région", geo.region),
        ("Ville", geo.city),
        ("Fuseau horaire", geo.timezone),
    ]
    console.print()
    console.print(_section("Localisation estimée", place))

    console.print()
    console.print(_section("Réseau", [
        ("FAI (ISP)", geo.isp),
        ("Organisation", geo.organization),
        ("ASN", f"AS{geo.asn}" if geo.asn is not None else None),
        ("Domaine", geo.domain),
        ("DNS inverse", report.reverse_dns),
    ]))

    console.print()
    if geo.latitude is None or geo.longitude is None:
        print_status(console, "warn", "Coordonnées non fournies par la source.")
    else:
        radius = f"{geo.accuracy_radius_km} km" if geo.accuracy_radius_km is not None else "inconnu (non fourni)"
        console.print(_section("Coordonnées estimées (approximatives, pas un GPS)", [
            ("Latitude", geo.latitude),
            ("Longitude", geo.longitude),
            ("Rayon d'incertitude", radius),
            ("Google Maps", report.maps_url),
            ("OpenStreetMap", report.osm_url),
        ]))
        console.print(f"  {MAPS_DISCLAIMER}", style="dim", markup=False)

    console.print()
    _render_anonymity(console, report)
    _render_limitations(console, report)
    console.print(f"\n  Source : {geo.source} — {report.timestamp}", style="dim", markup=False)


def _render_anonymity(console: Console, report: IPReport) -> None:
    console.print("Indicateurs d'anonymisation (indicatif)", style="bold", markup=False)
    anon = report.anonymity
    if anon is None:
        console.print("  Analyse non effectuée (--no-anonymity).", markup=False)
        return
    kind = {STATUS_INDICATORS: "warn", STATUS_NO_INDICATOR: "ok", STATUS_INDETERMINATE: "warn"}[anon.status]
    for line in anon.summary_lines():
        print_status(console, kind, line)
    for error in anon.errors:
        console.print(f"  {error}", style="dim", markup=False)


def _render_limitations(console: Console, report: IPReport) -> None:
    if not report.limitations:
        return
    console.print("\nLimites", style="bold", markup=False)
    for item in report.limitations:
        console.print(f"  - {item}", style="dim", markup=False)


def to_json(report: IPReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def error_json(message: str, error_type: str, ip: str | None = None) -> str:
    return json.dumps({"ip": ip, "error": message, "error_type": error_type}, ensure_ascii=False, indent=2)
