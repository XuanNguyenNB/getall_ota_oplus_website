from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ota_backend.domain.models import Device, EdlRom, Release, ScanRun
from ota_backend.domain.ota import DEFAULT_RUI_CANDIDATES

if TYPE_CHECKING:
    from ota_backend.services.scan_management import ScanGroup


class DeviceOut(BaseModel):
    id: UUID
    catalog_id: int | None
    brand: str
    name: str
    product_model: str
    manifest_code: str | None
    scan_enabled: bool
    active_track: str
    catalog_visible: bool
    scan_group_key: str
    scan_group_name: str
    scan_eligibility: str
    consecutive_failures: int
    last_scan_error_code: str | None
    last_scan_error_message: str | None
    last_scan_failed_at: datetime | None

    @classmethod
    def from_domain(cls, device: Device) -> DeviceOut:
        return cls(**device.__dict__)


class ReleaseOut(BaseModel):
    id: UUID
    brand: str
    product_model: str
    manifest_code: str
    ota_track: str
    rui_version: int
    real_version_name: str
    real_ota_version: str
    computed_ota_version: str
    version_type_id: str
    about_update_url: str | None
    download_url: str
    security_patch: str | None
    discovered_at: datetime
    last_seen_at: datetime
    source: str
    region_code: str | None
    release_type: str
    published_at: datetime | None

    @classmethod
    def from_domain(cls, release: Release) -> ReleaseOut:
        return cls(
            id=release.id,
            brand=release.brand,
            product_model=release.product_model,
            manifest_code=release.manifest_code,
            ota_track=release.ota_track,
            rui_version=release.rui_version,
            real_version_name=release.real_version_name,
            real_ota_version=release.real_ota_version,
            computed_ota_version=release.computed_ota_version,
            version_type_id=release.version_type_id,
            about_update_url=release.about_update_url,
            download_url=release.download_url,
            security_patch=release.security_patch,
            discovered_at=release.discovered_at,
            last_seen_at=release.last_seen_at,
            source=release.source,
            region_code=release.region_code,
            release_type=release.release_type,
            published_at=release.published_at,
        )


class EdlRomOut(BaseModel):
    id: UUID
    brand: str
    product_model: str
    device_name: str | None
    region_code: str | None
    version_name: str
    build_date: datetime | None
    download_url: str
    source: str
    source_updated_at: datetime | None

    @classmethod
    def from_domain(cls, rom: EdlRom) -> EdlRomOut:
        return cls(
            id=rom.id,
            brand=rom.brand,
            product_model=rom.product_model,
            device_name=rom.device_name,
            region_code=rom.region_code,
            version_name=rom.version_name,
            build_date=rom.build_date,
            download_url=rom.download_url,
            source=rom.source,
            source_updated_at=rom.source_updated_at,
        )


class OtaRequestIn(BaseModel):
    """Internal/operator OTA query payload.

    Accepts the full input set (beta, imei0/imei1, guid) because the operator
    runtime is allowed to issue authenticated/identified queries. Public
    callers must use :class:`PublicOtaRequestIn`, which strips sensitive
    inputs at the schema layer.
    """

    product_model: str = Field(min_length=3, max_length=40)
    manifest_code: str = Field(min_length=2, max_length=2)
    ota_track: str = Field(min_length=1, max_length=1)
    rui_candidates: list[int] = Field(default_factory=lambda: list(DEFAULT_RUI_CANDIDATES))
    language: str = "en-EN"
    beta: bool = False
    imei0: str | None = None
    imei1: str | None = None
    guid: str | None = None
    persist_result: bool = True

    @field_validator("rui_candidates")
    @classmethod
    def _check_rui_candidates(cls, value: list[int]) -> list[int]:
        if len(value) == 0:
            raise ValueError("rui_candidates must not be empty")
        if len(value) > 5:
            raise ValueError("rui_candidates must contain at most 5 entries")
        for candidate in value:
            if not isinstance(candidate, int) or isinstance(candidate, bool):
                raise ValueError("rui_candidates entries must be integers")
            if candidate < 1 or candidate > 9:
                raise ValueError("rui_candidates entries must be between 1 and 9")
        return value


