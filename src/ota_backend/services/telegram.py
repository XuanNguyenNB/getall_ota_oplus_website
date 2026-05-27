from __future__ import annotations

from typing import Protocol

from ota_backend.domain.models import Release, TelegramDelivery
from ota_backend.repositories.interfaces import TelegramRepository


class TelegramSendError(Exception):
    pass


class TelegramTransport(Protocol):
    async def send_message(self, *, chat_id: int, message_thread_id: int, text: str) -> int:
        ...


class PythonTelegramTransport:
    def __init__(self, token: str) -> None:
        try:
            from telegram import Bot
        except ImportError as exc:  # pragma: no cover - installed runtime boundary
            raise RuntimeError("Install python-telegram-bot before running the bot service") from exc
        self._bot = Bot(token=token)

    @property
    def bot(self):
        return self._bot

    async def send_message(self, *, chat_id: int, message_thread_id: int, text: str) -> int:
        try:
            message = await self._bot.send_message(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                text=text,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            raise TelegramSendError("TELEGRAM_DELIVERY_FAILED") from exc
        return int(message.message_id)


class TelegramDeliveryService:
    def __init__(
        self,
        *,
        repository: TelegramRepository,
        transport: TelegramTransport,
        max_attempts: int,
        retry_seconds: int,
    ) -> None:
        self._repository = repository
        self._transport = transport
        self._max_attempts = max_attempts
        self._retry_seconds = retry_seconds

    async def deliver_once(self) -> bool:
        delivery = self._repository.claim_next_notification(max_attempts=self._max_attempts)
        if delivery is None:
            return False
        try:
            message_id = await self._transport.send_message(
                chat_id=delivery.target.chat_id,
                message_thread_id=delivery.target.message_thread_id,
                text=format_notification(delivery),
            )
        except TelegramSendError:
            self._repository.mark_notification_failed(
                delivery.notification.id,
                error_message="TELEGRAM_DELIVERY_FAILED",
                retry_seconds=self._retry_seconds,
            )
            return False
        self._repository.mark_notification_sent(
            delivery.notification.id, telegram_message_id=message_id
        )
        return True


def format_notification(delivery: TelegramDelivery) -> str:
    release = delivery.release
    return "\n".join(
        (
            "New OTA detected",
            "",
            f"Brand: {release.brand.title()}",
            f"Model: {release.product_model}",
            f"Manifest: {release.manifest_code}",
            f"Track: {release.ota_track}",
            f"Version: {release.real_version_name}",
            f"OTA: {release.real_ota_version}",
            "",
            f"Download: {release.download_url}",
        )
    )


def format_latest_release(release: Release | None) -> str:
    if release is None:
        return "No stored release found for this model."
    return "\n".join(
        (
            f"Latest OTA for {release.product_model}",
            f"Version: {release.real_version_name}",
            f"OTA: {release.real_ota_version}",
            f"Download: {release.download_url}",
        )
    )
