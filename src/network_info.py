"""Informations réseau complémentaires : DNS inverse (optionnel)."""

from __future__ import annotations

import socket
import threading

from .validation import InvalidIPError, classify_ip


def reverse_dns(ip: str, timeout: float = 5.0) -> str | None:
    """Renvoie le nom d'hôte (PTR) de ``ip`` ou ``None``.

    La requête DNS part vers le résolveur système de la machine. L'adresse est
    validée au préalable ; aucune commande système n'est exécutée.
    """
    try:
        check = classify_ip(ip)
    except InvalidIPError:
        return None
    if not check.is_public:
        return None

    outcome: list[str | None] = [None]

    def worker() -> None:
        try:
            outcome[0] = socket.gethostbyaddr(check.address)[0]
        except (OSError, UnicodeError):
            outcome[0] = None

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)
    return outcome[0] if not thread.is_alive() else None
