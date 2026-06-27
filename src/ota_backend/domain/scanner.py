from __future__ import annotations

import re
from hashlib import sha256

from ota_backend.domain.models import Device, OtaTrack, ScanEligibility
from ota_backend.domain.ota import BOOTSTRAP_TRACK_ORDER, SUPPORTED_TRACKS

SCAN_CYCLE_DAYS = 7


def stable_scan_shard(product_model: str, *, cycle_days: int = SCAN_CYCLE_DAYS) -> int:
    digest = sha256(product_model.strip().upper().encode("utf-8")).hexdigest()
    return int(digest, 16) % cycle_days


def stable_group_scan_shard(device: Device, *, cycle_days: int = SCAN_CYCLE_DAYS) -> int:
    shard_key = device.scan_group_key.strip() or device.product_model
    digest = sha256(shard_key.upper().encode("utf-8")).hexdigest()
    return int(digest, 16) % cycle_days


def is_scan_capable(device: Device, *, failure_threshold: int | None = None) -> bool:
    if not device.scan_enabled:
        return False
    if device.scan_eligibility != "active_scan":
        return False
    if device.manifest_code is None:
        return False
    if failure_threshold is not None and device.consecutive_failures >= failure_threshold:
        return False
    return True


def scan_eligibility_for(*, scan_enabled: bool, manifest_code: str | None) -> ScanEligibility:
    if manifest_code is None:
        return "invalid_for_scan"
    return "active_scan" if scan_enabled else "archive_only"


def is_legacy_oneplus_scan_candidate(device: Device) -> bool:
    if device.brand != "oneplus":
        return False
    model = device.product_model.upper()
    name = device.name.lower()
    if model.startswith(("ONEPLUS7", "ONEPLUS8")) or "_BETA" in model:
        return True
    return re.search(r"\boneplus\s+(7|7t|8|8t)\b", name) is not None


def tracks_for_device(device: Device) -> list[OtaTrack]:
    if not device.bootstrap_done:
        return list(BOOTSTRAP_TRACK_ORDER)

    active_index = SUPPORTED_TRACKS.index(device.active_track)
    return [
        track for track in BOOTSTRAP_TRACK_ORDER if SUPPORTED_TRACKS.index(track) >= active_index
    ]


def is_retryable_scan_error(error_code: str) -> bool:
    return error_code in {"UPSTREAM_ERROR", "UPSTREAM_TIMEOUT", "HTTP_5XX", "CONNECTION_RESET"}
