"""Avertissement d'usage et mémorisation de son affichage (aucune adresse IP stockée)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

WARNING_TEXT = (
    "Cet outil est destiné à l'apprentissage, à l'administration réseau et aux analyses de "
    "cybersécurité autorisées. Avant toute analyse dans un contexte professionnel, assurez-vous de "
    "disposer des autorisations nécessaires et de respecter la législation applicable ainsi que les "
    "conditions d'utilisation des sources de données. La géolocalisation IP est approximative et ne "
    "permet pas de déterminer de manière fiable l'adresse exacte d'une personne."
)

_MARKER_NAME = "disclaimer_shown"


def config_dir() -> Path:
    """Dossier de configuration (ne contient qu'un marqueur, jamais d'adresses IP)."""
    override = os.environ.get("IPINSIGHT_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "ipinsight-cli"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ipinsight-cli"


def already_shown() -> bool:
    return (config_dir() / _MARKER_NAME).exists()


def mark_shown() -> None:
    """Mémorise l'affichage ; échoue silencieusement si le dossier n'est pas inscriptible."""
    try:
        directory = config_dir()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / _MARKER_NAME).write_text("1\n", encoding="utf-8")
    except OSError:
        pass
