from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from uuid import UUID

from ota_backend.config import Settings, get_settings
from ota_backend.dependencies import AppDependencies, build_dependencies
from ota_backend.domain.models import Device, Release, ScanRun, ScanTask
from ota_backend.domain.ota import normalize_product_model
from ota_backend.domain.scanner import is_legacy_oneplus_scan_candidate
from ota_backend.services.scanner import ScannerService, ScanResult
from ota_backend.services.telegram import PythonTelegramTransport, TelegramSendError


def run_once(
    *,
    cycle_day: int | None = None,
    max_tasks: int | None = None,
    scan_run_id: UUID | None = None,
    settings: Settings | None = None,
    dependencies: AppDependencies | None = None,
) -> ScanResult:
    resolved_settings = settings or get_settings()
    # The worker uses ``build_dependencies`` directly instead of spinning
    # up a FastAPI app via ``create_app(settings)``. That avoids
    # installing request-logging middleware and static-file mounts that
    # the worker has no use for, and makes it explicit which
    # repositories/providers the worker depends on.
    deps = dependencies or build_dependencies(resolved_settings)
    service = ScannerService(
        device_repository=deps.device_repository,
        release_repository=deps.release_repository,
        scan_repository=deps.scan_repository,
        telegram_repository=deps.telegram_repository,
        provider=deps.ota_provider,
        rui_candidates=resolved_settings.parsed_rui_candidates,
        request_interval_seconds=resolved_settings.scan_request_interval_seconds,
        cycle_days=resolved_settings.scan_cycle_days,
        failure_rate_threshold=resolved_settings.scan_failure_rate_threshold,
        failure_archive_threshold=resolved_settings.scan_failure_archive_threshold,
        timeout_retries=resolved_settings.scan_timeout_retries,
        max_concurrency=resolved_settings.scan_max_concurrency,
    )
    if scan_run_id is not None:
        return service.run_existing_scan(scan_run_id)
    resolved_max_tasks = max_tasks or resolved_settings.scan_max_tasks_per_run
    return service.run_scheduled_scan(cycle_day=cycle_day, max_tasks=resolved_max_tasks)


def cleanup_scan_eligibility(*, settings: Settings, dry_run: bool = True) -> str:
    deps = build_dependencies(settings)
    repository = deps.device_repository
    devices: list[Device] = []
    offset = 0
    while True:
        page = repository.list_devices(
            q=None,
            brand=None,
            enabled_only=False,
            scan_enabled_only=False,
            limit=200,
            offset=offset,
        )
        devices.extend(page.items)
        offset += page.limit
        if not page.items or offset >= page.total:
            break
    missing_manifest = [
        device.product_model
        for device in devices
        if device.scan_enabled and device.manifest_code is None
    ]
    legacy_oneplus = [
        device.product_model
        for device in devices
        if device.scan_enabled and is_legacy_oneplus_scan_candidate(device)
    ]
    lines = [
        "scan eligibility cleanup",
        f"Missing manifest enabled devices: {len(missing_manifest)}",
        f"Legacy OnePlus enabled devices: {len(legacy_oneplus)}",
        f"Dry run: {dry_run}",
    ]
    if dry_run:
        return "\n".join(lines)
    if missing_manifest:
        repository.set_scan_eligibility(
            missing_manifest,
            "invalid_for_scan",
            scan_enabled=False,
        )
    if legacy_oneplus:
        repository.set_scan_eligibility(
            legacy_oneplus,
            "archive_only",
            scan_enabled=False,
        )
    lines.append("Cleanup applied.")
    return "\n".join(lines)


def _read_model_list(path: str) -> list[str]:
    models: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.split("#", 1)[0].strip()
            if line:
                models.append(line)
    return models


