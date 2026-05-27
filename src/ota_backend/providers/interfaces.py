from __future__ import annotations

from typing import Protocol

from ota_backend.domain.models import OtaProviderRelease, OtaQuery


class OtaNotFoundError(Exception):
    """Raised when the provider returns a valid no-update result."""


class OtaProviderUnavailableError(Exception):
    """Raised when a provider cannot run in the current runtime."""


class OtaProviderTimeoutError(OtaProviderUnavailableError):
    """Raised when the upstream OTA endpoint exceeds the configured timeout."""


class OtaProviderDecryptError(Exception):
    """Raised when a successful-looking OTA response cannot be decrypted or parsed."""


class OtaProvider(Protocol):
    def query(self, request: OtaQuery) -> OtaProviderRelease:
        ...
