from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol

from ota_backend.domain.models import Release, TelegramDelivery
from ota_backend.repositories.interfaces import TelegramRepository

# Stable, sanitized error cause labels used in retry/audit state. The bot's
# upstream client (python-telegram-bot) raises a variety of exception types;
# we collapse them into a small enum so operators looking at
# telegram_notifications.error_message can quickly tell whether the failure
# is recoverable (rate limit, transient network) or operator-blocking
# (revoked token, kicked from chat). Keep this list short so it remains
# greppable; OTHER is the catch-all.
TELEGRAM_CAUSE_AUTH = "TELEGRAM_AUTH"
TELEGRAM_CAUSE_RATE_LIMIT = "TELEGRAM_RATE_LIMIT"
TELEGRAM_CAUSE_CHAT_BLOCKED = "TELEGRAM_CHAT_BLOCKED"
TELEGRAM_CAUSE_NETWORK = "TELEGRAM_NETWORK"
TELEGRAM_CAUSE_OTHER = "TELEGRAM_DELIVERY_FAILED"


class TelegramSendError(Exception):
    """Sanitized wrapper around a python-telegram-bot send failure.

    The ``cause`` attribute carries a stable label so persisted retry/audit
    state can be filtered without parsing free-form messages. The original
    exception chain is preserved via ``__cause__`` for log inspection.
    """

    def __init__(self, cause: str = TELEGRAM_CAUSE_OTHER) -> None:
        super().__init__(cause)
        self.cause = cause


def _classify_telegram_exception(exc: BaseException) -> str:
    """Map a python-telegram-bot exception to a sanitized cause label.

    We import lazily to avoid forcing the optional ``telegram`` dependency
    on test runs that monkey-patch the transport.
    """

    try:
        from telegram import error as telegram_error
    except Exception:  # pragma: no cover - python-telegram-bot not installed
        return TELEGRAM_CAUSE_OTHER

    if isinstance(exc, telegram_error.RetryAfter):
        return TELEGRAM_CAUSE_RATE_LIMIT
    if isinstance(exc, telegram_error.InvalidToken):
        return TELEGRAM_CAUSE_AUTH
    if isinstance(exc, telegram_error.Forbidden):
        return TELEGRAM_CAUSE_CHAT_BLOCKED
    if isinstance(exc, telegram_error.ChatMigrated):
        return TELEGRAM_CAUSE_CHAT_BLOCKED
    if isinstance(exc, telegram_error.TimedOut):
        return TELEGRAM_CAUSE_NETWORK
    if isinstance(exc, telegram_error.NetworkError):
        return TELEGRAM_CAUSE_NETWORK
    if isinstance(exc, telegram_error.BadRequest):
        message = str(exc).lower()
        if "blocked" in message or "kicked" in message or "not found" in message:
            return TELEGRAM_CAUSE_CHAT_BLOCKED
    return TELEGRAM_CAUSE_OTHER


class TelegramTransport(Protocol):
    async def send_message(
        self, *, chat_id: int, message_thread_id: int | None, text: str
    ) -> int: ...


class PythonTelegramTransport:
    def __init__(self, token: str) -> None:
        try:
            from telegram import Bot
        except ImportError as exc:  # pragma: no cover - installed runtime boundary
            raise RuntimeError(
                "Install python-telegram-bot before running the bot service"
            ) from exc
        self._bot = Bot(token=token)

    @property
    def bot(self) -> Any:
        return self._bot

    async def send_message(self, *, chat_id: int, message_thread_id: int | None, text: str) -> int:
        try:
            if message_thread_id is not None:
                message = await self._bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    disable_web_page_preview=True,
                    message_thread_id=message_thread_id,
                )
            else:
                message = await self._bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    disable_web_page_preview=True,
                )
        except Exception as exc:
            raise TelegramSendError(_classify_telegram_exception(exc)) from exc
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
        except TelegramSendError as exc:
            self._repository.mark_notification_failed(
                delivery.notification.id,
                error_message=exc.cause,
                retry_seconds=self._retry_seconds,
            )
            return False
        self._repository.mark_notification_sent(
            delivery.notification.id, telegram_message_id=message_id
        )
        return True


def format_notification(delivery: TelegramDelivery) -> str:
    release = delivery.release
    header = [
        "OPlus Official ROMs",
        release.real_version_name,
        "",
    ]
    metadata = [
        ("ColorOS Version", _display_os_version(release)),
        ("Security patch level", release.security_patch),
        ("Published time", _format_datetime(release.published_at or release.discovered_at)),
        ("OTA version", release.real_ota_version),
        ("Region", _release_region(release)),
        ("Manifest", release.manifest_code),
        ("Track", release.ota_track),
        ("File size", _format_file_size(release.file_size)),
        ("MD5", release.md5),
        ("Component version", release.computed_ota_version),
    ]
    lines = header
    lines.extend(f"[{key}] {value}" for key, value in metadata if value)
    if release.about_update_url:
        lines.extend(["", "[Update log]", release.about_update_url])
    lines.extend(["", "[Download URL]", release.download_url])
    lines.append("")
    lines.append(_release_tags(release))
    return _fit_telegram_message(lines, required_tail=release.download_url)


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


def _display_os_version(release: Release) -> str | None:
    display = release.real_version_name
    match = re.search(r"_(\d{1,2}\.\d+\.\d+\.\d{3})(?:Patch\d+)?", display)
    if not match:
        return None
    major = match.group(1).split(".", 1)[0]
    if release.brand == "oneplus":
        return f"OxygenOS {major}.0"
    if release.brand == "realme":
        return f"realme UI {major}.0"
    return f"ColorOS {major}.0"


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _format_file_size(value: int | None) -> str | None:
    if value is None or value <= 0:
        return None
    gib = value / (1024**3)
    if gib >= 1:
        return f"{gib:.2f} GB ({value})"
    mib = value / (1024**2)
    if mib >= 1:
        return f"{mib:.0f} MB ({value})"
    kib = value / 1024
    if kib >= 1:
        return f"{kib:.0f} KB ({value})"
    return f"{value} B"


def _release_region(release: Release) -> str | None:
    if release.region_code and release.region_code != release.manifest_code:
        return f"{release.region_code} / {release.manifest_code}"
    return release.region_code or release.manifest_code or None


def _release_tags(release: Release) -> str:
    tags = [release.brand.title().replace("Oneplus", "OnePlus"), release.product_model]
    if release.region_code:
        tags.append(release.region_code)
    if release.release_type:
        tags.append(release.release_type.title())
    return " ".join("#" + re.sub(r"[^A-Za-z0-9_]", "", tag) for tag in tags if tag)


def _fit_telegram_message(lines: list[str], *, required_tail: str, limit: int = 4096) -> str:
    text = "\n".join(lines)
    if len(text) <= limit:
        return text
    compact = [line for line in lines if not line.startswith("[Update log]")]
    text = "\n".join(compact)
    if len(text) <= limit:
        return text
    tail = f"\n\n[Download URL]\n{required_tail}"
    budget = max(limit - len(tail), 0)
    return text[:budget].rstrip() + tail
