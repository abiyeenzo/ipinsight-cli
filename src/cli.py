"""Interface en ligne de commande d'IPInsight CLI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from rich.console import Console

from . import SIGNATURE, __version__
from . import analysis, disclaimer, local_db, maps, output
from .http_client import (
    NetworkUnavailableError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .models import IPReport
from .validation import InvalidIPError

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_PUBLIC = 3
EXIT_INTERRUPTED = 130

EPILOG = (
    "Exemples :\n"
    "  python main.py --ip 8.8.8.8\n"
    "  python main.py --ip 8.8.8.8 --json\n"
    "  python main.py --self\n"
    "  python main.py --ip 8.8.8.8 --mmdb dbip-city-lite.mmdb --reverse-geocode\n"
    "  python main.py --ip 8.8.8.8 --offline --mmdb dbip-city-lite.mmdb\n"
    "  python main.py            (mode interactif dans un terminal)\n\n"
    "Codes de sortie : 0 succès, 1 erreur de source/réseau, 2 entrée invalide, "
    "3 adresse non publique, 130 interruption.\n\n" + SIGNATURE
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipinsight",
        description="IPInsight CLI : analyse informative d'une adresse IP publique "
        "(cybersécurité défensive, administration réseau, audits autorisés, apprentissage).",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="afficher cette aide et quitter")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--ip", metavar="ADRESSE", help="adresse IPv4 ou IPv6 publique à analyser")
    target.add_argument("--self", dest="self_ip", action="store_true",
                        help="analyser l'adresse IP publique de cette machine")
    target.add_argument("-i", "--interactive", action="store_true", help="forcer le mode interactif")
    parser.add_argument("--json", dest="as_json", action="store_true", help="sortie JSON structurée")
    parser.add_argument("--no-color", action="store_true", help="désactiver couleurs et styles")
    parser.add_argument("--no-anonymity", action="store_true",
                        help="ne pas interroger les sources VPN/proxy/Tor (moins de requêtes externes)")
    parser.add_argument("--rdns", action="store_true", help="ajouter une résolution DNS inverse (via votre résolveur)")
    parser.add_argument("--mmdb", action="append", default=[], metavar="FICHIER",
                        help="base locale .mmdb (répétable ; variable IPINSIGHT_MMDB acceptée). "
                        "Compare avec les sources en ligne ou fonctionne hors ligne")
    parser.add_argument("--offline", action="store_true",
                        help="aucune requête réseau : utilise uniquement les bases --mmdb")
    parser.add_argument("--reverse-geocode", action="store_true",
                        help="géocodage inverse facultatif du point estimé (Nominatim/OpenStreetMap, "
                        "envoie les coordonnées estimées)")
    parser.add_argument("--open-map", action="store_true", help="ouvrir le lien Google Maps dans le navigateur")
    parser.add_argument("--copy-map", action="store_true", help="copier le lien Google Maps dans le presse-papiers")
    parser.add_argument("--timeout", type=float, default=8.0, metavar="SECONDES",
                        help="délai d'attente réseau par requête (défaut : 8)")
    parser.add_argument("--disclaimer", action="store_true", help="afficher l'avertissement d'usage et quitter")
    parser.add_argument("--version", action="store_true", help="afficher la version et quitter")
    return parser


def _error_exit_info(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, NetworkUnavailableError):
        return "network_unavailable", f"Réseau indisponible : {exc}"
    if isinstance(exc, ProviderTimeoutError):
        return "timeout", f"Délai dépassé : {exc}"
    if isinstance(exc, ProviderRateLimitError):
        return "rate_limited", f"Quota du fournisseur atteint : {exc}"
    return "provider_error", f"Erreur du fournisseur : {exc}"


def _run_analysis(
    target: str | None,
    args: argparse.Namespace,
    console: Console,
    databases: Sequence[local_db.LocalDatabase] = (),
) -> int:
    try:
        report = analysis.analyze(
            target,
            timeout=args.timeout,
            check_anonymity=not args.no_anonymity,
            with_reverse_dns=args.rdns,
            reverse_geocode=args.reverse_geocode,
            databases=databases,
            offline=args.offline,
        )
    except InvalidIPError as exc:
        if args.as_json:
            print(output.error_json(str(exc), "invalid_ip", target))
        else:
            output.print_status(console, "err", str(exc))
        return EXIT_USAGE
    except ProviderError as exc:
        error_type, message = _error_exit_info(exc)
        if args.as_json:
            print(output.error_json(message, error_type, target))
        else:
            output.print_status(console, "err", message)
            output.print_status(console, "warn", "Aucun résultat affiché : les données ne sont jamais inventées.")
        return EXIT_ERROR

    _emit_report(report, args, console)
    return EXIT_OK if report.geo is not None else EXIT_NOT_PUBLIC


def _emit_report(report: IPReport, args: argparse.Namespace, console: Console) -> None:
    if args.as_json:
        print(output.to_json(report))
    else:
        output.render_report(console, report)
    if report.maps_url and args.copy_map:
        copied = maps.copy_to_clipboard(report.maps_url)
        _notice(args, console, "ok" if copied else "warn",
                "Lien copié dans le presse-papiers." if copied else "Presse-papiers indisponible dans cet environnement.")
    if report.maps_url and args.open_map:
        opened = maps.open_in_browser(report.maps_url)
        _notice(args, console, "ok" if opened else "warn",
                "Lien ouvert dans le navigateur." if opened else "Impossible d'ouvrir le navigateur ici.")


def _notice(args: argparse.Namespace, console: Console, kind: str, message: str) -> None:
    if args.as_json:
        print(message, file=sys.stderr)
    else:
        output.print_status(console, kind, message)


def _maybe_show_first_run_warning(args: argparse.Namespace) -> None:
    """Affiche l'avertissement au premier lancement (sur stderr pour garder stdout propre)."""
    if disclaimer.already_shown():
        return
    err_console = output.make_console(args.no_color, stderr=True)
    output.print_warning_text(err_console)
    disclaimer.mark_shown()


