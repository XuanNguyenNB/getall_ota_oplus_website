from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPO_ROOT / "validation-artifacts" / "phase2-web-ui"
REALBROWSER_MJS = Path(
    os.environ.get(
        "REALBROWSER_SCRIPT",
        r"C:\Users\XuanNguyen\.codex\skills\realbrowser\scripts\realbrowser.mjs",
    )
)
STORY_ID = "PHASE2-WEB-UI"
VALIDATION_DOC = (
    REPO_ROOT
    / "docs"
    / "stories"
    / "epics"
    / "E02-web-ui"
    / "PHASE2-WEB-UI"
    / "validation.md"
)
START_MARKER = "<!-- PHASE2-LOCAL-VALIDATION:BEGIN -->"
END_MARKER = "<!-- PHASE2-LOCAL-VALIDATION:END -->"


class ValidationError(RuntimeError):
    pass


def now_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(
    url: str, timeout_seconds: float, server: subprocess.Popen[str]
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise ValidationError(
                f"FastAPI exited before readiness with code {server.returncode}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                body = json.loads(response.read().decode("utf-8"))
                if (
                    response.status == 200
                    and body.get("ok") is True
                    and server.poll() is None
                ):
                    return body
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise ValidationError(f"FastAPI did not become ready at {url}: {last_error}")


def run_command(
    args: list[str],
    *,
    env: dict[str, str],
    artifacts: Path,
    commands: list[dict[str, Any]],
    timeout: int = 60,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    result: subprocess.CompletedProcess[str] | None = None
    timed_out = False
    try:
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        result = subprocess.CompletedProcess(
            args,
            124,
            stdout=(exc.stdout or ""),
            stderr=(exc.stderr or f"timed out after {timeout}s"),
        )

    entry = {
        "args": args,
        "returncode": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": timed_out,
    }
    commands.append(entry)
    with (artifacts / "realbrowser-commands.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")

    if check and result.returncode != 0:
        raise ValidationError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stderr}"
        )
    return result


def run_rebrowser(
    rb_args: list[str],
    *,
    env: dict[str, str],
    artifacts: Path,
    commands: list[dict[str, Any]],
    session: str,
    timeout: int = 60,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    args = ["node", str(REALBROWSER_MJS), *rb_args]
    if "--anonymous" not in rb_args:
        args.extend(["--anonymous", "--session", session])
    return run_command(
        args,
        env=env,
        artifacts=artifacts,
        commands=commands,
        timeout=timeout,
        check=check,
    )


def start_server(port: int, artifacts: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else src_path + os.pathsep + env["PYTHONPATH"]
    )
    env["OTA_PROVIDER"] = "fake"
    env["REPOSITORY_BACKEND"] = "memory"
    env["ALLOW_LIVE_OTA"] = "false"
    out = (artifacts / "uvicorn.out.log").open("w", encoding="utf-8")
    err = (artifacts / "uvicorn.err.log").open("w", encoding="utf-8")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ota_backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=out,
        stderr=err,
        text=True,
    )


def stop_server(server: subprocess.Popen[str], timeout: int = 8) -> dict[str, Any]:
    if server.poll() is not None:
        return {"pid": server.pid, "already_exited": True, "returncode": server.returncode}
    server.terminate()
    try:
        server.wait(timeout=timeout)
        return {"pid": server.pid, "terminated": True, "returncode": server.returncode}
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=timeout)
        return {"pid": server.pid, "killed": True, "returncode": server.returncode}


