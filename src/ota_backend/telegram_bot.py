from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from ota_backend.app import create_app
from ota_backend.config import Settings, get_settings
from ota_backend.domain.models import ScanRun
from ota_backend.domain.ota import normalize_product_model
from ota_backend.services.scan_management import (
    ScanManagementService,
    format_scan_groups,
    format_scan_update,
    scan_help,
)
from ota_backend.services.telegram import (
    PythonTelegramTransport,
    TelegramDeliveryService,
    format_latest_release,
)


class TelegramBotService:
    def __init__(self, settings: Settings) -> None:
        if not settings.telegram_bot_token or settings.effective_telegram_command_chat_id is None:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_COMMAND_CHAT_ID or TELEGRAM_CHAT_ID "
                "are required for the bot service."
            )
        self._settings = settings
        self._app = create_app(settings=settings)
        self._transport = PythonTelegramTransport(settings.telegram_bot_token)
        self._delivery = TelegramDeliveryService(
            repository=self._app.state.telegram_repository,
            transport=self._transport,
            max_attempts=settings.telegram_notification_max_attempts,
            retry_seconds=settings.telegram_notification_retry_seconds,
        )
        self._offset = 0

    async def deliver_once(self) -> bool:
        return await self._delivery.deliver_once()

    async def poll_forever(self) -> None:
        while True:
            while await self.deliver_once():
                pass
            updates = await self._transport.bot.get_updates(
                offset=self._offset,
                timeout=self._settings.telegram_poll_timeout_seconds,
                allowed_updates=["message"],
            )
            for update in updates:
                self._offset = max(self._offset, update.update_id + 1)
                message = update.effective_message
                chat = update.effective_chat
                user = update.effective_user
                if message is None or chat is None or user is None or not message.text:
                    continue
                if chat.id != self._settings.effective_telegram_command_chat_id:
                    continue
                reply = self._command_reply(message.text, telegram_user_id=user.id)
                if reply:
                    await self._transport.bot.send_message(
                        chat_id=chat.id,
                        message_thread_id=message.message_thread_id,
                        text=reply,
                        disable_web_page_preview=True,
                    )

    def _command_reply(self, text: str, *, telegram_user_id: int) -> str | None:
        command, _, argument = text.strip().partition(" ")
        if command.split("@", 1)[0] == "/latest":
            if not argument.strip():
                return "Usage: /latest <model>"
            try:
                model = normalize_product_model(argument.strip())
            except ValueError:
                return "Invalid product model."
            page = self._app.state.release_repository.list_releases(
                q=None,
                brand=None,
                product_model=model,
                manifest_code=None,
                limit=1,
                offset=0,
            )
            return format_latest_release(page.items[0] if page.items else None)
        if command.split("@", 1)[0] == "/status":
            if telegram_user_id not in self._settings.parsed_telegram_admin_user_ids:
                return "Admin access is required."
            run = self._app.state.scan_repository.latest_run()
            if run is None:
                return "No scan run has been recorded."
            if argument.strip().lower() != "full":
                return format_scan_status_short(run)
            manager = ScanManagementService(self._app.state.device_repository)
            recent_runs = self._app.state.scan_repository.list_recent_runs(limit=7)
            return format_scan_status(
                run,
                scan_enabled_count=manager.enabled_count(),
                scan_cycle_days=self._settings.scan_cycle_days,
                scan_eligibility_counts=self._app.state.device_repository.count_scan_eligibility(),
                recent_runs=recent_runs,
            )
        if command.split("@", 1)[0] == "/scan":
            if telegram_user_id not in self._settings.parsed_telegram_admin_user_ids:
                return "Admin access is required."
            return self._scan_command_reply(argument)
        if command.split("@", 1)[0] == "/notify":
            if telegram_user_id not in self._settings.parsed_telegram_admin_user_ids:
                return "Admin access is required."
            return self._notify_command_reply(argument)
        return None

    def _scan_command_reply(self, argument: str) -> str:
        manager = ScanManagementService(self._app.state.device_repository)
        parts = argument.strip().split()
        if not parts or parts[0] == "help":
            return scan_help()
        subcommand = parts[0].lower()
        values = parts[1:]
        if subcommand == "search":
            if not values:
                return "Usage: /scan search <query>"
            groups = manager.search(" ".join(values))
            return format_scan_groups(groups, title=f"Scan groups matching: {' '.join(values)}")
        if subcommand in {"on-group", "off-group"}:
            if len(values) != 1:
                return f"Usage: /scan {subcommand} <scan_group_key>"
            enabled = subcommand == "on-group"
            updated = manager.enable_group(values[0], enabled)
            action = "enabled" if enabled else "disabled"
            if not updated:
                return f"No variants updated for group: {values[0]}"
            return format_scan_update(action=action, updated=updated)
        if subcommand in {"on", "off"}:
            if not values:
                return f"Usage: /scan {subcommand} <model...>"
            enabled = subcommand == "on"
            updated, missing, without_manifest = manager.set_models(values, enabled)
            return format_scan_update(
                action="enabled" if enabled else "disabled",
                updated=updated,
                missing=missing,
                without_manifest=without_manifest,
            )
        if subcommand == "list":
            if not values or values[0].lower() != "on":
                return "Usage: /scan list on [oppo|realme|oneplus]"
            brand = values[1].lower() if len(values) > 1 else None
            if brand is not None and brand not in {"oppo", "realme", "oneplus"}:
                return "Usage: /scan list on [oppo|realme|oneplus]"
            groups = manager.list_enabled_groups(brand=brand)
            return format_scan_groups(groups, title="Enabled scan groups", max_groups=20)
        if subcommand == "off-all":
            if values != ["CONFIRM"]:
                return "Usage: /scan off-all CONFIRM"
            changed = manager.disable_all()
            return f"Scan disabled for {changed} variants."
        return scan_help()

    def _notify_command_reply(self, argument: str) -> str:
        parts = argument.strip().split()
        if not parts or parts[0].lower() != "backfill-run":
            return "Usage: /notify backfill-run <scan_run_id> [limit]"
        if len(parts) < 2:
            return "Usage: /notify backfill-run <scan_run_id> [limit]"
        try:
            scan_run_id = UUID(parts[1])
        except ValueError:
            return "Invalid scan run ID."
        limit = 20
        if len(parts) >= 3:
            try:
                limit = max(1, min(int(parts[2]), 100))
            except ValueError:
                return "Invalid limit."
        tasks = self._app.state.scan_repository.list_tasks(scan_run_id)
        if not tasks:
            return "No scan tasks were found for that run."
        release_repository = self._app.state.release_repository
        telegram_repository = self._app.state.telegram_repository
        seen_release_ids: set[UUID] = set()
        enqueued = 0
        skipped_missing_target = 0
        skipped_missing_release = 0
        already_present = 0
        for task in tasks:
            if task.found_release_id is None or task.found_release_id in seen_release_ids:
                continue
            seen_release_ids.add(task.found_release_id)
            release = release_repository.get_by_id(task.found_release_id)
            if release is None:
                skipped_missing_release += 1
                continue
            target = telegram_repository.get_target_for_brand(release.brand)
            if target is None:
                skipped_missing_target += 1
                continue
            _notification, is_new = telegram_repository.enqueue_notification(
                release=release,
                target=target,
            )
            if is_new:
                enqueued += 1
            else:
                already_present += 1
            if enqueued + already_present >= limit:
                break
        return "\n".join(
            [
                "Backfill queued releases",
                f"Run: {scan_run_id}",
                f"Enqueued: {enqueued}",
                f"Already queued: {already_present}",
                f"Missing targets: {skipped_missing_target}",
                f"Missing releases: {skipped_missing_release}",
            ]
        )

    async def check_config(self) -> str:
        command_chat_id = self._settings.effective_telegram_command_chat_id
        lines = ["Telegram config check"]
        try:
            me = await self._transport.bot.get_me()
            username = getattr(me, "username", None) or getattr(me, "first_name", "bot")
            lines.append(f"Bot identity: @{username}" if username else "Bot identity: ok")
        except Exception as exc:
            lines.append(f"Bot identity: failed ({type(exc).__name__})")
        if command_chat_id is None:
            lines.append("Command chat: missing")
        else:
            try:
                await self._transport.bot.send_message(
                    chat_id=command_chat_id,
                    text="OPlus OTA bot config check: command chat OK",
                    disable_web_page_preview=True,
                )
                lines.append("Command chat send: ok")
            except Exception as exc:
                lines.append(f"Command chat send: failed ({type(exc).__name__})")
        lines.append(
            f"Worker log chat: {self._settings.effective_telegram_worker_log_chat_id or 'missing'}"
        )
        telegram_repository = getattr(self._app.state, "telegram_repository", None)
        for brand in ("oppo", "realme", "oneplus"):
            if telegram_repository is None:
                lines.append(f"Release target {brand}: unavailable")
                continue
            target = telegram_repository.get_target_for_brand(brand)
            if target is None:
                lines.append(f"Release target {brand}: missing")
                continue
            topic = (
                f"topic {target.message_thread_id}"
                if target.message_thread_id is not None
                else "no topic"
            )
            enabled = "enabled" if target.enabled else "disabled"
            lines.append(f"Release target {brand}: {enabled}, chat {target.chat_id}, {topic}")
        return "\n".join(lines)


