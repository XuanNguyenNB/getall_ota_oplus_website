"""Shared dependency-construction factory for ``app`` and ``worker``.

Both the FastAPI application and the standalone scanner worker need the
same set of repositories, providers, and access-control adapters. Before
this module existed, ``worker.run_once`` instantiated those dependencies
by spinning up an entire FastAPI app via ``create_app(settings)`` only
to read ``app.state.*`` back out. That pulled in request-logging
middleware, static-file mounts, and the resolver service that the
worker has no use for. It also coupled the worker's bootstrap to
``create_app``'s side effects.

:func:`build_dependencies` is the single source of truth for that wiring:

- Constructs the right repositories based on
  ``settings.repository_backend`` (Supabase vs. in-memory).
- Constructs the OTA provider, challenge verifier, admin authorizer,
  and resolver service the same way regardless of caller.
- Returns an immutable :class:`AppDependencies` bundle that the caller
  attaches to ``app.state`` or unpacks directly.

``create_app`` keeps its override surface (each dependency can be
passed in to support test seams), while ``worker.run_once`` becomes a
small helper that builds dependencies and hands them to
``ScannerService`` without ever creating a FastAPI instance.
"""

from __future__ import annotations

from dataclasses import dataclass

from ota_backend.config import Settings
from ota_backend.providers.fake import FakeOtaProvider
from ota_backend.providers.interfaces import OtaProvider
from ota_backend.providers.realme import RealmeOtaProvider
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
from ota_backend.repositories.memory import (
    InMemoryAdminRepository,
    InMemoryCatalogImportRepository,
    InMemoryDeviceRepository,
    InMemoryEdlRomRepository,
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
    SupabaseEdlRomRepository,
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


@dataclass(frozen=True)
class AppDependencies:
    """Bundle of constructed dependencies used by ``app`` and ``worker``."""

    settings: Settings
    device_repository: DeviceRepository
    release_repository: ReleaseRepository
    edl_rom_repository: EdlRomRepository
    scan_repository: ScanRepository
    telegram_repository: TelegramRepository
    catalog_import_repository: CatalogImportRepository
    public_action_repository: PublicActionRepository
    admin_repository: AdminRepository
    resolver_repository: ResolverRepository
    ota_provider: OtaProvider
    challenge_verifier: ChallengeVerifier | None
    admin_authorizer: AdminAuthorizer
    resolver_service: ResolverService


def create_provider(settings: Settings) -> OtaProvider:
    """Build the right OTA provider for the runtime mode."""

    if settings.ota_provider == "realme":
        return RealmeOtaProvider(settings)
    return FakeOtaProvider()


def build_dependencies(
    settings: Settings,
    *,
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
) -> AppDependencies:
    """Construct the dependency bundle for ``settings``.

    Any keyword overrides are honored verbatim so tests can swap in
    in-memory fakes without spinning up a Supabase client. The same
    construction order runs whether the caller is the FastAPI app or
    the scanner worker.
    """

    if settings.repository_backend == "supabase":
        client = create_supabase_client(settings)
        defaults_devices: DeviceRepository = SupabaseDeviceRepository(client)
        defaults_releases: ReleaseRepository = SupabaseReleaseRepository(client)
        defaults_edl_roms: EdlRomRepository = SupabaseEdlRomRepository(client)
        defaults_scans: ScanRepository = SupabaseScanRepository(client)
        defaults_telegram: TelegramRepository = SupabaseTelegramRepository(client)
        defaults_catalog_imports: CatalogImportRepository = SupabaseCatalogImportRepository(client)
        defaults_public_actions: PublicActionRepository = SupabasePublicActionRepository(client)
        defaults_admins: AdminRepository = SupabaseAdminRepository(client)
        defaults_resolver_requests: ResolverRepository = SupabaseResolverRepository(client)
        defaults_admin_authorizer: AdminAuthorizer = SupabaseAdminAuthorizer(
            client, admin_repository or defaults_admins
        )
    else:
        defaults_devices = InMemoryDeviceRepository()
        defaults_releases = InMemoryReleaseRepository()
        defaults_edl_roms = InMemoryEdlRomRepository()
        defaults_scans = InMemoryScanRepository()
        defaults_telegram = InMemoryTelegramRepository()
        defaults_catalog_imports = InMemoryCatalogImportRepository()
        defaults_public_actions = InMemoryPublicActionRepository()
        defaults_admins = InMemoryAdminRepository()
        defaults_resolver_requests = InMemoryResolverRepository()
        defaults_admin_authorizer = DenyAdminAuthorizer()

    resolved_devices = device_repository or defaults_devices
    resolved_releases = release_repository or defaults_releases
    resolved_edl_roms = edl_rom_repository or defaults_edl_roms
    resolved_scans = scan_repository or defaults_scans
    resolved_telegram = telegram_repository or defaults_telegram
    resolved_catalog_imports = catalog_import_repository or defaults_catalog_imports
    resolved_public_actions = public_action_repository or defaults_public_actions
    resolved_admins = admin_repository or defaults_admins
    resolved_resolver_requests = resolver_repository or defaults_resolver_requests
    resolved_provider = ota_provider or create_provider(settings)
    resolved_challenge: ChallengeVerifier | None
    if challenge_verifier is not None:
        resolved_challenge = challenge_verifier
    elif settings.public_site_enabled:
        resolved_challenge = TurnstileChallengeVerifier(settings)
    else:
        resolved_challenge = None
    resolved_admin_authorizer = admin_authorizer or defaults_admin_authorizer
    resolved_resolver_service = resolver_service or ResolverService(
        repository=resolved_resolver_requests,
        allowed_suffixes=settings.parsed_resolver_allowed_host_suffixes,
        timeout_seconds=settings.resolver_timeout_seconds,
        max_redirects=settings.resolver_max_redirects,
    )

    return AppDependencies(
        settings=settings,
        device_repository=resolved_devices,
        release_repository=resolved_releases,
        edl_rom_repository=resolved_edl_roms,
        scan_repository=resolved_scans,
        telegram_repository=resolved_telegram,
        catalog_import_repository=resolved_catalog_imports,
        public_action_repository=resolved_public_actions,
        admin_repository=resolved_admins,
        resolver_repository=resolved_resolver_requests,
        ota_provider=resolved_provider,
        challenge_verifier=resolved_challenge,
        admin_authorizer=resolved_admin_authorizer,
        resolver_service=resolved_resolver_service,
    )
