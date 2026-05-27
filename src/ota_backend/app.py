from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ota_backend.api.errors import install_error_handlers
from ota_backend.api.routes import router
from ota_backend.config import Settings, get_settings
from ota_backend.logging import RequestLoggingMiddleware, configure_logging
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.providers.interfaces import OtaProvider
from ota_backend.providers.realme import RealmeOtaProvider
from ota_backend.repositories.interfaces import (
    AdminRepository,
    CatalogImportRepository,
    DeviceRepository,
    PublicActionRepository,
    ReleaseRepository,
    ResolverRepository,
    ScanRepository,
    TelegramRepository,
)
from ota_backend.repositories.memory import (
    InMemoryAdminRepository,
    InMemoryCatalogImportRepository,
    InMemoryDeviceRepository,
    InMemoryPublicActionRepository,
    InMemoryReleaseRepository,
    InMemoryResolverRepository,
    InMemoryScanRepository,
    InMemoryTelegramRepository,
)
from ota_backend.repositories.supabase import (
    SupabaseAdminRepository,
    SupabaseCatalogImportRepository,
    SupabaseDeviceRepository,
    SupabasePublicActionRepository,
    SupabaseReleaseRepository,
    SupabaseResolverRepository,
    SupabaseScanRepository,
    SupabaseTelegramRepository,
    create_supabase_client,
)
from ota_backend.services.access import (
    AdminAuthorizer,
    ChallengeVerifier,
    DenyAdminAuthorizer,
    SupabaseAdminAuthorizer,
    TurnstileChallengeVerifier,
)
from ota_backend.services.resolver import ResolverService

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_provider(settings: Settings) -> OtaProvider:
    if settings.ota_provider == "realme":
        return RealmeOtaProvider(settings)
    return FakeOtaProvider()


def create_app(
    *,
    settings: Settings | None = None,
    device_repository: DeviceRepository | None = None,
    release_repository: ReleaseRepository | None = None,
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
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.validate_runtime_configuration()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(title=resolved_settings.service_name, version=resolved_settings.version)
    app.state.settings = resolved_settings
    if resolved_settings.repository_backend == "supabase":
        client = create_supabase_client(resolved_settings)
        default_devices: DeviceRepository = SupabaseDeviceRepository(client)
        default_releases: ReleaseRepository = SupabaseReleaseRepository(client)
        default_scans: ScanRepository = SupabaseScanRepository(client)
        default_telegram: TelegramRepository = SupabaseTelegramRepository(client)
        default_catalog_imports: CatalogImportRepository = SupabaseCatalogImportRepository(client)
        default_public_actions: PublicActionRepository = SupabasePublicActionRepository(client)
        default_admins: AdminRepository = SupabaseAdminRepository(client)
        default_resolver_requests: ResolverRepository = SupabaseResolverRepository(client)
        default_admin_authorizer: AdminAuthorizer = SupabaseAdminAuthorizer(client, admin_repository or default_admins)
    else:
        default_devices = InMemoryDeviceRepository()
        default_releases = InMemoryReleaseRepository()
        default_scans = InMemoryScanRepository()
        default_telegram = InMemoryTelegramRepository()
        default_catalog_imports = InMemoryCatalogImportRepository()
        default_public_actions = InMemoryPublicActionRepository()
        default_admins = InMemoryAdminRepository()
        default_resolver_requests = InMemoryResolverRepository()
        default_admin_authorizer = DenyAdminAuthorizer()
    app.state.device_repository = device_repository or default_devices
    app.state.release_repository = release_repository or default_releases
    app.state.scan_repository = scan_repository or default_scans
    app.state.telegram_repository = telegram_repository or default_telegram
    app.state.catalog_import_repository = catalog_import_repository or default_catalog_imports
    app.state.public_action_repository = public_action_repository or default_public_actions
    app.state.admin_repository = admin_repository or default_admins
    app.state.resolver_repository = resolver_repository or default_resolver_requests
    app.state.ota_provider = ota_provider or create_provider(resolved_settings)
    app.state.challenge_verifier = challenge_verifier or (
        TurnstileChallengeVerifier(resolved_settings)
        if resolved_settings.public_site_enabled
        else None
    )
    app.state.admin_authorizer = admin_authorizer or default_admin_authorizer
    app.state.resolver_service = resolver_service or ResolverService(
        repository=app.state.resolver_repository,
        allowed_suffixes=resolved_settings.parsed_resolver_allowed_host_suffixes,
        timeout_seconds=resolved_settings.resolver_timeout_seconds,
        max_redirects=resolved_settings.resolver_max_redirects,
    )

    app.add_middleware(RequestLoggingMiddleware)
    install_error_handlers(app)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def web_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
