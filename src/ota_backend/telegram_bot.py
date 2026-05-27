from __future__ import annotations

import argparse
import asyncio

from ota_backend.app import create_app
from ota_backend.config import Settings, get_settings
from ota_backend.domain.ota import normalize_product_model
from ota_backend.services.telegram import (
    PythonTelegramTransport,
    TelegramDeliveryService,
    format_latest_release,
)


class TelegramBotService:
    def __init__(self, settings: Settings) -> None:
        if not settings.telegram_bot_token or settings.telegram_chat_id is None:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for the bot service.")
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
                if chat.id != self._settings.telegram_chat_id:
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
            return (
                f"Scan status: {run.status}\n"
                f"Completed: {run.completed_tasks}/{run.total_tasks}\n"
                f"Failed: {run.failed_tasks}\n"
                f"New releases: {run.new_releases}"
            )
        return None


async def _main_async(*, once_delivery: bool) -> None:
    service = TelegramBotService(get_settings())
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
    args = parser.parse_args()
    asyncio.run(_main_async(once_delivery=args.once_delivery))


if __name__ == "__main__":
    main()
