from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from uuid import UUID

from ota_backend.domain.manifest import normalize_manifest_code
from ota_backend.domain.models import Device, OtaQuery, OtaTrack, ScanRun, ScanTask
from ota_backend.domain.ota import DEFAULT_RUI_CANDIDATES, normalize_product_model
from ota_backend.domain.scanner import stable_scan_shard, tracks_for_device
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
    ) -> None:
        self._device_repository = device_repository
        self._release_repository = release_repository
        self._scan_repository = scan_repository
        self._telegram_repository = telegram_repository
        self._provider = provider
        self._max_attempts = max_attempts
        self._rui_candidates = list(rui_candidates or DEFAULT_RUI_CANDIDATES)
        self._request_interval_seconds = request_interval_seconds
        self._has_sent_request = False

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
        self._scan_repository.start_run(scan_run_id)
        while True:
            task = self._scan_repository.claim_next_queued_task(scan_run_id)
            if task is None:
                break
            self._process_task(task)

        tasks = self._scan_repository.list_tasks(scan_run_id)
        status = "failed" if any(task.status == "failed" for task in tasks) else "completed"
        finished = self._scan_repository.finish_run(scan_run_id, status=status)
        return ScanResult(run=finished, tasks=self._scan_repository.list_tasks(scan_run_id))

    def _resolve_cycle_day(self, cycle_day: int | None) -> int:
        if cycle_day is None:
            return datetime.now(timezone.utc).date().toordinal() % 7
        if cycle_day < 0 or cycle_day > 6:
            raise ValueError("cycle_day must be between 0 and 6")
        return cycle_day

    def _devices_for_cycle_day(self, cycle_day: int, *, max_tasks: int | None) -> list[Device]:
        matching: list[Device] = []
        offset = 0
        limit = 200
        while True:
            page = self._device_repository.list_devices(
                q=None,
                brand=None,
                enabled_only=True,
                limit=limit,
                offset=offset,
            )
            for device in page.items:
                if (
                    device.manifest_code is not None
                    and stable_scan_shard(device.product_model) == cycle_day
                ):
                    matching.append(device)
                    if max_tasks is not None and len(matching) >= max_tasks:
                        return matching
            offset += len(page.items)
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
                self._throttle_provider_request()
                provider_release = self._provider.query(query)
            except OtaNotFoundError:
                continue
            except OtaProviderTimeoutError as exc:
                self._scan_repository.fail_task(
                    task.id,
                    error_code="UPSTREAM_TIMEOUT",
                    error_message=str(exc),
                    retryable=True,
                    max_attempts=self._max_attempts,
                    tracks_checked=tracks_checked,
                    rui_candidates_checked=rui_candidates_checked,
                )
                return
            except OtaProviderUnavailableError as exc:
                self._scan_repository.fail_task(
                    task.id,
                    error_code="UPSTREAM_ERROR",
                    error_message=str(exc),
                    retryable=True,
                    max_attempts=self._max_attempts,
                    tracks_checked=tracks_checked,
                    rui_candidates_checked=rui_candidates_checked,
                )
                return
            except OtaProviderDecryptError as exc:
                self._scan_repository.fail_task(
                    task.id,
                    error_code="DECRYPT_ERROR",
                    error_message=str(exc),
                    retryable=False,
                    max_attempts=self._max_attempts,
                    tracks_checked=tracks_checked,
                    rui_candidates_checked=rui_candidates_checked,
                )
                return

            persisted = self._release_repository.upsert_release(
                provider_release,
                discovered_by="worker",
            )
            self._device_repository.update_scan_state(
                device.id,
                active_track=provider_release.ota_track,
                bootstrap_done=True,
            )
            if persisted.is_new:
                target = self._telegram_repository.get_target_for_brand(
                    persisted.release.brand
                )
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

    def _throttle_provider_request(self) -> None:
        if self._has_sent_request and self._request_interval_seconds > 0:
            sleep(self._request_interval_seconds)
        self._has_sent_request = True
