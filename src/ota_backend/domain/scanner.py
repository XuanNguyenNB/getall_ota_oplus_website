from __future__ import annotations

from hashlib import sha256

from ota_backend.domain.models import Device, OtaTrack
from ota_backend.domain.ota import BOOTSTRAP_TRACK_ORDER, SUPPORTED_TRACKS

SCAN_CYCLE_DAYS = 7


def stable_scan_shard(product_model: str, *, cycle_days: int = SCAN_CYCLE_DAYS) -> int:
    digest = sha256(product_model.strip().upper().encode("utf-8")).hexdigest()
    return int(digest, 16) % cycle_days


def tracks_for_device(device: Device) -> list[OtaTrack]:
    if not device.bootstrap_done:
        return list(BOOTSTRAP_TRACK_ORDER)

    active_index = SUPPORTED_TRACKS.index(device.active_track)
    return [
        track
        for track in BOOTSTRAP_TRACK_ORDER
        if SUPPORTED_TRACKS.index(track) >= active_index
    ]


def is_retryable_scan_error(error_code: str) -> bool:
    return error_code in {"UPSTREAM_ERROR", "UPSTREAM_TIMEOUT", "HTTP_5XX", "CONNECTION_RESET"}
