"""Rendu terminal (Rich) et serialisation JSON."""

from __future__ import annotations

import io
import json
from pathlib import Path

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
    GeoResult,
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

STATUS_TEXT = {
    "no_data": "Aucune coordonnée exploitable.",
    "single_source": "Une seule source : aucune comparaison possible.",
    "concordant": "Sources concordantes (écart modéré).",
    "divergent": "Sources divergentes : prudence.",
    "contradictory": "Sources contradictoires : aucune position fiable ne peut être choisie.",
}


def make_console(no_color: bool = False, stderr: bool = False) -> Console:
    """Cree une console ; ``no_color`` desactive couleurs et styles."""
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


def _print_url(console: Console, label: str, url: str) -> None:
    """Affiche une URL sur une ligne logique unique : Rich n'y insere aucun retour a la ligne."""
    console.print(f"  {label} :", style="bold", markup=False)
    console.print(f"  {url}", markup=False, soft_wrap=True)


def _place(estimate: GeoResult) -> str:
    parts = [estimate.city, estimate.region, estimate.country_code or estimate.country]
    return ", ".join(p for p in parts if p) or NOT_AVAILABLE


def _coords(estimate: GeoResult) -> str:
    if estimate.point is None:
        return NOT_AVAILABLE
    return f"{estimate.latitude:.6f}, {estimate.longitude:.6f}"


def _radius(estimate: GeoResult) -> str:
    return f"{estimate.accuracy_radius_km:g} km" if estimate.accuracy_radius_km is not None else "inconnu"


def _render_estimates(console: Console, report: IPReport) -> None:
    table = Table(title="Estimations par source", title_justify="left", pad_edge=False)
    for column in ("Source", "Lieu estimé", "Latitude, longitude", "Rayon", "Base du"):
        table.add_column(column, overflow="fold", no_wrap=column == "Latitude, longitude")
    for estimate in report.estimates:
        table.add_row(
            estimate.source,
            _place(estimate),
            _coords(estimate),
            _radius(estimate),
            _value(estimate.database_date) if estimate.kind == "local" else "service en ligne",
        )
    console.print(table)
    for estimate in report.estimates:
        for issue in estimate.issues:
            if issue.severity in ("error", "warning"):
                console.print(f"  [{estimate.source}] {issue.message}", style="yellow", markup=False)


def _render_comparison(console: Console, report: IPReport) -> None:
    comparison = report.comparison
    if comparison is None:
        return
    console.print("Comparaison des sources", style="bold", markup=False)
    kind = {"concordant": "ok", "single_source": "warn", "divergent": "warn"}.get(comparison.status, "warn")
    if comparison.status == "contradictory":
        kind = "err"
    print_status(console, kind, STATUS_TEXT[comparison.status])
    if comparison.max_divergence_km is not None:
        console.print(f"  Écart maximal entre sources : {comparison.max_divergence_km:.1f} km", markup=False)
    for pair in comparison.pairs:
        km = "n/d" if pair.distance_km is None else f"{pair.distance_km:.1f} km"
        console.print(f"  {pair.source_a} / {pair.source_b} : {km}", markup=False)
    for note in comparison.notes:
        console.print(f"  - {note}", style="dim", markup=False)
    confidence = comparison.confidence
    console.print(
        f"  Confiance (qualitative, pas une probabilité) : {confidence.label}", style="bold", markup=False
    )
    for line in confidence.explanation:
        console.print(f"    - {line}", style="dim", markup=False)


def _render_location(console: Console, report: IPReport) -> None:
    location = report.location
    if location is None:
        console.print(_section("Localisation estimée", [("Position retenue", "aucune (sources contradictoires)")]))
        return
    rows: list[tuple[str, object]] = [
        ("Pays", f"{location.country} ({location.country_code})" if location.country and location.country_code else location.country),
        ("Région", location.region),
        ("Ville", location.city),
        ("Fuseau horaire", report.network.timezone if report.network else None),
        ("Source retenue", location.source),
    ]
    console.print(_section("Localisation estimée (retenue par IPInsight parmi les sources)", rows))


def _render_map(console: Console, report: IPReport) -> None:
    links, location = report.links, report.location
    if links is None or location is None:
        reason = "sources contradictoires" if report.comparison and report.comparison.status == "contradictory" else "coordonnées non fournies"
        print_status(console, "warn", f"Aucun lien cartographique principal : {reason}.")
        _render_per_source_links(console, report)
        return
    console.print("Coordonnées estimées (approximatives, pas un GPS)", style="bold", markup=False)
    console.print(f"  Latitude : {links.lat_text}   Longitude : {links.lon_text}", markup=False)
    console.print(f"  Rayon d'incertitude : {_radius(location)}", markup=False)
    console.print(f"  À coller dans une carte : {links.plain}", markup=False, soft_wrap=True)
    _print_url(console, "Google Maps", links.google)
    _print_url(console, "OpenStreetMap", links.osm)
    console.print(f"  Zoom identique ({links.zoom}) et mêmes valeurs dans les deux liens.", style="dim", markup=False)
    console.print(f"  {MAPS_DISCLAIMER}", style="dim", markup=False)