def archive_models_from_list(*, settings: Settings, models: list[str], dry_run: bool = True) -> str:
    deps = build_dependencies(settings)
    repository = deps.device_repository
    valid: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    for value in models:
        try:
            model = normalize_product_model(value)
        except ValueError:
            missing.append(value)
            continue
        if model in seen:
            continue
        seen.add(model)
        if repository.get_by_product_model(model) is None:
            missing.append(model)
        else:
            valid.append(model)
    lines = [
        "archive models from list",
        f"Models to archive: {len(valid)}",
        f"Missing/invalid: {len(missing)}",
        f"Dry run: {dry_run}",
    ]
    if missing:
        lines.append("Missing: " + ", ".join(missing[:20]))
        if len(missing) > 20:
            lines.append(f"...and {len(missing) - 20} more missing")
    if dry_run:
        return "\n".join(lines)
    if valid:
        repository.set_scan_eligibility(valid, "archive_only", scan_enabled=False)
    lines.append("Archive applied.")
    return "\n".join(lines)


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else "-"


def _format_duration_seconds(run: ScanRun) -> str:
    if not run.finished_at:
        return "-"
    seconds = max(int((run.finished_at - run.started_at).total_seconds()), 0)
    minutes, remaining = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remaining}s"
    return f"{remaining}s"


def _format_release_line(release: Release) -> str:
    return (
        f"- {release.brand.upper()} {release.product_model} / "
        f"{release.manifest_code} / {release.ota_track}: "
        f"{release.real_version_name} ({release.real_ota_version})"
    )


def _format_failed_task_line(task: ScanTask, device: Device | None) -> str:
    if device is None:
        return f"- {task.device_id}: {task.error_code or 'FAILED'}"
    return (
        f"- {device.brand.upper()} {device.product_model} "
        f"({device.scan_group_name or device.name}) "
        f"/ {device.manifest_code or 'manifest-needed'} "
        f"/ {task.error_code or 'FAILED'}"
    )


def format_worker_summary(
    run: ScanRun,
    tasks: list[ScanTask],
    new_releases: list[Release],
    *,
    release_limit: int = 10,
    scan_cycle_days: int | None = None,
    scan_capable_total: int | None = None,
    task_devices: dict[UUID, Device] | None = None,
) -> str:
    no_update = sum(
        1 for task in tasks if task.status == "completed" and task.found_release_id is None
    )
    skipped = sum(1 for task in tasks if task.status == "skipped")
    cycle_max = (scan_cycle_days - 1) if scan_cycle_days else 6
    lines = [
        "OPlus OTA worker completed",
        f"Run: {run.id}",
        f"Status: {run.status}",
        f"Cycle day: {run.cycle_day}/{cycle_max}",
        f"Started: {_format_datetime(run.started_at)}",
        f"Finished: {_format_datetime(run.finished_at)}",
        f"Duration: {_format_duration_seconds(run)}",
        f"Tasks: {run.completed_tasks}/{run.total_tasks}",
        f"Failed: {run.failed_tasks}",
        f"No update/skipped: {no_update + skipped}",
        f"New releases: {run.new_releases}",
    ]
    if scan_capable_total is not None:
        lines.insert(
            4,
            f"Coverage: {run.total_tasks}/{scan_capable_total} scan-capable variants in this shard",
        )
        if scan_cycle_days:
            lines.insert(5, f"Full-cycle ETA: ~{scan_cycle_days} days at 1 shard/day")
    if run.status == "completed" and run.failed_tasks:
        if run.error_message:
            lines.append(f"Warning: {run.error_message}")
        else:
            lines.append("Warning: task failures were below the run failure threshold.")
    if run.failed_tasks and task_devices:
        failed_lines = [
            _format_failed_task_line(task, task_devices.get(task.device_id))
            for task in tasks
            if task.status == "failed"
        ]
        if failed_lines:
            lines.extend(["", "Failed models:"])
            lines.extend(failed_lines[:10])
            remaining_failed = len(failed_lines) - 10
            if remaining_failed > 0:
                lines.append(f"...and {remaining_failed} more")
    if new_releases:
        lines.extend(["", "New release list:"])
        for release in new_releases[:release_limit]:
            lines.append(_format_release_line(release))
        remaining = len(new_releases) - release_limit
        if remaining > 0:
            lines.append(f"...and {remaining} more")
    return "\n".join(lines)


