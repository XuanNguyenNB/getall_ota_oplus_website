from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request, Response

from ota_backend.api.errors import ApiError
from ota_backend.api.schemas import (
    AdminScanEnqueueIn,
    DeviceOut,
    EdlRomOut,
    OtaRequestIn,
    OtaResultOut,
    ReleaseOut,
    ResolveRequestIn,
    ScanDisableAllIn,
    ScanGroupOut,
    ScanStatusRunOut,
    ScanToggleGroupIn,
    ScanToggleModelsIn,
)
from ota_backend.domain.models import OtaQuery
from ota_backend.domain.ota import normalize_product_model
from ota_backend.services.access import (
    claim_public_action,
    require_public_challenge,
    resolve_query_key,
)
from ota_backend.services.ota import OtaQueryService, OtaServiceError
from ota_backend.services.public_ota import PublicOtaService
from ota_backend.services.resolver import ResolverError
from ota_backend.services.scan_management import ScanManagementService

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Liveness probe.

    Returns only service identity and feature flags. The Supabase Auth
    bootstrap (URL + anon key) is intentionally not echoed here — see
    :func:`admin_bootstrap` — so an opportunistic anonymous probe of the
    health endpoint cannot extract a directly usable Supabase credential
    pair, even though the anon key is RLS-restricted by design.
    """

    settings = request.app.state.settings
    return {
        "ok": True,
        "service": settings.service_name,
        "version": settings.version,
        "features": {
            "public_site": settings.public_site_enabled,
            "resolver": settings.enable_resolver,
            "turnstile_site_key": (
                settings.turnstile_site_key if settings.public_site_enabled else None
            ),
            "admin_auth_enabled": bool(settings.supabase_url and settings.supabase_anon_key),
        },
    }


@router.get("/admin/bootstrap")
async def admin_bootstrap(request: Request) -> dict[str, object]:
    """Return the Supabase Auth bootstrap config for the admin UI.

    Cannot require admin auth itself: the admin UI needs ``supabase_url`` +
    anonymous public key to construct a Supabase client and obtain the JWT
    that would later be checked by ``require_admin``. The anon key is the
    documented public Supabase credential, protected by RLS; this endpoint
    just keeps it off the obvious liveness URL and makes the intent
    explicit in the OpenAPI surface.
    """

    settings = request.app.state.settings
    if not (settings.supabase_url and settings.supabase_anon_key):
        return {"ok": True, "admin_auth": None}
    return {
        "ok": True,
        "admin_auth": {
            "supabase_url": settings.supabase_url,
            "supabase_anon_key": settings.supabase_anon_key,
        },
    }


@router.get("/devices")
async def list_devices(
    request: Request,
    q: str | None = None,
    brand: str | None = Query(default=None, pattern="^(oppo|realme|oneplus)$"),
    enabled_only: bool = True,
    scan_enabled_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    page = request.app.state.device_repository.list_devices(
        q=q,
        brand=brand,
        enabled_only=enabled_only,
        scan_enabled_only=scan_enabled_only,
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
async def query_ota(request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    try:
        body = await request.json()
    except Exception as exc:
        raise ApiError(400, "VALIDATION_ERROR", "Request body must be JSON.") from exc
    if not isinstance(body, dict):
        raise ApiError(400, "VALIDATION_ERROR", "Request body must be a JSON object.")
    # Public mode delegates the full pre-flight (strict schema, challenge,
    # cache lookup, rate-limit claim) to PublicOtaService so the route
    # stays a thin glue layer. Operator/private mode keeps the simpler
    # OtaRequestIn parse path inline.
    if settings.public_site_enabled:
        public_service = PublicOtaService(
            settings=settings,
            release_repository=request.app.state.release_repository,
            public_action_repository=request.app.state.public_action_repository,
            challenge_verifier=request.app.state.challenge_verifier,
        )
        outcome = public_service.prepare(request, body)
        if outcome.cached is not None:
            return PublicOtaService.cached_response(response, outcome.cached)
        payload = outcome.internal_payload
    else:
        try:
            payload = OtaRequestIn.model_validate(body)
        except Exception as exc:  # pydantic.ValidationError
            raise ApiError(422, "VALIDATION_ERROR", "Invalid OTA request payload.") from exc

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
        "result": OtaResultOut.from_domain(result.release, is_new=result.is_new).model_dump(
            mode="json"
        ),
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
    releases = [ReleaseOut.from_domain(release).model_dump(mode="json") for release in page.items]
    return {
        "ok": True,
        "count": len(releases),
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
        "releases": releases,
    }


@router.get("/edl-roms")
async def list_edl_roms(
    request: Request,
    q: str | None = None,
    brand: str | None = Query(default=None, pattern="^(oppo|realme|oneplus)$"),
    product_model: str | None = None,
    region_code: str | None = None,
    sort: str = Query(default="build", pattern="^(build|imported)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    page = request.app.state.edl_rom_repository.list_edl_roms(
        q=q,
        brand=brand,
        product_model=product_model,
        region_code=region_code,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    roms = [EdlRomOut.from_domain(rom).model_dump(mode="json") for rom in page.items]
    return {
        "ok": True,
        "count": len(roms),
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
        "roms": roms,
    }


@router.get("/scan/status")
async def scan_status(request: Request) -> dict[str, object]:
    if request.app.state.settings.public_site_enabled:
        request.app.state.admin_authorizer.require_admin(request.headers.get("Authorization"))
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
    cycle_day = datetime.now(UTC).date().toordinal() % request.app.state.settings.scan_cycle_days
    run = request.app.state.scan_repository.create_run(
        cycle_day=cycle_day, total_tasks=len(devices), status="queued"
    )
    for device in devices:
        request.app.state.scan_repository.create_task(scan_run_id=run.id, device_id=device.id)
    return {"ok": True, "scan_run_id": str(run.id), "created_tasks": len(devices)}


@router.get("/admin/scan/groups")
async def admin_scan_groups(
    request: Request,
    q: str | None = None,
    brand: str | None = Query(default=None, pattern="^(oppo|realme|oneplus)$"),
    enabled_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    request.app.state.admin_authorizer.require_admin(request.headers.get("Authorization"))
    manager = ScanManagementService(request.app.state.device_repository)
    if enabled_only:
        groups = manager.list_enabled_groups(brand=brand, limit=limit)
    elif q:
        groups = manager.search(q, limit=limit)
    else:
        raise ApiError(400, "VALIDATION_ERROR", "Provide a search query or set enabled_only=true.")
    return {
        "ok": True,
        "count": len(groups),
        "enabled_total": manager.enabled_count(),
        "groups": [ScanGroupOut.from_domain(group).model_dump(mode="json") for group in groups],
    }


@router.post("/admin/scan/models")
async def admin_scan_set_models(request: Request, payload: ScanToggleModelsIn) -> dict[str, object]:
    request.app.state.admin_authorizer.require_admin(request.headers.get("Authorization"))
    manager = ScanManagementService(request.app.state.device_repository)
    updated, missing, without_manifest = manager.set_models(payload.product_models, payload.enabled)
    return {
        "ok": True,
        "updated": len(updated),
        "missing": missing,
        "without_manifest": without_manifest,
        "enabled_total": manager.enabled_count(),
    }


@router.post("/admin/scan/group")
async def admin_scan_set_group(request: Request, payload: ScanToggleGroupIn) -> dict[str, object]:
    request.app.state.admin_authorizer.require_admin(request.headers.get("Authorization"))
    manager = ScanManagementService(request.app.state.device_repository)
    updated = manager.enable_group(payload.scan_group_key, payload.enabled)
    return {
        "ok": True,
        "updated": len(updated),
        "enabled_total": manager.enabled_count(),
    }


@router.post("/admin/scan/disable-all")
async def admin_scan_disable_all(request: Request, payload: ScanDisableAllIn) -> dict[str, object]:
    request.app.state.admin_authorizer.require_admin(request.headers.get("Authorization"))
    if not payload.confirm:
        raise ApiError(400, "VALIDATION_ERROR", "Set confirm=true to disable all scanning.")
    manager = ScanManagementService(request.app.state.device_repository)
    disabled = manager.disable_all()
    return {"ok": True, "disabled": disabled, "enabled_total": manager.enabled_count()}


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
            query_key=resolve_query_key(payload.url),
            limit=settings.resolver_public_rate_limit_per_hour,
            cooldown_seconds=0,
        )
    try:
        result = request.app.state.resolver_service.resolve(payload.url, source="web")
    except ResolverError as exc:
        status_code = 400 if exc.code in {"VALIDATION_ERROR", "RESOLVE_BLOCKED_HOST"} else 502
        raise ApiError(status_code, exc.code, exc.message) from exc
    return {"ok": True, "input_url": result.input_url, "resolved_url": result.resolved_url}
