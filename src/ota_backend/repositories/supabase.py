from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from ota_backend.config import Settings
from ota_backend.domain.models import (
    Brand,
    CatalogDeviceCandidate,
    Device,
    DeviceCatalogImport,
    OtaProviderRelease,
    OtaTrack,
    Page,
    PersistedRelease,
    PublicActionDecision,
    Release,
    ResolveRequest,
    ScanRun,
    ScanTask,
    TelegramDelivery,
    TelegramNotification,
    TelegramTarget,
)


def create_supabase_client(settings: Settings) -> Any:
    if not settings.supabase_url or not settings.supabase_server_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY "
            "are required when REPOSITORY_BACKEND=supabase"
        )
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - depends on installed runtime
        raise RuntimeError("Install the supabase runtime dependency before using Supabase") from exc
    return create_client(settings.supabase_url, settings.supabase_server_key)


def _should_refresh_release_metadata(
    existing: Release,
    release: OtaProviderRelease,
) -> bool:
    return (
        existing.real_version_name == existing.real_ota_version
        and release.real_version_name != release.real_ota_version
    ) or (
        existing.published_at is None
        and release.published_at is not None
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _payload(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else {}
    return data if isinstance(data, dict) else {}


def _looks_like_missing_archive_metadata(exc: Exception) -> bool:
    message = str(exc)
    return any(
        marker in message
        for marker in (
            "published_at",
            "region_code",
            "release_type",
            "p_source",
            "p_region_code",
            "PGRST202",
            "42703",
        )
    )


def _datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime) or value is None:
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _device(row: dict[str, Any]) -> Device:
    return Device(
        id=UUID(str(row["id"])),
        catalog_id=row.get("catalog_id"),
        brand=row["brand"],
        name=row["name"],
        product_model=row["product_model"],
        manifest_code=row.get("manifest_code"),
        scan_enabled=bool(row.get("scan_enabled", True)),
        active_track=row.get("active_track", "C"),
        bootstrap_done=bool(row.get("bootstrap_done", False)),
        manual_override=bool(row.get("manual_override", False)),
        source=row.get("source", "manual"),
    )


def _release(row: dict[str, Any]) -> Release:
    return Release(
        id=UUID(str(row["id"])),
        brand=row["brand"],
        product_model=row["product_model"],
        manifest_code=row["manifest_code"],
        ota_track=row["ota_track"],
        rui_version=int(row["rui_version"]),
        real_ota_version=row["real_ota_version"],
        real_version_name=row["real_version_name"],
        computed_ota_version=row["computed_ota_version"],
        version_type_id=row["version_type_id"],
        about_update_url=row.get("about_update_url"),
        download_url=row["download_url"],
        discovered_by=row["discovered_by"],
        discovered_at=_datetime(row["discovered_at"]),  # type: ignore[arg-type]
        last_seen_at=_datetime(row["last_seen_at"]),  # type: ignore[arg-type]
        md5=row.get("md5"),
        file_size=row.get("file_size"),
        security_patch=row.get("security_patch"),
        raw_response=row.get("raw_response"),
        source=row.get("source", "live_provider"),
        region_code=row.get("region_code"),
        release_type=row.get("release_type", "official"),
        published_at=_datetime(row.get("published_at")),
        source_last_event_kind=row.get("source_last_event_kind"),
        source_last_event_at=_datetime(row.get("source_last_event_at")),
    )


def _scan_run(row: dict[str, Any]) -> ScanRun:
    return ScanRun(
        id=UUID(str(row["id"])),
        status=row["status"],
        cycle_day=int(row["cycle_day"]),
        started_at=_datetime(row["started_at"]),  # type: ignore[arg-type]
        finished_at=_datetime(row.get("finished_at")),
        total_tasks=int(row.get("total_tasks", 0)),
        completed_tasks=int(row.get("completed_tasks", 0)),
        failed_tasks=int(row.get("failed_tasks", 0)),
        new_releases=int(row.get("new_releases", 0)),
        error_message=row.get("error_message"),
    )


def _scan_task(row: dict[str, Any]) -> ScanTask:
    return ScanTask(
        id=UUID(str(row["id"])),
        scan_run_id=UUID(str(row["scan_run_id"])),
        device_id=UUID(str(row["device_id"])),
        status=row["status"],
        attempt_count=int(row.get("attempt_count", 0)),
        tracks_checked=list(row.get("tracks_checked") or []),
        rui_candidates_checked=list(row.get("rui_candidates_checked") or []),
        found_release_id=UUID(str(row["found_release_id"])) if row.get("found_release_id") else None,
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        started_at=_datetime(row.get("started_at")),
        finished_at=_datetime(row.get("finished_at")),
    )


def _telegram_target(row: dict[str, Any]) -> TelegramTarget:
    return TelegramTarget(
        id=UUID(str(row["id"])),
        brand=row["brand"],
        chat_id=int(row["chat_id"]),
        message_thread_id=int(row["message_thread_id"]),
        enabled=bool(row.get("enabled", True)),
        created_at=_datetime(row["created_at"]),  # type: ignore[arg-type]
        updated_at=_datetime(row["updated_at"]),  # type: ignore[arg-type]
    )


def _telegram_notification(row: dict[str, Any]) -> TelegramNotification:
    return TelegramNotification(
        id=UUID(str(row["id"])),
        release_id=UUID(str(row["release_id"])),
        telegram_target_id=UUID(str(row["telegram_target_id"])),
        status=row["status"],
        created_at=_datetime(row["created_at"]),  # type: ignore[arg-type]
        telegram_message_id=row.get("telegram_message_id"),
        error_message=row.get("error_message"),
        sent_at=_datetime(row.get("sent_at")),
        attempt_count=int(row.get("attempt_count", 0)),
        last_attempt_at=_datetime(row.get("last_attempt_at")),
        next_attempt_at=_datetime(row.get("next_attempt_at")),
    )


def _resolve_request(row: dict[str, Any]) -> ResolveRequest:
    return ResolveRequest(
        id=UUID(str(row["id"])),
        source=row["source"],
        status=row["status"],
        created_at=_datetime(row["created_at"]),  # type: ignore[arg-type]
        input_url=row.get("input_url"),
        resolved_url=row.get("resolved_url"),
        telegram_user_id=row.get("telegram_user_id"),
        telegram_chat_id=row.get("telegram_chat_id"),
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        expires_at=_datetime(row.get("expires_at")),
    )


class SupabaseDeviceRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def list_devices(
        self,
        *,
        q: str | None,
        brand: str | None,
        enabled_only: bool,
        limit: int,
        offset: int,
    ) -> Page[Device]:
        query = self._client.table("devices").select("*", count="exact")
        if enabled_only:
            query = query.eq("scan_enabled", True)
        if brand:
            query = query.eq("brand", brand)
        if q:
            needle = re.sub(r"[^A-Za-z0-9 _+.-]", "", q).strip()
            if needle:
                query = query.or_(f"name.ilike.%{needle}%,product_model.ilike.%{needle}%")
        response = query.order("name").range(offset, offset + limit - 1).execute()
        items = [_device(row) for row in _rows(response)]
        total = getattr(response, "count", None)
        return Page(items=items, total=total if total is not None else len(items), limit=limit, offset=offset)

    def get_by_product_model(self, product_model: str) -> Device | None:
        response = (
            self._client.table("devices")
            .select("*")
            .eq("product_model", product_model.upper())
            .limit(1)
            .execute()
        )
        rows = _rows(response)
        return _device(rows[0]) if rows else None

    def get_by_id(self, device_id: UUID) -> Device | None:
        response = self._client.table("devices").select("*").eq("id", str(device_id)).limit(1).execute()
        rows = _rows(response)
        return _device(rows[0]) if rows else None

    def update_scan_state(
        self,
        device_id: UUID,
        *,
        active_track: OtaTrack,
        bootstrap_done: bool,
    ) -> Device:
        response = (
            self._client.table("devices")
            .update({"active_track": active_track, "bootstrap_done": bootstrap_done})
            .eq("id", str(device_id))
            .execute()
        )
        rows = _rows(response)
        if not rows:
            raise KeyError(f"device not found: {device_id}")
        return _device(rows[0])

    def upsert_catalog_device(
        self,
        *,
        catalog_id: int | None,
        brand: Brand,
        name: str,
        product_model: str,
        manifest_code: str | None,
        scan_enabled: bool,
        source: str = "oxygen_updater",
    ) -> Device:
        existing = self.get_by_product_model(product_model)
        if existing is not None and existing.manual_override:
            return existing
        payload = {
            "catalog_id": catalog_id,
            "brand": brand,
            "name": name,
            "product_model": product_model,
            "manifest_code": manifest_code,
            "scan_enabled": scan_enabled,
            "source": source,
        }
        if existing is not None:
            response = (
                self._client.table("devices")
                .update(payload)
                .eq("id", str(existing.id))
                .execute()
            )
        else:
            response = self._client.table("devices").insert(payload).execute()
        rows = _rows(response)
        if not rows:
            raise RuntimeError("catalog device write returned no row")
        return _device(rows[0])

    def upsert_catalog_devices(self, devices: list[CatalogDeviceCandidate]) -> int:
        manual_rows = _rows(
            self._client.table("devices")
            .select("product_model")
            .eq("manual_override", True)
            .execute()
        )
        manual_models = {str(row["product_model"]).upper() for row in manual_rows}
        payloads = [
            {
                "catalog_id": device.catalog_id,
                "brand": device.brand,
                "name": device.name,
                "product_model": device.product_model,
                "manifest_code": device.manifest_code,
                "scan_enabled": device.scan_enabled,
                "source": device.source,
            }
            for device in devices
            if device.product_model.upper() not in manual_models
        ]
        for offset in range(0, len(payloads), 200):
            self._client.table("devices").upsert(
                payloads[offset : offset + 200], on_conflict="product_model"
            ).execute()
        return len(devices)


class SupabaseReleaseRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def list_releases(
        self,
        *,
        q: str | None = None,
        brand: str | None = None,
        product_model: str | None = None,
        manifest_code: str | None = None,
        region_code: str | None = None,
        release_type: str | None = None,
        source: str | None = None,
        sort: str = "discovered",
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Release]:
        query = self._client.table("ota_releases").select("*", count="exact")
        if brand:
            query = query.eq("brand", brand)
        if product_model:
            query = query.eq("product_model", product_model.upper())
        if manifest_code:
            query = query.eq("manifest_code", manifest_code.upper())
        if region_code:
            query = query.eq("region_code", region_code.upper())
        if release_type:
            query = query.eq("release_type", release_type.lower())
        if source:
            query = query.eq("source", source)
        if q:
            needle = re.sub(r"[^A-Za-z0-9 _+.-]", "", q).strip()
            if needle:
                query = query.or_(
                    f"product_model.ilike.%{needle}%,real_version_name.ilike.%{needle}%,real_ota_version.ilike.%{needle}%"
                )
        if sort == "published":
            query = query.order(
                "published_at",
                desc=True,
                nullsfirst=False,
            ).order("discovered_at", desc=True)
        else:
            query = query.order("discovered_at", desc=True)
        try:
            response = query.range(offset, offset + limit - 1).execute()
        except Exception as exc:
            if not _looks_like_missing_archive_metadata(exc):
                raise
            query = self._client.table("ota_releases").select("*", count="exact")
            if brand:
                query = query.eq("brand", brand)
            if product_model:
                query = query.eq("product_model", product_model.upper())
            if manifest_code:
                query = query.eq("manifest_code", manifest_code.upper())
            if q:
                needle = re.sub(r"[^A-Za-z0-9 _+.-]", "", q).strip()
                if needle:
                    query = query.or_(
                        f"product_model.ilike.%{needle}%,real_version_name.ilike.%{needle}%,real_ota_version.ilike.%{needle}%"
                    )
            response = query.order("discovered_at", desc=True).range(offset, offset + limit - 1).execute()
        items = [_release(row) for row in _rows(response)]
        total = getattr(response, "count", None)
        return Page(items=items, total=total if total is not None else len(items), limit=limit, offset=offset)

    def upsert_release(
        self,
        release: OtaProviderRelease,
        *,
        discovered_by: str,
    ) -> PersistedRelease:
        payload = {
            "p_brand": release.brand,
            "p_product_model": release.product_model,
            "p_manifest_code": release.manifest_code,
            "p_ota_track": release.ota_track,
            "p_rui_version": release.rui_version,
            "p_real_ota_version": release.real_ota_version,
            "p_real_version_name": release.real_version_name,
            "p_computed_ota_version": release.computed_ota_version,
            "p_version_type_id": release.version_type_id,
            "p_about_update_url": release.about_update_url,
            "p_download_url": release.download_url,
            "p_md5": release.md5,
            "p_file_size": release.file_size,
            "p_security_patch": release.security_patch,
            "p_raw_response": release.raw_response,
            "p_discovered_by": discovered_by,
            "p_source": release.source,
            "p_region_code": release.region_code,
            "p_release_type": release.release_type,
            "p_published_at": release.published_at.isoformat() if release.published_at else None,
            "p_source_last_event_kind": release.source_last_event_kind,
            "p_source_last_event_at": (
                release.source_last_event_at.isoformat()
                if release.source_last_event_at
                else None
            ),
        }
        try:
            result = _payload(self._client.rpc("upsert_ota_release", payload).execute())
        except Exception as exc:
            if release.source != "live_provider" or not _looks_like_missing_archive_metadata(exc):
                raise
            legacy_payload = {
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "p_source",
                    "p_region_code",
                    "p_release_type",
                    "p_published_at",
                    "p_source_last_event_kind",
                    "p_source_last_event_at",
                }
            }
            result = _payload(self._client.rpc("upsert_ota_release", legacy_payload).execute())
        persisted = _release(result["release"])
        is_new = bool(result["is_new"])
        if not is_new and _should_refresh_release_metadata(persisted, release):
            persisted = self._refresh_release_metadata(persisted, release)
        return PersistedRelease(release=persisted, is_new=is_new)

    def _refresh_release_metadata(
        self,
        existing: Release,
        release: OtaProviderRelease,
    ) -> Release:
        payload = {
            "real_version_name": release.real_version_name,
            "about_update_url": release.about_update_url or existing.about_update_url,
            "published_at": (
                release.published_at.isoformat()
                if release.published_at
                else existing.published_at.isoformat()
                if existing.published_at
                else None
            ),
            "region_code": release.region_code or existing.region_code,
        }
        response = (
            self._client.table("ota_releases")
            .update(payload)
            .eq("id", str(existing.id))
            .execute()
        )
        rows = _rows(response)
        return _release(rows[0]) if rows else existing

    def get_by_id(self, release_id: UUID) -> Release | None:
        response = self._client.table("ota_releases").select("*").eq("id", str(release_id)).limit(1).execute()
        rows = _rows(response)
        return _release(rows[0]) if rows else None


class SupabaseScanRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_run(
        self, *, cycle_day: int, total_tasks: int, status: str = "running"
    ) -> ScanRun:
        response = (
            self._client.table("scan_runs")
            .insert({"status": status, "cycle_day": cycle_day, "total_tasks": total_tasks})
            .execute()
        )
        return _scan_run(_rows(response)[0])

    def create_task(self, *, scan_run_id: UUID, device_id: UUID) -> ScanTask:
        response = (
            self._client.table("scan_tasks")
            .upsert(
                {"scan_run_id": str(scan_run_id), "device_id": str(device_id), "status": "queued"},
                on_conflict="scan_run_id,device_id",
            )
            .execute()
        )
        return _scan_task(_rows(response)[0])

    def list_tasks(self, scan_run_id: UUID) -> list[ScanTask]:
        response = self._client.table("scan_tasks").select("*").eq("scan_run_id", str(scan_run_id)).execute()
        return [_scan_task(row) for row in _rows(response)]

    def start_run(self, scan_run_id: UUID) -> ScanRun:
        response = (
            self._client.table("scan_runs")
            .update({"status": "running", "finished_at": None, "error_message": None})
            .eq("id", str(scan_run_id))
            .execute()
        )
        return _scan_run(_rows(response)[0])

    def claim_next_queued_task(self, scan_run_id: UUID) -> ScanTask | None:
        response = self._client.rpc("claim_scan_task", {"p_scan_run_id": str(scan_run_id)}).execute()
        rows = _rows(response)
        return _scan_task(rows[0]) if rows else None

    def complete_task(
        self,
        task_id: UUID,
        *,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
        found_release_id: UUID | None,
        new_release: bool,
    ) -> ScanTask:
        response = self._client.rpc(
            "complete_scan_task",
            {
                "p_task_id": str(task_id),
                "p_tracks_checked": tracks_checked,
                "p_rui_candidates_checked": rui_candidates_checked,
                "p_found_release_id": str(found_release_id) if found_release_id else None,
                "p_new_release": new_release,
            },
        ).execute()
        return _scan_task(_rows(response)[0])

    def fail_task(
        self,
        task_id: UUID,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
        max_attempts: int,
        tracks_checked: list[OtaTrack],
        rui_candidates_checked: list[int],
    ) -> ScanTask:
        task = self._get_task(task_id)
        should_retry = retryable and task.attempt_count < max_attempts
        response = (
            self._client.table("scan_tasks")
            .update(
                {
                    "status": "queued" if should_retry else "failed",
                    "tracks_checked": tracks_checked,
                    "rui_candidates_checked": rui_candidates_checked,
                    "error_code": error_code,
                    "error_message": error_message,
                    "finished_at": None if should_retry else datetime.now().astimezone().isoformat(),
                }
            )
            .eq("id", str(task_id))
            .execute()
        )
        return _scan_task(_rows(response)[0])

    def finish_run(self, scan_run_id: UUID, *, status: str, error_message: str | None = None) -> ScanRun:
        tasks = self.list_tasks(scan_run_id)
        response = (
            self._client.table("scan_runs")
            .update(
                {
                    "status": status,
                    "completed_tasks": sum(task.status == "completed" for task in tasks),
                    "failed_tasks": sum(task.status == "failed" for task in tasks),
                    "finished_at": datetime.now().astimezone().isoformat(),
                    "error_message": error_message,
                }
            )
            .eq("id", str(scan_run_id))
            .execute()
        )
        return _scan_run(_rows(response)[0])

    def latest_run(self) -> ScanRun | None:
        response = self._client.table("scan_runs").select("*").order("started_at", desc=True).limit(1).execute()
        rows = _rows(response)
        return _scan_run(rows[0]) if rows else None

    def _get_task(self, task_id: UUID) -> ScanTask:
        response = self._client.table("scan_tasks").select("*").eq("id", str(task_id)).limit(1).execute()
        rows = _rows(response)
        if not rows:
            raise KeyError(f"scan task not found: {task_id}")
        return _scan_task(rows[0])

    def _get_run(self, scan_run_id: UUID) -> ScanRun:
        response = self._client.table("scan_runs").select("*").eq("id", str(scan_run_id)).limit(1).execute()
        rows = _rows(response)
        if not rows:
            raise KeyError(f"scan run not found: {scan_run_id}")
        return _scan_run(rows[0])


class SupabaseTelegramRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def get_target_for_brand(self, brand: Brand) -> TelegramTarget | None:
        response = (
            self._client.table("telegram_targets")
            .select("*")
            .eq("brand", brand)
            .eq("enabled", True)
            .limit(1)
            .execute()
        )
        rows = _rows(response)
        return _telegram_target(rows[0]) if rows else None

    def enqueue_notification(
        self,
        *,
        release: Release,
        target: TelegramTarget,
    ) -> tuple[TelegramNotification, bool]:
        result = _payload(
            self._client.rpc(
                "enqueue_telegram_notification",
                {"p_release_id": str(release.id), "p_telegram_target_id": str(target.id)},
            ).execute()
        )
        return _telegram_notification(result["notification"]), bool(result["is_new"])

    def claim_next_notification(self, *, max_attempts: int) -> TelegramDelivery | None:
        result = _payload(
            self._client.rpc(
                "claim_telegram_notification",
                {"p_max_attempts": max_attempts},
            ).execute()
        )
        if not result:
            return None
        return TelegramDelivery(
            notification=_telegram_notification(result["notification"]),
            release=_release(result["release"]),
            target=_telegram_target(result["target"]),
        )

    def mark_notification_sent(
        self, notification_id: UUID, *, telegram_message_id: int
    ) -> TelegramNotification:
        rows = _rows(
            self._client.rpc(
                "complete_telegram_notification",
                {
                    "p_notification_id": str(notification_id),
                    "p_telegram_message_id": telegram_message_id,
                },
            ).execute()
        )
        return _telegram_notification(rows[0])

    def mark_notification_failed(
        self, notification_id: UUID, *, error_message: str, retry_seconds: int
    ) -> TelegramNotification:
        rows = _rows(
            self._client.rpc(
                "fail_telegram_notification",
                {
                    "p_notification_id": str(notification_id),
                    "p_error_message": error_message,
                    "p_retry_seconds": retry_seconds,
                },
            ).execute()
        )
        return _telegram_notification(rows[0])


class SupabaseCatalogImportRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def start_import(self, *, source: str) -> DeviceCatalogImport:
        response = self._client.table("device_catalog_imports").insert({"source": source, "status": "running"}).execute()
        return self._from_row(_rows(response)[0])

    def complete_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        upserted_count: int,
        disabled_count: int,
    ) -> DeviceCatalogImport:
        return self._update(
            import_id,
            {
                "status": "completed",
                "fetched_count": fetched_count,
                "upserted_count": upserted_count,
                "disabled_count": disabled_count,
                "finished_at": datetime.now().astimezone().isoformat(),
            },
        )

    def fail_import(
        self,
        import_id: UUID,
        *,
        fetched_count: int,
        disabled_count: int,
        error_message: str,
    ) -> DeviceCatalogImport:
        return self._update(
            import_id,
            {
                "status": "failed",
                "fetched_count": fetched_count,
                "disabled_count": disabled_count,
                "error_message": error_message,
                "finished_at": datetime.now().astimezone().isoformat(),
            },
        )

    def _update(self, import_id: UUID, payload: dict[str, Any]) -> DeviceCatalogImport:
        response = self._client.table("device_catalog_imports").update(payload).eq("id", str(import_id)).execute()
        return self._from_row(_rows(response)[0])

    @staticmethod
    def _from_row(row: dict[str, Any]) -> DeviceCatalogImport:
        return DeviceCatalogImport(
            id=UUID(str(row["id"])),
            source=row["source"],
            status=row["status"],
            started_at=_datetime(row["started_at"]),  # type: ignore[arg-type]
            fetched_count=int(row.get("fetched_count", 0)),
            upserted_count=int(row.get("upserted_count", 0)),
            disabled_count=int(row.get("disabled_count", 0)),
            error_message=row.get("error_message"),
            finished_at=_datetime(row.get("finished_at")),
        )


class SupabasePublicActionRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def claim(
        self,
        *,
        action: str,
        actor_hash: str,
        query_key: str,
        limit: int,
        window_seconds: int,
        cooldown_seconds: int,
    ) -> PublicActionDecision:
        result = _payload(
            self._client.rpc(
                "claim_public_action",
                {
                    "p_action": action,
                    "p_actor_hash": actor_hash,
                    "p_query_key": query_key,
                    "p_limit": limit,
                    "p_window_seconds": window_seconds,
                    "p_cooldown_seconds": cooldown_seconds,
                },
            ).execute()
        )
        return PublicActionDecision(
            allowed=bool(result.get("allowed")),
            retry_after_seconds=int(result.get("retry_after_seconds", 0)),
        )


class SupabaseAdminRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def is_enabled_admin(self, user_id: UUID) -> bool:
        response = (
            self._client.table("admin_users")
            .select("user_id")
            .eq("user_id", str(user_id))
            .eq("enabled", True)
            .limit(1)
            .execute()
        )
        return bool(_rows(response))


class SupabaseResolverRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def record(self, request: ResolveRequest) -> ResolveRequest:
        response = (
            self._client.table("resolve_requests")
            .insert(
                {
                    "id": str(request.id),
                    "source": request.source,
                    "status": request.status,
                    "input_url": request.input_url,
                    "resolved_url": request.resolved_url,
                    "telegram_user_id": request.telegram_user_id,
                    "telegram_chat_id": request.telegram_chat_id,
                    "error_code": request.error_code,
                    "error_message": request.error_message,
                    "expires_at": request.expires_at.isoformat() if request.expires_at else None,
                }
            )
            .execute()
        )
        return _resolve_request(_rows(response)[0])
