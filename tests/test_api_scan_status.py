from fastapi.testclient import TestClient

from ota_backend.app import create_app
from ota_backend.repositories.memory import InMemoryDeviceRepository
from ota_backend.services.scanner import ScannerService
from ota_backend.domain.scanner import stable_scan_shard


def test_scan_status_returns_empty_state():
    client = TestClient(create_app())

    response = client.get("/api/scan/status")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "latest_run": None}


def test_scan_status_returns_latest_run_shape():
    app = create_app(device_repository=InMemoryDeviceRepository())
    device = app.state.device_repository.get_by_product_model("RMX3301")
    service = ScannerService(
        device_repository=app.state.device_repository,
        release_repository=app.state.release_repository,
        scan_repository=app.state.scan_repository,
        telegram_repository=app.state.telegram_repository,
        provider=app.state.ota_provider,
    )
    assert device is not None
    service.run_scheduled_scan(cycle_day=stable_scan_shard(device.product_model))
    client = TestClient(app)

    response = client.get("/api/scan/status")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert set(body["latest_run"]) == {
        "id",
        "status",
        "cycle_day",
        "started_at",
        "completed_tasks",
        "failed_tasks",
        "pending_tasks",
    }
    assert body["latest_run"]["status"] == "completed"
    assert body["latest_run"]["completed_tasks"] == 1
    assert body["latest_run"]["pending_tasks"] == 0
