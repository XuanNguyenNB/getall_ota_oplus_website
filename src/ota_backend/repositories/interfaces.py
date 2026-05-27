from __future__ import annotations

from typing import Protocol

from uuid import UUID

from ota_backend.domain.models import (
    Brand,
    CatalogDeviceCandidate,
    Device,
    DeviceCatalogImport,
    OtaProviderRelease,
    OtaTrack,
    Page,
    PersistedRelease,
    PublicActionDecision,
    Release,
    ResolveRequest,
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
    ) -> Page[Device]:
        ...

    def get_by_product_model(self, product_model: str) -> Device | None:
        ...

    def get_by_id(self, device_id: UUID) -> Device | None:
        ...

    def update_scan_state(
        self,
        device_id: UUID,
        *,
        active_track: OtaTrack,
        bootstrap_done: bool,
    ) -> Device:
        ...

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
    ) -> Device:
        ...

    def upsert_catalog_devices(self, devices: list[CatalogDeviceCandidate]) -> int:
        ...


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
    ) -> Page[Release]:
        ...

    def upsert_release(
        self,
        release: OtaProviderRelease,
        *,
        discovered_by: str,
    ) -> PersistedRelease:
        ...

    def get_by_id(self, release_id: UUID) -> Release | None:
        ...


class ScanRepository(Protocol):
    def create_run(
        self, *, cycle_day: int, total_tasks: int, status: str = "running"
    ) -> ScanRun:
        ...

    def create_task(self, *, scan_run_id: UUID, device_id: UUID) -> ScanTask:
        ...

    def list_tasks(self, scan_run_id: UUID) -> list[ScanTask]:
        ...

    def start_run(self, scan_run_id: UUID) -> ScanRun:
        ...

    def claim_next_queued_task(self, scan_run_id: UUID) -> ScanTask | None:
        ...

    def complete_task(
        self,
        task_id: UUID,
        *,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
        found_release_id: UUID | None,
        new_release: bool,
    ) -> ScanTask:
        ...

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
    ) -> ScanTask:
        ...

    def finish_run(self, scan_run_id: UUID, *, status: str, error_message: str | None = None) -> ScanRun:
        ...

    def latest_run(self) -> ScanRun | None:
        ...


class TelegramRepository(Protocol):
    def get_target_for_brand(self, brand: Brand) -> TelegramTarget | None:
        ...

    def enqueue_notification(
        self,
        *,
        release: Release,
        target: TelegramTarget,
    ) -> tuple[TelegramNotification, bool]:
        ...

    def claim_next_notification(self, *, max_attempts: int) -> TelegramDelivery | None:
        ...

    def mark_notification_sent(
        self, notification_id: UUID, *, telegram_message_id: int
    ) -> TelegramNotification:
        ...

    def mark_notification_failed(
        self, notification_id: UUID, *, error_message: str, retry_seconds: int
    ) -> TelegramNotification:
        ...


class CatalogImportRepository(Protocol):
    def start_import(self, *, source: str) -> DeviceCatalogImport:
        ...

    def complete_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        upserted_count: int,
        disabled_count: int,
    ) -> DeviceCatalogImport:
        ...

    def fail_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        disabled_count: int,
        error_message: str,
    ) -> DeviceCatalogImport:
        ...


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
    ) -> PublicActionDecision:
        ...


class AdminRepository(Protocol):
    def is_enabled_admin(self, user_id: UUID) -> bool:
        ...


class ResolverRepository(Protocol):
    def record(self, request: ResolveRequest) -> ResolveRequest:
        ...