def format_worker_failure(exc: Exception) -> str:
    message = str(exc).replace("\n", " ")[:300]
    return "\n".join(
        (
            "OPlus OTA worker failed",
            f"Error: {type(exc).__name__}",
            f"Message: {message}",
        )
    )


async def send_worker_summary(settings: Settings, text: str) -> bool:
    chat_id = settings.effective_telegram_worker_log_chat_id
    if (
        not settings.telegram_worker_logs_enabled
        or not settings.telegram_bot_token
        or chat_id is None
    ):
        return False
    transport = PythonTelegramTransport(settings.telegram_bot_token)
    try:
        await transport.bot.send_message(
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        raise TelegramSendError("TELEGRAM_WORKER_LOG_FAILED") from exc
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an OPlus OTA scanner batch.")
    parser.add_argument(
        "--once", action="store_true", help="Run one scheduled shard batch and exit."
    )
    parser.add_argument("--cycle-day", type=int)
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument(
        "--scan-run-id", type=UUID, help="Process queued tasks in an existing admin run."
    )
    parser.add_argument(
        "--cleanup-scan-eligibility",
        action="store_true",
        help="Disable missing-manifest and legacy OnePlus scan entries.",
    )
    parser.add_argument(
        "--archive-models",
        metavar="PATH",
        help="Archive the product models listed in a file (one per line, # comments allowed).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview cleanup actions without changing stored state.",
    )
    args = parser.parse_args()
    execution_flags_set = (
        args.scan_run_id is not None or args.cycle_day is not None or args.max_tasks is not None
    )
    if args.scan_run_id and (args.cycle_day is not None or args.max_tasks is not None):
        parser.error("--scan-run-id cannot be combined with --cycle-day or --max-tasks")
    if args.cleanup_scan_eligibility and (execution_flags_set or args.archive_models):
        parser.error("--cleanup-scan-eligibility cannot be combined with worker execution flags")
    if args.archive_models and execution_flags_set:
        parser.error("--archive-models cannot be combined with worker execution flags")
    settings = get_settings()
    if args.cycle_day is not None and not (0 <= args.cycle_day < settings.scan_cycle_days):
        parser.error(f"--cycle-day must be between 0 and {settings.scan_cycle_days - 1}")
    if args.cleanup_scan_eligibility:
        print(cleanup_scan_eligibility(settings=settings, dry_run=args.dry_run))
        return
    if args.archive_models:
        models = _read_model_list(args.archive_models)
        print(
            archive_models_from_list(
                settings=settings,
                models=models,
                dry_run=args.dry_run,
            )
        )
        return
    try:
        result = run_once(
            cycle_day=args.cycle_day,
            max_tasks=args.max_tasks,
            scan_run_id=args.scan_run_id,
            settings=settings,
        )
    except Exception as exc:
        if settings.telegram_worker_logs_enabled:
            try:
                asyncio.run(
                    send_worker_summary(
                        settings,
                        format_worker_failure(exc),
                    )
                )
            except TelegramSendError:
                pass
        raise

    summary = (
        "scan_run "
        f"id={result.run.id} status={result.run.status} "
        f"total={result.run.total_tasks} completed={result.run.completed_tasks} "
        f"failed={result.run.failed_tasks} new_releases={result.run.new_releases}"
    )
    print(summary)
    try:
        asyncio.run(
            send_worker_summary(
                settings,
                format_worker_summary(
                    result.run,
                    result.tasks,
                    result.new_releases,
                    release_limit=settings.telegram_worker_log_release_limit,
                    scan_cycle_days=settings.scan_cycle_days,
                    scan_capable_total=result.scan_capable_total,
                    task_devices=result.task_devices,
                ),
            )
        )
    except TelegramSendError:
        print("telegram_worker_log status=failed")


if __name__ == "__main__":
    main()
