from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from time import sleep
from uuid import UUID

from ota_backend.domain.manifest import normalize_manifest_code
from ota_backend.domain.models import (
    Device,
    OtaProviderRelease,
    OtaQuery,
    OtaTrack,
    Release,
    ScanRun,
    ScanTask,
)
from ota_backend.domain.ota import DEFAULT_RUI_CANDIDATES, normalize_product_model
from ota_backend.domain.scanner import (
    is_scan_capable,
    stable_group_scan_shard,
    tracks_for_device,
)
from ota_backend.providers.interfaces import (
    OtaNotFoundError,
    OtaProvider,
    OtaProviderDecryptError,
    OtaProviderTimeoutError,
    OtaProviderUnavailableError,
)
from ota_backend.repositories.interfaces import (
    DeviceRepository,
    ReleaseRepository,
    ScanRepository,
    TelegramRepository,
)

MAX_SCAN_ATTEMPTS = 3


@dataclass(frozen=True)
class ScanResult:
    run: ScanRun
    tasks: list[ScanTask]
    new_releases: list[Release]
    task_devices: dict[UUID, Device]
    scan_capable_total: int


class ScannerService:
    def __init__(
        self,
        *,
        device_repository: DeviceRepository,
        release_repository: ReleaseRepository,
        scan_repository: ScanRepository,
        telegram_repository: TelegramRepository,
        provider: OtaProvider,
        max_attempts: int = MAX_SCAN_ATTEMPTS,
        rui_candidates: list[int] | None = None,
        request_interval_seconds: float = 0,
        cycle_days: int = 7,
        failure_rate_threshold: float = 0.10,
        failure_archive_threshold: int = 3,
        timeout_retries: int = 1,
        max_concurrency: int = 1,
    ) -> None:
        self._device_repository = device_repository
        self._release_repository = release_repository
        self._scan_repository = scan_repository
        self._telegram_repository = telegram_repository
        self._provider = provider
        self._max_attempts = max_attempts
        self._rui_candidates = list(rui_candidates or DEFAULT_RUI_CANDIDATES)
        self._request_interval_seconds = request_interval_seconds
        if cycle_days < 1:
            raise ValueError("cycle_days must be at least 1")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._cycle_days = cycle_days
        self._failure_rate_threshold = failure_rate_threshold
        self._failure_archive_threshold = failure_archive_threshold
        self._timeout_retries = timeout_retries
        self._max_concurrency = max_concurrency
        self._has_sent_request = False
        # Throttle state has to be guarded once concurrent workers share
        # the service. The sequential default path also takes the lock,
        # but uncontested locks are cheap and keeps the code path single.
        self._throttle_lock = Lock()

    def run_scheduled_scan(
        self,
        *,
        cycle_day: int | None = None,
        max_tasks: int | None = None,
    ) -> ScanResult:
        resolved_cycle_day = self._resolve_cycle_day(cycle_day)
        if max_tasks is not None and max_tasks < 1:
            raise ValueError("max_tasks must be at least 1")
        devices = self._devices_for_cycle_day(resolved_cycle_day, max_tasks=max_tasks)
        run = self._scan_repository.create_run(
            cycle_day=resolved_cycle_day,
            total_tasks=len(devices),
        )
        for device in devices:
            self._scan_repository.create_task(scan_run_id=run.id, device_id=device.id)

        return self.run_existing_scan(run.id)

    def run_existing_scan(self, scan_run_id: UUID) -> ScanResult:
        started = self._scan_repository.start_run(scan_run_id)
        if self._max_concurrency <= 1:
            while True:
                task = self._scan_repository.claim_next_queued_task(scan_run_id)
                if task is None:
                    break
                self._process_task(task)
        else:
            # Bounded concurrency: each worker thread claims its own task
            # via the atomic claim RPC (SKIP LOCKED in Supabase / lock in
            # the in-memory repo) so there is no chance two workers pick
            # the same task. The provider HTTP client is sync; threads
            # are the right primitive here.
            with ThreadPoolExecutor(max_workers=self._max_concurrency) as pool:
                futures = [
                    pool.submit(self._drain_queue, scan_run_id)
                    for _ in range(self._max_concurrency)
                ]
                # Propagate the first exception so the run finishes with a
                # recorded error rather than silently swallowing failures.
                for future in futures:
                    future.result()

        tasks = self._scan_repository.list_tasks(scan_run_id)
        status, error_message = self._run_status(tasks)
        finished = self._scan_repository.finish_run(
            scan_run_id,
            status=status,
            error_message=error_message,
        )
        final_tasks = self._scan_repository.list_tasks(scan_run_id)
        new_releases = self._new_releases_for_run(final_tasks, started_at=started.started_at)
        # Bulk fetch all task devices in one go via get_by_ids instead of
        # an N+1 get_by_id loop. With the partial index introduced in
        # 202606270001 and the get_by_ids API added in Phase 2, this is
        # an O(1) round-trip even for large runs.
        device_ids = [task.device_id for task in final_tasks]
        task_devices: dict[UUID, Device] = (
            self._device_repository.get_by_ids(device_ids) if device_ids else {}
        )
        return ScanResult(
            run=finished,
            tasks=final_tasks,
            new_releases=new_releases,
            task_devices=task_devices,
            scan_capable_total=self._device_repository.count_scan_enabled(),
        )

    def _new_releases_for_run(
        self, tasks: list[ScanTask], *, started_at: datetime
    ) -> list[Release]:
        releases: list[Release] = []
        seen: set[UUID] = set()
        for task in tasks:
            if task.found_release_id is None or task.found_release_id in seen:
                continue
            seen.add(task.found_release_id)
            release = self._release_repository.get_by_id(task.found_release_id)
            if (
                release is not None
                and release.discovered_by == "worker"
                and release.discovered_at >= started_at
            ):
                releases.append(release)
        return sorted(releases, key=lambda release: release.discovered_at, reverse=True)

    def _resolve_cycle_day(self, cycle_day: int | None) -> int:
        if cycle_day is None:
            return datetime.now(UTC).date().toordinal() % self._cycle_days
        if cycle_day < 0 or cycle_day >= self._cycle_days:
            raise ValueError(f"cycle_day must be between 0 and {self._cycle_days - 1}")
        return cycle_day

    def _devices_for_cycle_day(self, cycle_day: int, *, max_tasks: int | None) -> list[Device]:
        matching: list[Device] = []
        offset = 0
        limit = 200
        while True:
            page = self._device_repository.list_scan_enabled_devices(
                limit=limit,
                offset=offset,
            )
            for device in page.items:
                if (
                    is_scan_capable(device, failure_threshold=self._failure_archive_threshold)
                    and stable_group_scan_shard(device, cycle_days=self._cycle_days) == cycle_day
                ):
                    matching.append(device)
                    if max_tasks is not None and len(matching) >= max_tasks:
                        return matching
            offset += page.limit
            if not page.items or offset >= page.total:
                return matching

    def _process_task(self, task: ScanTask) -> None:
        device = self._device_repository.get_by_id(task.device_id)
        if device is None:
            self._scan_repository.fail_task(
                task.id,
                error_code="DEVICE_NOT_FOUND",
                error_message="Device no longer exists.",
                retryable=False,
                max_attempts=self._max_attempts,
                tracks_checked=[],
                rui_candidates_checked=[],
            )
            return

        try:
            product_model = normalize_product_model(device.product_model)
            manifest_code = normalize_manifest_code(device.manifest_code or "")
        except ValueError as exc:
            self._scan_repository.fail_task(
                task.id,
                error_code="VALIDATION_ERROR",
                error_message=str(exc),
                retryable=False,
                max_attempts=self._max_attempts,
                tracks_checked=[],
                rui_candidates_checked=[],
            )
            return

        tracks_checked: list[OtaTrack] = []
        rui_candidates_checked: list[int] = []
        for track in tracks_for_device(device):
            tracks_checked.append(track)
            rui_candidates_checked = list(self._rui_candidates)
            query = OtaQuery(
                product_model=product_model,
                manifest_code=manifest_code,
                ota_track=track,
                rui_candidates=list(self._rui_candidates),
                language="en-EN",
                beta=False,
                persist_result=True,
                brand=device.brand,
            )
            try:
                provider_release = self._query_with_timeout_retry(query)
            except OtaNotFoundError:
                continue
            except OtaProviderTimeoutError as exc:
                self._handle_provider_failure(
                    task,
                    device,
                    exc=exc,
                    error_code="UPSTREAM_TIMEOUT",
                    retryable=True,
                    tracks_checked=tracks_checked,
                    rui_candidates_checked=rui_candidates_checked,
                )
                return
            except OtaProviderUnavailableError as exc:
                self._handle_provider_failure(
                    task,
                    device,
                    exc=exc,
                    error_code="UPSTREAM_ERROR",
                    retryable=True,
                    tracks_checked=tracks_checked,
                    rui_candidates_checked=rui_candidates_checked,
                )
                return
            except OtaProviderDecryptError as exc:
                self._handle_provider_failure(
                    task,
                    device,
                    exc=exc,
                    error_code="DECRYPT_ERROR",
                    retryable=False,
                    tracks_checked=tracks_checked,
                    rui_candidates_checked=rui_candidates_checked,
                )
                return

            persisted = self._release_repository.upsert_release(
                provider_release,
                discovered_by="worker",
            )
            self._device_repository.record_scan_success(device.id)
            self._device_repository.update_scan_state(
                device.id,
                active_track=provider_release.ota_track,
                bootstrap_done=True,
            )
            if persisted.is_new:
                target = self._telegram_repository.get_target_for_brand(persisted.release.brand)
                if target is not None:
                    self._telegram_repository.enqueue_notification(
                        release=persisted.release,
                        target=target,
                    )
            self._scan_repository.complete_task(
                task.id,
                tracks_checked=tracks_checked,
                rui_candidates_checked=rui_candidates_checked,
                found_release_id=persisted.release.id,
                new_release=persisted.is_new,
            )
            return

        self._scan_repository.complete_task(
            task.id,
            tracks_checked=tracks_checked,
            rui_candidates_checked=rui_candidates_checked,
            found_release_id=None,
            new_release=False,
        )
        self._device_repository.record_scan_success(device.id)

    def _handle_provider_failure(
        self,
        task: ScanTask,
        device: Device,
        *,
        exc: Exception,
        error_code: str,
        retryable: bool,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
    ) -> None:
        """Single source of truth for provider-side scan failures.

        Replaces three near-identical except blocks that diverged over
        time (one nearly forgot to forward ``tracks_checked``).
        Responsibilities:

        - Mark the scan task failed (or re-queued for retry) with a
          stable error_code.
        - When the task lands in a terminal ``failed`` state, also
          increment the device's consecutive_failures counter so the
          archive-on-failure threshold logic in
          ``record_scan_failure`` can move chronically broken devices
          to ``archive_only``.
        """

        message = str(exc)
        updated = self._scan_repository.fail_task(
            task.id,
            error_code=error_code,
            error_message=message,
            retryable=retryable,
            max_attempts=self._max_attempts,
            tracks_checked=tracks_checked,
            rui_candidates_checked=rui_candidates_checked,
        )
        if updated.status == "failed":
            self._device_repository.record_scan_failure(
                device.id,
                error_code=error_code,
                error_message=message,
                archive_threshold=self._failure_archive_threshold,
            )

    def _drain_queue(self, scan_run_id: UUID) -> None:
        """Concurrent worker loop. Each worker keeps claiming the next
        queued task atomically until the queue is empty for this run."""

        while True:
            task = self._scan_repository.claim_next_queued_task(scan_run_id)
            if task is None:
                return
            self._process_task(task)

    def _throttle_provider_request(self) -> None:
        with self._throttle_lock:
            if self._has_sent_request and self._request_interval_seconds > 0:
                sleep(self._request_interval_seconds)
            self._has_sent_request = True

    def _query_with_timeout_retry(self, query: OtaQuery) -> OtaProviderRelease:
        timeout_attempts = 0
        while True:
            try:
                self._throttle_provider_request()
                return self._provider.query(query)
            except OtaProviderTimeoutError:
                if timeout_attempts >= self._timeout_retries:
                    raise
                timeout_attempts += 1

    def _run_status(self, tasks: list[ScanTask]) -> tuple[str, str | None]:
        total = len(tasks)
        failed = sum(1 for task in tasks if task.status == "failed")
        if total == 0 or failed == 0:
            return "completed", None
        failure_rate = failed / total
        if failure_rate > self._failure_rate_threshold:
            return (
                "failed",
                (
                    f"Failure rate {failed}/{total} exceeded "
                    f"{int(self._failure_rate_threshold * 100)}% threshold."
                ),
            )
        return (
            "completed",
            (
                f"Completed with warnings: {failed}/{total} tasks failed "
                f"below the {int(self._failure_rate_threshold * 100)}% threshold."
            ),
        )
