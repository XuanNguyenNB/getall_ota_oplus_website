from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import UUID
from uuid import uuid4

from ota_backend.domain.models import (
    Brand,
    CatalogDeviceCandidate,
    Device,
    DeviceCatalogImport,
    OtaTrack,
    OtaProviderRelease,
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
    release_key,
    utc_now,
)
from ota_backend.repositories.interfaces import (
    AdminRepository,
    DeviceRepository,
    CatalogImportRepository,
    PublicActionRepository,
    ReleaseRepository,
    ResolverRepository,
    ScanRepository,
    TelegramRepository,
)


def seed_devices() -> list[Device]:
    return [
        Device(
            id=UUID("11111111-1111-4111-8111-111111111111"),
            catalog_id=1515,
            brand="oneplus",
            name="OnePlus Nord CE6 (IN)",
            product_model="CPH2805IN",
            manifest_code="1B",
            scan_enabled=True,
            active_track="C",
            bootstrap_done=True,
        ),
        Device(
            id=UUID("22222222-2222-4222-8222-222222222222"),
            catalog_id=3301,
            brand="realme",
            name="Realme GT 2 Pro",
            product_model="RMX3301",
            manifest_code="1B",
            scan_enabled=True,
            active_track="H",
            bootstrap_done=False,
        ),
        Device(
            id=UUID("33333333-3333-4333-8333-333333333333"),
            catalog_id=4401,
            brand="oppo",
            name="OPPO Find X EU",
            product_model="CPH2305EU",
            manifest_code="44",
            scan_enabled=False,
            active_track="F",
            bootstrap_done=True,
        ),
    ]


class InMemoryDeviceRepository(DeviceRepository):
    def __init__(self, devices: list[Device] | None = None) -> None:
        self._devices = list(seed_devices() if devices is None else devices)

    def list_devices(
        self,
        *,
        q: str | None,
        brand: str | None,
        enabled_only: bool,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Device]:
        rows = self._devices
        if enabled_only:
            rows = [row for row in rows if row.scan_enabled]
        if brand:
            rows = [row for row in rows if row.brand == brand]
        if q:
            needle = q.lower()
            rows = [
                row
                for row in rows
                if needle in row.name.lower() or needle in row.product_model.lower()
            ]
        total = len(rows)
        return Page(items=rows[offset : offset + limit], total=total, limit=limit, offset=offset)

    def get_by_product_model(self, product_model: str) -> Device | None:
        normalized = product_model.upper()
        return next(
            (row for row in self._devices if row.product_model.upper() == normalized),
            None,
        )

    def get_by_id(self, device_id: UUID) -> Device | None:
        return next((row for row in self._devices if row.id == device_id), None)

    def update_scan_state(
        self,
        device_id: UUID,
        *,
        active_track: OtaTrack,
        bootstrap_done: bool,
    ) -> Device:
        for idx, existing in enumerate(self._devices):
            if existing.id == device_id:
                updated = replace(
                    existing,
                    active_track=active_track,
                    bootstrap_done=bootstrap_done,
                )
                self._devices[idx] = updated
                return updated
        raise KeyError(f"device not found: {device_id}")

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
        existing = self.get_by_product_model(product_model)
        if existing is not None and existing.manual_override:
            return existing
        if existing is not None:
            updated = replace(
                existing,
                catalog_id=catalog_id,
                brand=brand,
                name=name,
                manifest_code=manifest_code,
                scan_enabled=scan_enabled,
                source=source,
            )
            self._devices[self._devices.index(existing)] = updated
            return updated
        created = Device(
            id=uuid4(),
            catalog_id=catalog_id,
            brand=brand,
            name=name,
            product_model=product_model,
            manifest_code=manifest_code,
            scan_enabled=scan_enabled,
            active_track="C",
            source=source,
        )
        self._devices.append(created)
        return created

    def upsert_catalog_devices(self, devices: list[CatalogDeviceCandidate]) -> int:
        for device in devices:
            self.upsert_catalog_device(
                catalog_id=device.catalog_id,
                brand=device.brand,
                name=device.name,
                product_model=device.product_model,
                manifest_code=device.manifest_code,
                scan_enabled=device.scan_enabled,
                source=device.source,
            )
        return len(devices)