def format_scan_status(
    run: ScanRun,
    *,
    scan_enabled_count: int | None = None,
    scan_cycle_days: int | None = None,
    scan_eligibility_counts: dict[str, int] | None = None,
    recent_runs: list[ScanRun] | None = None,
) -> str:
    started = run.started_at.isoformat(timespec="seconds") if run.started_at else "-"
    finished = run.finished_at.isoformat(timespec="seconds") if run.finished_at else "-"
    cycle_max = (scan_cycle_days - 1) if scan_cycle_days else 6
    lines = [
        "OPlus OTA scan status",
        f"Run: {run.id}",
        f"Status: {run.status}",
        f"Cycle day: {run.cycle_day}/{cycle_max}",
    ]
    if scan_enabled_count is not None:
        lines.append(f"Auto-scan variants enabled: {scan_enabled_count}")
    if scan_eligibility_counts is not None:
        lines.append(
            "Eligibility: "
            f"active={scan_eligibility_counts.get('active_scan', 0)}, "
            f"archive={scan_eligibility_counts.get('archive_only', 0)}, "
            f"invalid={scan_eligibility_counts.get('invalid_for_scan', 0)}"
        )
    if scan_cycle_days is not None:
        lines.append(f"Scan cycle days: {scan_cycle_days}")
    if recent_runs:
        covered = {item.cycle_day for item in recent_runs}
        lines.append(
            f"Recent coverage: {len(covered)}/{scan_cycle_days or 7} cycle days in latest runs"
        )
    lines.extend(
        [
            f"Started: {started}",
            f"Finished: {finished}",
            f"Tasks: {run.completed_tasks}/{run.total_tasks}",
            f"Failed: {run.failed_tasks}",
            f"New releases: {run.new_releases}",
            "",
            "VPS logs: sudo journalctl -u ota-worker.service -f",
        ]
    )
    return "\n".join(lines)


def format_scan_status_short(run: ScanRun) -> str:
    return "\n".join(
        (
            f"Scan status: {run.status}",
            f"Completed: {run.completed_tasks}/{run.total_tasks}",
            f"Failed: {run.failed_tasks}",
            f"New releases: {run.new_releases}",
        )
    )


async def _main_async(*, once_delivery: bool, check_config: bool) -> None:
    service = TelegramBotService(get_settings())
    if check_config:
        print(await service.check_config())
        return
    if once_delivery:
        delivered = await service.deliver_once()
        print(f"telegram_delivery sent={int(delivered)}")
        return
    await service.poll_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Telegram notification delivery and commands.")
    parser.add_argument(
        "--once-delivery",
        action="store_true",
        help="Attempt to deliver one queued notification and exit.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check Telegram token, command chat and release targets without printing secrets.",
    )
    args = parser.parse_args()
    if args.once_delivery and args.check_config:
        parser.error("--once-delivery cannot be combined with --check-config")
    asyncio.run(_main_async(once_delivery=args.once_delivery, check_config=args.check_config))


if __name__ == "__main__":
    main()
