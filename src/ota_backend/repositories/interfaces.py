from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from ota_backend.domain.models import (
    Brand,
    CatalogDeviceCandidate,
    Device,
    DeviceCatalogImport,
    EdlRom,
    OtaProviderRelease,
    OtaTrack,
    Page,
    PersistedRelease,
    PublicActionDecision,
    Release,
    ResolveRequest,
    ScanEligibility,
    ScanRun,
    ScanTask,
    TelegramDelivery,
    TelegramNotification,
    TelegramTarget,
)


class DeviceRepository(Protocol):
    def list_devices(
        self,
        *,
        q: str | None,
        brand: str | None,
        enabled_only: bool,
        limit: int,
        offset: int,
        scan_enabled_only: bool = False,
    ) -> Page[Device]: ...

    def list_scan_enabled_devices(
        self,
        *,
        brand: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Device]: ...

    def list_devices_by_scan_group(self, scan_group_key: str) -> list[Device]: ...

    def get_by_product_model(self, product_model: str) -> Device | None: ...

    def get_by_id(self, device_id: UUID) -> Device | None: ...

    def get_by_ids(self, device_ids: list[UUID]) -> dict[UUID, Device]:
        """Bulk lookup for a set of device IDs.

        Returns a dict keyed by the device IDs that were found. Callers must
        not assume the dict has an entry for every requested ID; missing
        rows simply mean the device no longer exists. The Supabase
        implementation should perform a single ``in`` filter so the scanner
        does not pay O(n) round-trips per scan run.
        """
        ...

    def update_scan_state(
        self,
        device_id: UUID,
        *,
        active_track: OtaTrack,
        bootstrap_done: bool,
    ) -> Device: ...

    def upsert_catalog_device(
        self,
        *,
        catalog_id: int | None,
        brand: Brand,
        name: str,
        product_model: str,
        manifest_code: str | None,
        scan_enabled: bool,
        source: str = "oxygen_updater",
    ) -> Device: ...

    def upsert_catalog_devices(self, devices: list[CatalogDeviceCandidate]) -> int: ...

    def set_scan_enabled(self, product_models: list[str], enabled: bool) -> list[Device]: ...

    def set_scan_eligibility(
        self,
        product_models: list[str],
        eligibility: ScanEligibility,
        *,
        scan_enabled: bool | None = None,
    ) -> list[Device]: ...

    def set_all_scan_enabled(self, enabled: bool) -> int: ...

    def count_scan_enabled(self) -> int: ...

    def count_scan_eligibility(self) -> dict[str, int]: ...

    def record_scan_success(self, device_id: UUID) -> Device: ...

    def record_scan_failure(
        self,
        device_id: UUID,
        *,
        error_code: str,
        error_message: str,
        archive_threshold: int,
    ) -> Device: ...


class ReleaseRepository(Protocol):
    def list_releases(
        self,
        *,
        q: str | None = None,
        brand: str | None = None,
        product_model: str | None = None,
        manifest_code: str | None = None,
        region_code: str | None = None,
        release_type: str | None = None,
        source: str | None = None,
        sort: str = "discovered",
        limit: int = 50,
        offset: int = 0,
        last_seen_since: datetime | None = None,
    ) -> Page[Release]: ...

    def upsert_release(
        self,
        release: OtaProviderRelease,
        *,
        discovered_by: str,
    ) -> PersistedRelease: ...

    def get_by_id(self, release_id: UUID) -> Release | None: ...


class EdlRomRepository(Protocol):
    def list_edl_roms(
        self,
        *,
        q: str | None = None,
        brand: str | None = None,
        product_model: str | None = None,
        region_code: str | None = None,
        sort: str = "build",
        limit: int = 50,
        offset: int = 0,
    ) -> Page[EdlRom]: ...

    def upsert_edl_roms(self, roms: list[EdlRom]) -> int: ...


class ScanRepository(Protocol):
    def create_run(
        self, *, cycle_day: int, total_tasks: int, status: str = "running"
    ) -> ScanRun: ...

    def create_task(self, *, scan_run_id: UUID, device_id: UUID) -> ScanTask: ...

    def list_tasks(self, scan_run_id: UUID) -> list[ScanTask]: ...

    def start_run(self, scan_run_id: UUID) -> ScanRun: ...

    def claim_next_queued_task(self, scan_run_id: UUID) -> ScanTask | None: ...

    def complete_task(
        self,
        task_id: UUID,
        *,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
        found_release_id: UUID | None,
        new_release: bool,
    ) -> ScanTask: ...

    def fail_task(
        self,
        task_id: UUID,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
        max_attempts: int,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
    ) -> ScanTask: ...

    def finish_run(
        self, scan_run_id: UUID, *, status: str, error_message: str | None = None
    ) -> ScanRun: ...

    def latest_run(self) -> ScanRun | None: ...

    def list_recent_runs(self, *, limit: int = 7) -> list[ScanRun]: ...


class TelegramRepository(Protocol):
    def get_target_for_brand(self, brand: Brand) -> TelegramTarget | None: ...

    def enqueue_notification(
        self,
        *,
        release: Release,
        target: TelegramTarget,
    ) -> tuple[TelegramNotification, bool]: ...

    def claim_next_notification(self, *, max_attempts: int) -> TelegramDelivery | None: ...

    def mark_notification_sent(
        self, notification_id: UUID, *, telegram_message_id: int
    ) -> TelegramNotification: ...

    def mark_notification_failed(
        self, notification_id: UUID, *, error_message: str, retry_seconds: int
    ) -> TelegramNotification: ...


class CatalogImportRepository(Protocol):
    def start_import(self, *, source: str) -> DeviceCatalogImport: ...

    def complete_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        upserted_count: int,
        disabled_count: int,
    ) -> DeviceCatalogImport: ...

    def fail_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        disabled_count: int,
        error_message: str,
    ) -> DeviceCatalogImport: ...


class PublicActionRepository(Protocol):
    def claim(
        self,
        *,
        action: str,
        actor_hash: str,
        query_key: str,
        limit: int,
        window_seconds: int,
        cooldown_seconds: int,
    ) -> PublicActionDecision: ...


class AdminRepository(Protocol):
    def is_enabled_admin(self, user_id: UUID) -> bool: ...


class ResolverRepository(Protocol):
    def record(self, request: ResolveRequest) -> ResolveRequest: ...
