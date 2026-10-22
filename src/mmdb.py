"""Lecteur minimal du format MaxMind DB (.mmdb) en Python pur, sans dependance.

Specification : https://maxmind.github.io/MaxMind-DB/ (format ouvert).
Compatible avec les bases GeoLite2, DB-IP Lite et toute base respectant ce format.
Lecture seule ; aucune ecriture, aucun acces reseau.
"""

from __future__ import annotations

import ipaddress
import mmap
import struct
from pathlib import Path
from typing import Any

METADATA_MARKER = b"\xab\xcd\xefMaxMind.com"
DATA_SEPARATOR_SIZE = 16
MAX_DEPTH = 32


class MMDBError(Exception):
    """Fichier .mmdb illisible, corrompu ou non supporte."""


def _decode(buf: Any, base: int, offset: int, depth: int = 0) -> tuple[Any, int]:
    """Decode une valeur a ``base + offset`` ; renvoie ``(valeur, nouvel_offset)``."""
    if depth > MAX_DEPTH:
        raise MMDBError("Imbrication excessive dans la section de données.")
    try:
        ctrl = buf[base + offset]
        offset += 1
        kind = ctrl >> 5
        if kind == 1:  # pointeur
            ss, vvv = (ctrl >> 3) & 3, ctrl & 7
            width = ss + 1
            raw = int.from_bytes(buf[base + offset: base + offset + width], "big")
            offset += width
            pointer = (
                (vvv << 8) | raw if ss == 0
                else ((vvv << 16) | raw) + 2048 if ss == 1
                else ((vvv << 24) | raw) + 526336 if ss == 2
                else raw
            )
            value, _ = _decode(buf, base, pointer, depth + 1)
            return value, offset
        if kind == 0:  # type etendu
            kind = 7 + buf[base + offset]
            offset += 1
        size = ctrl & 0x1F
        if size == 29:
            size = 29 + buf[base + offset]
            offset += 1
        elif size == 30:
            size = 285 + int.from_bytes(buf[base + offset: base + offset + 2], "big")
            offset += 2
        elif size == 31:
            size = 65821 + int.from_bytes(buf[base + offset: base + offset + 3], "big")
            offset += 3
        return _decode_value(buf, base, offset, kind, size, depth)
    except (IndexError, struct.error, UnicodeDecodeError) as exc:
        raise MMDBError("Section de données tronquée ou corrompue.") from exc


def _decode_value(buf: Any, base: int, offset: int, kind: int, size: int, depth: int) -> tuple[Any, int]:
    start = base + offset
    if kind == 7:  # map
        result: dict[Any, Any] = {}
        for _ in range(size):
            key, offset = _decode(buf, base, offset, depth + 1)
            value, offset = _decode(buf, base, offset, depth + 1)
            result[key] = value
        return result, offset
    if kind == 11:  # array
        items = []
        for _ in range(size):
            value, offset = _decode(buf, base, offset, depth + 1)
            items.append(value)
        return items, offset
    if kind == 14:  # booleen : la valeur est dans la taille
        return bool(size), offset
    if kind == 13:  # marqueur de fin
        return None, offset
    chunk = bytes(buf[start: start + size])
    if len(chunk) != size:
        raise MMDBError("Section de données tronquée.")
    if kind == 2:
        return chunk.decode("utf-8"), offset + size
    if kind == 3:
        if size != 8:
            raise MMDBError("Double invalide.")
        return struct.unpack(">d", chunk)[0], offset + size
    if kind == 15:
        if size != 4:
            raise MMDBError("Float invalide.")
        return struct.unpack(">f", chunk)[0], offset + size
    if kind == 4:
        return chunk, offset + size
    if kind in (5, 6, 9, 10):
        return int.from_bytes(chunk, "big"), offset + size
    if kind == 8:
        return int.from_bytes(chunk, "big", signed=size == 4), offset + size
    raise MMDBError(f"Type de données non supporté : {kind}.")


class MMDBReader:
    """Lecteur d'un fichier .mmdb. Utiliser comme gestionnaire de contexte ou appeler ``close()``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        try:
            with self.path.open("rb") as handle:
                self._buf: Any = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError) as exc:
            raise MMDBError(f"Impossible de lire {self.path.name} : {exc}") from exc
        try:
            self._load_metadata()
        except MMDBError:
            self.close()
            raise
        except (KeyError, TypeError, ValueError) as exc:
            self.close()
            raise MMDBError(f"Métadonnées invalides dans {self.path.name}.") from exc

    def _load_metadata(self) -> None:
        position = self._buf.rfind(METADATA_MARKER)
        if position < 0:
            raise MMDBError(f"{self.path.name} n'est pas une base MaxMind DB valide.")
        meta, _ = _decode(self._buf, position + len(METADATA_MARKER), 0)
        if not isinstance(meta, dict):
            raise MMDBError("Métadonnées illisibles.")
        self.metadata: dict[str, Any] = meta
        self.node_count = int(meta["node_count"])
        self.record_size = int(meta["record_size"])
        self.ip_version = int(meta["ip_version"])
        if self.record_size not in (24, 28, 32) or self.ip_version not in (4, 6):
            raise MMDBError("Paramètres de base non supportés.")
        self._node_bytes = self.record_size // 4
        self._tree_size = self._node_bytes * self.node_count
        self._data_start = self._tree_size + DATA_SEPARATOR_SIZE
        if self._data_start > len(self._buf):
            raise MMDBError("Base tronquée : l'arbre de recherche dépasse la taille du fichier.")

    @property
    def database_type(self) -> str:
        return str(self.metadata.get("database_type", ""))

    @property
    def build_epoch(self) -> int | None:
        value = self.metadata.get("build_epoch")
        return int(value) if isinstance(value, int) else None

    def _read_record(self, node: int, bit: int) -> int:
        offset = node * self._node_bytes
        chunk = self._buf[offset: offset + self._node_bytes]
        if len(chunk) != self._node_bytes:
            raise MMDBError("Arbre de recherche tronqué.")
        if self.record_size == 24:
            return int.from_bytes(chunk[3 * bit: 3 * bit + 3], "big")
        if self.record_size == 28:
            if bit == 0:
                return ((chunk[3] & 0xF0) << 20) | int.from_bytes(chunk[0:3], "big")
            return ((chunk[3] & 0x0F) << 24) | int.from_bytes(chunk[4:7], "big")
        return int.from_bytes(chunk[4 * bit: 4 * bit + 4], "big")

    def get(self, ip: str) -> dict[str, Any] | None:
        """Renvoie l'enregistrement de ``ip`` ou ``None`` si absent. Leve ``ValueError`` si ``ip`` est invalide."""
        address = ipaddress.ip_address(ip)
        if address.version == 6 and self.ip_version == 4:
            return None
        packed = address.packed
        node = 0
        if address.version == 4 and self.ip_version == 6:
            for _ in range(96):
                if node >= self.node_count:
                    break
                node = self._read_record(node, 0)
        for index in range(len(packed) * 8):
            if node >= self.node_count:
                break
            bit = (packed[index >> 3] >> (7 - (index & 7))) & 1
            node = self._read_record(node, bit)
        if node == self.node_count:
            return None
        if node < self.node_count:
            raise MMDBError("Arbre de recherche invalide.")
        pointer = node - self.node_count - DATA_SEPARATOR_SIZE
        record, _ = _decode(self._buf, self._data_start, pointer)
        return record if isinstance(record, dict) else None

    def close(self) -> None:
        buf = getattr(self, "_buf", None)
        if buf is not None:
            buf.close()

    def __enter__(self) -> "MMDBReader":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
