from __future__ import annotations

from uuid import UUID

from ota_backend.domain.models import Device, OtaProviderRelease, OtaQuery, Page, ScanTask
from ota_backend.domain.ota import build_seed_ota_version
from ota_backend.domain.scanner import (
    stable_group_scan_shard,
    stable_scan_shard,
    tracks_for_device,
)
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.providers.interfaces import (
    OtaNotFoundError,
    OtaProviderTimeoutError,
    OtaProviderUnavailableError,
)
from ota_backend.repositories.memory import (
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
    InMemoryScanRepository,
    InMemoryTelegramRepository,
)
from ota_backend.services.scanner import ScannerService


def _device(
    *,
    product_model: str = "RMX3301",
    manifest_code: str | None = "1B",
    active_track: str = "C",
    bootstrap_done: bool = False,
    scan_enabled: bool = True,
) -> Device:
    return Device(
        id=UUID("99999999-9999-4999-8999-999999999999"),
        catalog_id=1,
        brand="realme",
        name="Realme Test",
        product_model=product_model,
        manifest_code=manifest_code,
        scan_enabled=scan_enabled,
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


def _cycle_day(device: Device) -> int:
    prepared = InMemoryDeviceRepository([device]).get_by_product_model(device.product_model)
    assert prepared is not None
    return stable_group_scan_shard(prepared)


class TransientThenSuccessProvider:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def query(self, request: OtaQuery) -> OtaProviderRelease:
        self.calls += 1
        if self.calls <= self.failures:
            raise OtaProviderUnavailableError("temporary upstream failure")
        return _release_for(request)


class TimeoutOnceProvider:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, request: OtaQuery) -> OtaProviderRelease:
        self.calls += 1
        if self.calls == 1:
            raise OtaProviderTimeoutError("temporary timeout")
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


class RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[OtaQuery] = []

    def query(self, request: OtaQuery) -> OtaProviderRelease:
        self.requests.append(request)
        return _release_for(request)


class PagedDeviceRepository(InMemoryDeviceRepository):
    def __init__(self, target: Device) -> None:
        self.target = target
        self.calls: list[int] = []

    def list_scan_enabled_devices(self, *, brand=None, limit=50, offset=0):
        self.calls.append(offset)
        if offset == 0:
            other_model = next(
                f"RMX{number:04d}"
                for number in range(1, 100)
                if stable_group_scan_shard(_device(product_model=f"RMX{number:04d}"))
                != stable_group_scan_shard(self.target)
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
    max_attempts: int = 3,
    failure_archive_threshold: int = 3,
    max_concurrency: int = 1,
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
            max_attempts=max_attempts,
            failure_archive_threshold=failure_archive_threshold,
            max_concurrency=max_concurrency,
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

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))

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

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))

    assert provider.calls == 3
    assert result.tasks[0].attempt_count == 3
    assert result.tasks[0].status == "completed"
    assert (
        releases.list_releases(
            q=None,
            brand=None,
            product_model="RMX3301",
            manifest_code=None,
            limit=10,
            offset=0,
        ).total
        == 1
    )


def test_non_retryable_validation_failure_fails_once():
    device = _device(manifest_code="ZZ")
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device])
    )

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))

    assert result.run.status == "failed"
    assert result.tasks[0].status == "failed"
    assert result.tasks[0].attempt_count == 1
    assert result.tasks[0].error_code == "VALIDATION_ERROR"


def test_scheduled_scan_does_not_enqueue_devices_without_manifest_mapping():
    device = _device(manifest_code=None)
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device])
    )

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))

    assert result.run.status == "completed"
    assert result.run.total_tasks == 0
    assert result.tasks == []


def test_scheduled_scan_only_selects_scan_enabled_allowlist_devices():
    enabled = _device(product_model="RMX3301", scan_enabled=True)
    disabled = _device(product_model="RMX3302", scan_enabled=False)
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([enabled, disabled])
    )

    result = service.run_scheduled_scan(cycle_day=_cycle_day(enabled))

    assert result.run.total_tasks == 1
    assert result.tasks[0].device_id == enabled.id


