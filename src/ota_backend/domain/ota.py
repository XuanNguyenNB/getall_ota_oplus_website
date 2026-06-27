from __future__ import annotations

import re

from ota_backend.domain.models import Brand, OtaTrack

SUPPORTED_TRACKS: tuple[OtaTrack, ...] = ("A", "C", "F", "H")
BOOTSTRAP_TRACK_ORDER: tuple[OtaTrack, ...] = ("H", "F", "C", "A")
DEFAULT_RUI_CANDIDATES = [8, 7, 6]
MANIFEST_SUFFIX_MAP = {
    "LATAM": "9A",
    "EUEX": "44",
    "EEA": "44",
    "APC": "A4",
    "OCA": "A5",
    "MEA": "A6",
    "ROW": "A7",
    "EU": "44",
    "PH": "3E",
    "RU": "37",
    "SG": "2C",
    "TW": "1A",
    "JP": "3B",
    "SA": "83",
    "ID": "33",
    "EX": "00",
    "MX": "7B",
    "AU": "1E",
    "HK": "82",
    "MY": "38",
    "TR": "51",
    "EG": "75",
    "BR": "9E",
    "IN": "1B",
    "TH": "39",
    "VN": "3C",
    "CN": "97",
}
# These extra catalog aliases can be removed for upstream model fallback even
# when they do not establish a safe manifest mapping by themselves.
QUERY_MODEL_SUFFIXES = (
    "LATAM",
    "EUEX",
    "_IND",
    "IND",
    "EEA",
    "APC",
    "OCA",
    "MEA",
    "ROW",
    "KZ",
    "LK",
    *(
        suffix
        for suffix in MANIFEST_SUFFIX_MAP
        if suffix not in {"LATAM", "EUEX", "EEA", "APC", "OCA", "MEA", "ROW"}
    ),
)
MODEL_PATTERN = re.compile(r"^[A-Z0-9_+-]{3,40}$")
CATALOG_REGION_MANIFEST_MAP = {
    "EX": "00",
    "APC": "A4",
    "OCA": "A5",
    "MEA": "A6",
    "ROW": "A7",
    "GLO": "A7",
    "GLOBAL": "A7",
    "TW": "1A",
    "IN": "1B",
    "AU": "1E",
    "SG": "2C",
    "ID": "33",
    "RU": "37",
    "MY": "38",
    "TH": "39",
    "JP": "3B",
    "VN": "3C",
    "PH": "3E",
    "EU": "44",
    "EUEX": "44",
    "EEA": "44",
    "TR": "51",
    "EG": "75",
    "MX": "7B",
    "HK": "82",
    "SA": "83",
    "EU-NO": "8D",
    "CN": "97",
    "LATAM": "9A",
    "BR": "9E",
}


def normalize_product_model(value: str) -> str:
    model = value.strip().upper()
    if not MODEL_PATTERN.fullmatch(model):
        raise ValueError("invalid product model")
    return model


def normalize_track(value: str) -> OtaTrack:
    track = value.strip().upper()
    if track not in SUPPORTED_TRACKS:
        raise ValueError("unsupported OTA track")
    return track


def normalize_rui_candidates(value: list[int] | None) -> list[int]:
    candidates = value or list(DEFAULT_RUI_CANDIDATES)
    if not candidates or len(candidates) > 5:
        raise ValueError("invalid RUI candidates")
    for candidate in candidates:
        if candidate < 1 or candidate > 9:
            raise ValueError("invalid RUI candidate")
    return candidates


def derive_ota_model(product_model: str) -> str:
    model = normalize_product_model(product_model)
    for suffix in QUERY_MODEL_SUFFIXES:
        if model.endswith(suffix) and len(model) > len(suffix) + 3:
            return model[: -len(suffix)]
    return model


def build_seed_ota_version(product_model: str, track: OtaTrack) -> str:
    ota_model = derive_ota_model(product_model)
    normalized_track = normalize_track(track)
    return f"{ota_model}_11.{normalized_track}.00_0000_000000000000"


def infer_brand(name: str | None, product_model: str) -> Brand:
    display_name = (name or "").lower()
    if "oppo" in display_name:
        return "oppo"
    if "realme" in display_name:
        return "realme"
    if "oneplus" in display_name:
        return "oneplus"
    if product_model.upper().startswith("RMX"):
        return "realme"
    return "oneplus" if product_model.upper().startswith(("CPH", "P")) else "oppo"


def infer_manifest_code(product_model: str, name: str | None = None) -> str | None:
    model = normalize_product_model(product_model)
    for suffix, manifest_code in MANIFEST_SUFFIX_MAP.items():
        if model.endswith(suffix) and len(model) > len(suffix) + 3:
            return manifest_code
    match = re.search(r"\(([^()]+)\)\s*$", name or "")
    if match:
        return CATALOG_REGION_MANIFEST_MAP.get(match.group(1).strip().upper())
    return None
