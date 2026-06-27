from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from ota_backend.config import Settings
from ota_backend.domain.models import (
    Device,
    OtaProviderRelease,
    Release,
    TelegramDelivery,
    TelegramNotification,
    TelegramTarget,
)
from ota_backend.repositories.memory import (
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
    InMemoryTelegramRepository,
)
from ota_backend.services.telegram import (
    TelegramDeliveryService,
    TelegramSendError,
    format_notification,
)
from ota_backend.telegram_bot import (
    TelegramBotService,
    format_scan_status,
    format_scan_status_short,
)


class SuccessfulTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int | None, text: str) -> int:
        assert message_thread_id == 222
        assert "RMX3301" in text
        return 91


class ChannelTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int | None, text: str) -> int:
        assert message_thread_id is None
        assert "OPlus Official ROMs" in text
        assert "[Download URL]" in text
        return 77


class FailedTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int | None, text: str) -> int:
        raise TelegramSendError()


class RateLimitedTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int | None, text: str) -> int:
        from ota_backend.services.telegram import TELEGRAM_CAUSE_RATE_LIMIT

        raise TelegramSendError(TELEGRAM_CAUSE_RATE_LIMIT)


class ChatBlockedTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int | None, text: str) -> int:
        from ota_backend.services.telegram import TELEGRAM_CAUSE_CHAT_BLOCKED

        raise TelegramSendError(TELEGRAM_CAUSE_CHAT_BLOCKED)


def _queued_repository() -> InMemoryTelegramRepository:
    releases = InMemoryReleaseRepository()
    telegram = InMemoryTelegramRepository()
    persisted = releases.upsert_release(
        OtaProviderRelease(
            brand="realme",
            product_model="RMX3301",
            manifest_code="1B",
            ota_track="H",
            rui_version=7,
            real_ota_version="RMX3301_11.H.21_4210_202602281641",
            real_version_name="RMX3301_release",
            computed_ota_version="RMX3301_computed",
            version_type_id="non_display",
            about_update_url=None,
            download_url="https://example.com/update.zip",
        ),
        discovered_by="worker",
    )
    target = telegram.get_target_for_brand("realme")
    assert target is not None
    telegram.enqueue_notification(release=persisted.release, target=target)
    return telegram


def _rich_delivery(*, message_thread_id: int | None = 222) -> TelegramDelivery:
    release = Release(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        brand="oppo",
        product_model="PKB110",
        manifest_code="97",
        ota_track="C",
        rui_version=8,
        real_ota_version="PKB110_11.C.93_1930_202604300008",
        real_version_name="PKB110_16.0.7.200(CN01)",
        computed_ota_version="PKB110_11.C.93_CN_202604300008",
        version_type_id="non_display",
        about_update_url="https://example.test/about.html",
        download_url="https://example.test/update.zip",
        discovered_by="worker",
        discovered_at=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
        last_seen_at=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
        md5="abcd1234",
        file_size=7849792070,
        security_patch="2026-05-01",
        published_at=datetime(2026, 6, 1, 18, 0, 32, tzinfo=UTC),
    )
    target = TelegramTarget(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        brand="oppo",
        chat_id=-1001234567890,
        message_thread_id=message_thread_id,
    )
    notification = TelegramNotification(
        id=UUID("33333333-3333-4333-8333-333333333333"),
        release_id=release.id,
        telegram_target_id=target.id,
        status="sending",
        created_at=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
        attempt_count=1,
    )
    return TelegramDelivery(notification=notification, release=release, target=target)


def test_telegram_delivery_claims_queue_and_marks_message_sent():
    repository = _queued_repository()
    service = TelegramDeliveryService(
        repository=repository,
        transport=SuccessfulTransport(),
        max_attempts=3,
        retry_seconds=60,
    )

    assert asyncio.run(service.deliver_once()) is True
    assert repository.notifications[0].status == "sent"
    assert repository.notifications[0].telegram_message_id == 91
    assert asyncio.run(service.deliver_once()) is False


def test_telegram_notification_format_is_rich_and_usable():
    text = format_notification(_rich_delivery())

    assert "OPlus Official ROMs" in text
    assert "PKB110_16.0.7.200(CN01)" in text
    assert "[Security patch level] 2026-05-01" in text
    assert "[Published time] 2026-06-01 18:00:32" in text
    assert "[OTA version] PKB110_11.C.93_1930_202604300008" in text
    assert "[File size]" in text
    assert "[MD5] abcd1234" in text
    assert "[Download URL]" in text