def test_scheduled_scan_shards_by_scan_group_key():
    first = _device(product_model="PKC110")
    second = _device(product_model="CPH2651", manifest_code="A7")
    first = Device(
        **{
            **first.__dict__,
            "brand": "oppo",
            "name": "OPPO Find X8 Pro (CN)",
            "scan_group_key": "oppo-find-x8-pro",
            "scan_group_name": "OPPO Find X8 Pro",
        }
    )
    second = Device(
        **{
            **second.__dict__,
            "brand": "oppo",
            "name": "OPPO Find X8 Pro (GLO)",
            "scan_group_key": "oppo-find-x8-pro",
            "scan_group_name": "OPPO Find X8 Pro",
        }
    )
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([first, second])
    )

    selected = service._devices_for_cycle_day(  # noqa: SLF001 - exercises grouping contract
        stable_group_scan_shard(first),
        max_tasks=None,
    )

    assert {device.product_model for device in selected} == {"PKC110", "CPH2651"}


def test_worker_query_shape_matches_manual_standard_ota_inputs():
    device = _device(product_model="CPH2651ID", manifest_code="33")
    provider = RecordingProvider()
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device]),
        provider=provider,
    )

    service.run_scheduled_scan(cycle_day=_cycle_day(device))

    assert provider.requests
    request = provider.requests[0]
    assert request.product_model == "CPH2651ID"
    assert request.manifest_code == "33"
    assert request.ota_track == "H"
    assert request.rui_candidates == [8, 7, 6]
    assert request.language == "en-EN"
    assert request.beta is False
    assert request.persist_result is True


def test_low_failure_rate_completes_run_with_warning():
    service, _releases, _scans, _telegram = _service(device_repository=InMemoryDeviceRepository([]))
    run_id = UUID("11111111-1111-4111-8111-111111111111")
    tasks = [
        ScanTask(
            id=UUID(f"22222222-2222-4222-8222-{index:012d}"),
            scan_run_id=run_id,
            device_id=UUID(f"33333333-3333-4333-8333-{index:012d}"),
            status="failed" if index < 3 else "completed",
        )
        for index in range(225)
    ]

    status, message = service._run_status(tasks)  # noqa: SLF001 - policy unit test

    assert status == "completed"
    assert message is not None
    assert "below the 10% threshold" in message


def test_legacy_oneplus_repeated_upstream_error_moves_to_archive_only():
    device = Device(
        id=UUID("99999999-9999-4999-8999-999999999999"),
        catalog_id=1,
        brand="oneplus",
        name="OnePlus 8T (EU)",
        product_model="ONEPLUS8T_EEA",
        manifest_code="44",
        scan_enabled=True,
        active_track="C",
    )
    repository = InMemoryDeviceRepository([device])
    provider = TransientThenSuccessProvider(failures=99)
    service, _releases, _scans, _telegram = _service(
        device_repository=repository,
        provider=provider,
        max_attempts=1,
        failure_archive_threshold=1,
    )

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))
    updated = repository.get_by_product_model("ONEPLUS8T_EEA")

    assert result.tasks[0].status == "failed"
    assert updated is not None
    assert updated.scan_enabled is False
    assert updated.scan_eligibility == "archive_only"


def test_timeout_retries_once_inside_same_task_before_success():
    device = _device()
    provider = TimeoutOnceProvider()
    service, _releases, _scans, _telegram = _service(
        device_repository=InMemoryDeviceRepository([device]),
        provider=provider,
    )

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))

    assert provider.calls == 2
    assert result.tasks[0].attempt_count == 1
    assert result.tasks[0].status == "completed"


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
    cycle_day = _cycle_day(device)

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
        stable_group_scan_shard(target),
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

    result = service.run_scheduled_scan(cycle_day=_cycle_day(device))

    assert result.tasks[0].tracks_checked == ["H", "F"]
    assert provider.calls == ["H", "F"]
    assert "C" not in provider.calls
    assert "A" not in provider.calls


