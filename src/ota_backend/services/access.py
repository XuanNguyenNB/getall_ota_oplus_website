from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

import httpx
from fastapi import Request

from ota_backend.api.errors import ApiError
from ota_backend.config import Settings
from ota_backend.domain.models import OtaTrack, Release, utc_now
from ota_backend.repositories.interfaces import AdminRepository, PublicActionRepository, ReleaseRepository


class ChallengeVerifier(Protocol):
    def verify(self, *, token: str, remote_ip: str | None, action: str) -> bool:
        ...


class AdminAuthorizer(Protocol):
    def require_admin(self, authorization: str | None) -> UUID:
        ...


class TurnstileChallengeVerifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.turnstile_secret_key:
            raise RuntimeError("TURNSTILE_SECRET_KEY is required for public requests")
        self._secret = settings.turnstile_secret_key
        self._expected_hostname = settings.turnstile_expected_hostname

    def verify(self, *, token: str, remote_ip: str | None, action: str) -> bool:
        try:
            response = httpx.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                json={"secret": self._secret, "response": token, "remoteip": remote_ip},
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError):
            return False
        validated_action = result.get("action")
        return bool(result.get("success")) and (
            validated_action in {None, "", action}
        ) and (
            not self._expected_hostname
            or result.get("hostname") == self._expected_hostname
        )


class SupabaseAdminAuthorizer:
    def __init__(self, auth_client: Any, repository: AdminRepository) -> None:
        self._auth_client = auth_client
        self._repository = repository

    def require_admin(self, authorization: str | None) -> UUID:
        if not authorization or not authorization.startswith("Bearer "):
            raise ApiError(401, "AUTH_REQUIRED", "Admin authentication is required.")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            response = self._auth_client.auth.get_user(token)
            raw_id = response.user.id
            user_id = UUID(str(raw_id))
        except Exception as exc:
            raise ApiError(401, "AUTH_REQUIRED", "Admin authentication is required.") from exc
        if not self._repository.is_enabled_admin(user_id):
            raise ApiError(403, "FORBIDDEN", "Admin access is required.")
        return user_id


class DenyAdminAuthorizer:
    def require_admin(self, _authorization: str | None) -> UUID:
        raise ApiError(401, "AUTH_REQUIRED", "Admin authentication is required.")


def require_public_challenge(
    request: Request, *, verifier: ChallengeVerifier, action: str
) -> None:
    token = request.headers.get("X-Turnstile-Token", "").strip()
    if not token or not verifier.verify(
        token=token,
        remote_ip=request.headers.get("CF-Connecting-IP")
        or (request.client.host if request.client else None),
        action=action,
    ):
        raise ApiError(403, "CHALLENGE_FAILED", "Human verification is required.")


def actor_hash(request: Request, settings: Settings) -> str:
    if not settings.public_rate_limit_salt:
        raise RuntimeError("PUBLIC_RATE_LIMIT_SALT is required for public requests")
    address = request.headers.get("CF-Connecting-IP")
    if not address:
        address = request.client.host if request.client else "unknown"
    value = f"{settings.public_rate_limit_salt}:{address}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def ota_query_key(
    *,
    product_model: str,
    manifest_code: str,
    ota_track: str,
    rui_candidates: list[int],
    language: str,
) -> str:
    normalized = "|".join(
        (
            product_model.strip().upper(),
            manifest_code.strip().upper(),
            ota_track.strip().upper(),
            ",".join(str(item) for item in rui_candidates),
            language.strip().lower(),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def claim_public_action(
    *,
    repository: PublicActionRepository,
    request: Request,
    settings: Settings,
    action: str,
    query_key: str,
    limit: int,
    cooldown_seconds: int,
) -> None:
    decision = repository.claim(
        action=action,
        actor_hash=actor_hash(request, settings),
        query_key=query_key,
        limit=limit,
        window_seconds=3600,
        cooldown_seconds=cooldown_seconds,
    )
    if not decision.allowed:
        retry = max(decision.retry_after_seconds, 1)
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Request limit reached. Try again later.",
            headers={
                "Retry-After": str(retry),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": (utc_now() + timedelta(seconds=retry)).isoformat(),
            },
        )


def find_cached_ota_release(
    repository: ReleaseRepository,
    *,
    product_model: str,
    manifest_code: str,
    ota_track: OtaTrack,
    rui_candidates: list[int],
    ttl_seconds: int,
) -> Release | None:
    if ttl_seconds <= 0:
        return None
    page = repository.list_releases(
        q=None,
        brand=None,
        product_model=product_model.strip().upper(),
        manifest_code=manifest_code.strip().upper(),
        source="live_provider",
        limit=20,
        offset=0,
    )
    cutoff = utc_now() - timedelta(seconds=ttl_seconds)
    return next(
        (
            release
            for release in page.items
            if release.ota_track == ota_track
            and release.rui_version in rui_candidates
            and release.last_seen_at >= cutoff
        ),
        None,
    )