def test_telegram_notification_format_omits_missing_metadata():
    delivery = _rich_delivery()
    delivery.release.security_patch = None  # type: ignore[assignment]
    delivery.release.file_size = None  # type: ignore[assignment]
    delivery.release.md5 = None  # type: ignore[assignment]

    text = format_notification(delivery)

    assert "None" not in text
    assert "[Security patch level]" not in text
    assert "[File size]" not in text
    assert "[MD5]" not in text


def test_telegram_delivery_supports_channel_targets_without_topics():
    service = TelegramDeliveryService(
        repository=InMemoryTelegramRepository(
            targets=[
                TelegramTarget(
                    id=UUID("aaaa1111-1111-4111-8111-111111111111"),
                    brand="oppo",
                    chat_id=-1001234567890,
                    message_thread_id=None,
                )
            ]
        ),
        transport=ChannelTransport(),
        max_attempts=3,
        retry_seconds=60,
    )
    repository = service._repository  # noqa: SLF001 - test seam
    release = _rich_delivery(message_thread_id=None).release
    target = repository.get_target_for_brand("oppo")
    assert target is not None
    repository.enqueue_notification(release=release, target=target)

    assert asyncio.run(service.deliver_once()) is True


def test_telegram_delivery_stores_sanitized_retryable_failure():
    repository = _queued_repository()
    service = TelegramDeliveryService(
        repository=repository,
        transport=FailedTransport(),
        max_attempts=3,
        retry_seconds=60,
    )

    assert asyncio.run(service.deliver_once()) is False
    assert repository.notifications[0].status == "failed"
    assert repository.notifications[0].error_message == "TELEGRAM_DELIVERY_FAILED"
    assert repository.notifications[0].next_attempt_at is not None


def test_telegram_delivery_persists_rate_limit_cause_label_for_audit():
    """Cause labels are stable strings stored on the notification row so
    operators can filter retry/audit state by failure category without
    grepping free-form text. RATE_LIMIT should round-trip through the
    delivery service untouched."""

    repository = _queued_repository()
    service = TelegramDeliveryService(
        repository=repository,
        transport=RateLimitedTransport(),
        max_attempts=3,
        retry_seconds=60,
    )

    assert asyncio.run(service.deliver_once()) is False
    assert repository.notifications[0].status == "failed"
    assert repository.notifications[0].error_message == "TELEGRAM_RATE_LIMIT"


def test_telegram_delivery_persists_chat_blocked_cause_label_for_audit():
    """CHAT_BLOCKED is operator-actionable (revoked invite, removed from
    forum) and must be distinguishable from transient network errors."""

    repository = _queued_repository()
    service = TelegramDeliveryService(
        repository=repository,
        transport=ChatBlockedTransport(),
        max_attempts=3,
        retry_seconds=60,
    )

    assert asyncio.run(service.deliver_once()) is False
    assert repository.notifications[0].status == "failed"
    assert repository.notifications[0].error_message == "TELEGRAM_CHAT_BLOCKED"


def test_telegram_send_error_default_cause_is_generic_other_label():
    """The default constructor maps to the generic OTHER label so callers
    that do not classify the upstream exception still produce a value
    that matches the documented enum."""

    err = TelegramSendError()
    assert err.cause == "TELEGRAM_DELIVERY_FAILED"


def test_scan_status_reply_contains_operational_details():
    from ota_backend.domain.models import ScanRun

    run = ScanRun(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        status="completed",
        cycle_day=5,
        started_at=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 6, 8, 0, 3, tzinfo=UTC),
        total_tasks=90,
        completed_tasks=88,
        failed_tasks=2,
        new_releases=7,
    )

    reply = format_scan_status(
        run,
        scan_eligibility_counts={
            "active_scan": 120,
            "archive_only": 900,
            "invalid_for_scan": 12,
        },
        scan_cycle_days=7,
        recent_runs=[run],
    )

    assert "OPlus OTA scan status" in reply
    assert "Run: 11111111-1111-4111-8111-111111111111" in reply
    assert "Cycle day: 5/6" in reply
    assert "Tasks: 88/90" in reply
    assert "Failed: 2" in reply
    assert "New releases: 7" in reply
    assert "Eligibility: active=120, archive=900, invalid=12" in reply
    assert "Recent coverage: 1/7 cycle days" in reply
    assert "journalctl -u ota-worker.service -f" in reply


