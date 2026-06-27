from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from ota_backend.config import Settings
from ota_backend.domain.manifest import (
    get_authoritative_manifest_target,
    live_manifest_map_complete,
)
from ota_backend.domain.models import OtaProviderRelease, OtaQuery, OtaTrack
from ota_backend.domain.ota import build_seed_ota_version, derive_ota_model, infer_brand
from ota_backend.providers.interfaces import (
    OtaNotFoundError,
    OtaProvider,
    OtaProviderDecryptError,
    OtaProviderTimeoutError,
    OtaProviderUnavailableError,
)

# Region-specific upstream model suffixes. Some catalog models only return an
# OTA when queried with a region-suffixed variant under the matching manifest
# (e.g. India model CPH2659 resolves as CPH2659IN, DN2101 as DN2101IND). The
# exact catalog model is always tried first; these variants are only attempted
# when it returns no release, so devices that resolve directly cost no extra
# upstream requests.
REGION_MODEL_VARIANT_SUFFIXES: dict[str, tuple[str, ...]] = {
    "1B": ("IN", "IND", "_IND", "_IN"),
    "44": ("EEA", "EUEX"),
}
OPLUS_CN_COST_AUTO_PREFIX = "gauss-compotacostauto-cn."
OPLUS_CN_COST_MANUAL_PREFIX = "gauss-componentotacostmanual-cn."
DISPLAY_VERSION_PATTERN = re.compile(r"\b(\d{1,2}\.\d+\.\d+\.\d{3})(?:Patch\d+)?\b")
OTA_TIMESTAMP_PATTERN = re.compile(r"_(\d{12})$")
ABOUT_UPDATE_DATE_PATTERN = re.compile(r"/(?:component-ota|ota)/(\d{2})/(\d{2})/(\d{2})/")


@dataclass(frozen=True)
class AboutUpdateMetadata:
    display_version_name: str | None = None
    published_at: datetime | None = None


class RealmeOtaProvider(OtaProvider):
    """Live adapter around the GPLv3 realme-ota request/encryption implementation."""

    def __init__(
        self,
        settings: Settings,
        *,
        request_cls: type[Any] | None = None,
        post: Callable[..., Any] | None = None,
        get: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings
        self._post = post or httpx.post
        self._get = get or httpx.get
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
        # query() guarantees this is set, but mypy needs the narrowing here.
        if self._request_cls is None:  # pragma: no cover - defensive guard
            raise OtaProviderUnavailableError("realme-ota is not importable in this environment")
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
            about_update_url = _find_string(content, "panelUrl")
            real_version_name = _find_display_version_name(content, real_ota_version)
            about_metadata = AboutUpdateMetadata(
                published_at=_infer_published_at(
                    about_update_url=about_update_url,
                    real_ota_version=real_ota_version,
                )
            )
            if not real_version_name and about_update_url:
                about_metadata = self._fetch_about_update_metadata(
                    about_update_url=about_update_url,
                    product_model=request.product_model,
                    region_label=region_label,
                    fallback_published_at=about_metadata.published_at,
                )
                real_version_name = about_metadata.display_version_name
            real_version_name = real_version_name or real_ota_version

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
                about_update_url=about_update_url,
                download_url=_normalize_download_url(download_url),
                md5=_find_string(content, "md5"),
                file_size=_find_int(content, "size"),
                security_patch=_find_string(content, "securityPatch"),
                raw_response=content if self._settings.enable_raw_response else None,
                region_code=region_label,
                published_at=about_metadata.published_at,
            )

        if found_no_release:
            raise OtaNotFoundError("OTA endpoint returned no release")
        raise OtaProviderUnavailableError(
            "OTA endpoint returned an error response"
        ) from last_validation_error

    def _fetch_about_update_metadata(
        self,
        *,
        about_update_url: str,
        product_model: str,
        region_label: str,
        fallback_published_at: datetime | None,
    ) -> AboutUpdateMetadata:
        try:
            response = self._get(
                about_update_url,
                timeout=min(self._settings.realme_ota_timeout_seconds, 10),
            )
        except Exception:
            return AboutUpdateMetadata(published_at=fallback_published_at)
        status_code = getattr(response, "status_code", 0)
        if not (200 <= status_code < 300):
            return AboutUpdateMetadata(published_at=fallback_published_at)
        body = str(getattr(response, "text", "") or "")
        display_version_name = _display_version_name_from_update_notes(
            body,
            product_model=product_model,
            region_label=region_label,
        )
        return AboutUpdateMetadata(
            display_version_name=display_version_name,
            published_at=fallback_published_at,
        )


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

    candidates: list[str] = [normalized_model]
    for suffix in REGION_MODEL_VARIANT_SUFFIXES.get(normalized_manifest, ()):
        if not normalized_model.endswith(suffix):
            candidates.append(f"{normalized_model}{suffix}")

    base_model = derive_ota_model(normalized_model)
    if base_model != normalized_model:
        candidates.append(base_model)

    return tuple(dict.fromkeys(candidates))


