from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ota_backend.api.errors import install_error_handlers
from ota_backend.api.routes import router
from ota_backend.config import Settings, get_settings
from ota_backend.dependencies import (
    AppDependencies,
    build_dependencies,
    create_provider,  # re-exported for backward compatibility
)
from ota_backend.logging import RequestLoggingMiddleware, configure_logging
from ota_backend.providers.interfaces import OtaProvider
from ota_backend.repositories.interfaces import (
    AdminRepository,
    CatalogImportRepository,
    DeviceRepository,
    EdlRomRepository,
    PublicActionRepository,
    ReleaseRepository,
    ResolverRepository,
    ScanRepository,
    TelegramRepository,
)
from ota_backend.services.access import AdminAuthorizer, ChallengeVerifier
from ota_backend.services.resolver import ResolverService

STATIC_DIR = Path(__file__).resolve().parent / "static"


# ``create_provider`` is re-exported above so callers importing it from
# ``ota_backend.app`` keep working after the dependency factory was
# extracted into ``ota_backend.dependencies``.
__all__ = ["create_app", "create_provider"]


def create_app(
    *,
    settings: Settings | None = None,
    device_repository: DeviceRepository | None = None,
    release_repository: ReleaseRepository | None = None,
    edl_rom_repository: EdlRomRepository | None = None,
    scan_repository: ScanRepository | None = None,
    telegram_repository: TelegramRepository | None = None,
    catalog_import_repository: CatalogImportRepository | None = None,
    public_action_repository: PublicActionRepository | None = None,
    admin_repository: AdminRepository | None = None,
    resolver_repository: ResolverRepository | None = None,
    ota_provider: OtaProvider | None = None,
    challenge_verifier: ChallengeVerifier | None = None,
    admin_authorizer: AdminAuthorizer | None = None,
    resolver_service: ResolverService | None = None,
    dependencies: AppDependencies | None = None,
) -> FastAPI:
    resolved_settings = (
        dependencies.settings if dependencies is not None else (settings or get_settings())
    )
    resolved_settings.validate_runtime_configuration()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(title=resolved_settings.service_name, version=resolved_settings.version)
    app.state.settings = resolved_settings

    deps = dependencies or build_dependencies(
        resolved_settings,
        device_repository=device_repository,
        release_repository=release_repository,
        edl_rom_repository=edl_rom_repository,
        scan_repository=scan_repository,
        telegram_repository=telegram_repository,
        catalog_import_repository=catalog_import_repository,
        public_action_repository=public_action_repository,
        admin_repository=admin_repository,
        resolver_repository=resolver_repository,
        ota_provider=ota_provider,
        challenge_verifier=challenge_verifier,
        admin_authorizer=admin_authorizer,
        resolver_service=resolver_service,
    )

    app.state.device_repository = deps.device_repository
    app.state.release_repository = deps.release_repository
    app.state.edl_rom_repository = deps.edl_rom_repository
    app.state.scan_repository = deps.scan_repository
    app.state.telegram_repository = deps.telegram_repository
    app.state.catalog_import_repository = deps.catalog_import_repository
    app.state.public_action_repository = deps.public_action_repository
    app.state.admin_repository = deps.admin_repository
    app.state.resolver_repository = deps.resolver_repository
    app.state.ota_provider = deps.ota_provider
    app.state.challenge_verifier = deps.challenge_verifier
    app.state.admin_authorizer = deps.admin_authorizer
    app.state.resolver_service = deps.resolver_service

    app.add_middleware(RequestLoggingMiddleware)
    install_error_handlers(app)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def web_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/admin", include_in_schema=False)
    async def admin_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "admin.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