def _render_per_source_links(console: Console, report: IPReport) -> None:
    """Sources en desaccord : un lien par source, pour comparer sans en privilegier une."""
    from . import maps

    shown = False
    for estimate in report.estimates:
        links = maps.build_links(
            estimate.latitude, estimate.longitude, zoom=maps.zoom_for_radius(estimate.accuracy_radius_km)
        )
        if links is None:
            continue
        if not shown:
            console.print("Liens par source (à comparer, aucune n'est privilégiée)", style="bold", markup=False)
            shown = True
        console.print(f"  {estimate.source} ({links.plain})", markup=False, soft_wrap=True)
        console.print(f"  {links.google}", markup=False, soft_wrap=True)
        console.print(f"  {links.osm}", markup=False, soft_wrap=True)


def _render_reverse_geocode(console: Console, report: IPReport) -> None:
    rg = report.reverse_geocode
    if rg is None:
        return
    console.print()
    rows: list[tuple[str, object]] = [
        ("Pays", rg.country), ("Région", rg.state), ("Département / comté", rg.county),
        ("Ville", rg.city), ("Quartier", rg.neighbourhood),
    ]
    console.print(_section(f"Contexte autour du point estimé ({rg.source}, zoom {rg.zoom})", rows))
    for note in rg.notes:
        console.print(f"  - {note}", style="dim", markup=False)
    console.print(f"  {rg.attribution}", style="dim", markup=False)


def _render_rdap(console: Console, report: IPReport) -> None:
    rdap = report.rdap
    if rdap is None:
        return
    console.print()
    rows: list[tuple[str, object]] = [
        ("Registre (RIR)", rdap.registry),
        ("Bloc / handle", rdap.handle),
        ("Nom du réseau", rdap.name),
        ("Préfixe CIDR", rdap.cidr),
        ("Plage IP", rdap.range_text),
        ("Titulaire déclaré", rdap.registrant),
        ("Pays d'enregistrement", rdap.country),
        ("Contact abus", rdap.abuse_email),
        ("Allocation / MAJ", _rdap_dates(rdap.registration_date, rdap.last_changed)),
    ]
    console.print(_section(f"Enregistrement RDAP ({rdap.source})", rows))
    for note in rdap.notes:
        console.print(f"  - {note}", style="dim", markup=False)


def _rdap_dates(registered: str | None, changed: str | None) -> str | None:
    if registered and changed:
        return f"{registered} (MAJ {changed})"
    return registered or changed


def render_report(console: Console, report: IPReport) -> None:
    """Affiche le rapport organise par categories."""
    console.print(_section("Adresse", [("IP", report.ip), ("Type", report.scope_description)]))
    if report.geo is None and not report.estimates and report.scope != "public":
        print_status(console, "warn", "Aucune géolocalisation : adresse non publique, aucune requête effectuée.")
        _render_limitations(console, report)
        return

    console.print()
    if report.estimates:
        _render_location(console, report)
        console.print()
        _render_estimates(console, report)
        console.print()
        _render_comparison(console, report)
        console.print()
        net = report.network
        if net is not None:
            console.print(_section("Réseau", [
                ("FAI (ISP)", net.isp),
                ("Organisation", net.organization),
                ("ASN", f"AS{net.asn}" if net.asn is not None else None),
                ("Domaine", net.domain),
                ("DNS inverse", report.reverse_dns),
            ]))
            console.print()
        _render_map(console, report)
        _render_reverse_geocode(console, report)
        _render_rdap(console, report)
    else:
        print_status(console, "warn", "Aucune estimation disponible.")
        _render_rdap(console, report)
    console.print()
    _render_anonymity(console, report)
    _render_source_errors(console, report)
    _render_limitations(console, report)
    names = ", ".join(e.source for e in report.estimates) or NOT_AVAILABLE
    console.print(f"\n  Sources : {names} - {report.timestamp}", style="dim", markup=False)


def _render_anonymity(console: Console, report: IPReport) -> None:
    console.print("Indicateurs d'anonymisation (indicatif)", style="bold", markup=False)
    anon = report.anonymity
    if anon is None:
        reason = "mode hors ligne" if report.offline else "--no-anonymity"
        console.print(f"  Analyse non effectuée ({reason}).", markup=False)
        return
    kind = {STATUS_INDICATORS: "warn", STATUS_NO_INDICATOR: "ok", STATUS_INDETERMINATE: "warn"}[anon.status]
    for line in anon.summary_lines():
        print_status(console, kind, line)
    if anon.has_indicator:
        console.print(
            "  La position estimée peut être celle d'un serveur intermédiaire, pas celle de l'appareil d'origine.",
            style="yellow", markup=False,
        )
    for error in anon.errors:
        console.print(f"  {error}", style="dim", markup=False)


def _render_source_errors(console: Console, report: IPReport) -> None:
    if not report.source_errors:
        return
    console.print("\nSources indisponibles ou incomplètes", style="bold", markup=False)
    for item in report.source_errors:
        console.print(f"  - {item}", style="dim", markup=False)


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


def format_report_text(report: IPReport, *, width: int = 100) -> str:
    """Genere le rapport complet en texte brut UTF-8 (sans codes ANSI)."""
    buffer = io.StringIO()
    console = Console(file=buffer, no_color=True, color_system=None, width=width, highlight=False)
    print_banner(console)
    render_report(console, report)
    return buffer.getvalue()


def write_report_file(report: IPReport, path: str | Path, *, as_json: bool = False) -> Path:
    """Enregistre le rapport dans ``path`` (JSON si ``as_json`` ou extension ``.json``, sinon texte)."""
    dest = Path(path)
    use_json = as_json or dest.suffix.lower() == ".json"
    content = (to_json(report) + "\n") if use_json else format_report_text(report)
    if dest.parent and str(dest.parent) not in ("", "."):
        dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest

