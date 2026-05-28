from __future__ import annotations

import argparse
import csv
import html as html_lib
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx

from ota_backend.app import create_app
from ota_backend.config import get_settings
from ota_backend.domain.models import Brand, CatalogDeviceCandidate, OtaProviderRelease, OtaTrack
from ota_backend.domain.ota import (
    CATALOG_REGION_MANIFEST_MAP,
    derive_ota_model,
    infer_brand,
    infer_manifest_code,
    normalize_product_model,
)
from ota_backend.repositories.interfaces import (
    CatalogImportRepository,
    DeviceRepository,
    ReleaseRepository,
)

OXYGEN_DEVICES_URL = "https://oxygenupdater.com/api/v2.10/devices/all"
OXYGEN_HEADERS = {
    "User-Agent": "Oxygen_updater_7.1.0",
    "X-Requested-With": "com.arjanvlek.oxygenupdater",
}
LSCTOOL_HEADERS = {"User-Agent": "Mozilla/5.0"}

OPPO_CN_SITEMAP_URL = "https://www.oppo.com/cn/sitemap.xml"
OPPO_CN_ONEPLUS_URL = "https://www.oppo.com/cn/oneplus/smartphones/"
OPPO_CN_REALME_URL = "https://www.oppo.com/cn/realme/smartphones/"
COLOROS_ROM_BRAND_LIST_URL = "https://www.coloros.com/api/colorOS/business/rom/brandList"
COLOROS_ROM_PRODUCT_LIST_URL = "https://www.coloros.com/api/colorOS/business/rom/productList"
LSCTOOL_OTA_DATA_URL = "https://ota.lsctool.online/data/ota_data.json"
LSCTOOL_DEVICE_DATA_URL = "https://ota.lsctool.online/data/device_data.json"
LSCTOOL_DEFAULT_REGIONS_URL = "https://ota.lsctool.online/data/default_regions.txt"
DOMESTIC_CN_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "domestic_cn_models.csv"
DOMESTIC_CN_MANIFEST_CODE = "97"
DOMESTIC_CN_SOURCE = "domestic_cn"
LSCTOOL_CN_CATALOG_SOURCE = "lsctool_cn_catalog"
LSCTOOL_ARCHIVE_SOURCE = "lsctool_archive"
DOMESTIC_FETCH_WORKERS = 8

P_MODEL_PATTERN = re.compile(r"\bP[A-Z0-9]{2,5}\d{2,3}\b")
RMX_MODEL_PATTERN = re.compile(r"\bRMX\d{3,5}\b")
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_TITLE_PATTERN = re.compile(
    r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)",
    re.IGNORECASE | re.DOTALL,
)
HREF_PATTERN = re.compile(r"https?[^\"\\'<> ]+")
SCRIPT_SRC_PATTERN = re.compile(r"<script[^>]+src=[\"']([^\"']+)", re.IGNORECASE)
NETWORK_MODEL_FIELD_PATTERN = re.compile(
    r"name:\"\u5165\u7f51\u578b\u53f7\",value:\[([^\]]+)\]"
)
OTA_TRACK_PATTERN = re.compile(r"_11\.([ACFH])\.")
VERSION_MAJOR_PATTERN = re.compile(r"^[A-Z0-9_+-]+_(\d{1,2})\.")
LSCTOOL_TIMEZONE = timezone(timedelta(hours=7))
TRACK_RANK: dict[OtaTrack, int] = {"A": 0, "C": 1, "F": 2, "H": 3}
LSCTOOL_REGION_MANIFEST_MAP = {**CATALOG_REGION_MANIFEST_MAP, "GL": "A7"}


@dataclass(frozen=True)
class CatalogImportSummary:
    fetched_count: int
    upserted_count: int
    disabled_count: int
    skipped_count: int = 0
    error_count: int = 0
    dry_run: bool = False


@dataclass(frozen=True)
class DomesticCatalogFetch:
    candidates: list[CatalogDeviceCandidate]
    skipped_count: int = 0
    error_count: int = 0


@dataclass(frozen=True)
class LsctoolArchiveFetch:
    devices: list[CatalogDeviceCandidate]
    releases: list[OtaProviderRelease]
    skipped_count: int = 0
    error_count: int = 0


class CatalogImporter:
    def __init__(
        self,
        *,
        device_repository: DeviceRepository,
        import_repository: CatalogImportRepository,
        fetch_rows: Callable[[], list[dict[str, Any]]],
    ) -> None:
        self._device_repository = device_repository
        self._import_repository = import_repository
        self._fetch_rows = fetch_rows

    def import_oxygen(self) -> CatalogImportSummary:
        run = self._import_repository.start_import(source="oxygen_updater")
        rows: list[dict[str, Any]] = []
        disabled_count = 0
        try:
            rows = self._fetch_rows()
            candidates: dict[str, CatalogDeviceCandidate] = {}
            for row in rows:
                if not _is_enabled(row.get("enabled")):
                    disabled_count += 1
                    continue
                name = str(row.get("name") or "").strip()
                for product_model in split_product_models(str(row.get("product_names") or "")):
                    candidates[product_model] = CatalogDeviceCandidate(
                        catalog_id=_optional_int(row.get("id")),
                        brand=infer_brand(name, product_model),
                        name=name or product_model,
                        product_model=product_model,
                        manifest_code=infer_manifest_code(product_model, name),
                        scan_enabled=True,
                        source="oxygen_updater",
                    )
            upserted_count = self._device_repository.upsert_catalog_devices(
                list(candidates.values())
            )
        except Exception as exc:
            self._import_repository.fail_import(
                run.id,
                fetched_count=len(rows),
                disabled_count=disabled_count,
                error_message="CATALOG_UNAVAILABLE",
            )
            raise RuntimeError("CATALOG_UNAVAILABLE") from exc

        self._import_repository.complete_import(
            run.id,
            fetched_count=len(rows),
            upserted_count=upserted_count,
            disabled_count=disabled_count,
        )
        return CatalogImportSummary(
            fetched_count=len(rows),
            upserted_count=upserted_count,
            disabled_count=disabled_count,
        )

    def import_candidates(
        self,
        *,
        source: str,
        candidates: list[CatalogDeviceCandidate],
        dry_run: bool = False,
        skipped_count: int = 0,
        error_count: int = 0,
    ) -> CatalogImportSummary:
        if dry_run:
            return CatalogImportSummary(
                fetched_count=len(candidates),
                upserted_count=0,
                disabled_count=0,
                skipped_count=skipped_count,
                error_count=error_count,
                dry_run=True,
            )

        run = self._import_repository.start_import(source=source)
        try:
            upserted_count = self._device_repository.upsert_catalog_devices(candidates)
        except Exception as exc:
            self._import_repository.fail_import(
                run.id,
                fetched_count=len(candidates),
                disabled_count=0,
                error_message="CATALOG_UNAVAILABLE",
            )
            raise RuntimeError("CATALOG_UNAVAILABLE") from exc

        self._import_repository.complete_import(
            run.id,
            fetched_count=len(candidates),
            upserted_count=upserted_count,
            disabled_count=0,
        )
        return CatalogImportSummary(
            fetched_count=len(candidates),
            upserted_count=upserted_count,
            disabled_count=0,
            skipped_count=skipped_count,
            error_count=error_count,
        )


class ReleaseArchiveImporter:
    def __init__(
        self,
        *,
        device_repository: DeviceRepository,
        release_repository: ReleaseRepository,
        import_repository: CatalogImportRepository,
    ) -> None:
        self._device_repository = device_repository
        self._release_repository = release_repository
        self._import_repository = import_repository

    def import_lsctool_archive(
        self,
        archive: LsctoolArchiveFetch,
        *,
        dry_run: bool = False,
    ) -> CatalogImportSummary:
        if dry_run:
            return CatalogImportSummary(
                fetched_count=len(archive.releases),
                upserted_count=0,
                disabled_count=0,
                skipped_count=archive.skipped_count,
                error_count=archive.error_count,
                dry_run=True,
            )

        run = self._import_repository.start_import(source=LSCTOOL_ARCHIVE_SOURCE)
        try:
            self._ensure_archive_devices(archive.devices)
            upserted_count = 0
            highest_track_by_model: dict[str, OtaTrack] = {}
            for release in archive.releases:
                release = self._route_archive_release(release)
                persisted = self._release_repository.upsert_release(
                    release,
                    discovered_by="import",
                )
                upserted_count += 1
                highest_track_by_model[release.product_model] = _higher_track(
                    highest_track_by_model.get(release.product_model),
                    persisted.release.ota_track,
                )
            self._update_archive_scan_state(highest_track_by_model)
        except Exception as exc:
            self._import_repository.fail_import(
                run.id,
                fetched_count=len(archive.releases),
                disabled_count=0,
                error_message="LSCTOOL_ARCHIVE_UNAVAILABLE",
            )
            raise RuntimeError("LSCTOOL_ARCHIVE_UNAVAILABLE") from exc

        self._import_repository.complete_import(
            run.id,
            fetched_count=len(archive.releases),
            upserted_count=upserted_count,
            disabled_count=0,
        )
        return CatalogImportSummary(
            fetched_count=len(archive.releases),
            upserted_count=upserted_count,
            disabled_count=0,
            skipped_count=archive.skipped_count,
            error_count=archive.error_count,
        )

    def _ensure_archive_devices(self, devices: list[CatalogDeviceCandidate]) -> None:
        for device in devices:
            if self._device_repository.get_by_product_model(device.product_model) is not None:
                continue
            is_cn_device = device.manifest_code == DOMESTIC_CN_MANIFEST_CODE
            self._device_repository.upsert_catalog_device(
                catalog_id=None,
                brand=device.brand,
                name=device.name,
                product_model=device.product_model,
                manifest_code=device.manifest_code,
                scan_enabled=is_cn_device,
                source=LSCTOOL_CN_CATALOG_SOURCE if is_cn_device else LSCTOOL_ARCHIVE_SOURCE,
            )

    def _route_archive_release(self, release: OtaProviderRelease) -> OtaProviderRelease:
        base_model = derive_ota_model(release.product_model)
        page = self._device_repository.list_devices(
            q=base_model,
            brand=release.brand,
            enabled_only=False,
            limit=200,
            offset=0,
        )
        compatible = [
            device
            for device in page.items
            if derive_ota_model(device.product_model) == base_model
            and device.manifest_code == release.manifest_code
        ]
        exact = [
            device
            for device in compatible
            if device.product_model == release.product_model
        ]
        candidates = exact or compatible
        if len(candidates) != 1:
            return release
        target = candidates[0]
        if target.product_model == release.product_model:
            return release
        return replace(release, product_model=target.product_model)

    def _update_archive_scan_state(self, highest_track_by_model: dict[str, OtaTrack]) -> None:
        for product_model, track in highest_track_by_model.items():
            device = self._device_repository.get_by_product_model(product_model)
            if device is None or device.manual_override:
                continue
            self._device_repository.update_scan_state(
                device.id,
                active_track=track,
                bootstrap_done=True,
            )


def fetch_oxygen_rows(*, timeout_seconds: float = 30) -> list[dict[str, Any]]:
    response = httpx.get(OXYGEN_DEVICES_URL, headers=OXYGEN_HEADERS, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise RuntimeError("invalid Oxygen catalog response")
    return payload


def fetch_domestic_cn_candidates(*, timeout_seconds: float = 30) -> DomesticCatalogFetch:
    candidates: list[CatalogDeviceCandidate] = []
    skipped_count = 0
    error_count = 0

    for fetcher in (
        lambda: fetch_oppo_cn_specs_candidates(timeout_seconds=timeout_seconds),
        lambda: fetch_coloros_rom_candidates(timeout_seconds=timeout_seconds),
        lambda: fetch_opposhop_listing_candidates(
            OPPO_CN_ONEPLUS_URL,
            brand="oneplus",
            source="opposhop_cn",
            timeout_seconds=timeout_seconds,
        ),
        lambda: fetch_opposhop_listing_candidates(
            OPPO_CN_REALME_URL,
            brand="realme",
            source="opposhop_cn",
            timeout_seconds=timeout_seconds,
        ),
        lambda: fetch_lsctool_cn_catalog_candidates(timeout_seconds=timeout_seconds),
    ):
        try:
            result = fetcher()
        except Exception:
            error_count += 1
            continue
        candidates.extend(result.candidates)
        skipped_count += result.skipped_count
        error_count += result.error_count

    seed_candidates = load_domestic_cn_seed()
    candidates.extend(seed_candidates)
    deduped = _dedupe_candidates(candidates)
    if not deduped and error_count:
        raise RuntimeError("domestic CN catalog sources returned no usable models")
    return DomesticCatalogFetch(
        candidates=deduped,
        skipped_count=skipped_count,
        error_count=error_count,
    )


def fetch_lsctool_cn_catalog_candidates(*, timeout_seconds: float = 30) -> DomesticCatalogFetch:
    with httpx.Client(headers=LSCTOOL_HEADERS, timeout=timeout_seconds) as client:
        device_data = client.get(LSCTOOL_DEVICE_DATA_URL).raise_for_status().json()
        default_regions = client.get(LSCTOOL_DEFAULT_REGIONS_URL).raise_for_status().text
    if not isinstance(device_data, dict):
        raise RuntimeError("invalid LSCTool device catalog response")
    return parse_lsctool_cn_catalog(
        device_data=device_data,
        default_regions_text=default_regions,
    )


def parse_lsctool_cn_catalog(
    *,
    device_data: dict[str, Any],
    default_regions_text: str,
) -> DomesticCatalogFetch:
    candidates: list[CatalogDeviceCandidate] = []
    skipped_count = 0
    default_regions = parse_default_regions_text(default_regions_text)
    for product_model, region_code in default_regions.items():
        if region_code.upper() != "CN":
            continue
        metadata = device_data.get(product_model)
        metadata = metadata if isinstance(metadata, dict) else {}
        device_name = str(metadata.get("device_name") or product_model).strip()
        brand = _infer_lsctool_brand(device_name, product_model)
        if brand is None:
            skipped_count += 1
            continue
        try:
            candidates.append(
                _domestic_candidate(
                    brand=brand,
                    name=_normalize_lsctool_cn_name(device_name, brand),
                    product_model=product_model,
                    source=LSCTOOL_CN_CATALOG_SOURCE,
                )
            )
        except ValueError:
            skipped_count += 1
    return DomesticCatalogFetch(
        candidates=_dedupe_candidates(candidates),
        skipped_count=skipped_count,
    )


def fetch_lsctool_archive(*, timeout_seconds: float = 30) -> LsctoolArchiveFetch:
    with httpx.Client(headers=LSCTOOL_HEADERS, timeout=timeout_seconds) as client:
        ota_data = client.get(LSCTOOL_OTA_DATA_URL).raise_for_status().json()
        device_data = client.get(LSCTOOL_DEVICE_DATA_URL).raise_for_status().json()
        default_regions = client.get(LSCTOOL_DEFAULT_REGIONS_URL).raise_for_status().text
    if not isinstance(ota_data, dict) or not isinstance(device_data, dict):
        raise RuntimeError("invalid LSCTool archive response")
    return parse_lsctool_archive(
        ota_data=ota_data,
        device_data=device_data,
        default_regions_text=default_regions,
    )


def parse_lsctool_archive(
    *,
    ota_data: dict[str, Any],
    device_data: dict[str, Any],
    default_regions_text: str = "",
) -> LsctoolArchiveFetch:
    default_regions = parse_default_regions_text(default_regions_text)
    devices: dict[str, CatalogDeviceCandidate] = {}
    releases: list[OtaProviderRelease] = []
    skipped_count = 0

    for raw_model, raw_rows in ota_data.items():
        if not isinstance(raw_rows, list):
            skipped_count += 1
            continue
        try:
            product_model = normalize_product_model(str(raw_model))
        except ValueError:
            skipped_count += len(raw_rows)
            continue
        metadata = device_data.get(product_model)
        metadata = metadata if isinstance(metadata, dict) else {}
        device_name = str(metadata.get("device_name") or product_model).strip()
        brand = _infer_lsctool_brand(device_name, product_model)
        if brand is None:
            skipped_count += len(raw_rows)
            continue
        normalized_name = _normalize_lsctool_device_name(device_name, brand)
        fallback_region = default_regions.get(product_model)

        for row in raw_rows:
            if not isinstance(row, dict):
                skipped_count += 1
                continue
            release = parse_lsctool_release_row(
                row,
                product_model=product_model,
                brand=brand,
                fallback_region=fallback_region,
            )
            if release is None:
                skipped_count += 1
                continue
            devices.setdefault(
                product_model,
                CatalogDeviceCandidate(
                    catalog_id=None,
                    brand=brand,
                    name=normalized_name,
                    product_model=product_model,
                    manifest_code=release.manifest_code,
                    scan_enabled=False,
                    source=LSCTOOL_ARCHIVE_SOURCE,
                ),
            )
            releases.append(release)

    return LsctoolArchiveFetch(
        devices=list(devices.values()),
        releases=releases,
        skipped_count=skipped_count,
    )


def parse_lsctool_release_row(
    row: dict[str, Any],
    *,
    product_model: str,
    brand: Brand,
    fallback_region: str | None = None,
) -> OtaProviderRelease | None:
    download_url = str(row.get("download_check_link") or "").strip()
    real_version_name = str(row.get("version_name") or "").strip()
    real_ota_version = str(row.get("ota_version") or "").strip()
    region_code = str(row.get("region_code") or fallback_region or "").strip().upper()
    if not download_url or not real_version_name or not region_code:
        return None
    manifest_code = LSCTOOL_REGION_MANIFEST_MAP.get(region_code)
    if manifest_code is None:
        return None
    track = _infer_archive_track(real_ota_version, real_version_name)
    if track is None:
        return None
    rui_version = _infer_archive_rui_version(real_version_name)
    if rui_version is None:
        return None
    release_type = "beta" if bool(row.get("is_gray")) else "official"
    return OtaProviderRelease(
        brand=brand,
        product_model=product_model,
        manifest_code=manifest_code,
        ota_track=track,
        rui_version=rui_version,
        real_ota_version=real_ota_version or real_version_name,
        real_version_name=real_version_name,
        computed_ota_version=real_ota_version or real_version_name,
        version_type_id=release_type,
        about_update_url=str(row.get("about_update_url") or "").strip() or None,
        download_url=download_url,
        security_patch=str(row.get("security_os") or "").strip() or None,
        raw_response={"source": LSCTOOL_ARCHIVE_SOURCE, "row": row},
        source=LSCTOOL_ARCHIVE_SOURCE,
        region_code=region_code,
        release_type=release_type,
        published_at=_parse_lsctool_time(row.get("published_time")),
        source_last_event_kind=str(row.get("last_event_kind") or "").strip() or None,
        source_last_event_at=_parse_lsctool_time(row.get("last_event_time")),
    )


def fetch_oppo_cn_specs_candidates(*, timeout_seconds: float = 30) -> DomesticCatalogFetch:
    sitemap = httpx.get(OPPO_CN_SITEMAP_URL, timeout=timeout_seconds).text
    urls = parse_oppo_cn_specs_urls(sitemap)
    return _fetch_product_pages(
        urls,
        parser=lambda body, url: parse_oppo_cn_specs_page(body, url),
        timeout_seconds=timeout_seconds,
    )


def fetch_coloros_rom_candidates(*, timeout_seconds: float = 30) -> DomesticCatalogFetch:
    brand_payload = httpx.get(COLOROS_ROM_BRAND_LIST_URL, timeout=timeout_seconds).json()
    brand_rows = brand_payload.get("data") if isinstance(brand_payload, dict) else None
    if not isinstance(brand_rows, list):
        raise RuntimeError("invalid ColorOS brand list response")

    candidates: list[CatalogDeviceCandidate] = []
    error_count = 0
    for brand_row in brand_rows:
        if not isinstance(brand_row, dict) or "id" not in brand_row:
            continue
        try:
            response = httpx.get(
                COLOROS_ROM_PRODUCT_LIST_URL,
                params={"brandId": brand_row["id"]},
                timeout=timeout_seconds,
            )
            payload = response.json()
            product_rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(product_rows, list):
                error_count += 1
                continue
            candidates.extend(parse_coloros_rom_product_rows(product_rows))
        except Exception:
            error_count += 1
    return DomesticCatalogFetch(
        candidates=_dedupe_candidates(candidates),
        error_count=error_count,
    )


def fetch_opposhop_listing_candidates(
    listing_url: str,
    *,
    brand: Brand,
    source: str,
    timeout_seconds: float = 30,
) -> DomesticCatalogFetch:
    listing = httpx.get(listing_url, timeout=timeout_seconds).text
    urls = parse_opposhop_product_urls(listing)
    return _fetch_product_pages(
        urls,
        parser=lambda body, url: parse_opposhop_product_page(
            body,
            brand=brand,
            source=source,
            url=url,
        ),
        timeout_seconds=timeout_seconds,
    )


def parse_oppo_cn_specs_urls(sitemap_xml: str) -> list[str]:
    root = ET.fromstring(sitemap_xml)
    urls = [
        node.text.strip()
        for node in root.findall(".//{*}loc")
        if node.text and "/cn/smartphones/" in node.text and "/specs/" in node.text
    ]
    return sorted(dict.fromkeys(urls))


def parse_oppo_cn_specs_page(html_text: str, url: str) -> list[CatalogDeviceCandidate]:
    name = _normalize_domestic_name(_extract_title(html_text) or _name_from_url(url), "oppo")
    return [
        _domestic_candidate(
            brand="oppo",
            name=name,
            product_model=code,
            source="oppo_cn_specs",
        )
        for code in sorted(set(P_MODEL_PATTERN.findall(html_text)))
    ]


def parse_coloros_rom_product_rows(rows: list[dict[str, Any]]) -> list[CatalogDeviceCandidate]:
    candidates: list[CatalogDeviceCandidate] = []
    for row in rows:
        product_code = str(row.get("productCode") or "").strip().upper()
        product_name = str(row.get("productName") or product_code).strip()
        if not product_code:
            continue
        try:
            candidates.append(
                _domestic_candidate(
                    brand="oppo",
                    name=_normalize_domestic_name(product_name, "oppo"),
                    product_model=product_code,
                    source="coloros_rom",
                )
            )
        except ValueError:
            continue
    return candidates


def parse_opposhop_product_urls(listing_html: str) -> list[str]:
    urls: list[str] = []
    for sku_id in sorted(set(re.findall(r"skuId=(\d+)", listing_html))):
        urls.append(f"https://www.opposhop.cn/cn/m/product/index?skuId={sku_id}")
    for raw_url in HREF_PATTERN.findall(listing_html):
        url = html_lib.unescape(raw_url)
        parsed = urlparse(url)
        if parsed.netloc.endswith("opposhop.cn") and re.search(r"/cn/web/products/\d+\.html", parsed.path):
            urls.append(url.split("#", 1)[0])
    return sorted(dict.fromkeys(urls))


def parse_opposhop_product_page(
    html_text: str,
    *,
    brand: Brand,
    source: str,
    url: str,
) -> list[CatalogDeviceCandidate]:
    pattern = RMX_MODEL_PATTERN if brand == "realme" else P_MODEL_PATTERN
    codes = _extract_network_model_codes(html_text, pattern)
    name = _normalize_domestic_name(_extract_title(html_text) or _name_from_url(url), brand)
    candidates: list[CatalogDeviceCandidate] = []
    for code in codes:
        try:
            candidates.append(
                _domestic_candidate(
                    brand=brand,
                    name=name,
                    product_model=code,
                    source=source,
                )
            )
        except ValueError:
            continue
    return candidates


def load_domestic_cn_seed(path: Path = DOMESTIC_CN_SEED_PATH) -> list[CatalogDeviceCandidate]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "brand",
            "name",
            "product_model",
            "manifest_code",
            "source",
            "source_url",
            "scan_enabled",
        }
        if set(reader.fieldnames or []) != required:
            raise ValueError("domestic CN seed has invalid columns")
        candidates: list[CatalogDeviceCandidate] = []
        for row in reader:
            brand = str(row.get("brand") or "").strip().lower()
            product_model = str(row.get("product_model") or "").strip().upper()
            manifest_code = str(row.get("manifest_code") or "").strip().upper()
            name = str(row.get("name") or "").strip()
            source = str(row.get("source") or "").strip()
            if brand not in {"oppo", "oneplus", "realme"}:
                raise ValueError("domestic CN seed has invalid brand")
            if manifest_code != DOMESTIC_CN_MANIFEST_CODE:
                raise ValueError("domestic CN seed must use manifest 97")
            candidates.append(
                _domestic_candidate(
                    brand=brand,  # type: ignore[arg-type]
                    name=name,
                    product_model=product_model,
                    source=source or "domestic_cn_seed",
                    scan_enabled=_is_enabled(row.get("scan_enabled")),
                )
            )
        return candidates


def split_product_models(value: str) -> list[str]:
    models: list[str] = []
    for entry in re.split(r"[,;|\n]+", value):
        if entry.strip():
            try:
                models.append(normalize_product_model(entry))
            except ValueError:
                continue
    return models


def _fetch_product_pages(
    urls: list[str],
    *,
    parser: Callable[[str, str], list[CatalogDeviceCandidate]],
    timeout_seconds: float,
) -> DomesticCatalogFetch:
    candidates: list[CatalogDeviceCandidate] = []
    skipped_count = 0
    error_count = 0
    with ThreadPoolExecutor(max_workers=DOMESTIC_FETCH_WORKERS) as executor:
        future_urls = {
            executor.submit(_fetch_text, url, timeout_seconds): url
            for url in urls
        }
        for future in as_completed(future_urls):
            url = future_urls[future]
            try:
                body = future.result()
                page_candidates = parser(body, url)
                if not page_candidates:
                    skipped_count += 1
                candidates.extend(page_candidates)
            except Exception:
                error_count += 1
    return DomesticCatalogFetch(
        candidates=_dedupe_candidates(candidates),
        skipped_count=skipped_count,
        error_count=error_count,
    )


def _fetch_text(url: str, timeout_seconds: float) -> str:
    response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
    response.raise_for_status()
    return response.text


def _domestic_candidate(
    *,
    brand: Brand,
    name: str,
    product_model: str,
    source: str,
    scan_enabled: bool = True,
) -> CatalogDeviceCandidate:
    normalized = normalize_product_model(product_model)
    return CatalogDeviceCandidate(
        catalog_id=None,
        brand=brand,
        name=_normalize_domestic_name(name or normalized, brand),
        product_model=normalized,
        manifest_code=DOMESTIC_CN_MANIFEST_CODE,
        scan_enabled=scan_enabled,
        source=source,
    )


def _dedupe_candidates(candidates: list[CatalogDeviceCandidate]) -> list[CatalogDeviceCandidate]:
    deduped: dict[str, CatalogDeviceCandidate] = {}
    for candidate in candidates:
        deduped.setdefault(candidate.product_model.upper(), candidate)
    return list(deduped.values())


def parse_default_regions_text(raw_text: str) -> dict[str, str]:
    regions: dict[str, str] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                regions[normalize_product_model(parts[0])] = parts[1].upper()
            except ValueError:
                continue
    return regions


def _infer_lsctool_brand(name: str, product_model: str) -> Brand | None:
    lowered = name.lower()
    if "oppo" in lowered:
        return "oppo"
    if "oneplus" in lowered or "one plus" in lowered:
        return "oneplus"
    if "realme" in lowered:
        return "realme"
    if product_model.upper().startswith("RMX"):
        return "realme"
    return None


def _normalize_lsctool_device_name(name: str, brand: Brand) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip()
    if not cleaned:
        return brand.upper()
    if brand == "oppo" and cleaned.upper().startswith("OPPO "):
        return "OPPO " + cleaned[5:].title()
    if brand == "oneplus" and cleaned.upper().startswith("ONEPLUS "):
        return "OnePlus " + cleaned[8:].title()
    if brand == "realme" and cleaned.upper().startswith("REALME "):
        return "realme " + cleaned[7:].title()
    return cleaned.title()


def _normalize_lsctool_cn_name(name: str, brand: Brand) -> str:
    cleaned = re.sub(r"\s+", " ", html_lib.unescape(name)).strip()
    cleaned = cleaned.replace("\u4e00\u52a0", "OnePlus")
    cleaned = cleaned.replace("\u771f\u6211", "realme")
    prefixes = {
        "oppo": r"^oppo\s+",
        "oneplus": r"^(oneplus|one\s+plus)\s+",
        "realme": r"^realme\s+",
    }
    body = re.sub(prefixes[brand], "", cleaned, flags=re.IGNORECASE).strip()
    body = re.sub(r"\b(GT|NEO)(\d)", r"\1 \2", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+", " ", body).strip().title()
    body = re.sub(r"\bGt\b", "GT", body)
    body = re.sub(r"\bRmx\b", "RMX", body)
    body = re.sub(r"\b5g\b", "5G", body, flags=re.IGNORECASE)
    if brand == "oppo":
        return _normalize_domestic_name(f"OPPO {body}", brand)
    if brand == "oneplus":
        return _normalize_domestic_name(f"OnePlus {body}", brand)
    return _normalize_domestic_name(f"realme {body}", brand)


def _infer_archive_track(*values: str) -> OtaTrack | None:
    for value in values:
        match = OTA_TRACK_PATTERN.search(value or "")
        if match:
            return match.group(1)  # type: ignore[return-value]
    return None


def _infer_archive_rui_version(version_name: str) -> int | None:
    match = VERSION_MAJOR_PATTERN.search(version_name)
    if not match:
        return None
    return int(match.group(1))


def _parse_lsctool_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=LSCTOOL_TIMEZONE
        )
    except ValueError:
        return None


def _higher_track(current: OtaTrack | None, candidate: OtaTrack) -> OtaTrack:
    if current is None:
        return candidate
    return candidate if TRACK_RANK[candidate] > TRACK_RANK[current] else current


def _extract_title(html_text: str) -> str | None:
    for pattern in (META_TITLE_PATTERN, TITLE_PATTERN):
        match = pattern.search(html_text)
        if match:
            return html_lib.unescape(_strip_tags(match.group(1))).strip()
    return None


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _extract_network_model_codes(html_text: str, pattern: re.Pattern[str]) -> list[str]:
    field_values = " ".join(NETWORK_MODEL_FIELD_PATTERN.findall(html_lib.unescape(html_text)))
    return sorted(set(pattern.findall(field_values)))


