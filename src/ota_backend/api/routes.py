from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, Response

from ota_backend.api.errors import ApiError
from ota_backend.api.schemas import (
    AdminScanEnqueueIn,
    DeviceOut,
    OtaRequestIn,
    OtaResultOut,
    ReleaseOut,
    ResolveRequestIn,
    ScanStatusRunOut,
)
from ota_backend.domain.models import OtaQuery
from ota_backend.domain.ota import normalize_product_model
from ota_backend.services.access import (
    claim_public_action,
    find_cached_ota_release,
    ota_query_key,
    require_public_challenge,
)
from ota_backend.services.ota import OtaQueryService, OtaServiceError
from ota_backend.services.resolver import ResolverError

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "ok": True,
        "service": settings.service_name,
        "version": settings.version,
        "features": {
            "public_site": settings.public_site_enabled,
            "resolver": settings.enable_resolver,
            "turnstile_site_key": settings.turnstile_site_key if settings.public_site_enabled else None,
        },
    }


@router.get("/devices")
async def list_devices(
    request: Request,
    q: str | None = None,
    brand: str | None = Query(default=None, pattern="^(oppo|realme|oneplus)$"),
    enabled_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    page = request.app.state.device_repository.list_devices(
        q=q,
        brand=brand,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )
    devices = [DeviceOut.from_domain(device).model_dump(mode="json") for device in page.items]
    return {
        "ok": True,
        "count": len(devices),
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
        "devices": devices,
    }


@router.post("/ota")
async def query_ota(
    request: Request, response: Response, payload: OtaRequestIn
) -> dict[str, object]:
    settings = request.app.state.settings
    if settings.public_site_enabled:
        if payload.beta or payload.imei0 or payload.imei1 or payload.guid:
            raise ApiError(
                400,
                "VALIDATION_ERROR",
                "Public OTA queries support standard releases only.",
            )
        require_public_challenge(
            request, verifier=request.app.state.challenge_verifier, action="ota"
        )
        query_key = ota_query_key(
            product_model=payload.product_model,
            manifest_code=payload.manifest_code,
            ota_track=payload.ota_track,
            rui_candidates=payload.rui_candidates,
            language=payload.language,
        )
        cached = find_cached_ota_release(
            request.app.state.release_repository,
            product_model=payload.product_model,
            manifest_code=payload.manifest_code,
            ota_track=payload.ota_track,  # type: ignore[arg-type]
            rui_candidates=payload.rui_candidates,
            ttl_seconds=settings.ota_public_cache_ttl_seconds,
        )
        claim_public_action(
            repository=request.app.state.public_action_repository,
            request=request,
            settings=settings,
            action="ota",
            query_key=query_key,
            limit=settings.ota_public_rate_limit_per_hour,
            cooldown_seconds=0 if cached else settings.ota_public_cache_ttl_seconds,
        )
        if cached is not None:
            response.headers["X-OTA-Source"] = "cache"
            return {
                "ok": True,
                "result": OtaResultOut.from_domain(cached, is_new=False).model_dump(mode="json"),
            }

    service = OtaQueryService(
        provider=request.app.state.ota_provider,
        release_repository=request.app.state.release_repository,
        device_repository=request.app.state.device_repository,
    )
    try:
        result = service.run_manual_query(
            OtaQuery(
                product_model=payload.product_model,
                manifest_code=payload.manifest_code,
                ota_track=payload.ota_track,  # type: ignore[arg-type]
                rui_candidates=payload.rui_candidates,
                language=payload.language,
                beta=payload.beta,
                imei0=payload.imei0,
                imei1=payload.imei1,
                persist_result=payload.persist_result,
            )
        )
    except OtaServiceError as exc:
        status_code = 404 if exc.code == "OTA_NOT_FOUND" else 400
        if exc.code in {"UPSTREAM_ERROR", "UPSTREAM_TIMEOUT", "DECRYPT_ERROR"}:
            status_code = 502
        raise ApiError(status_code, exc.code, exc.message) from exc

    if settings.public_site_enabled:
        response.headers["X-OTA-Source"] = "live"
    return {
        "ok": True,
        "result": OtaResultOut.from_domain(
            result.release, is_new=result.is_new
        ).model_dump(mode="json"),
    }


@router.get("/releases")
async def list_releases(
    request: Request,
    q: str | None = None,
    brand: str | None = Query(default=None, pattern="^(oppo|realme|oneplus)$"),
    product_model: str | None = None,
    manifest_code: str | None = None,
    region_code: str | None = None,
    release_type: str | None = Query(default=None, pattern="^(official|beta)$"),
    source: str | None = None,
    sort: str = Query(default="discovered", pattern="^(discovered|published)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    page = request.app.state.release_repository.list_releases(
        q=q,
        brand=brand,
        product_model=product_model,
        manifest_code=manifest_code,
        region_code=region_code,
        release_type=release_type,
        source=source,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    releases = [
        ReleaseOut.from_domain(release).model_dump(mode="json") for release in page.items
    ]
    return {
        "ok": True,
        "count": len(releases),
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
        "releases": releases,
    }


@router.get("/scan/status")
async def scan_status(request: Request) -> dict[str, object]:
    if request.app.state.settings.public_site_enabled:
        request.app.state.admin_authorizer.require_admin(
            request.headers.get("Authorization")
        )
    latest_run = request.app.state.scan_repository.latest_run()
    return {
        "ok": True,
        "latest_run": None
        if latest_run is None
        else ScanStatusRunOut.from_domain(latest_run).model_dump(mode="json"),
    }


@router.post("/admin/scan/enqueue", status_code=202)
async def enqueue_admin_scan(request: Request, payload: AdminScanEnqueueIn) -> dict[str, object]:
    request.app.state.admin_authorizer.require_admin(request.headers.get("Authorization"))
    devices = []
    missing = []
    for value in dict.fromkeys(payload.product_models):
        try:
            model = normalize_product_model(value)
        except ValueError:
            missing.append(value)
            continue
        device = request.app.state.device_repository.get_by_product_model(model)
        if device is None:
            missing.append(model)
        else:
            devices.append(device)
    if missing:
        raise ApiError(400, "VALIDATION_ERROR", "One or more product models are not known.")
    cycle_day = datetime.now(timezone.utc).date().toordinal() % 7
    run = request.app.state.scan_repository.create_run(
        cycle_day=cycle_day, total_tasks=len(devices), status="queued"
    )
    for device in devices:
        request.app.state.scan_repository.create_task(
            scan_run_id=run.id, device_id=device.id
        )
    return {"ok": True, "scan_run_id": str(run.id), "created_tasks": len(devices)}


@router.post("/resolve")
async def resolve_url(request: Request, payload: ResolveRequestIn) -> dict[str, object]:
    settings = request.app.state.settings
    if not settings.enable_resolver:
        raise ApiError(503, "FEATURE_NOT_ENABLED", "Resolver is not enabled.")
    if settings.public_site_enabled:
        require_public_challenge(
            request, verifier=request.app.state.challenge_verifier, action="resolve"
        )
        claim_public_action(
            repository=request.app.state.public_action_repository,
            request=request,
            settings=settings,
            action="resolve",
            query_key=ota_query_key(
                product_model="resolve",
                manifest_code="url",
                ota_track="R",
                rui_candidates=[],
                language=payload.url,
            ),
            limit=settings.resolver_public_rate_limit_per_hour,
            cooldown_seconds=0,
        )
    try:
        result = request.app.state.resolver_service.resolve(payload.url, source="web")
    except ResolverError as exc:
        status_code = 400 if exc.code in {"VALIDATION_ERROR", "RESOLVE_BLOCKED_HOST"} else 502
        raise ApiError(status_code, exc.code, exc.message) from exc
    return {"ok": True, "input_url": result.input_url, "resolved_url": result.resolved_url}