class PublicOtaRequestIn(BaseModel):
    """Public-facing OTA query payload.

    The public contract accepts the same shape as the internal model so that
    callers may pass ``beta=False`` and ``imei0/imei1/guid=None`` placeholders
    without a 422, but truthy values for operator-only fields are refused
    with a 400 VALIDATION_ERROR in the route. The schema layer enforces the
    ``rui_candidates`` integer bounds so an attacker cannot submit values
    that bypass the manifest map's expected 1-9 range.
    """

    product_model: str = Field(min_length=3, max_length=40)
    manifest_code: str = Field(min_length=2, max_length=2)
    ota_track: str = Field(min_length=1, max_length=1)
    rui_candidates: list[int] = Field(default_factory=lambda: list(DEFAULT_RUI_CANDIDATES))
    language: str = "en-EN"
    beta: bool = False
    imei0: str | None = None
    imei1: str | None = None
    guid: str | None = None
    persist_result: bool = True

    @field_validator("rui_candidates")
    @classmethod
    def _check_rui_candidates(cls, value: list[int]) -> list[int]:
        if len(value) == 0:
            raise ValueError("rui_candidates must not be empty")
        if len(value) > 5:
            raise ValueError("rui_candidates must contain at most 5 entries")
        for candidate in value:
            if not isinstance(candidate, int) or isinstance(candidate, bool):
                raise ValueError("rui_candidates entries must be integers")
            if candidate < 1 or candidate > 9:
                raise ValueError("rui_candidates entries must be between 1 and 9")
        return value

    def has_sensitive_inputs(self) -> bool:
        """Whether the caller supplied operator-only fields.

        Public callers should pass ``False/None`` for these placeholders; any
        truthy value indicates the caller is trying to use the public surface
        for identified queries, which is not supported.
        """

        return bool(self.beta or self.imei0 or self.imei1 or self.guid)

    def to_internal(self) -> OtaRequestIn:
        """Lift a public payload into the internal model with safe defaults."""

        return OtaRequestIn(
            product_model=self.product_model,
            manifest_code=self.manifest_code,
            ota_track=self.ota_track,
            rui_candidates=list(self.rui_candidates),
            language=self.language,
            beta=False,
            imei0=None,
            imei1=None,
            guid=None,
            persist_result=self.persist_result,
        )


class OtaResultOut(BaseModel):
    release_id: UUID
    brand: str
    product_model: str
    manifest_code: str
    ota_track: str
    rui_version: int
    real_ota_version: str
    real_version_name: str
    computed_ota_version: str
    version_type_id: str
    about_update_url: str | None
    download_url: str
    is_new: bool

    @classmethod
    def from_domain(cls, release: Release, *, is_new: bool) -> OtaResultOut:
        return cls(
            release_id=release.id,
            brand=release.brand,
            product_model=release.product_model,
            manifest_code=release.manifest_code,
            ota_track=release.ota_track,
            rui_version=release.rui_version,
            real_ota_version=release.real_ota_version,
            real_version_name=release.real_version_name,
            computed_ota_version=release.computed_ota_version,
            version_type_id=release.version_type_id,
            about_update_url=release.about_update_url,
            download_url=release.download_url,
            is_new=is_new,
        )


class AdminScanEnqueueIn(BaseModel):
    product_models: list[str] = Field(min_length=1, max_length=100)
    reason: str = Field(default="manual", min_length=1, max_length=80)


class ScanVariantOut(BaseModel):
    product_model: str
    manifest_code: str | None
    name: str
    scan_enabled: bool


class ScanGroupOut(BaseModel):
    key: str
    name: str
    brand: str
    enabled_count: int
    variant_count: int
    variants: list[ScanVariantOut]

    @classmethod
    def from_domain(cls, group: ScanGroup) -> ScanGroupOut:
        return cls(
            key=group.key,
            name=group.name,
            brand=group.brand,
            enabled_count=group.enabled_count,
            variant_count=len(group.variants),
            variants=[
                ScanVariantOut(
                    product_model=variant.product_model,
                    manifest_code=variant.manifest_code,
                    name=variant.name,
                    scan_enabled=variant.scan_enabled,
                )
                for variant in group.variants
            ],
        )


class ScanToggleModelsIn(BaseModel):
    product_models: list[str] = Field(min_length=1, max_length=200)
    enabled: bool


class ScanToggleGroupIn(BaseModel):
    scan_group_key: str = Field(min_length=1, max_length=200)
    enabled: bool


class ScanDisableAllIn(BaseModel):
    confirm: bool = False


class ResolveRequestIn(BaseModel):
    url: str = Field(min_length=10, max_length=4096)
    source: str = Field(default="web", pattern="^web$")


class ScanStatusRunOut(BaseModel):
    id: UUID
    status: str
    cycle_day: int
    started_at: datetime
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int

    @classmethod
    def from_domain(cls, run: ScanRun) -> ScanStatusRunOut:
        pending_tasks = max(
            run.total_tasks - run.completed_tasks - run.failed_tasks,
            0,
        )
        return cls(
            id=run.id,
            status=run.status,
            cycle_day=run.cycle_day,
            started_at=run.started_at,
            completed_tasks=run.completed_tasks,
            failed_tasks=run.failed_tasks,
            pending_tasks=pending_tasks,
        )