class InMemoryReleaseRepository(ReleaseRepository):
    def __init__(self, releases: list[Release] | None = None) -> None:
        self._releases = list([] if releases is None else releases)

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
        rows = self._releases
        if brand:
            rows = [row for row in rows if row.brand == brand]
        if product_model:
            rows = [
                row
                for row in rows
                if row.product_model.upper() == product_model.upper()
            ]
        if manifest_code:
            rows = [
                row
                for row in rows
                if row.manifest_code.upper() == manifest_code.upper()
            ]
        if region_code:
            rows = [
                row
                for row in rows
                if (row.region_code or "").upper() == region_code.upper()
            ]
        if release_type:
            rows = [
                row
                for row in rows
                if row.release_type.lower() == release_type.lower()
            ]
        if source:
            rows = [row for row in rows if row.source == source]
        if q:
            needle = q.lower()
            rows = [
                row
                for row in rows
                if needle in row.product_model.lower()
                or needle in row.real_version_name.lower()
                or needle in row.real_ota_version.lower()
            ]
        if sort == "published":
            rows = sorted(
                rows,
                key=lambda row: row.published_at or row.discovered_at,
                reverse=True,
            )
        else:
            rows = sorted(rows, key=lambda row: row.discovered_at, reverse=True)
        total = len(rows)
        return Page(items=rows[offset : offset + limit], total=total, limit=limit, offset=offset)

    def upsert_release(
        self,
        release: OtaProviderRelease,
        *,
        discovered_by: str,
    ) -> PersistedRelease:
        key = release_key(release)
        for idx, existing in enumerate(self._releases):
            if release_key(existing) == key:
                updated = replace(
                    existing,
                    last_seen_at=utc_now(),
                    region_code=existing.region_code or release.region_code,
                    published_at=existing.published_at or release.published_at,
                    source_last_event_kind=(
                        existing.source_last_event_kind or release.source_last_event_kind
                    ),
                    source_last_event_at=(
                        existing.source_last_event_at or release.source_last_event_at
                    ),
                    raw_response=existing.raw_response or release.raw_response,
                )
                self._releases[idx] = updated
                return PersistedRelease(release=updated, is_new=False)

        persisted = Release.from_provider(release, discovered_by=discovered_by)  # type: ignore[arg-type]
        if persisted.discovered_at.tzinfo is None:
            persisted.discovered_at = persisted.discovered_at.replace(tzinfo=timezone.utc)
        self._releases.append(persisted)
        return PersistedRelease(release=persisted, is_new=True)

    def get_by_id(self, release_id: UUID) -> Release | None:
        return next((row for row in self._releases if row.id == release_id), None)


class InMemoryScanRepository(ScanRepository):
    def __init__(self) -> None:
        self._runs: list[ScanRun] = []
        self._tasks: list[ScanTask] = []
        self._lock = Lock()

    def create_run(
        self, *, cycle_day: int, total_tasks: int, status: str = "running"
    ) -> ScanRun:
        now = utc_now()
        run = ScanRun(
            id=uuid4(),
            status=status,  # type: ignore[arg-type]
            cycle_day=cycle_day,
            started_at=now,
            total_tasks=total_tasks,
        )
        with self._lock:
            self._runs.append(run)
        return replace(run)

    def create_task(self, *, scan_run_id: UUID, device_id: UUID) -> ScanTask:
        with self._lock:
            existing = next(
                (
                    task
                    for task in self._tasks
                    if task.scan_run_id == scan_run_id and task.device_id == device_id
                ),
                None,
            )
            if existing is not None:
                return replace(existing)

            task = ScanTask(
                id=uuid4(),
                scan_run_id=scan_run_id,
                device_id=device_id,
                status="queued",
            )
            self._tasks.append(task)
            self._refresh_run_counts(scan_run_id)
            return replace(task)

    def list_tasks(self, scan_run_id: UUID) -> list[ScanTask]:
        with self._lock:
            return [replace(task) for task in self._tasks if task.scan_run_id == scan_run_id]

    def start_run(self, scan_run_id: UUID) -> ScanRun:
        with self._lock:
            run = self._get_run(scan_run_id)
            updated = replace(run, status="running", finished_at=None, error_message=None)
            self._replace_run(updated)
            return replace(updated)

    def claim_next_queued_task(self, scan_run_id: UUID) -> ScanTask | None:
        with self._lock:
            for idx, task in enumerate(self._tasks):
                if task.scan_run_id == scan_run_id and task.status == "queued":
                    claimed = replace(
                        task,
                        status="running",
                        attempt_count=task.attempt_count + 1,
                        started_at=task.started_at or utc_now(),
                        finished_at=None,
                    )
                    self._tasks[idx] = claimed
                    self._refresh_run_counts(scan_run_id)
                    return replace(claimed)
        return None

    def complete_task(
        self,
        task_id: UUID,
        *,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
        found_release_id: UUID | None,
        new_release: bool,
    ) -> ScanTask:
        with self._lock:
            task = self._get_task(task_id)
            updated = replace(
                task,
                status="completed",
                tracks_checked=list(tracks_checked),
                rui_candidates_checked=list(rui_candidates_checked),
                found_release_id=found_release_id,
                error_code=None,
                error_message=None,
                finished_at=utc_now(),
            )
            self._replace_task(updated)
            self._increment_new_release(updated.scan_run_id) if new_release else None
            self._refresh_run_counts(updated.scan_run_id)
            return replace(updated)

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
        with self._lock:
            task = self._get_task(task_id)
            should_retry = retryable and task.attempt_count < max_attempts
            updated = replace(
                task,
                status="queued" if should_retry else "failed",
                tracks_checked=list(tracks_checked),
                rui_candidates_checked=list(rui_candidates_checked),
                error_code=error_code,
                error_message=error_message,
                finished_at=None if should_retry else utc_now(),
            )
            self._replace_task(updated)
            self._refresh_run_counts(updated.scan_run_id)
            return replace(updated)

    def finish_run(
        self,
        scan_run_id: UUID,
        *,
        status: str,
        error_message: str | None = None,
    ) -> ScanRun:
        with self._lock:
            run = self._get_run(scan_run_id)
            updated = replace(
                run,
                status=status,  # type: ignore[arg-type]
                finished_at=utc_now(),
                error_message=error_message,
            )
            self._replace_run(updated)
            self._refresh_run_counts(scan_run_id)
            return replace(self._get_run(scan_run_id))

    def latest_run(self) -> ScanRun | None:
        with self._lock:
            if not self._runs:
                return None
            latest = max(self._runs, key=lambda run: run.started_at)
            self._refresh_run_counts(latest.id)
            return replace(self._get_run(latest.id))

    def _get_run(self, scan_run_id: UUID) -> ScanRun:
        for run in self._runs:
            if run.id == scan_run_id:
                return run
        raise KeyError(f"scan run not found: {scan_run_id}")

    def _replace_run(self, updated: ScanRun) -> None:
        for idx, run in enumerate(self._runs):
            if run.id == updated.id:
                self._runs[idx] = updated
                return
        raise KeyError(f"scan run not found: {updated.id}")

    def _get_task(self, task_id: UUID) -> ScanTask:
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"scan task not found: {task_id}")

    def _replace_task(self, updated: ScanTask) -> None:
        for idx, task in enumerate(self._tasks):
            if task.id == updated.id:
                self._tasks[idx] = updated
                return
        raise KeyError(f"scan task not found: {updated.id}")

    def _increment_new_release(self, scan_run_id: UUID) -> None:
        run = self._get_run(scan_run_id)
        self._replace_run(replace(run, new_releases=run.new_releases + 1))

    def _refresh_run_counts(self, scan_run_id: UUID) -> None:
        run = self._get_run(scan_run_id)
        tasks = [task for task in self._tasks if task.scan_run_id == scan_run_id]
        self._replace_run(
            replace(
                run,
                total_tasks=len(tasks),
                completed_tasks=sum(1 for task in tasks if task.status == "completed"),
                failed_tasks=sum(1 for task in tasks if task.status == "failed"),
            )
        )


def seed_telegram_targets() -> list[TelegramTarget]:
    return [
        TelegramTarget(
            id=UUID("aaaa1111-1111-4111-8111-111111111111"),
            brand="oppo",
            chat_id=-1001234567890,
            message_thread_id=111,
        ),
        TelegramTarget(
            id=UUID("bbbb2222-2222-4222-8222-222222222222"),
            brand="realme",
            chat_id=-1001234567890,
            message_thread_id=222,
        ),
        TelegramTarget(
            id=UUID("cccc3333-3333-4333-8333-333333333333"),
            brand="oneplus",
            chat_id=-1001234567890,
            message_thread_id=333,
        ),
    ]


class InMemoryTelegramRepository(TelegramRepository):
    def __init__(self, targets: list[TelegramTarget] | None = None) -> None:
        self._targets = list(seed_telegram_targets() if targets is None else targets)
        self._notifications: list[TelegramNotification] = []
        self._releases: dict[UUID, Release] = {}

    @property
    def notifications(self) -> list[TelegramNotification]:
        return list(self._notifications)

    def get_target_for_brand(self, brand: Brand) -> TelegramTarget | None:
        return next(
            (target for target in self._targets if target.brand == brand and target.enabled),
            None,
        )

    def enqueue_notification(
        self,
        *,
        release: Release,
        target: TelegramTarget,
    ) -> tuple[TelegramNotification, bool]:
        self._releases[release.id] = release
        existing = next(
            (
                notification
                for notification in self._notifications
                if notification.release_id == release.id
                and notification.telegram_target_id == target.id
            ),
            None,
        )
        if existing is not None:
            return existing, False

        notification = TelegramNotification(
            id=uuid4(),
            release_id=release.id,
            telegram_target_id=target.id,
            status="queued",
            created_at=utc_now(),
        )
        self._notifications.append(notification)
        return notification, True

    def claim_next_notification(self, *, max_attempts: int) -> TelegramDelivery | None:
        now = utc_now()
        for index, notification in enumerate(self._notifications):
            retry_ready = (
                notification.status == "failed"
                and notification.next_attempt_at is not None
                and notification.next_attempt_at <= now
            )
            if (
                notification.status != "queued"
                and not retry_ready
            ) or notification.attempt_count >= max_attempts:
                continue
            target = next(
                (item for item in self._targets if item.id == notification.telegram_target_id),
                None,
            )
            if target is None or not target.enabled:
                continue
            claimed = replace(
                notification,
                status="sending",
                attempt_count=notification.attempt_count + 1,
                last_attempt_at=now,
                next_attempt_at=None,
            )
            self._notifications[index] = claimed
            release = self._releases.get(notification.release_id)
            if release is None:
                return None
            return TelegramDelivery(notification=claimed, release=release, target=target)
        return None

    def mark_notification_sent(
        self, notification_id: UUID, *, telegram_message_id: int
    ) -> TelegramNotification:
        return self._update_notification(
            notification_id,
            status="sent",
            telegram_message_id=telegram_message_id,
            sent_at=utc_now(),
            error_message=None,
            next_attempt_at=None,
        )

    def mark_notification_failed(
        self, notification_id: UUID, *, error_message: str, retry_seconds: int
    ) -> TelegramNotification:
        return self._update_notification(
            notification_id,
            status="failed",
            error_message=error_message,
            next_attempt_at=utc_now() + timedelta(seconds=retry_seconds),
        )

    def _update_notification(self, notification_id: UUID, **changes: object) -> TelegramNotification:
        for index, current in enumerate(self._notifications):
            if current.id == notification_id:
                updated = replace(current, **changes)
                self._notifications[index] = updated
                return updated
        raise KeyError(f"telegram notification not found: {notification_id}")


class InMemoryCatalogImportRepository(CatalogImportRepository):
    def __init__(self) -> None:
        self.imports: list[DeviceCatalogImport] = []

    def start_import(self, *, source: str) -> DeviceCatalogImport:
        catalog_import = DeviceCatalogImport(
            id=uuid4(),
            source=source,
            status="running",
            started_at=utc_now(),
        )
        self.imports.append(catalog_import)
        return replace(catalog_import)

    def complete_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        upserted_count: int,
        disabled_count: int,
    ) -> DeviceCatalogImport:
        return self._update(
            import_id,
            status="completed",
            fetched_count=fetched_count,
            upserted_count=upserted_count,
            disabled_count=disabled_count,
            finished_at=utc_now(),
        )

    def fail_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        disabled_count: int,
        error_message: str,
    ) -> DeviceCatalogImport:
        return self._update(
            import_id,
            status="failed",
            fetched_count=fetched_count,
            disabled_count=disabled_count,
            error_message=error_message,
            finished_at=utc_now(),
        )

    def _update(self, import_id: UUID, **changes: object) -> DeviceCatalogImport:
        for index, current in enumerate(self.imports):
            if current.id == import_id:
                updated = replace(current, **changes)
                self.imports[index] = updated
                return replace(updated)
        raise KeyError(f"catalog import not found: {import_id}")


class InMemoryPublicActionRepository(PublicActionRepository):
    def __init__(self) -> None:
        self._actions: list[tuple[str, str, str, datetime]] = []

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
        now = utc_now()
        window_start = now - timedelta(seconds=window_seconds)
        recent = [
            item
            for item in self._actions
            if item[0] == action and item[1] == actor_hash and item[3] >= window_start
        ]
        if len(recent) >= limit:
            retry_after = max(
                int((recent[0][3] + timedelta(seconds=window_seconds) - now).total_seconds()),
                1,
            )
            return PublicActionDecision(allowed=False, retry_after_seconds=retry_after)
        same_query = [
            item for item in recent if item[2] == query_key
        ]
        if cooldown_seconds and same_query:
            retry_after = int(
                (
                    same_query[-1][3]
                    + timedelta(seconds=cooldown_seconds)
                    - now
                ).total_seconds()
            )
            if retry_after > 0:
                return PublicActionDecision(allowed=False, retry_after_seconds=retry_after)
        self._actions.append((action, actor_hash, query_key, now))
        return PublicActionDecision(allowed=True)


class InMemoryAdminRepository(AdminRepository):
    def __init__(self, enabled_users: set[UUID] | None = None) -> None:
        self._enabled_users = set(enabled_users or set())

    def is_enabled_admin(self, user_id: UUID) -> bool:
        return user_id in self._enabled_users


class InMemoryResolverRepository(ResolverRepository):
    def __init__(self) -> None:
        self.requests: list[ResolveRequest] = []

    def record(self, request: ResolveRequest) -> ResolveRequest:
        self.requests.append(request)
        return request
