"""Génération de liens cartographiques à partir de coordonnées estimées."""

from __future__ import annotations

import math
import shutil
import subprocess
import webbrowser
from urllib.parse import urlparse

ALLOWED_MAP_HOSTS = {"www.google.com", "www.openstreetmap.org"}

MAPS_DISCLAIMER = (
    "Ce lien affiche le point cartographique associé aux coordonnées estimées de l'adresse IP, "
    "et non nécessairement la position physique de la personne ou de l'appareil qui l'utilise."
)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_coordinates(latitude: object, longitude: object) -> tuple[float, float] | None:
    """Renvoie ``(lat, lon)`` si les valeurs sont valides, sinon ``None``."""
    if not (_is_number(latitude) and _is_number(longitude)):
        return None
    lat, lon = float(latitude), float(longitude)  # type: ignore[arg-type]
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def build_google_maps_url(latitude: object, longitude: object) -> str | None:
    coords = validate_coordinates(latitude, longitude)
    if coords is None:
        return None
    return f"https://www.google.com/maps?q={coords[0]:.6f},{coords[1]:.6f}"


def build_osm_url(latitude: object, longitude: object) -> str | None:
    coords = validate_coordinates(latitude, longitude)
    if coords is None:
        return None
    lat, lon = coords
    return f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=10/{lat:.6f}/{lon:.6f}"


def open_in_browser(url: str) -> bool:
    """Ouvre ``url`` dans le navigateur, uniquement si elle pointe vers un service cartographique connu."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_MAP_HOSTS:
        return False
    try:
        return bool(webbrowser.open(url))
    except webbrowser.Error:
        return False


_CLIPBOARD_COMMANDS = (
    ("pbcopy",),
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
    ("clip",),
)


def copy_to_clipboard(text: str) -> bool:
    """Copie ``text`` via un outil système connu. Les commandes sont fixes (aucune entrée utilisateur)."""
    for command in _CLIPBOARD_COMMANDS:
        executable = shutil.which(command[0])
        if executable is None:
            continue
        try:
            subprocess.run(  # noqa: S603 - commande fixe, texte passé sur stdin
                [executable, *command[1:]],
                input=text.encode("utf-8"),
                check=True,
                timeout=5,
                capture_output=True,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            continue
    return False
