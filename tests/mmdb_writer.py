"""Ecriture minimale de fichiers .mmdb de TEST (n'est pas utilisee par l'outil).

Permet de verifier le lecteur sans telecharger de base reelle : les donnees
sont entierement fictives.
"""

from __future__ import annotations

import ipaddress
import struct
from typing import Any

MARKER = b"\xab\xcd\xefMaxMind.com"


def _ctrl(kind: int, size: int) -> bytes:
    first = kind << 5 if kind <= 7 else 0
    ext = b"" if kind <= 7 else bytes([kind - 7])
    if size < 29:
        return bytes([first | size]) + ext
    if size < 285:
        return bytes([first | 29]) + ext + bytes([size - 29])
    if size < 65821:
        return bytes([first | 30]) + ext + (size - 285).to_bytes(2, "big")
    return bytes([first | 31]) + ext + (size - 65821).to_bytes(3, "big")


def encode(value: Any) -> bytes:
    if isinstance(value, bool):
        return _ctrl(14, int(value))
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _ctrl(2, len(raw)) + raw
    if isinstance(value, float):
        return _ctrl(3, 8) + struct.pack(">d", value)
    if isinstance(value, int):
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return _ctrl(6 if len(raw) <= 4 else 9, len(raw)) + raw
    if isinstance(value, dict):
        return _ctrl(7, len(value)) + b"".join(encode(k) + encode(v) for k, v in value.items())
    if isinstance(value, list):
        return _ctrl(11, len(value)) + b"".join(encode(v) for v in value)
    raise TypeError(type(value))


def _record_bytes(left: int, right: int, record_size: int) -> bytes:
    if record_size == 24:
        return left.to_bytes(3, "big") + right.to_bytes(3, "big")
    if record_size == 28:
        middle = ((left >> 24) << 4) | (right >> 24)
        return (left & 0xFFFFFF).to_bytes(3, "big") + bytes([middle]) + (right & 0xFFFFFF).to_bytes(3, "big")
    return left.to_bytes(4, "big") + right.to_bytes(4, "big")


def build_mmdb(
    entries: list[tuple[str, dict[str, Any]]],
    *,
    ip_version: int = 4,
    record_size: int = 24,
    database_type: str = "Test-City",
    build_epoch: int = 1_700_000_000,
) -> bytes:
    """Construit une base ``.mmdb`` a partir de ``(reseau CIDR, enregistrement)``."""
    nodes: list[list[Any]] = [[None, None]]
    data = b""
    for cidr, record in entries:
        network = ipaddress.ip_network(cidr)
        bits = [int(b) for b in format(int(network.network_address), f"0{network.max_prefixlen}b")][: network.prefixlen]
        if ip_version == 6 and network.version == 4:
            bits = [0] * 96 + bits
        offset = len(data)
        data += encode(record)
        node = 0
        for position, bit in enumerate(bits):
            last = position == len(bits) - 1
            if last:
                nodes[node][bit] = ("data", offset)
            else:
                nxt = nodes[node][bit]
                if not isinstance(nxt, int):
                    nodes.append([None, None])
                    nxt = len(nodes) - 1
                    nodes[node][bit] = nxt
                node = nxt
    node_count = len(nodes)

    def resolve(record: Any) -> int:
        if record is None:
            return node_count
        if isinstance(record, tuple):
            return node_count + 16 + record[1]
        return record

    tree = b"".join(_record_bytes(resolve(n[0]), resolve(n[1]), record_size) for n in nodes)
    metadata = {
        "node_count": node_count,
        "record_size": record_size,
        "ip_version": ip_version,
        "database_type": database_type,
        "languages": ["en"],
        "binary_format_major_version": 2,
        "binary_format_minor_version": 0,
        "build_epoch": build_epoch,
        "description": {"en": "base de test fictive"},
    }
    return tree + b"\x00" * 16 + data + MARKER + encode(metadata)


def city_record(
    lat: float | None,
    lon: float | None,
    *,
    country: str = "Testland",
    iso: str = "TL",
    region: str | None = "Test Region",
    city: str | None = "Test City",
    radius: int | None = None,
) -> dict[str, Any]:
    location: dict[str, Any] = {}
    if lat is not None:
        location["latitude"] = lat
    if lon is not None:
        location["longitude"] = lon
    if radius is not None:
        location["accuracy_radius"] = radius
    record: dict[str, Any] = {"country": {"iso_code": iso, "names": {"en": country}}, "location": location}
    if region:
        record["subdivisions"] = [{"names": {"en": region}}]
    if city:
        record["city"] = {"names": {"en": city}}
    return record
