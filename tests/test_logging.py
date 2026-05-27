from ota_backend.logging import sanitize_mapping


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
