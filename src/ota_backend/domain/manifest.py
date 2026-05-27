from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ACCEPTED_MANIFEST_CODES: tuple[str, ...] = (
    "00",
    "A4",
    "A5",
    "A6",
    "A7",
    "1A",
    "1B",
    "1E",
    "2C",
    "33",
    "37",
    "38",
    "39",
    "3B",
    "3C",
    "3E",
    "44",
    "51",
    "75",
    "7B",
    "82",
    "83",
    "8D",
    "97",
    "9A",
    "9E",
)

ServerRegion = Literal[0, 1, 2, 3]


@dataclass(frozen=True)
class ManifestTarget:
    code: str
    nv_id: str
    server_region: ServerRegion
    server_region_label: str
    source: str
    live_query_enabled: bool = True


AUTHORITATIVE_MANIFEST_TARGETS: dict[str, ManifestTarget] = {
    code: ManifestTarget(
        code=code,
        nv_id=nv_id,
        server_region=server_region,
        server_region_label=label,
        source="Universal OTA DownloadeR REGIONS/SERVERS map; maintainer-approved live source",
    )
    for code, nv_id, server_region, label in (
        ("00", "00000000", 3, "EX"),
        ("A4", "10100100", 3, "APC"),
        ("A5", "10100101", 3, "OCA"),
        ("A6", "10100110", 3, "MEA"),
        ("A7", "10100111", 3, "ROW"),
        ("1A", "00011010", 3, "TW"),
        ("1B", "00011011", 3, "IN"),
        ("1E", "00011110", 3, "AU"),
        ("2C", "00101100", 3, "SG"),
        ("33", "00110011", 3, "ID"),
        ("37", "00110111", 3, "RU"),
        ("38", "00111000", 3, "MY"),
        ("39", "00111001", 3, "TH"),
        ("3B", "00111011", 3, "JP"),
        ("3C", "00111100", 3, "VN"),
        ("3E", "00111110", 3, "PH"),
        ("44", "01000100", 0, "EUEX"),
        ("51", "01010001", 0, "TR"),
        ("75", "01110101", 3, "EG"),
        ("7B", "01111011", 3, "MX"),
        ("82", "10000010", 3, "HK"),
        ("83", "10000011", 3, "SA"),
        ("8D", "10001101", 3, "EU-NO"),
        ("97", "10010111", 1, "CN"),
        ("9A", "10011010", 3, "LATAM"),
        ("9E", "10011110", 3, "BR"),
    )
}


def normalize_manifest_code(value: str) -> str:
    code = value.strip().upper()
    if code not in ACCEPTED_MANIFEST_CODES:
        raise ValueError("unsupported manifest code")
    return code


def get_authoritative_manifest_target(code: str) -> ManifestTarget | None:
    return AUTHORITATIVE_MANIFEST_TARGETS.get(normalize_manifest_code(code))


def manifest_blockers() -> list[str]:
    return [
        code
        for code in ACCEPTED_MANIFEST_CODES
        if code not in AUTHORITATIVE_MANIFEST_TARGETS
    ]


def live_manifest_map_complete() -> bool:
    return not manifest_blockers()
