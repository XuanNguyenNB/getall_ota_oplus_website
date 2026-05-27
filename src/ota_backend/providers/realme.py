from __future__ import annotations

import json
import re
from importlib import import_module
from typing import Any, Callable

import httpx

from ota_backend.config import Settings
from ota_backend.domain.manifest import get_authoritative_manifest_target, live_manifest_map_complete
from ota_backend.domain.models import OtaProviderRelease, OtaQuery, OtaTrack
from ota_backend.domain.ota import build_seed_ota_version, derive_ota_model, infer_brand
from ota_backend.providers.interfaces import (
    OtaNotFoundError,
    OtaProvider,
    OtaProviderDecryptError,
    OtaProviderTimeoutError,
    OtaProviderUnavailableError,
)


MODEL_ALIAS_OVERRIDES: dict[tuple[str, str], tuple[str, ...]] = {
    ("CPH2659", "1B"): ("CPH2659", "CPH2659IN"),
}


class RealmeOtaProvider(OtaProvider):
    """Live adapter around the GPLv3 realme-ota request/encryption implementation."""

    def __init__(
        self,
        settings: Settings,
        *,
        request_cls: type[Any] | None = None,
        post: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings
        self._post = post or httpx.post
        self._request_cls = request_cls
        self._import_error: Exception | None = None
        if self._request_cls is None:
            try:
                self._request_cls = import_module("realme_ota.utils.request").Request
            except Exception as exc:  # pragma: no cover - optional runtime dependency
                self._import_error = exc

    def query(self, request: OtaQuery) -> OtaProviderRelease:
        if self._import_error is not None or self._request_cls is None:
            raise OtaProviderUnavailableError(
                "realme-ota is not importable in this environment"
            ) from self._import_error
        if not self._settings.allow_live_ota:
            raise OtaProviderUnavailableError("live OTA queries are disabled")
        if not live_manifest_map_complete():
            raise OtaProviderUnavailableError(
                "live OTA queries require the complete approved manifest map"
            )

        target = get_authoritative_manifest_target(request.manifest_code)
        if target is None:
            raise OtaProviderUnavailableError("manifest code is not live-query enabled")

        for candidate in request.rui_candidates:
            try:
                return self._query_candidate(
                    request,
                    candidate,
                    target.nv_id,
                    target.server_region,
                    target.server_region_label,
                )
            except OtaNotFoundError:
                continue
        raise OtaNotFoundError("no OTA found for configured RUI candidates")

    def _query_candidate(
        self,
        request: OtaQuery,
        rui_version: int,
        nv_id: str,
        server_region: int,
        region_label: str,
    ) -> OtaProviderRelease:
        last_validation_error: Exception | None = None
        found_no_release = False
        for upstream_model in _upstream_product_models(
            request.product_model,
            request.manifest_code,
        ):
            content: dict[str, Any] | None = None
            for ota_version in _seed_ota_versions(upstream_model, request.ota_track):
                prepared = self._request_cls(
                    req_version=1 if rui_version == 1 else 2,
                    model=upstream_model,
                    ota_version=ota_version,
                    nv_identifier=nv_id,
                    rui_version=rui_version,
                    region=server_region,
                    imei0=request.imei0,
                    imei1=request.imei1,
                    beta=request.beta,
                    language=request.language,
                )
                try:
                    prepared.set_vars()
                    prepared.set_body_headers()
                except Exception as exc:
                    raise OtaProviderUnavailableError("unable to build OTA request") from exc

                try:
                    response = self._post(
                        prepared.url,
                        content=prepared.body,
                        headers=prepared.headers,
                        timeout=self._settings.realme_ota_timeout_seconds,
                    )
                except httpx.TimeoutException as exc:
                    raise OtaProviderTimeoutError("OTA endpoint timed out") from exc
                except httpx.HTTPError as exc:
                    raise OtaProviderUnavailableError("OTA endpoint request failed") from exc

                try:
                    envelope = json.loads(response.content)
                    encrypted = envelope.get(prepared.resp_key)
                except Exception as exc:
                    raise OtaProviderUnavailableError(
                        "OTA endpoint returned an invalid response"
                    ) from exc
                try:
                    prepared.validate_response(response)
                except Exception as exc:
                    last_validation_error = exc
                    if encrypted is None:
                        continue
                    # The current OPlus API returns decryptable no-update payloads
                    # with non-200 responseCode values rejected by upstream CLI validation.
                try:
                    if encrypted is None:
                        last_validation_error = RuntimeError("OTA endpoint response body is empty")
                        continue
                    if isinstance(encrypted, dict):
                        encrypted = json.dumps(encrypted)
                    decrypted = prepared.decrypt(encrypted)
                    content = json.loads(decrypted)
                except Exception as exc:
                    raise OtaProviderDecryptError("Unable to decrypt OTA response.") from exc
                break
            if content is None:
                continue

            if content.get("checkFailReason"):
                found_no_release = True
                continue

            real_ota_version = _find_string(content, "realOtaVersion")
            download_url = _find_download_url(content)
            if not real_ota_version or not download_url:
                found_no_release = True
                continue
            real_version_name = _find_string(content, "realVersionName") or real_ota_version

            return OtaProviderRelease(
                brand=request.brand or infer_brand(None, request.product_model),
                product_model=request.product_model,
                manifest_code=request.manifest_code,
                ota_track=request.ota_track,
                rui_version=rui_version,
                real_ota_version=real_ota_version,
                real_version_name=real_version_name,
                computed_ota_version=_computed_ota_version(
                    request.product_model, region_label, real_ota_version
                ),
                version_type_id=_find_string(content, "versionTypeId") or "unknown",
                about_update_url=_find_string(content, "panelUrl"),
                download_url=download_url.replace("componentotacostmanual", "opexcostmanual"),
                md5=_find_string(content, "md5"),
                file_size=_find_int(content, "size"),
                security_patch=_find_string(content, "securityPatch"),
                raw_response=content if self._settings.enable_raw_response else None,
            )

        if found_no_release:
            raise OtaNotFoundError("OTA endpoint returned no release")
        raise OtaProviderUnavailableError(
            "OTA endpoint returned an error response"
        ) from last_validation_error


def _seed_ota_versions(product_model: str, ota_track: OtaTrack) -> tuple[str, str]:
    primary = build_seed_ota_version(product_model, ota_track)
    fallback = primary.rsplit("_", 2)[0] + "_0001_000000000001"
    return primary, fallback


def _upstream_product_models(
    product_model: str,
    manifest_code: str | None = None,
) -> tuple[str, ...]:
    normalized_model = product_model.strip().upper()
    normalized_manifest = (manifest_code or "").strip().upper()
    candidates = MODEL_ALIAS_OVERRIDES.get((normalized_model, normalized_manifest))
    if candidates is None:
        base_model = derive_ota_model(normalized_model)
        candidates = (
            (normalized_model,)
            if base_model == normalized_model
            else (normalized_model, base_model)
        )

    return tuple(dict.fromkeys(candidates))


def _walk(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _find_string(content: dict[str, Any], key: str) -> str | None:
    for candidate_key, value in _walk(content):
        if candidate_key == key and isinstance(value, str) and value:
            return value
    return None


def _find_int(content: dict[str, Any], key: str) -> int | None:
    for candidate_key, value in _walk(content):
        if candidate_key == key and isinstance(value, int):
            return value
    return None


def _find_download_url(content: dict[str, Any]) -> str | None:
    for key in ("url", "downloadUrl", "download_url", "otaUrl", "ota_url"):
        value = _find_string(content, key)
        if value and value.startswith(("https://", "http://")):
            return value
    for _key, value in _walk(content):
        if isinstance(value, str) and value.startswith(("https://", "http://")) and ".zip" in value:
            return value
    return None


def _computed_ota_version(product_model: str, region_label: str, real_ota_version: str) -> str:
    match = re.search(r"_11\.([A-Z]\.[0-9]+).*_([0-9]{12})$", real_ota_version)
    if match:
        return f"{derive_ota_model(product_model)}_11.{match.group(1)}_{region_label}_{match.group(2)}"
    return f"{product_model}_{region_label}_{real_ota_version}"