def test_scan_run_new_releases_counter_is_idempotent_under_repeated_completion():
    """Calling complete_task twice (or completing a previously-new task as
    non-new after a retry) must not double-count new_releases. The counter
    is derived state recomputed from tasks; the in-memory repo mirrors the
    SQL recompute introduced by 202606270002_scan_run_counters_recompute."""

    scans = InMemoryScanRepository()
    run = scans.create_run(cycle_day=0, total_tasks=1)
    device_id = UUID("11111111-1111-4111-8111-111111111111")
    task = scans.create_task(scan_run_id=run.id, device_id=device_id)
    scans.start_run(run.id)
    scans.claim_next_queued_task(run.id)

    release_id = UUID("22222222-2222-4222-8222-222222222222")
    scans.complete_task(
        task.id,
        tracks_checked=["H"],
        rui_candidates_checked=[8],
        found_release_id=release_id,
        new_release=True,
    )
    after_first = scans.latest_run()
    assert after_first is not None
    assert after_first.new_releases == 1

    # Re-completing the same task (idempotent retry path) must keep the
    # counter at 1, not 2.
    scans.complete_task(
        task.id,
        tracks_checked=["H"],
        rui_candidates_checked=[8],
        found_release_id=release_id,
        new_release=True,
    )
    after_repeat = scans.latest_run()
    assert after_repeat is not None
    assert after_repeat.new_releases == 1

    # Completing the same task as non-new (e.g. retry produced an existing
    # release) must drop the counter back to 0 because it is derived from
    # task state.
    scans.complete_task(
        task.id,
        tracks_checked=["H"],
        rui_candidates_checked=[8],
        found_release_id=release_id,
        new_release=False,
    )
    after_non_new = scans.latest_run()
    assert after_non_new is not None
    assert after_non_new.new_releases == 0


def test_scan_run_with_bounded_concurrency_processes_every_task_exactly_once():
    """The bounded-concurrency path must rely on the atomic claim RPC so
    each task is processed once even when several worker threads drain
    the same scan run. This is the same property the Supabase SKIP
    LOCKED claim provides in production; the in-memory repo emulates it
    via a lock."""

    devices = InMemoryDeviceRepository(
        [
            _device(
                product_model=f"RMX330{i}",
                manifest_code="1B",
                active_track="H",
                bootstrap_done=True,
            )
            for i in range(1, 5)
        ]
    )
    # Use a single-shard cycle so every device lands in cycle_day 0.
    service, _releases, scans, _telegram = _service(
        device_repository=devices,
        max_concurrency=4,
    )

    result = service.run_scheduled_scan(cycle_day=None)

    assert result.run.total_tasks >= 1
    assert result.run.completed_tasks + result.run.failed_tasks == result.run.total_tasks
    # Every task must be terminal (no leftover queued/running rows).
    tasks = scans.list_tasks(result.run.id)
    assert all(task.status in {"completed", "failed", "skipped"} for task in tasks)
    # And there must be exactly one task per device that was scheduled
    # (no double-processing).
    device_ids = [task.device_id for task in tasks]
    assert len(device_ids) == len(set(device_ids))


def test_scanner_service_rejects_invalid_max_concurrency():
    """Configuration sanity check: scan_max_concurrency=0 is meaningless;
    the constructor must refuse to build a service that would never make
    progress."""

    import pytest

    with pytest.raises(ValueError):
        ScannerService(
            device_repository=InMemoryDeviceRepository(),
            release_repository=InMemoryReleaseRepository(),
            scan_repository=InMemoryScanRepository(),
            telegram_repository=InMemoryTelegramRepository(),
            provider=FakeOtaProvider(),
            max_concurrency=0,
        )
