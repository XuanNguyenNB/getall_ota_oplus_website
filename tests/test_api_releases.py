from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings
from ota_backend.domain.models import OtaProviderRelease
from ota_backend.repositories.memory import InMemoryDeviceRepository, InMemoryReleaseRepository


def test_releases_empty_page_shape(client):
    response = client.get("/api/releases")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "count": 0,
        "total": 0,
        "limit": 50,
        "offset": 0,
        "releases": [],
    }


def test_releases_filter_archive_metadata_and_sort_by_published():
    releases = InMemoryReleaseRepository()
    old = releases.upsert_release(
        OtaProviderRelease(
            brand="oppo",
            product_model="PKC110",
            manifest_code="97",
            ota_track="C",
            rui_version=16,
            real_ota_version="PKC110_11.C.70_1700_202601241456",
            real_version_name="PKC110_16.0.3.502(CN01)",
            computed_ota_version="PKC110_11.C.70_1700_202601241456",
            version_type_id="official",
            about_update_url=None,
            download_url="https://example.test/old.zip",
            source="lsctool_archive",
            region_code="CN",
            release_type="official",
        ),
        discovered_by="import",
    )
    new = releases.upsert_release(
        OtaProviderRelease(
            brand="oppo",
            product_model="PKC110",
            manifest_code="97",
            ota_track="C",
            rui_version=16,
            real_ota_version="PKC110_11.C.75_1750_202605052105",
            real_version_name="PKC110_16.0.7.200(CN01)",
            computed_ota_version="PKC110_11.C.75_1750_202605052105",
            version_type_id="official",
            about_update_url="https://example.test/about.html",
            download_url="https://example.test/new.zip",
            security_patch="2026-05-01",
            source="lsctool_archive",
            region_code="CN",
            release_type="official",
        ),
        discovered_by="import",
    )
    old.release.published_at = old.release.discovered_at
    new.release.published_at = new.release.discovered_at
    app = create_app(
        settings=Settings(),
        device_repository=InMemoryDeviceRepository(),
        release_repository=releases,
    )
    client = TestClient(app)

    response = client.get(
        "/api/releases",
        params={
            "product_model": "PKC110",
            "region_code": "CN",
            "release_type": "official",
            "source": "lsctool_archive",
            "sort": "published",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["releases"][0]["real_version_name"] == "PKC110_16.0.7.200(CN01)"
    assert body["releases"][0]["manifest_code"] == "97"
    assert body["releases"][0]["region_code"] == "CN"
    assert body["releases"][0]["release_type"] == "official"
    assert body["releases"][0]["source"] == "lsctool_archive"
    assert body["releases"][0]["security_patch"] == "2026-05-01"


def test_release_upsert_refreshes_existing_technical_display_metadata():
    releases = InMemoryReleaseRepository()
    technical = releases.upsert_release(
        OtaProviderRelease(
            brand="oppo",
            product_model="PKJ110",
            manifest_code="97",
            ota_track="C",
            rui_version=8,
            real_ota_version="PKJ110_11.C.65_1650_202604091920",
            real_version_name="PKJ110_11.C.65_1650_202604091920",
            computed_ota_version="PKJ110_11.C.65_CN_202604091920",
            version_type_id="non_display",
            about_update_url="https://example.test/component-ota/26/05/07/update.html",
            download_url="https://example.test/update.zip",
        ),
        discovered_by="manual",
    )

    refreshed = releases.upsert_release(
        OtaProviderRelease(
            brand="oppo",
            product_model="PKJ110",
            manifest_code="97",
            ota_track="C",
            rui_version=8,
            real_ota_version="PKJ110_11.C.65_1650_202604091920",
            real_version_name="PKJ110_16.0.5.702(CN01)",
            computed_ota_version="PKJ110_11.C.65_CN_202604091920",
            version_type_id="non_display",
            about_update_url="https://example.test/component-ota/26/05/07/update.html",
            download_url="https://example.test/update.zip",
            published_at=datetime(2026, 5, 7, tzinfo=UTC),
        ),
        discovered_by="manual",
    )

    assert refreshed.is_new is False
    assert refreshed.release.id == technical.release.id
    assert refreshed.release.real_version_name == "PKJ110_16.0.5.702(CN01)"
    assert refreshed.release.published_at == datetime(2026, 5, 7, tzinfo=UTC)
