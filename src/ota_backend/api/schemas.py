from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ota_backend.domain.models import Device, Release
from ota_backend.domain.models import ScanRun
from ota_backend.domain.ota import DEFAULT_RUI_CANDIDATES


class DeviceOut(BaseModel):
    id: UUID
    catalog_id: int | None
    brand: str
    name: str
    product_model: str
    manifest_code: str | None
    scan_enabled: bool
    active_track: str

    @classmethod
    def from_domain(cls, device: Device) -> "DeviceOut":
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
    def from_domain(cls, release: Release) -> "ReleaseOut":
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


class OtaRequestIn(BaseModel):
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
    def from_domain(cls, release: Release, *, is_new: bool) -> "OtaResultOut":
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
    def from_domain(cls, run: ScanRun) -> "ScanStatusRunOut":
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
