from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.config import Settings
from ota_backend.domain.models import EdlRom
from ota_backend.repositories.memory import InMemoryEdlRomRepository


def _edl_rom(
    *,
    product_model: str = "PKB110",
    version_name: str = "PKB110_16.0.7.200(CN01)",
    region_code: str = "CN",
    build_date: datetime = datetime(2026, 5, 27, 17, 43, tzinfo=UTC),
) -> EdlRom:
    return EdlRom(
        id=uuid4(),
        brand="oppo",
        product_model=product_model,
        device_name="OPPO Find X8",
        region_code=region_code,
        version_name=version_name,
        build_date=build_date,
        download_url=f"https://example.test/{version_name}.zip",
        source="lsctool_edl",
        source_updated_at=datetime(2026, 5, 28, 2, 6, tzinfo=UTC),
        raw_response={"source": "lsctool_edl"},
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
        updated_at=datetime(2026, 5, 28, tzinfo=UTC),
    )


def test_edl_roms_empty_page_shape(client):
    response = client.get("/api/edl-roms")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "count": 0,
        "total": 0,
        "limit": 50,
        "offset": 0,
        "roms": [],
    }


def test_edl_roms_filter_and_sort_by_build_date():
    repository = InMemoryEdlRomRepository(
        [
            _edl_rom(
                version_name="PKB110_15.0.0.124(CN01)",
                build_date=datetime(2025, 10, 1, tzinfo=UTC),
            ),
            _edl_rom(
                version_name="PKB110_16.0.7.200(CN01)",
                build_date=datetime(2026, 5, 27, tzinfo=UTC),
            ),
        ]
    )
    app = create_app(settings=Settings(), edl_rom_repository=repository)
    client = TestClient(app)

    response = client.get(
        "/api/edl-roms",
        params={"product_model": "PKB110", "region_code": "CN", "q": "16.0", "sort": "build"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["roms"][0]["product_model"] == "PKB110"
    assert body["roms"][0]["version_name"] == "PKB110_16.0.7.200(CN01)"
    assert body["roms"][0]["region_code"] == "CN"
    assert body["roms"][0]["source"] == "lsctool_edl"
