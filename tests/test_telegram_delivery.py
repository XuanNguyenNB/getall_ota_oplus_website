from __future__ import annotations

import asyncio

from ota_backend.domain.models import OtaProviderRelease
from ota_backend.repositories.memory import InMemoryReleaseRepository, InMemoryTelegramRepository
from ota_backend.services.telegram import TelegramDeliveryService, TelegramSendError


class SuccessfulTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int, text: str) -> int:
        assert message_thread_id == 222
        assert "RMX3301" in text
        return 91


class FailedTransport:
    async def send_message(self, *, chat_id: int, message_thread_id: int, text: str) -> int:
        raise TelegramSendError("failure")


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
