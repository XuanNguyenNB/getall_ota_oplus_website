"""Public-mode orchestration for ``POST /api/ota``.

Splits the public OTA flow out of the FastAPI route handler so the
handler reads as a thin glue layer: parse, dispatch to the right
service, format the response. The service is also unit-testable
without a TestClient.

Responsibilities of :class:`PublicOtaService`:

- Validate that the public payload is non-sensitive (no imei/guid/beta).
- Enforce the Turnstile challenge.
- Look up a fresh cached release (Phase 2 SQL-bounded query) and
  rate-limit-claim under the cache-aware cooldown.
- When a fresh cache hit exists, short-circuit and return the cached
  result with ``X-OTA-Source: cache``.
- Otherwise return the lifted :class:`OtaRequestIn` so the caller can
  run the live provider query and tag ``X-OTA-Source: live``.

Operator/private mode does not go through this service; it stays inline
in the route because the surface there is intentionally simpler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response

from ota_backend.api.errors import ApiError
from ota_backend.api.schemas import OtaRequestIn, OtaResultOut, PublicOtaRequestIn
from ota_backend.config import Settings
from ota_backend.domain.models import Release
from ota_backend.repositories.interfaces import (
    PublicActionRepository,
    ReleaseRepository,
)
from ota_backend.services.access import (
    ChallengeVerifier,
    claim_public_action,
    find_cached_ota_release,
    ota_query_key,
    require_public_challenge,
)


@dataclass(frozen=True)
class PublicOtaOutcome:
    """Result of the public-mode pre-flight.

    ``cached`` is set when a fresh cache hit exists; the caller must
    respond with ``X-OTA-Source: cache`` and the cached release. When
    ``cached`` is ``None``, the caller proceeds with the live provider
    query using :attr:`internal_payload` and must set
    ``X-OTA-Source: live`` on the final response.
    """

    internal_payload: OtaRequestIn
    cached: Release | None


class PublicOtaService:
    def __init__(
        self,
        *,
        settings: Settings,
        release_repository: ReleaseRepository,
        public_action_repository: PublicActionRepository,
        challenge_verifier: ChallengeVerifier,
    ) -> None:
        self._settings = settings
        self._release_repository = release_repository
        self._public_action_repository = public_action_repository
        self._challenge_verifier = challenge_verifier

    def prepare(self, request: Request, body: Any) -> PublicOtaOutcome:
        if not isinstance(body, dict):
            raise ApiError(400, "VALIDATION_ERROR", "Request body must be a JSON object.")
        try:
            public_payload = PublicOtaRequestIn.model_validate(body)
        except Exception as exc:  # pydantic.ValidationError
            raise ApiError(
                422, "VALIDATION_ERROR", "Public OTA queries support standard releases only."
            ) from exc
        if public_payload.has_sensitive_inputs():
            raise ApiError(
                400,
                "VALIDATION_ERROR",
                "Public OTA queries support standard releases only.",
            )
        payload = public_payload.to_internal()
        require_public_challenge(request, verifier=self._challenge_verifier, action="ota")
        query_key = ota_query_key(
            product_model=payload.product_model,
            manifest_code=payload.manifest_code,
            ota_track=payload.ota_track,
            rui_candidates=payload.rui_candidates,
            language=payload.language,
        )
        cached = find_cached_ota_release(
            self._release_repository,
            product_model=payload.product_model,
            manifest_code=payload.manifest_code,
            ota_track=payload.ota_track,  # type: ignore[arg-type]
            rui_candidates=payload.rui_candidates,
            ttl_seconds=self._settings.ota_public_cache_ttl_seconds,
        )
        # Rate limit cooldown drops to zero on a cache hit so cached
        # responses do not waste the caller's per-hour quota.
        claim_public_action(
            repository=self._public_action_repository,
            request=request,
            settings=self._settings,
            action="ota",
            query_key=query_key,
            limit=self._settings.ota_public_rate_limit_per_hour,
            cooldown_seconds=(0 if cached else self._settings.ota_public_cache_ttl_seconds),
        )
        return PublicOtaOutcome(internal_payload=payload, cached=cached)

    @staticmethod
    def cached_response(response: Response, cached: Release) -> dict[str, object]:
        """Format the cache-hit branch's response body and set the
        ``X-OTA-Source`` header so observers can tell apart live and
        cached results without inspecting the body."""

        response.headers["X-OTA-Source"] = "cache"
        return {
            "ok": True,
            "result": OtaResultOut.from_domain(cached, is_new=False).model_dump(mode="json"),
        }
