"""Garde-fou : le caractere U+2014 (tiret cadratin) ne doit apparaitre dans aucun fichier du projet."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = chr(0x2014)  # U+2014, ecrit sans le caractere litteral
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", "venv"}


def test_no_em_dash_anywhere_in_project():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if EM_DASH in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []
