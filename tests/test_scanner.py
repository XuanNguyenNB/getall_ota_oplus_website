from __future__ import annotations

from uuid import UUID

from ota_backend.domain.models import Device, OtaProviderRelease, OtaQuery
from ota_backend.domain.ota import build_seed_ota_version
from ota_backend.domain.scanner import stable_scan_shard, tracks_for_device
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.providers.interfaces import OtaNotFoundError, OtaProviderUnavailableError
from ota_backend.repositories.memory import (
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
    InMemoryScanRepository,
    InMemoryTelegramRepository,
)
from ota_backend.services.scanner import ScannerService
from ota_backend.domain.models import Page


def _device(
    *,
    product_model: str = "RMX3301",
    manifest_code: str | None = "1B",
    active_track: str = "C",
    bootstrap_done: bool = False,
) -> Device:
    return Device(
        id=UUID("99999999-9999-4999-8999-999999999999"),
        catalog_id=1,
        brand="realme",
        name="Realme Test",
        product_model=product_model,
        manifest_code=manifest_code,
        scan_enabled=True,
        active_track=active_track,  # type: ignore[arg-type]
        bootstrap_done=bootstrap_done,
    )


def _release_for(request: OtaQuery) -> OtaProviderRelease:
    return OtaProviderRelease(
        brand="realme",
        product_model=request.product_model,
        manifest_code=request.manifest_code,
        ota_track=request.ota_track,
        rui_version=request.rui_candidates[0],
        real_ota_version=f"{request.product_model}_11.{request.ota_track}.01_0000_202605260000",
        real_version_name=f"{request.product_model}_test",
        computed_ota_version=build_seed_ota_version(
            request.product_model,
            request.ota_track,
        ),
        version_type_id="non_display",
        about_update_url=None,
        download_url=f"https://example.com/{request.product_model}.zip",
    )


class TransientThenSuccessProvider:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def query(self, request: OtaQuery) -> OtaProviderRelease:
        self.calls += 1
        if self.calls <= self.failures:
            raise OtaProviderUnavailableError("temporary upstream failure")
        return _release_for(request)


class TrackSelectiveProvider:
    def __init__(self, success_track: str) -> None:
        self.success_track = success_track
        self.calls: list[str] = []

    def query(self, request: OtaQuery) -> OtaProviderRelease:
        self.calls.append(request.ota_track)
        if request.ota_track != self.success_track:
            raise OtaNotFoundError("not found")
        return _release_for(request)


class PagedDeviceRepository(InMemoryDeviceRepository):
    def __init__(self, target: Device) -> None:
        self.target = target
        self.calls: list[int] = []

    def list_devices(self, *, q, brand, enabled_only, limit, offset):
        self.calls.append(offset)
        if offset == 0:
            other_model = next(
                f"RMX{number:04d}"
                for number in range(1, 100)
                if stable_scan_shard(f"RMX{number:04d}") != stable_scan_shard(self.target.product_model)
            )
            other = _device(product_model=other_model)
            return Page(items=[other] * 200, total=201, limit=limit, offset=offset)
        return Page(items=[self.target], total=201, limit=limit, offset=offset)


def _service(
    *,
    device_repository: InMemoryDeviceRepository,
    release_repository: InMemoryReleaseRepository | None = None,
    scan_repository: InMemoryScanRepository | None = None,
    telegram_repository: InMemoryTelegramRepository | None = None,
    provider=None,
) -> tuple[
    ScannerService,
    InMemoryReleaseRepository,
    InMemoryScanRepository,
    InMemoryTelegramRepository,
]:
    releases = release_repository or InMemoryReleaseRepository()
    scans = scan_repository or InMemoryScanRepository()
    telegram = telegram_repository or InMemoryTelegramRepository()
    return (
        ScannerService(
            device_repository=device_repository,
            release_repository=releases,
            scan_repository=scans,
            telegram_repository=telegram,
            provider=provider or FakeOtaProvider(),
        ),
        releases,
        scans,
        telegram,
    )


def test_stable_scan_shard_is_deterministic_and_7_day_bounded():
    values = [stable_scan_shard("RMX3301") for _ in range(3)]

    assert values == [values[0], values[0], values[0]]
    assert 0 <= values[0] <= 6
    assert stable_scan_shard("rmx3301") == values[0]


def test_bootstrap_track_order_and_recurring_track_progression():
    assert tracks_for_device(_device(bootstrap_done=False)) == ["H", "F", "C", "A"]
    assert tracks_for_device(_device(active_track="C", bootstrap_done=True)) == ["H", "F", "C"]
    assert tracks_for_device(_device(active_track="F", bootstrap_done=True)) == ["H", "F"]
    assert tracks_for_device(_device(active_track="H", bootstrap_done=True)) == ["H"]


def test_scan_run_tasks_release_and_notification_persistence():
    device = _device()
    service, releases, scans, telegram = _service(
        device_repository=InMemoryDeviceRepository([device])
    )

    result = service.run_scheduled_scan(cycle_day=stable_scan_shard(device.product_model))

    assert result.run.status == "completed"
    assert result.run.total_tasks == 1
    assert result.run.completed_tasks == 1
    assert result.run.failed_tasks == 0
    assert result.run.new_releases == 1
    assert result.tasks[0].status == "completed"
    assert result.tasks[0].tracks_checked == ["H"]

    release_page = releases.list_releases(
        q=None,
        brand=None,
        product_model="RMX3301",
        manifest_code=None,
        limit=10,
        offset=0,
    )
    assert release_page.total == 1
    assert release_page.items[0].discovered_by == "worker"
    assert len(telegram.notifications) == 1
    assert telegram.notifications[0].release_id == release_page.items[0].id
    assert scans.latest_run() is not None


def test_claim_next_queued_task_is_atomic_for_queued_tasks():
    scans = InMemoryScanRepository()
    run = scans.create_run(cycle_day=0, total_tasks=1)
    scans.create_task(
        scan_run_id=run.id,
        device_id=UUID("11111111-1111-4111-8111-111111111111"),
    )

    first_claim = scans.claim_next_queued_task(run.id)
    second_claim = scans.claim_next_queued_task(run.id)

    assert first_claim is not None
    assert first_claim.status == "running"
    assert first_claim.attempt_count == 1
    assert second_claim is None


def test_retryable_task_retries_before_success():
    device = _device()
    provider = TransientThenSuccessProvider(failures=2)
    service, releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device]),
        provider=provider,
    )

    result = service.run_scheduled_scan(cycle_day=stable_scan_shard(device.product_model))

    assert provider.calls == 3
    assert result.tasks[0].attempt_count == 3
    assert result.tasks[0].status == "completed"
    assert releases.list_releases(
        q=None,
        brand=None,
        product_model="RMX3301",
        manifest_code=None,
        limit=10,
        offset=0,
    ).total == 1


def test_non_retryable_validation_failure_fails_once():
    device = _device(manifest_code="ZZ")
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device])
    )

    result = service.run_scheduled_scan(cycle_day=stable_scan_shard(device.product_model))

    assert result.run.status == "failed"
    assert result.tasks[0].status == "failed"
    assert result.tasks[0].attempt_count == 1
    assert result.tasks[0].error_code == "VALIDATION_ERROR"


def test_scheduled_scan_does_not_enqueue_devices_without_manifest_mapping():
    device = _device(manifest_code=None)
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device])
    )

    result = service.run_scheduled_scan(cycle_day=stable_scan_shard(device.product_model))

    assert result.run.status == "completed"
    assert result.run.total_tasks == 0
    assert result.tasks == []


def test_duplicate_release_updates_last_seen_and_deduplicates_notification():
    device = _device()
    device_repository = InMemoryDeviceRepository([device])
    release_repository = InMemoryReleaseRepository()
    scan_repository = InMemoryScanRepository()
    telegram_repository = InMemoryTelegramRepository()
    service, releases, _scans, telegram = _service(
        device_repository=device_repository,
        release_repository=release_repository,
        scan_repository=scan_repository,
        telegram_repository=telegram_repository,
    )
    cycle_day = stable_scan_shard(device.product_model)

    first = service.run_scheduled_scan(cycle_day=cycle_day)
    release = releases.list_releases(
        q=None,
        brand=None,
        product_model="RMX3301",
        manifest_code=None,
        limit=10,
        offset=0,
    ).items[0]
    first_last_seen = release.last_seen_at
    second = service.run_scheduled_scan(cycle_day=cycle_day)
    release_after_duplicate = releases.list_releases(
        q=None,
        brand=None,
        product_model="RMX3301",
        manifest_code=None,
        limit=10,
        offset=0,
    ).items[0]

    assert first.run.new_releases == 1
    assert second.run.new_releases == 0
    assert release_after_duplicate.id == release.id
    assert release_after_duplicate.last_seen_at >= first_last_seen
    assert len(telegram.notifications) == 1


def test_scan_device_selection_paginates_catalog_until_matching_shard_is_found():
    target = _device(product_model="RMX9999")
    devices = PagedDeviceRepository(target)
    service, _releases, _scans, _telegram = _service(device_repository=devices)

    selected = service._devices_for_cycle_day(  # noqa: SLF001 - exercises paging contract
        stable_scan_shard(target.product_model),
        max_tasks=1,
    )

    assert selected == [target]
    assert devices.calls == [0, 200]


def test_recurring_scan_skips_tracks_older_than_active_track():
    device = _device(active_track="F", bootstrap_done=True)
    provider = TrackSelectiveProvider(success_track="F")
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device]),
        provider=provider,
    )

    result = service.run_scheduled_scan(cycle_day=stable_scan_shard(device.product_model))

    assert result.tasks[0].tracks_checked == ["H", "F"]
    assert provider.calls == ["H", "F"]
    assert "C" not in provider.calls
    assert "A" not in provider.calls
