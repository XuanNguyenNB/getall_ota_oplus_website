from __future__ import annotations

import html
import re

from ota_backend.domain.models import Brand
from ota_backend.domain.ota import derive_ota_model

REGION_SUFFIX_PATTERN = re.compile(
    r"\s*\((?:CN|IN|ID|TH|EU|EEA|GLO|GLOBAL|GL|ROW|APC|OCA|MEA|TW|JP|MY|SG|PH|RU|AU|BR|TR|MX|LATAM|SA|HK|EX|EUEX)\)\s*$",
    re.IGNORECASE,
)
TECHNICAL_NAME_PATTERN = re.compile(r"^[A-Z0-9_+-]{4,}$")


def infer_scan_group_name(*, brand: Brand, name: str, product_model: str) -> str:
    cleaned = html.unescape(name or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = _strip_region_suffixes(cleaned)
    if not cleaned or TECHNICAL_NAME_PATTERN.fullmatch(cleaned.upper()):
        cleaned = derive_ota_model(product_model)
    return _ensure_brand_prefix(brand, cleaned)


def infer_scan_group_key(*, brand: Brand, name: str, product_model: str) -> str:
    group_name = infer_scan_group_name(
        brand=brand,
        name=name,
        product_model=product_model,
    )
    slug = re.sub(r"[^a-z0-9]+", "-", group_name.lower()).strip("-")
    return slug or f"{brand}-{derive_ota_model(product_model).lower()}"


def _strip_region_suffixes(value: str) -> str:
    previous = value
    while True:
        current = REGION_SUFFIX_PATTERN.sub("", previous).strip()
        if current == previous:
            return current
        previous = current


def _ensure_brand_prefix(brand: Brand, value: str) -> str:
    lowered = value.lower()
    if brand == "oppo":
        return value if lowered.startswith("oppo ") else f"OPPO {value}"
    if brand == "oneplus":
        return value if lowered.startswith("oneplus ") else f"OnePlus {value}"
    return value if lowered.startswith("realme ") else f"realme {value}"
