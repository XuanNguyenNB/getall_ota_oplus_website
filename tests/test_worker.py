from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import ota_backend.worker as worker_module
from ota_backend.config import Settings
from ota_backend.domain.models import Device, Release, ScanRun, ScanTask
from ota_backend.repositories.memory import InMemoryDeviceRepository
from ota_backend.worker import (
    archive_models_from_list,
    format_worker_failure,
    format_worker_summary,
)


def _release(index: int) -> Release:
    return Release(
        id=UUID(f"11111111-1111-4111-8111-{index:012d}"),
        brand="oppo",
        product_model=f"PKB{index:03d}",
        manifest_code="97",
        ota_track="C",
        rui_version=8,
        real_ota_version=f"PKB{index:03d}_11.C.93_1930_202604300008",
        real_version_name=f"PKB{index:03d}_16.0.7.200(CN01)",
        computed_ota_version=f"PKB{index:03d}_11.C.93_CN_202604300008",
        version_type_id="non_display",
        about_update_url=None,
        download_url="https://example.com/update.zip",
        discovered_by="worker",
        discovered_at=datetime(2026, 6, 8, 0, index % 60, tzinfo=UTC),
        last_seen_at=datetime(2026, 6, 8, 0, index % 60, tzinfo=UTC),
    )


def test_format_worker_summary_without_new_releases_is_useful():
    run = ScanRun(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        status="completed",
        cycle_day=2,
        started_at=datetime(2026, 6, 8, tzinfo=UTC),
        finished_at=datetime(2026, 6, 8, 0, 5, tzinfo=UTC),
        total_tasks=10,
        completed_tasks=9,
        failed_tasks=1,
        new_releases=0,
    )
    tasks = [
        ScanTask(
            id=UUID("22222222-2222-4222-8222-222222222222"),
            scan_run_id=run.id,
            device_id=UUID("33333333-3333-4333-8333-333333333333"),
            status="completed",
            found_release_id=None,
        )
    ]

    summary = format_worker_summary(run, tasks, [], release_limit=10)

    assert "OPlus OTA worker completed" in summary
    assert "11111111-1111-4111-8111-111111111111" in summary
    assert "Status: completed" in summary
    assert "Cycle day: 2/6" in summary
    assert "Duration: 5m 0s" in summary
    assert "Tasks: 9/10" in summary
    assert "Failed: 1" in summary
    assert "No update/skipped: 1" in summary
    assert "New releases: 0" in summary
    assert "New release list:" not in summary


def test_format_worker_summary_includes_coverage_and_failed_models():
    run = ScanRun(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        status="completed",
        cycle_day=6,
        started_at=datetime(2026, 6, 13, tzinfo=UTC),
        finished_at=datetime(2026, 6, 13, 0, 1, tzinfo=UTC),
        total_tasks=225,
        completed_tasks=222,
        failed_tasks=3,
        new_releases=0,
        error_message="Completed with warnings: 3/225 tasks failed below the 10% threshold.",
    )
    task = ScanTask(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        scan_run_id=run.id,
        device_id=UUID("33333333-3333-4333-8333-333333333333"),
        status="failed",
        error_code="UPSTREAM_ERROR",
    )
    device = Device(
        id=task.device_id,
        catalog_id=None,
        brand="oneplus",
        name="OnePlus 8T (EU)",
        product_model="ONEPLUS8T_EEA",
        manifest_code="44",
        scan_enabled=True,
        active_track="C",
        scan_group_name="OnePlus 8T",
    )

    summary = format_worker_summary(
        run,
        [task],
        [],
        scan_cycle_days=7,
        scan_capable_total=1673,
        task_devices={device.id: device},
    )

    assert "Coverage: 225/1673 scan-capable variants in this shard" in summary
    assert "Full-cycle ETA: ~7 days at 1 shard/day" in summary
    assert "Warning: Completed with warnings" in summary
    assert "Failed models:" in summary
    assert "ONEPLUS8T_EEA" in summary
    assert "UPSTREAM_ERROR" in summary


def test_format_worker_summary_limits_new_release_list():
    run = ScanRun(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        status="completed",
        cycle_day=4,
        started_at=datetime(2026, 6, 8, tzinfo=UTC),
        finished_at=datetime(2026, 6, 8, 0, 1, tzinfo=UTC),
        total_tasks=12,
        completed_tasks=12,
        failed_tasks=0,
        new_releases=12,
    )
    releases = [_release(index) for index in range(12)]

    summary = format_worker_summary(run, [], releases, release_limit=10)

    assert "New releases: 12" in summary
    assert "New release list:" in summary
    assert "PKB000_16.0.7.200(CN01)" in summary
    assert "PKB009_16.0.7.200(CN01)" in summary
    assert "PKB010_16.0.7.200(CN01)" not in summary
    assert "...and 2 more" in summary


def test_format_worker_failure_is_short_and_single_line_message():
    error = RuntimeError("bad secret\nwith traceback-ish detail " + "x" * 500)

    message = format_worker_failure(error)

    assert "OPlus OTA worker failed" in message
    assert "RuntimeError" in message
    assert "bad secret with traceback-ish detail" in message
    assert len(message) < 380


def _patch_app_with_repository(monkeypatch, repository):
    """Patch the dependency factory the worker uses so we can swap in
    an in-memory device repository without spinning up the full
    Supabase wiring."""

    monkeypatch.setattr(
        worker_module,
        "build_dependencies",
        lambda settings: SimpleNamespace(device_repository=repository),
    )


def test_archive_models_dry_run_reports_without_changing_state(monkeypatch):
    repository = InMemoryDeviceRepository()
    _patch_app_with_repository(monkeypatch, repository)

    summary = archive_models_from_list(
        settings=Settings(),
        models=["CPH2805IN", "UNKNOWN999"],
        dry_run=True,
    )

    assert "Models to archive: 1" in summary
    assert "Missing/invalid: 1" in summary
    assert "Dry run: True" in summary
    assert "Archive applied." not in summary
    target = repository.get_by_product_model("CPH2805IN")
    assert target.scan_enabled is True
    assert target.scan_eligibility == "active_scan"


def test_archive_models_execute_disables_listed_models_only(monkeypatch):
    repository = InMemoryDeviceRepository()
    _patch_app_with_repository(monkeypatch, repository)

    summary = archive_models_from_list(
        settings=Settings(),
        models=["CPH2805IN", "cph2805in", "MISSING000"],
        dry_run=False,
    )

    assert "Models to archive: 1" in summary
    assert "Missing/invalid: 1" in summary
    assert "Archive applied." in summary

    archived = repository.get_by_product_model("CPH2805IN")
    assert archived.scan_enabled is False
    assert archived.scan_eligibility == "archive_only"

    untouched = repository.get_by_product_model("RMX3301")
    assert untouched.scan_enabled is True
    assert untouched.scan_eligibility == "active_scan"
