import logging

from ota_backend.logging import JsonFormatter, sanitize_mapping, sanitize_text


def test_logging_sanitizer_redacts_sensitive_fields():
    payload = sanitize_mapping(
        {
            "product_model": "RMX3301",
            "imei0": "123456789012345",
            "guid": "secret-guid",
            "Authorization": "Bearer token",
            "SUPABASE_SERVICE_ROLE_KEY": "service-secret",
            "protectedKey": "protected",
            "request_body": {"imei1": "54321"},
        }
    )

    assert payload["product_model"] == "RMX3301"
    assert payload["imei0"] == "[REDACTED]"
    assert payload["guid"] == "[REDACTED]"
    assert payload["Authorization"] == "[REDACTED]"
    assert payload["SUPABASE_SERVICE_ROLE_KEY"] == "[REDACTED]"
    assert payload["protectedKey"] == "[REDACTED]"
    assert payload["request_body"] == "[REDACTED]"


def test_sanitize_text_redacts_tokens_embedded_in_messages():
    assert sanitize_text("POST https://api.telegram.org/bot123:ABC_def/getUpdates") == (
        "POST https://api.telegram.org/[REDACTED]/getUpdates"
    )
    assert sanitize_text("using sb_secret_abcdef123456") == "using [REDACTED]"


def test_json_formatter_redacts_message_text():
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="POST https://api.telegram.org/bot123:ABC_def/getUpdates",
        args=(),
        exc_info=None,
    )

    assert "bot123:ABC_def" not in JsonFormatter().format(record)
