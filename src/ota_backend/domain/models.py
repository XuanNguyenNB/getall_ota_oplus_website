from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID, uuid4

Brand = Literal["oppo", "realme", "oneplus"]
OtaTrack = Literal["A", "C", "F", "H"]
ScanRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ScanTaskStatus = Literal["queued", "running", "completed", "failed", "skipped"]
TelegramNotificationStatus = Literal["queued", "sending", "sent", "failed"]
CatalogImportStatus = Literal["running", "completed", "failed"]
ResolveStatus = Literal["success", "failed", "blocked"]

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class Device:
    id: UUID
    catalog_id: int | None
    brand: Brand
    name: str
    product_model: str
    manifest_code: str | None
    scan_enabled: bool
    active_track: OtaTrack
    bootstrap_done: bool = False
    manual_override: bool = False
    source: str = "manual"


@dataclass(frozen=True)
class CatalogDeviceCandidate:
    catalog_id: int | None
    brand: Brand
    name: str
    product_model: str
    manifest_code: str | None
    scan_enabled: bool
    source: str = "oxygen_updater"


@dataclass(frozen=True)
class OtaQuery:
    product_model: str
    manifest_code: str
    ota_track: OtaTrack
    rui_candidates: list[int]
    language: str
    beta: bool
    imei0: str | None = None
    imei1: str | None = None
    persist_result: bool = True
    brand: Brand | None = None


@dataclass(frozen=True)
class OtaProviderRelease:
    brand: Brand
    product_model: str
    manifest_code: str
    ota_track: OtaTrack
    rui_version: int
    real_ota_version: str
    real_version_name: str
    computed_ota_version: str
    version_type_id: str
    about_update_url: str | None
    download_url: str
    md5: str | None = None
    file_size: int | None = None
    security_patch: str | None = None
    raw_response: dict[str, Any] | None = None
    source: str = "live_provider"
    region_code: str | None = None
    release_type: str = "official"
    published_at: datetime | None = None
    source_last_event_kind: str | None = None
    source_last_event_at: datetime | None = None


@dataclass
class Release:
    id: UUID
    brand: Brand
    product_model: str
    manifest_code: str
    ota_track: OtaTrack
    rui_version: int
    real_ota_version: str
    real_version_name: str
    computed_ota_version: str
    version_type_id: str
    about_update_url: str | None
    download_url: str
    discovered_by: Literal["manual", "worker", "import"]
    discovered_at: datetime
    last_seen_at: datetime
    md5: str | None = None
    file_size: int | None = None
    security_patch: str | None = None
    raw_response: dict[str, Any] | None = None
    source: str = "live_provider"
    region_code: str | None = None
    release_type: str = "official"
    published_at: datetime | None = None
    source_last_event_kind: str | None = None
    source_last_event_at: datetime | None = None

    @classmethod
    def from_provider(
        cls, result: OtaProviderRelease, discovered_by: Literal["manual", "worker", "import"]
    ) -> "Release":
        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            brand=result.brand,
            product_model=result.product_model,
            manifest_code=result.manifest_code,
            ota_track=result.ota_track,
            rui_version=result.rui_version,
            real_ota_version=result.real_ota_version,
            real_version_name=result.real_version_name,
            computed_ota_version=result.computed_ota_version,
            version_type_id=result.version_type_id,
            about_update_url=result.about_update_url,
            download_url=result.download_url,
            discovered_by=discovered_by,
            discovered_at=now,
            last_seen_at=now,
            md5=result.md5,
            file_size=result.file_size,
            security_patch=result.security_patch,
            raw_response=result.raw_response,
            source=result.source,
            region_code=result.region_code,
            release_type=result.release_type,
            published_at=result.published_at,
            source_last_event_kind=result.source_last_event_kind,
            source_last_event_at=result.source_last_event_at,
        )


@dataclass(frozen=True)
class PersistedRelease:
    release: Release
    is_new: bool


@dataclass
class ScanRun:
    id: UUID
    status: ScanRunStatus
    cycle_day: int
    started_at: datetime
    finished_at: datetime | None = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    new_releases: int = 0
    error_message: str | None = None


@dataclass
class ScanTask:
    id: UUID
    scan_run_id: UUID
    device_id: UUID
    status: ScanTaskStatus
    attempt_count: int = 0
    tracks_checked: list[OtaTrack] = field(default_factory=list)
    rui_candidates_checked: list[int] = field(default_factory=list)
    found_release_id: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class TelegramTarget:
    id: UUID
    brand: Brand
    chat_id: int
    message_thread_id: int
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TelegramNotification:
    id: UUID
    release_id: UUID
    telegram_target_id: UUID
    status: TelegramNotificationStatus
    created_at: datetime
    telegram_message_id: int | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    attempt_count: int = 0
    last_attempt_at: datetime | None = None
    next_attempt_at: datetime | None = None


@dataclass(frozen=True)
class TelegramDelivery:
    notification: TelegramNotification
    release: Release
    target: TelegramTarget


@dataclass
class DeviceCatalogImport:
    id: UUID
    source: str
    status: CatalogImportStatus
    started_at: datetime
    fetched_count: int = 0
    upserted_count: int = 0
    disabled_count: int = 0
    error_message: str | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class PublicActionDecision:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass
class ResolveRequest:
    id: UUID
    source: Literal["web", "telegram", "internal"]
    status: ResolveStatus
    created_at: datetime
    input_url: str | None = None
    resolved_url: str | None = None
    telegram_user_id: int | None = None
    telegram_chat_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    expires_at: datetime | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def release_key(release: OtaProviderRelease | Release) -> tuple[str, str, str, str]:
    return (
        release.product_model.upper(),
        release.manifest_code.upper(),
        release.real_ota_version,
        release.download_url,
    )
