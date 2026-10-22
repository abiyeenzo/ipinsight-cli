"""Liens cartographiques construits à partir d'un seul couple de coordonnées validé.

Garanties :
  * latitude puis longitude, WGS84 décimal, signes conservés, point décimal ;
  * les liens Google Maps et OpenStreetMap sont construits à partir des MÊMES
    chaînes de caractères (``lat_text`` et ``lon_text``) ;
  * le niveau de zoom est identique dans les deux liens ;
  * le point représente une ESTIMATION, jamais une adresse ni un résultat de
    géocodage.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

ALLOWED_MAP_HOSTS = {"www.google.com", "www.openstreetmap.org"}
DEFAULT_ZOOM = 10  # échelle d'une ville : ne suggère pas une précision de rue
COORDINATE_DECIMALS = 6  # environ 0,1 m : aucun arrondi significatif

MAPS_DISCLAIMER = (
    "Ces liens affichent le point cartographique associé aux coordonnées estimées de l'adresse IP, "
    "et non nécessairement la position physique de la personne ou de l'appareil qui l'utilise. "
    "Les deux cartes reçoivent exactement les mêmes valeurs ; leurs fonds de carte, leurs libellés "
    "et leur gestion du zoom diffèrent."
)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_coordinates(latitude: object, longitude: object) -> tuple[float, float] | None:
    """Renvoie ``(lat, lon)`` si les valeurs sont des nombres WGS84 valides, sinon ``None``."""
    if not (_is_number(latitude) and _is_number(longitude)):
        return None
    lat, lon = float(latitude), float(longitude)  # type: ignore[arg-type]
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def format_coordinate(value: float) -> str:
    """Texte décimal à 6 décimales, point comme séparateur, sans « -0.000000 »."""
    return f"{round(value, COORDINATE_DECIMALS) + 0.0:.{COORDINATE_DECIMALS}f}"


def zoom_for_radius(radius_km: float | None) -> int:
    """Zoom d'affichage (1 à 19) selon le rayon d'incertitude ; ville (10) si inconnu."""
    if radius_km is None or not _is_number(radius_km) or radius_km < 0:
        return DEFAULT_ZOOM
    if radius_km <= 1:
        return 14
    if radius_km <= 5:
        return 13
    if radius_km <= 25:
        return 11
    if radius_km <= 100:
        return 9
    return 7


@dataclass(frozen=True)
class MapLinks:
    """Liens pour un même point. ``plain`` se colle dans la barre de recherche d'une carte."""

    latitude: float
    longitude: float
    lat_text: str
    lon_text: str
    zoom: int
    google: str
    osm: str
    plain: str


def build_links(latitude: object, longitude: object, *, zoom: int = DEFAULT_ZOOM) -> MapLinks | None:
    """Construit les liens ; ``None`` si les coordonnées sont absentes ou invalides."""
    coords = validate_coordinates(latitude, longitude)
    if coords is None:
        return None
    lat, lon = coords
    zoom = max(1, min(19, int(zoom)))
    lat_text, lon_text = format_coordinate(lat), format_coordinate(lon)
    return MapLinks(
        latitude=lat,
        longitude=lon,
        lat_text=lat_text,
        lon_text=lon_text,
        zoom=zoom,
        google=f"https://www.google.com/maps?q={lat_text},{lon_text}&z={zoom}",
        osm=f"https://www.openstreetmap.org/?mlat={lat_text}&mlon={lon_text}#map={zoom}/{lat_text}/{lon_text}",
        plain=f"{lat_text},{lon_text}",
    )


def build_google_maps_url(latitude: object, longitude: object, zoom: int = DEFAULT_ZOOM) -> str | None:
    links = build_links(latitude, longitude, zoom=zoom)
    return links.google if links else None


def build_osm_url(latitude: object, longitude: object, zoom: int = DEFAULT_ZOOM) -> str | None:
    links = build_links(latitude, longitude, zoom=zoom)
    return links.osm if links else None


def extract_coordinates(url: str) -> tuple[float, float] | None:
    """Relit ``(lat, lon)`` dans un lien Google Maps ou OpenStreetMap généré par ce module.

    Pour OpenStreetMap, le marqueur (``mlat``/``mlon``) et le centre (``#map=``) doivent
    concorder ; sinon ``None``. Sert à vérifier que deux liens désignent le même point.
    """
    parsed = urlparse(url)
    try:
        if parsed.hostname == "www.google.com":
            lat_s, lon_s = parse_qs(parsed.query)["q"][0].split(",")
            return validate_coordinates(float(lat_s), float(lon_s))
        if parsed.hostname == "www.openstreetmap.org":
            query = parse_qs(parsed.query)
            marker = (float(query["mlat"][0]), float(query["mlon"][0]))
            _zoom, frag_lat, frag_lon = parsed.fragment.removeprefix("map=").split("/")
            center = (float(frag_lat), float(frag_lon))
            if marker != center:
                return None
            return validate_coordinates(*marker)
    except (KeyError, ValueError, IndexError):
        return None
    return None


def links_are_consistent(links: MapLinks) -> bool:
    """Vrai si les deux liens relus donnent exactement le même couple de coordonnées."""
    google = extract_coordinates(links.google)
    osm = extract_coordinates(links.osm)
    return google is not None and google == osm


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
