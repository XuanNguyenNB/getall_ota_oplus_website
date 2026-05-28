from __future__ import annotations

import pytest
import httpx
from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings
from ota_backend.repositories.memory import InMemoryResolverRepository
from ota_backend.services.resolver import HttpxResolverTransport, ResolverError, ResolverService


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


def test_resolver_preserves_cn_manual_cost_cdn_link_for_metadata_validation():
    repository = InMemoryResolverRepository()
    transport = HeadTransport([(200, None)])
    service = ResolverService(
        repository=repository,
        allowed_suffixes=("allawnfs.com",),
        timeout_seconds=5,
        max_redirects=2,
        transport=transport,
        dns_resolver=lambda _host: ["8.8.8.8"],
    )

    result = service.resolve(
        "https://gauss-componentotacostmanual-cn.allawnfs.com/remove-id/component-ota/file.zip"
    )

    assert transport.urls == [
        "https://gauss-componentotacostmanual-cn.allawnfs.com/remove-id/component-ota/file.zip"
    ]
    assert result.resolved_url == transport.urls[0]
    assert repository.requests[0].status == "success"


def test_resolver_converts_cn_cost_auto_cdn_link_to_manual_cdn_link():
    repository = InMemoryResolverRepository()
    transport = HeadTransport([(200, None)])
    service = ResolverService(
        repository=repository,
        allowed_suffixes=("allawnfs.com",),
        timeout_seconds=5,
        max_redirects=2,
        transport=transport,
        dns_resolver=lambda _host: ["8.8.8.8"],
    )

    result = service.resolve(
        "https://gauss-compotacostauto-cn.allawnfs.com/remove-id/component-ota/file.zip"
    )

    assert transport.urls == [
        "https://gauss-componentotacostmanual-cn.allawnfs.com/remove-id/component-ota/file.zip"
    ]
    assert result.resolved_url == transport.urls[0]
    assert repository.requests[0].status == "success"


def test_resolver_reports_stale_cn_cost_auto_cdn_link_after_normalization():
    repository = InMemoryResolverRepository()
    transport = HeadTransport([(403, None)])
    service = ResolverService(
        repository=repository,
        allowed_suffixes=("allawnfs.com",),
        timeout_seconds=5,
        max_redirects=2,
        transport=transport,
        dns_resolver=lambda _host: ["8.8.8.8"],
    )

    with pytest.raises(ResolverError) as error:
        service.resolve(
            "https://gauss-compotacostauto-cn.allawnfs.com/remove-id/component-ota/file.zip"
        )

    assert error.value.code == "RESOLVE_FAILED"
    assert "legacy auto CDN link" in error.value.message
    assert repository.requests[0].status == "failed"


def test_resolver_handles_oplus_downloadcheck_redirect_to_cdn():
    repository = InMemoryResolverRepository()
    transport = HeadTransport(
        [
            (
                302,
                "https://gauss-compota-c-cn.allawnfs.com/remove-id/g-id/component-ota/file.zip?sign=abc",
            ),
            (200, None),
        ]
    )
    service = ResolverService(
        repository=repository,
        allowed_suffixes=("coloros.com", "allawnfs.com"),
        timeout_seconds=5,
        max_redirects=2,
        transport=transport,
        dns_resolver=lambda _host: ["8.8.8.8"],
    )

    result = service.resolve("https://component-ota-gray.coloros.com/downloadCheck?id=1")

    assert result.resolved_url.startswith("https://gauss-compota-c-cn.allawnfs.com/")
    assert result.resolved_url.endswith("file.zip?sign=abc")
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


def test_downloadcheck_transport_sends_oplus_metadata_headers(monkeypatch):
    seen_headers: dict[str, str] = {}

    def fake_get(url, *, headers, follow_redirects, timeout):
        seen_headers.update(headers)
        assert url == "https://component-ota-gray.coloros.com/downloadCheck?id=1"
        assert follow_redirects is False
        assert timeout == 5
        return httpx.Response(
            302,
            headers={
                "location": "https://gauss-compota-c-cn.allawnfs.com/component-ota/file.zip"
            },
        )

    monkeypatch.setattr("ota_backend.services.resolver.httpx.get", fake_get)

    status_code, location = HttpxResolverTransport().head(
        "https://component-ota-gray.coloros.com/downloadCheck?id=1", timeout=5
    )

    assert status_code == 302
    assert location == "https://gauss-compota-c-cn.allawnfs.com/component-ota/file.zip"
    assert seen_headers["User-Agent"] == "okhttp/3.14.9"
    assert seen_headers["userId"] == "oplus-ota|16000015"


def test_direct_cn_cdn_transport_uses_download_client_metadata_headers(monkeypatch):
    seen_headers: dict[str, str] = {}

    def fake_head(url, *, headers, follow_redirects, timeout):
        seen_headers.update(headers)
        assert url == "https://gauss-componentotacostmanual-cn.allawnfs.com/component-ota/file.zip"
        assert follow_redirects is False
        assert timeout == 5
        return httpx.Response(200)

    monkeypatch.setattr("ota_backend.services.resolver.httpx.head", fake_head)

    status_code, location = HttpxResolverTransport().head(
        "https://gauss-componentotacostmanual-cn.allawnfs.com/component-ota/file.zip",
        timeout=5,
    )

    assert status_code == 200
    assert location is None
    assert seen_headers["User-Agent"] == "curl/8.0.1"


def test_downloadcheck_transport_extracts_nested_json_download_url(monkeypatch):
    def fake_get(url, *, headers, follow_redirects, timeout):
        return httpx.Response(
            200,
            json={
                "responseCode": 0,
                "body": {
                    "components": [
                        {
                            "componentPackets": [
                                {
                                    "manualUrl": "https://gauss-compota-c-cn.allawnfs.com/component-ota/file.zip"
                                }
                            ]
                        }
                    ]
                },
            },
        )

    monkeypatch.setattr("ota_backend.services.resolver.httpx.get", fake_get)

    status_code, location = HttpxResolverTransport().head(
        "https://component-ota-gray.coloros.com/downloadCheck?id=1", timeout=5
    )

    assert status_code == 302
    assert location == "https://gauss-compota-c-cn.allawnfs.com/component-ota/file.zip"


def test_downloadcheck_transport_maps_oplus_2306_to_resolver_error(monkeypatch):
    def fake_get(url, *, headers, follow_redirects, timeout):
        return httpx.Response(
            200,
            json={
                "body": None,
                "errMsg": "[2306]Params check failed: user id not exist",
                "responseCode": 2306,
            },
        )

    monkeypatch.setattr("ota_backend.services.resolver.httpx.get", fake_get)

    with pytest.raises(ResolverError) as error:
        HttpxResolverTransport().head(
            "https://component-ota-gray.coloros.com/downloadCheck?id=1", timeout=5
        )

    assert error.value.code == "RESOLVE_FAILED"


def test_default_resolver_allowlist_includes_oplus_allawnfs_cdn():
    assert "allawnfs.com" in Settings().parsed_resolver_allowed_host_suffixes


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
