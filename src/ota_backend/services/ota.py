from __future__ import annotations

from ota_backend.domain.manifest import normalize_manifest_code
from ota_backend.domain.models import OtaQuery, PersistedRelease, Release
from ota_backend.domain.ota import (
    infer_brand,
    normalize_product_model,
    normalize_rui_candidates,
    normalize_track,
)
from ota_backend.providers.interfaces import (
    OtaNotFoundError,
    OtaProvider,
    OtaProviderDecryptError,
    OtaProviderTimeoutError,
    OtaProviderUnavailableError,
)
from ota_backend.repositories.interfaces import DeviceRepository, ReleaseRepository


class OtaServiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OtaQueryService:
    def __init__(
        self,
        *,
        provider: OtaProvider,
        release_repository: ReleaseRepository,
        device_repository: DeviceRepository | None = None,
    ) -> None:
        self._provider = provider
        self._release_repository = release_repository
        self._device_repository = device_repository

    def run_manual_query(self, request: OtaQuery) -> PersistedRelease:
        try:
            product_model = normalize_product_model(request.product_model)
            device = (
                self._device_repository.get_by_product_model(product_model)
                if self._device_repository is not None
                else None
            )
            normalized = OtaQuery(
                product_model=product_model,
                manifest_code=normalize_manifest_code(request.manifest_code),
                ota_track=normalize_track(request.ota_track),
                rui_candidates=normalize_rui_candidates(request.rui_candidates),
                language=request.language,
                beta=request.beta,
                imei0=request.imei0,
                imei1=request.imei1,
                persist_result=request.persist_result,
                brand=request.brand
                or (device.brand if device else infer_brand(None, product_model)),
            )
        except ValueError as exc:
            raise OtaServiceError("VALIDATION_ERROR", str(exc)) from exc

        try:
            provider_release = self._provider.query(normalized)
        except OtaNotFoundError as exc:
            raise OtaServiceError("OTA_NOT_FOUND", "No OTA release found.") from exc
        except OtaProviderTimeoutError as exc:
            raise OtaServiceError("UPSTREAM_TIMEOUT", "The OTA endpoint timed out.") from exc
        except OtaProviderDecryptError as exc:
            raise OtaServiceError("DECRYPT_ERROR", "The OTA response could not be parsed.") from exc
        except OtaProviderUnavailableError as exc:
            raise OtaServiceError("UPSTREAM_ERROR", str(exc)) from exc

        if not normalized.persist_result:
            return PersistedRelease(
                release=Release.from_provider(provider_release, discovered_by="manual"),
                is_new=False,
            )

        return self._release_repository.upsert_release(provider_release, discovered_by="manual")