def assert_contains(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise ValidationError(f"{path} is missing expected text: {missing}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_network(network_path: Path, initial_network_path: Path) -> None:
    entries = load_json(network_path)
    initial_entries = load_json(initial_network_path)
    combined = [*initial_entries, *entries]
    seen = {
        (
            str(entry.get("method")),
            int(entry.get("status", 0) or 0),
            str(entry.get("url")),
        )
        for entry in combined
    }

    required = [
        ("GET", 200, "/api/health"),
        ("GET", 200, "/api/devices"),
        ("GET", 200, "/api/releases"),
        ("POST", 200, "/api/ota"),
        ("POST", 404, "/api/ota"),
    ]
    missing: list[str] = []
    for method, status, fragment in required:
        if not any(
            row_method == method and row_status == status and fragment in row_url
            for row_method, row_status, row_url in seen
        ):
            missing.append(f"{method} {fragment} {status}")
    if missing:
        raise ValidationError(f"network proof missing expected calls: {missing}")


def assert_console(console_path: Path) -> None:
    console = load_json(console_path)
    messages = console if isinstance(console, list) else []
    errors = [
        message
        for message in messages
        if str(message.get("type") or message.get("level") or "").lower()
        in {"error", "exception"}
    ]
    if errors:
        raise ValidationError(f"unexpected console errors: {errors}")


def write_latest_doc(summary: dict[str, Any]) -> None:
    artifact_rel = summary["artifact_dir"]
    run_id = summary["run_id"]
    block = f"""{START_MARKER}
## Automated Local Validation

Single command:

```powershell
python scripts/validate_phase2_ui.py
```

Latest result:

- Run: `{run_id}`
- Status: `{summary["status"]}`
- Artifacts: `{artifact_rel}`
- Browser proof: `initial.png`, `success.png`, `after-success.txt`, `after-copy.txt`, `after-error.txt`, `initial-network.json`, `network-list.json`, `network.har`, `console-list.json`
- Server proof: `uvicorn.out.log`, `uvicorn.err.log`
- Harness proof: story `{STORY_ID}` is updated by the validation command after a passing run.

{END_MARKER}"""

    current = VALIDATION_DOC.read_text(encoding="utf-8")
    if START_MARKER in current and END_MARKER in current:
        before = current.split(START_MARKER, 1)[0].rstrip()
        after = current.split(END_MARKER, 1)[1].lstrip()
        updated = f"{before}\n\n{block}\n\n{after}".rstrip() + "\n"
    else:
        updated = current.rstrip() + "\n\n" + block + "\n"
    VALIDATION_DOC.write_text(updated, encoding="utf-8")


def run_harness(
    args: list[str],
    *,
    env: dict[str, str],
    artifacts: Path,
    commands: list[dict[str, Any]],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        ["bash", "scripts/harness", *args],
        env=env,
        artifacts=artifacts,
        commands=commands,
        timeout=30,
        check=check,
    )


def update_harness(summary: dict[str, Any], env: dict[str, str], artifacts: Path, commands: list[dict[str, Any]]) -> None:
    evidence = (
        "python scripts/validate_phase2_ui.py passed; "
        f"artifacts: {summary['artifact_dir']}; "
        "realbrowser smoke covered device load, OTA success, release refresh, copy URL, "
        "OTA_NOT_FOUND error state, console list, network list, HAR, and screenshots."
    )
    run_harness(
        [
            "story",
            "update",
            "--id",
            STORY_ID,
            "--status",
            "implemented",
            "--integration",
            "1",
            "--e2e",
            "1",
            "--platform",
            "1",
            "--evidence",
            evidence,
        ],
        env=env,
        artifacts=artifacts,
        commands=commands,
    )
    run_harness(
        [
            "trace",
            "--summary",
            "Automated Phase 2 FastAPI UI local validation loop",
            "--story",
            STORY_ID,
            "--agent",
            "codex",
            "--outcome",
            "completed",
            "--actions",
            "start FastAPI,run realbrowser smoke,capture artifacts,update story evidence,stop FastAPI",
            "--changed",
            "validation-artifacts,docs/stories/epics/E02-web-ui/PHASE2-WEB-UI/validation.md,harness story evidence",
            "--notes",
            evidence,
        ],
        env=env,
        artifacts=artifacts,
        commands=commands,
    )


def run_validation(port: int | None) -> dict[str, Any]:
    if not REALBROWSER_MJS.exists():
        raise ValidationError(f"realbrowser script not found: {REALBROWSER_MJS}")
    if not shutil.which("node"):
        raise ValidationError("node is required to run realbrowser")
    if not shutil.which("bash"):
        raise ValidationError("bash is required to run scripts/harness on this Windows repo")

    run_id = now_run_id()
    artifacts = ARTIFACT_ROOT / run_id
    artifacts.mkdir(parents=True, exist_ok=False)
    commands: list[dict[str, Any]] = []
    selected_port = port or find_free_port()
    base_url = f"http://127.0.0.1:{selected_port}"
    health_url = f"{base_url}/api/health"
    session = f"phase2-ui-validation-{run_id.lower()}"
    env = os.environ.copy()
    env["REALBROWSER_OWNER"] = session

    summary: dict[str, Any] = {
        "run_id": run_id,
        "status": "running",
        "artifact_dir": str(artifacts.relative_to(REPO_ROOT)).replace("\\", "/"),
        "base_url": base_url,
        "server_cleanup": None,
        "browser_cleanup": [],
    }

    server = start_server(selected_port, artifacts)
    summary["server_pid"] = server.pid

    try:
        health = wait_for_health(health_url, 25, server)
        (artifacts / "health.json").write_text(
            json.dumps(health, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        run_rebrowser(
            ["tab", "ensure", f"{base_url}/", "--label", "phase2ui", "--background"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["wait", "ready", "-t", "phase2ui", "--visual-stable", "--timeout", "10000"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            timeout=20,
        )
        run_rebrowser(
            [
                "network",
                "list",
                "-t",
                "phase2ui",
                "--filter",
                "/api/",
                "--json",
                "--out",
                str(artifacts / "initial-network.json"),
            ],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["read", "tree", "-t", "phase2ui", "-i", "-c", "--out", str(artifacts / "initial-tree.txt")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["screenshot", "capture", "-t", "phase2ui", str(artifacts / "initial.png")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            timeout=40,
        )
        run_rebrowser(
            ["action", "click", "-t", "phase2ui", '[data-model="RMX3301"]'],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["action", "submit", "-t", "phase2ui", "--root", "active", "--text", "Find OTA"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["wait", "ready", "-t", "phase2ui", "--visual-stable", "--timeout", "10000"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            timeout=20,
        )
        run_rebrowser(
            ["read", "text", "-t", "phase2ui", "--selector", "main", "--out", str(artifacts / "after-success.txt")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["screenshot", "capture", "-t", "phase2ui", str(artifacts / "success.png")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            timeout=40,
        )
        run_rebrowser(
            ["action", "click", "-t", "phase2ui", "#refreshButton"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["wait", "ready", "-t", "phase2ui", "--visual-stable", "--timeout", "10000"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            timeout=20,
        )
        run_rebrowser(
            ["action", "click", "-t", "phase2ui", "#copyResultButton"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["read", "text", "-t", "phase2ui", "--out", str(artifacts / "after-copy.txt")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["state", "clipboard", "read", "-t", "phase2ui", "--values"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            check=False,
        )
        (artifacts / "clipboard.txt").write_text(
            commands[-1].get("stdout", ""),
            encoding="utf-8",
        )
        run_rebrowser(
            ["action", "fill", "-t", "phase2ui", "#productModel", "NOFIXTURE"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["action", "submit", "-t", "phase2ui", "--root", "active", "--text", "Find OTA"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["wait", "ready", "-t", "phase2ui", "--visual-stable", "--timeout", "10000"],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
            timeout=20,
        )
        run_rebrowser(
            ["read", "text", "-t", "phase2ui", "--selector", "main", "--out", str(artifacts / "after-error.txt")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["network", "list", "-t", "phase2ui", "--filter", "/api/", "--json", "--out", str(artifacts / "network-list.json")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["console", "list", "-t", "phase2ui", "--limit", "100", "--json", "--out", str(artifacts / "console-list.json")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )
        run_rebrowser(
            ["network", "export", "-t", "phase2ui", "--format", "har", "--out", str(artifacts / "network.har")],
            env=env,
            artifacts=artifacts,
            commands=commands,
            session=session,
        )

        assert_contains(
            artifacts / "after-success.txt",
            [
                "RMX3301_15.0.0.1410(EX01)",
                "RMX3301_11.H.21_4210_202602281641",
                "https://example.com/update.zip",
                "1 persisted release",
            ],
        )
        assert_contains(artifacts / "after-error.txt", ["OTA_NOT_FOUND: No OTA release found."])
        assert_contains(artifacts / "after-copy.txt", ["Download URL copied"])
        assert_network(artifacts / "network-list.json", artifacts / "initial-network.json")
        assert_console(artifacts / "console-list.json")

        summary["status"] = "passed"
        write_latest_doc(summary)
        update_harness(summary, env, artifacts, commands)
        return summary
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = str(exc)
        raise
    finally:
        for cleanup_args in (
            ["tab", "done", "--close", "--anonymous", "--session", session],
            ["session", "stop", session],
        ):
            try:
                cleanup = run_command(
                    ["node", str(REALBROWSER_MJS), *cleanup_args],
                    env=env,
                    artifacts=artifacts,
                    commands=commands,
                    timeout=30,
                    check=False,
                )
                summary["browser_cleanup"].append(
                    {"args": cleanup_args, "returncode": cleanup.returncode}
                )
            except Exception as cleanup_exc:
                summary["browser_cleanup"].append(
                    {"args": cleanup_args, "error": str(cleanup_exc)}
                )

        summary["server_cleanup"] = stop_server(server)
        (artifacts / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (ARTIFACT_ROOT / "latest.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local Phase 2 FastAPI UI realbrowser validation loop."
    )
    parser.add_argument("--port", type=int, default=None, help="Port to bind FastAPI on.")
    args = parser.parse_args()

    try:
        summary = run_validation(args.port)
    except Exception as exc:
        print(f"Phase 2 UI validation failed: {exc}", file=sys.stderr)
        return 1

    print("Phase 2 UI validation passed.")
    print(f"Artifacts: {summary['artifact_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
