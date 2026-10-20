"""Client HTTP minimal (bibliothèque standard) avec erreurs explicites.

La validation TLS reste toujours activée (contexte SSL par défaut).
Aucune donnée n'est envoyée ailleurs que vers l'URL demandée.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from . import __version__

USER_AGENT = f"IPInsight-CLI/{__version__} (+https://github.com/abiyeenzo)"
MIN_INTERVAL_SECONDS = 0.5
MAX_RESPONSE_BYTES = 2_000_000

_lock = threading.Lock()
_last_request_at = 0.0


class ProviderError(Exception):
    """Erreur générique d'un fournisseur de données."""


class NetworkUnavailableError(ProviderError):
    """Aucune connexion réseau exploitable."""


class ProviderTimeoutError(ProviderError):
    """Délai d'attente dépassé."""


class ProviderRateLimitError(ProviderError):
    """Quota ou limite de requêtes atteint (HTTP 429)."""


class ProviderResponseError(ProviderError):
    """Réponse invalide, incomplète ou refusée par le fournisseur."""


def _throttle() -> None:
    global _last_request_at
    with _lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def get_text(url: str, timeout: float) -> str:
    """Récupère ``url`` (HTTPS uniquement) et renvoie le corps décodé en UTF-8."""
    if not url.lower().startswith("https://"):
        raise ProviderResponseError("Seules les URL HTTPS sont autorisées.")
    _throttle()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - HTTPS imposé
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise ProviderRateLimitError("Limite de requêtes atteinte (HTTP 429).") from exc
        raise ProviderResponseError(f"Le fournisseur a répondu HTTP {exc.code}.") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ProviderTimeoutError("Délai d'attente dépassé.") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ProviderTimeoutError("Délai d'attente dépassé.") from exc
        raise NetworkUnavailableError(f"Connexion impossible : {exc.reason}") from exc
    except OSError as exc:
        raise NetworkUnavailableError(f"Erreur réseau : {exc}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderResponseError("Réponse trop volumineuse.")
    return raw.decode("utf-8", errors="replace")


def get_json(url: str, timeout: float) -> dict[str, Any]:
    """Récupère ``url`` et renvoie un objet JSON (dictionnaire)."""
    text = get_text(url, timeout)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError("Réponse JSON invalide.") from exc
    if not isinstance(data, dict):
        raise ProviderResponseError("Format de réponse inattendu.")
    return data
