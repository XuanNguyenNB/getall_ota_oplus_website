import pytest

from ota_backend.config import Settings


def test_environment_reads_preferred_and_legacy_names(monkeypatch):
    assert Settings(environment="production").environment == "production"

    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings().environment == "production"

    monkeypatch.delenv("ENVIRONMENT")
    monkeypatch.setenv("APP_ENV", "staging")
    assert Settings().environment == "staging"


def test_production_runtime_requires_live_supabase_settings(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("OTA_PROVIDER", "fake")
    monkeypatch.setenv("ALLOW_LIVE_OTA", "false")
    settings = Settings()

    with pytest.raises(RuntimeError, match="Production runtime requires"):
        settings.validate_runtime_configuration()


def test_realme_provider_requires_explicit_live_ota(monkeypatch):
    monkeypatch.setenv("OTA_PROVIDER", "realme")
    monkeypatch.setenv("ALLOW_LIVE_OTA", "false")
    settings = Settings()

    with pytest.raises(RuntimeError, match="ALLOW_LIVE_OTA=true"):
        settings.validate_runtime_configuration()


def test_supabase_backend_requires_server_key(monkeypatch):
    monkeypatch.setenv("REPOSITORY_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://project-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    settings = Settings()

    with pytest.raises(RuntimeError, match="Supabase runtime requires"):
        settings.validate_runtime_configuration()


def test_blank_optional_telegram_chat_id_is_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    monkeypatch.setenv("TELEGRAM_COMMAND_CHAT_ID", "")
    monkeypatch.setenv("TELEGRAM_WORKER_LOG_CHAT_ID", "")

    settings = Settings()
    assert settings.telegram_chat_id is None
    assert settings.telegram_command_chat_id is None
    assert settings.telegram_worker_log_chat_id is None


def test_effective_telegram_chats_fallback_to_legacy(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

    settings = Settings()

    assert settings.effective_telegram_command_chat_id == 123
    assert settings.effective_telegram_worker_log_chat_id == 123
