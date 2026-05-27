from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings
from ota_backend.repositories.memory import InMemoryResolverRepository
from ota_backend.services.resolver import ResolverError, ResolverService


class HeadTransport:
    def __init__(self, responses: list[tuple[int, str | None]]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def head(self, url: str, *, timeout: float) -> tuple[int, str | None]:
        self.urls.append(url)
        return self.responses.pop(0)


def _service(repository, transport) -> ResolverService:
    return ResolverService(
        repository=repository,
        allowed_suffixes=("allawnofs.com",),
        timeout_seconds=5,
        max_redirects=2,
        transport=transport,
        dns_resolver=lambda _host: ["8.8.8.8"],
    )


def test_resolver_applies_proven_component_hostname_transform_and_safe_redirect():
    repository = InMemoryResolverRepository()
    transport = HeadTransport([(302, "/final.zip"), (200, None)])
    service = _service(repository, transport)

    result = service.resolve(
        "https://gauss-componentotacostmanual.allawnofs.com/path/update.zip"
    )

    assert "opexcostmanual" in transport.urls[0]
    assert result.resolved_url.endswith("/final.zip")
    assert repository.requests[0].status == "success"


def test_resolver_blocks_non_global_resolution_without_storing_unvalidated_url():
    repository = InMemoryResolverRepository()
    service = ResolverService(
        repository=repository,
        allowed_suffixes=("allawnofs.com",),
        timeout_seconds=5,
        max_redirects=1,
        transport=HeadTransport([]),
        dns_resolver=lambda _host: ["127.0.0.1"],
    )

    with pytest.raises(ResolverError) as error:
        service.resolve("https://safe.allawnofs.com/file.zip")

    assert error.value.code == "RESOLVE_BLOCKED_HOST"
    assert repository.requests[0].status == "blocked"
    assert repository.requests[0].input_url is None


def test_resolver_endpoint_is_blocked_until_live_proof_flag_enables_it():
    disabled = TestClient(create_app())
    response = disabled.post("/api/resolve", json={"url": "https://safe.allawnofs.com/x"})
    assert response.status_code == 503

    service = _service(InMemoryResolverRepository(), HeadTransport([(200, None)]))
    enabled = TestClient(
        create_app(
            settings=Settings(enable_resolver=True, resolver_live_proof_confirmed=True),
            resolver_service=service,
        )
    )
    response = enabled.post(
        "/api/resolve",
        json={"url": "https://safe.allawnofs.com/x", "source": "web"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