def _normalize_domestic_name(name: str, brand: Brand) -> str:
    cleaned = html_lib.unescape(name).strip()
    cleaned = cleaned.replace("\u4e00\u52a0", "OnePlus")
    cleaned = cleaned.replace("\u771f\u6211", "realme")
    cleaned = re.sub(r"^(OnePlus|realme)(?=[A-Z0-9])", r"\1 ", cleaned)
    cleaned = re.split(r"\s*[|_-]\s*", cleaned, maxsplit=1)[0].strip()
    if cleaned and cleaned[0].isascii():
        cleaned = re.split(r"\s*[\u4e00-\u9fff]", cleaned, maxsplit=1)[0].strip() or cleaned
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if brand == "oppo" and not cleaned.lower().startswith("oppo"):
        cleaned = f"OPPO {cleaned}".strip()
    if brand == "oneplus" and not cleaned.lower().startswith("oneplus"):
        cleaned = f"OnePlus {cleaned}".strip()
    if brand == "realme" and not cleaned.lower().startswith("realme"):
        cleaned = f"realme {cleaned}".strip()
    if "(CN)" not in cleaned:
        cleaned = f"{cleaned} (CN)"
    return cleaned


def _name_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.split("/")[-2 if path.endswith("/specs") else -1]
    return slug.replace("-", " ").title()


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _is_enabled(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"} if not isinstance(value, bool) else value


def _format_summary(command: str, summary: CatalogImportSummary) -> str:
    dry_run = " dry_run=true" if summary.dry_run else ""
    return (
        f"catalog_import command={command} status=completed{dry_run} "
        f"fetched={summary.fetched_count} upserted={summary.upserted_count} "
        f"disabled={summary.disabled_count} skipped={summary.skipped_count} "
        f"errors={summary.error_count}"
    )


def _require_supabase(settings: Any) -> None:
    if settings.repository_backend != "supabase":
        raise SystemExit("Set REPOSITORY_BACKEND=supabase before importing the live catalog.")


def main() -> None:
    parser = argparse.ArgumentParser(description="OPlus OTA catalog maintenance")
    parser.add_argument(
        "command",
        choices=[
            "import-oxygen",
            "import-domestic-cn",
            "import-lsctool-archive",
            "import-all",
        ],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch import data without writing to DB where supported.",
    )
    args = parser.parse_args()
    settings = get_settings()

    if args.command in {"import-domestic-cn", "import-lsctool-archive"} and args.dry_run:
        if args.command == "import-domestic-cn":
            fetched = fetch_domestic_cn_candidates(
                timeout_seconds=settings.realme_ota_timeout_seconds
            )
            fetched_count = len(fetched.candidates)
        else:
            fetched = fetch_lsctool_archive(
                timeout_seconds=settings.realme_ota_timeout_seconds
            )
            fetched_count = len(fetched.releases)
        summary = CatalogImportSummary(
            fetched_count=fetched_count,
            upserted_count=0,
            disabled_count=0,
            skipped_count=fetched.skipped_count,
            error_count=fetched.error_count,
            dry_run=True,
        )
        print(_format_summary(args.command, summary))
        return
    if args.dry_run:
        raise SystemExit("--dry-run is only supported for import-domestic-cn and import-lsctool-archive.")

    _require_supabase(settings)
    app = create_app(settings=settings)
    importer = CatalogImporter(
        device_repository=app.state.device_repository,
        import_repository=app.state.catalog_import_repository,
        fetch_rows=lambda: fetch_oxygen_rows(timeout_seconds=settings.realme_ota_timeout_seconds),
    )

    if args.command in {"import-oxygen", "import-all"}:
        result = importer.import_oxygen()
        print(_format_summary("import-oxygen", result))

    if args.command in {"import-domestic-cn", "import-all"}:
        domestic = fetch_domestic_cn_candidates(timeout_seconds=settings.realme_ota_timeout_seconds)
        result = importer.import_candidates(
            source=DOMESTIC_CN_SOURCE,
            candidates=domestic.candidates,
            skipped_count=domestic.skipped_count,
            error_count=domestic.error_count,
        )
        print(_format_summary("import-domestic-cn", result))

    if args.command in {"import-lsctool-archive", "import-all"}:
        archive = fetch_lsctool_archive(timeout_seconds=settings.realme_ota_timeout_seconds)
        archive_importer = ReleaseArchiveImporter(
            device_repository=app.state.device_repository,
            release_repository=app.state.release_repository,
            import_repository=app.state.catalog_import_repository,
        )
        result = archive_importer.import_lsctool_archive(archive)
        print(_format_summary("import-lsctool-archive", result))


if __name__ == "__main__":
    main()
