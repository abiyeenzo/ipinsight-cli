"""Calculs géographiques élémentaires (WGS84 décimal, degrés).

Limites à connaître :
  * La formule de Haversine suppose une Terre sphérique de rayon moyen
    6371,0088 km. L'erreur par rapport à l'ellipsoïde WGS84 peut atteindre
    environ 0,5 %, ce qui est négligeable pour comparer des estimations IP
    (dizaines ou centaines de km) mais insuffisant pour la géodésie de
    précision (utiliser alors Vincenty ou Karney).
  * Ces fonctions contrôlent et comparent des données existantes. Elles ne
    calculent jamais la position réelle d'une personne.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

EARTH_RADIUS_KM = 6371.0088

Point = tuple[float, float]  # (latitude, longitude)


def haversine_km(a: Point, b: Point) -> float:
    """Distance orthodromique entre deux points, en kilomètres."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    half_dlat = (lat2 - lat1) / 2
    half_dlon = (lon2 - lon1) / 2
    h = math.sin(half_dlat) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(half_dlon) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def swap_lat_lon(point: Point) -> Point:
    """Renvoie le point avec latitude et longitude permutées (pour détecter une inversion)."""
    return (point[1], point[0])


def pairwise_distances_km(points: Sequence[Point]) -> list[tuple[int, int, float]]:
    """Distances entre toutes les paires de points : liste de ``(i, j, km)`` avec ``i < j``."""
    return [
        (i, j, haversine_km(points[i], points[j]))
        for i in range(len(points))
        for j in range(i + 1, len(points))
    ]


def max_pairwise_km(points: Sequence[Point]) -> float | None:
    """Plus grand écart entre deux points, ou ``None`` s'il y a moins de deux points."""
    distances = pairwise_distances_km(points)
    return max((d for _, _, d in distances), default=None)


def medoid_index(points: Sequence[Point]) -> int | None:
    """Indice du point le plus central (somme des distances minimale).

    Un point réellement présent dans les données est toujours choisi, jamais une
    moyenne artificielle. En cas d'égalité, l'indice le plus petit l'emporte.
    """
    if not points:
        return None
    best_index, best_total = 0, math.inf
    for i, point in enumerate(points):
        total = sum(haversine_km(point, other) for other in points)
        if total < best_total - 1e-9:
            best_index, best_total = i, total
    return best_index


def in_bounding_box(point: Point, south: float, north: float, west: float, east: float) -> bool:
    """Vrai si ``point`` est dans la boîte englobante (gère l'antiméridien si ``west > east``)."""
    lat, lon = point
    if not south <= lat <= north:
        return False
    if west <= east:
        return west <= lon <= east
    return lon >= west or lon <= east


def within_radius_km(point: Point, center: Point, radius_km: float) -> bool:
    """Vrai si ``point`` est à au plus ``radius_km`` de ``center``."""
    return haversine_km(point, center) <= radius_km
