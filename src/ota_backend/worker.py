from __future__ import annotations

import argparse
from uuid import UUID

from ota_backend.app import create_app
from ota_backend.config import get_settings
from ota_backend.services.scanner import ScannerService


def run_once(
    *, cycle_day: int | None = None, max_tasks: int | None = None, scan_run_id: UUID | None = None
):
    settings = get_settings()
    app = create_app(settings=settings)
    service = ScannerService(
        device_repository=app.state.device_repository,
        release_repository=app.state.release_repository,
        scan_repository=app.state.scan_repository,
        telegram_repository=app.state.telegram_repository,
        provider=app.state.ota_provider,
        rui_candidates=settings.parsed_rui_candidates,
        request_interval_seconds=settings.scan_request_interval_seconds,
    )
    if scan_run_id is not None:
        return service.run_existing_scan(scan_run_id)
    return service.run_scheduled_scan(cycle_day=cycle_day, max_tasks=max_tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an OPlus OTA scanner batch.")
    parser.add_argument("--once", action="store_true", help="Run one scheduled shard batch and exit.")
    parser.add_argument("--cycle-day", type=int, choices=range(0, 7))
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--scan-run-id", type=UUID, help="Process queued tasks in an existing admin run.")
    args = parser.parse_args()
    if args.scan_run_id and (args.cycle_day is not None or args.max_tasks is not None):
        parser.error("--scan-run-id cannot be combined with --cycle-day or --max-tasks")
    result = run_once(
        cycle_day=args.cycle_day, max_tasks=args.max_tasks, scan_run_id=args.scan_run_id
    )
    print(
        "scan_run "
        f"id={result.run.id} status={result.run.status} "
        f"total={result.run.total_tasks} completed={result.run.completed_tasks} "
        f"failed={result.run.failed_tasks} new_releases={result.run.new_releases}"
    )


if __name__ == "__main__":
    main()
