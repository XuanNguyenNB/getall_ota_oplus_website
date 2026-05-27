from pathlib import Path


def test_compose_uses_correct_entrypoints_and_does_not_publish_web_origin():
    compose = Path("compose.yaml").read_text()

    assert 'command: ["python", "-m", "ota_backend.telegram_bot"]' in compose
    assert 'profiles: ["bot"]' in compose
    assert 'command: ["python", "-m", "ota_backend.worker", "--once"]' in compose
    assert 'profiles: ["jobs"]' in compose
    assert "cloudflared:" in compose
    assert "condition: service_healthy" in compose
    assert "ports:" not in compose


def test_worker_timer_uses_one_shot_command_under_overlap_lock():
    service = Path("deploy/systemd/ota-worker.service").read_text()
    timer = Path("deploy/systemd/ota-worker.timer").read_text()

    assert "flock -n /run/ota-worker.lock" in service
    assert "docker compose --profile jobs run --rm worker" in service
    assert "run --rm worker --once" not in service
    assert "OnCalendar=" in timer


def test_ci_keeps_live_services_out_of_automated_proof():
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert "python -m pytest" in workflow
    assert "python -m compileall -q src tests" in workflow
    assert "cp .env.example .env" in workflow
    assert "docker compose config --quiet" in workflow
    assert "ALLOW_LIVE_OTA=true" not in workflow
