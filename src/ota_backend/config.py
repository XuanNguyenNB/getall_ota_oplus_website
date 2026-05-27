from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    service_name: str = "getall_ota_oplus_website"
    version: str = "0.1.0"
    environment: str = Field(
        default="local", validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV")
    )
    log_level: str = "INFO"

    repository_backend: Literal["memory", "supabase"] = "memory"
    ota_provider: Literal["fake", "realme"] = "fake"
    allow_live_ota: bool = False

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_secret_key: str | None = Field(default=None, alias="SUPABASE_SECRET_KEY")
    supabase_service_role_key: str | None = Field(
        default=None, alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    scan_max_concurrency: int = Field(default=3, ge=1, le=20)
    scan_request_interval_seconds: float = Field(default=1.0, ge=0, le=60)
    realme_ota_timeout_seconds: float = Field(default=30, gt=0, le=120)
    rui_candidates: str = "8,7,6"
    enable_raw_response: bool = False

    public_site_enabled: bool = False
    turnstile_site_key: str | None = Field(default=None, alias="TURNSTILE_SITE_KEY")
    turnstile_secret_key: str | None = Field(default=None, alias="TURNSTILE_SECRET_KEY")
    turnstile_expected_hostname: str | None = Field(default=None, alias="TURNSTILE_EXPECTED_HOSTNAME")
    public_rate_limit_salt: str | None = Field(default=None, alias="PUBLIC_RATE_LIMIT_SALT")
    ota_public_cache_ttl_seconds: int = Field(default=1800, ge=0, le=86400)
    ota_public_rate_limit_per_hour: int = Field(default=5, ge=1, le=1000)
    resolver_public_rate_limit_per_hour: int = Field(default=10, ge=1, le=1000)

    enable_resolver: bool = False
    resolver_live_proof_confirmed: bool = False
    resolver_allowed_host_suffixes: str = (
        "allawnofs.com,allawnos.com,allawntech.com,allawnfs.com,coloros.com,realmemobile.com,h2os.com"
    )
    resolver_timeout_seconds: float = Field(default=30, gt=0, le=120)
    resolver_max_redirects: int = Field(default=5, ge=0, le=10)

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: int | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    telegram_admin_user_ids: str = ""
    telegram_poll_timeout_seconds: int = Field(default=20, ge=1, le=50)
    telegram_notification_max_attempts: int = Field(default=3, ge=1, le=20)
    telegram_notification_retry_seconds: int = Field(default=300, ge=1, le=86400)

    @field_validator("telegram_chat_id", mode="before")
    @classmethod
    def _blank_optional_int(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def supabase_server_key(self) -> str | None:
        return self.supabase_secret_key or self.supabase_service_role_key

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}

    @property
    def parsed_rui_candidates(self) -> list[int]:
        try:
            candidates = [int(item.strip()) for item in self.rui_candidates.split(",") if item.strip()]
        except ValueError as exc:
            raise ValueError("RUI_CANDIDATES must contain comma-separated integers") from exc
        if not candidates or any(candidate < 1 or candidate > 9 for candidate in candidates):
            raise ValueError("RUI_CANDIDATES must contain values from 1 to 9")
        return candidates

    @property
    def parsed_resolver_allowed_host_suffixes(self) -> tuple[str, ...]:
        suffixes = tuple(
            item.strip().lower().lstrip(".")
            for item in self.resolver_allowed_host_suffixes.split(",")
            if item.strip()
        )
        if not suffixes:
            raise ValueError("RESOLVER_ALLOWED_HOST_SUFFIXES must not be empty")
        return suffixes

    @property
    def parsed_telegram_admin_user_ids(self) -> set[int]:
        try:
            return {
                int(item.strip())
                for item in self.telegram_admin_user_ids.split(",")
                if item.strip()
            }
        except ValueError as exc:
            raise ValueError("TELEGRAM_ADMIN_USER_IDS must contain integer IDs") from exc

    def validate_runtime_configuration(self) -> None:
        if self.repository_backend == "supabase":
            required = {
                "SUPABASE_URL": self.supabase_url,
                "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY": self.supabase_server_key,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise RuntimeError(
                    "Supabase runtime requires server configuration: "
                    + ", ".join(missing)
                )
        if self.ota_provider == "realme" and not self.allow_live_ota:
            raise RuntimeError(
                "OTA_PROVIDER=realme requires ALLOW_LIVE_OTA=true."
            )
        if self.is_production:
            invalid = []
            if self.repository_backend != "supabase":
                invalid.append("REPOSITORY_BACKEND=supabase")
            if self.ota_provider != "realme":
                invalid.append("OTA_PROVIDER=realme")
            if not self.allow_live_ota:
                invalid.append("ALLOW_LIVE_OTA=true")
            if not self.supabase_url:
                invalid.append("SUPABASE_URL")
            if not self.supabase_server_key:
                invalid.append("SUPABASE_SECRET_KEY")
            if invalid:
                raise RuntimeError(
                    "Production runtime requires: " + ", ".join(invalid)
                )
        if self.public_site_enabled:
            required = {
                "TURNSTILE_SITE_KEY": self.turnstile_site_key,
                "TURNSTILE_SECRET_KEY": self.turnstile_secret_key,
                "TURNSTILE_EXPECTED_HOSTNAME": self.turnstile_expected_hostname,
                "PUBLIC_RATE_LIMIT_SALT": self.public_rate_limit_salt,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise RuntimeError(
                    "Public runtime requires server configuration: " + ", ".join(missing)
                )
        if self.enable_resolver and not self.resolver_live_proof_confirmed:
            raise RuntimeError(
                "ENABLE_RESOLVER requires RESOLVER_LIVE_PROOF_CONFIRMED=true after bounded validation."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