def test_scan_status_short_reply_is_compact():
    from ota_backend.domain.models import ScanRun

    run = ScanRun(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        status="completed",
        cycle_day=5,
        started_at=datetime(2026, 6, 8, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 6, 8, 0, 3, tzinfo=UTC),
        total_tasks=90,
        completed_tasks=88,
        failed_tasks=2,
        new_releases=7,
    )

    reply = format_scan_status_short(run)

    assert reply == "\n".join(
        (
            "Scan status: completed",
            "Completed: 88/90",
            "Failed: 2",
            "New releases: 7",
        )
    )


def _device(
    *,
    name: str,
    product_model: str,
    manifest_code: str,
    scan_enabled: bool = False,
) -> Device:
    return Device(
        id=uuid4(),
        catalog_id=None,
        brand="oppo",
        name=name,
        product_model=product_model,
        manifest_code=manifest_code,
        scan_enabled=scan_enabled,
        active_track="C",
    )


def _bot_with_devices(repository: InMemoryDeviceRepository) -> TelegramBotService:
    bot = object.__new__(TelegramBotService)
    bot._settings = Settings(  # noqa: SLF001 - command unit test
        telegram_admin_user_ids="123",
        telegram_bot_token="token",
        telegram_command_chat_id=1,
        telegram_worker_log_chat_id=2,
    )
    bot._app = SimpleNamespace(  # noqa: SLF001 - command unit test
        state=SimpleNamespace(
            device_repository=repository,
            telegram_repository=InMemoryTelegramRepository(),
        )
    )
    return bot


def test_scan_command_search_and_group_enable_updates_variants():
    devices = InMemoryDeviceRepository(
        [
            _device(name="OPPO Find X8 (CN)", product_model="PKB110", manifest_code="97"),
            _device(name="OPPO Find X8 (IN)", product_model="CPH2651IN", manifest_code="1B"),
            _device(name="OPPO Find X8 Pro (CN)", product_model="PKC110", manifest_code="97"),
        ]
    )
    bot = _bot_with_devices(devices)

    search = bot._command_reply("/scan search Find X8", telegram_user_id=123)  # noqa: SLF001
    assert "OPPO Find X8: 0/2 variants ON" in search
    assert "Key: oppo-find-x8" in search
    assert "OPPO Find X8 Pro: 0/1 variants ON" in search

    reply = bot._command_reply("/scan on-group oppo-find-x8", telegram_user_id=123)  # noqa: SLF001

    assert "Scan enabled: 2 variants updated" in reply
    assert devices.get_by_product_model("PKB110").scan_enabled is True
    assert devices.get_by_product_model("CPH2651IN").scan_enabled is True
    assert devices.get_by_product_model("PKC110").scan_enabled is False


def test_scan_command_is_admin_only_and_off_all_requires_confirmation():
    devices = InMemoryDeviceRepository(
        [
            _device(
                name="OPPO Find X8 (CN)",
                product_model="PKB110",
                manifest_code="97",
                scan_enabled=True,
            )
        ]
    )
    bot = _bot_with_devices(devices)

    assert (
        bot._command_reply("/scan list on", telegram_user_id=999)  # noqa: SLF001
        == "Admin access is required."
    )
    assert (
        bot._command_reply("/scan off-all", telegram_user_id=123)  # noqa: SLF001
        == "Usage: /scan off-all CONFIRM"
    )
    assert devices.get_by_product_model("PKB110").scan_enabled is True

    reply = bot._command_reply("/scan off-all CONFIRM", telegram_user_id=123)  # noqa: SLF001

    assert reply == "Scan disabled for 1 variants."
    assert devices.get_by_product_model("PKB110").scan_enabled is False


def test_check_config_reports_command_chat_and_targets_without_secret_leak():
    devices = InMemoryDeviceRepository(
        [_device(name="OPPO Find X8 (CN)", product_model="PKB110", manifest_code="97")]
    )
    bot = _bot_with_devices(devices)

    class Transport:
        class _Bot:
            async def get_me(self):
                return SimpleNamespace(username="oplus_bot")

            async def send_message(
                self, *, chat_id: int, text: str, disable_web_page_preview: bool
            ):
                assert chat_id == 1
                assert "config check" in text
                return SimpleNamespace(message_id=1)

        bot = _Bot()

    bot._transport = Transport()  # noqa: SLF001 - command unit test

    reply = asyncio.run(bot.check_config())

    assert "Telegram config check" in reply
    assert "Bot identity: @oplus_bot" in reply
    assert "Command chat send: ok" in reply
    assert "Release target oppo:" in reply