def _walk(value: Any) -> Iterator[tuple[Any, Any]]:
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
    for key in (
        "manualUrl",
        "manual_url",
        "downloadCheck",
        "download_check",
        "downloadUrl",
        "download_url",
        "otaUrl",
        "ota_url",
        "url",
    ):
        value = _find_string(content, key)
        if value and value.startswith(("https://", "http://")):
            return value
    for _key, value in _walk(content):
        if isinstance(value, str) and value.startswith(("https://", "http://")) and ".zip" in value:
            return value
    return None


def _find_display_version_name(content: dict[str, Any], real_ota_version: str) -> str | None:
    for key in (
        "realVersionName",
        "versionName",
        "version_name",
        "displayVersion",
        "display_version",
    ):
        value = _find_string(content, key)
        if value and not _is_technical_ota_version(value, real_ota_version):
            return value
    return None


def _is_technical_ota_version(value: str, real_ota_version: str) -> bool:
    normalized = value.strip()
    if normalized == real_ota_version:
        return True
    return bool(re.search(r"_[0-9]{2}\.[ACFH]\.[0-9]+_[0-9]{4}_[0-9]{12}$", normalized))


def _display_version_name_from_update_notes(
    body: str,
    *,
    product_model: str,
    region_label: str,
) -> str | None:
    match = DISPLAY_VERSION_PATTERN.search(body)
    if not match:
        return None
    suffix = _display_region_suffix(region_label)
    model = derive_ota_model(product_model)
    display_version = match.group(1)
    return f"{model}_{display_version}({suffix})" if suffix else f"{model}_{display_version}"


def _display_region_suffix(region_label: str) -> str | None:
    if region_label == "CN":
        return "CN01"
    return None


def _infer_published_at(
    *,
    about_update_url: str | None,
    real_ota_version: str,
) -> datetime | None:
    if about_update_url:
        match = ABOUT_UPDATE_DATE_PATTERN.search(urlsplit(about_update_url).path)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return datetime(2000 + year, month, day, tzinfo=UTC)
            except ValueError:
                pass
    match = OTA_TIMESTAMP_PATTERN.search(real_ota_version)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M").replace(tzinfo=UTC)
    except ValueError:
        return None


def _normalize_download_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    if hostname.startswith(OPLUS_CN_COST_AUTO_PREFIX):
        hostname = OPLUS_CN_COST_MANUAL_PREFIX + hostname.removeprefix(OPLUS_CN_COST_AUTO_PREFIX)
    elif not hostname.startswith(OPLUS_CN_COST_MANUAL_PREFIX):
        hostname = hostname.replace("componentotacostmanual", "opexcostmanual")
    netloc = hostname + (f":{parsed.port}" if parsed.port else "")
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))


def _computed_ota_version(product_model: str, region_label: str, real_ota_version: str) -> str:
    match = re.search(r"_11\.([A-Z]\.[0-9]+).*_([0-9]{12})$", real_ota_version)
    if match:
        return (
            f"{derive_ota_model(product_model)}_11.{match.group(1)}_{region_label}_{match.group(2)}"
        )
    return f"{product_model}_{region_label}_{real_ota_version}"