def _interactive(args: argparse.Namespace, console: Console, databases: Sequence[local_db.LocalDatabase]) -> int:
    output.print_banner(console)
    console.print("Commandes : <adresse IP> | self | disclaimer | help | quit\n", markup=False)
    while True:
        try:
            line = console.input("ipinsight> ").strip()
        except EOFError:
            return EXIT_OK
        lowered = line.lower()
        if not line:
            continue
        if lowered in {"q", "quit", "exit"}:
            return EXIT_OK
        if lowered in {"h", "help", "?"}:
            console.print("Saisissez une adresse IP publique, 'self', 'disclaimer' ou 'quit'.", markup=False)
        elif lowered == "disclaimer":
            output.print_warning_text(console)
        elif lowered == "self":
            _run_analysis(None, args, console, databases)
        else:
            _run_analysis(line, args, console, databases)
        console.print()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"IPInsight CLI {__version__}\n{SIGNATURE}")
        return EXIT_OK

    console = output.make_console(args.no_color)
    try:
        if args.disclaimer:
            output.print_warning_text(console)
            return EXIT_OK
        if args.timeout <= 0:
            parser.error("--timeout doit être strictement positif.")

        interactive = args.interactive or not (args.ip or args.self_ip)
        if interactive and (not sys.stdin.isatty() or args.as_json):
            parser.print_help()
            return EXIT_USAGE

        _maybe_show_first_run_warning(args)
        databases, db_errors = local_db.open_databases([*args.mmdb, *local_db.paths_from_environment()])
        try:
            for message in db_errors:
                if args.as_json:
                    print(f"Base locale ignorée : {message}", file=sys.stderr)
                else:
                    output.print_status(console, "warn", f"Base locale ignorée : {message}")
            if args.offline and not databases:
                message = "--offline nécessite au moins une base locale valide (--mmdb FICHIER)."
                if args.as_json:
                    print(output.error_json(message, "no_local_database", args.ip))
                else:
                    output.print_status(console, "err", message)
                return EXIT_USAGE
            if interactive:
                return _interactive(args, console, databases)
            if not args.as_json:
                output.print_banner(console)
            return _run_analysis(args.ip if args.ip else None, args, console, databases)
        finally:
            local_db.close_all(databases)
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur.", file=sys.stderr)
        return EXIT_INTERRUPTED
