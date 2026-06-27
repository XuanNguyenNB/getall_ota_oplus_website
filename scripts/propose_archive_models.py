"""Propose archive candidates to cut live OTA scan volume.

Read-only. Run inside the web container (Supabase env vars present):
    sudo docker cp scripts/propose_archive_models.py <web>:/tmp/propose.py
    sudo docker exec <web> python /tmp/propose.py > archive_candidates.txt

Writes the candidate list to stdout in a format the worker accepts:
    PRODUCT_MODEL  # brand / manifest / name / reason
Lines beginning with '#' are comments (ignored by --archive-models).

A candidate is a scan-enabled variant that EITHER never produced a live
release OR whose newest live release is older than STALE_MONTHS. Variants
under manifests targeted by the region-suffix fix (1B India, 44 EU) that have
no release yet are held back into a separate "WAIT FOR REGION FIX" section
instead of being proposed, so the operator does not archive devices the fix
is expected to rescue.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from ota_backend.config import get_settings
from ota_backend.repositories.supabase import create_supabase_client

STALE_MONTHS = 18
REGION_FIX_MANIFESTS = {"1B", "44"}
NOW = datetime.now(timezone.utc)


def fetch_all(client, table, columns):
    rows = []
    page = 0
    size = 1000
    while True:
        resp = (
            client.table(table)
            .select(columns)
            .range(page * size, page * size + size - 1)
            .execute()
        )
        data = getattr(resp, "data", None) or []
        rows.extend(data)
        if len(data) < size:
            break
        page += 1
    return rows


def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main():
    client = create_supabase_client(get_settings())
    devices = fetch_all(
        client,
        "devices",
        "product_model,manifest_code,scan_enabled,name,brand,scan_group_name",
    )
    releases = fetch_all(
        client, "ota_releases", "product_model,manifest_code,source,published_at,discovered_at"
    )

    newest = {}
    for r in releases:
        if r.get("source") != "live_provider":
            continue
        dt = parse_dt(r.get("published_at")) or parse_dt(r.get("discovered_at"))
        if dt is None:
            continue
        key = (r["product_model"].upper(), r.get("manifest_code"))
        if key not in newest or dt > newest[key]:
            newest[key] = dt

    candidates = defaultdict(list)  # group_name -> [(model, line)]
    waiting = []
    for d in devices:
        if not d.get("scan_enabled"):
            continue
        model = d["product_model"].upper()
        manifest = d.get("manifest_code")
        key = (model, manifest)
        last = newest.get(key)
        if last is None:
            if manifest in REGION_FIX_MANIFESTS:
                waiting.append((model, manifest, d.get("name")))
                continue
            reason = "never-live"
        else:
            months = (NOW - last).days / 30.4
            if months < STALE_MONTHS:
                continue
            reason = f"{int(months)}mo-stale"
        group = d.get("scan_group_name") or "(ungrouped)"
        line = f"{model}  # {d.get('brand')} / {manifest} / {d.get('name')} / {reason}"
        candidates[group].append((model, line))

    total = sum(len(v) for v in candidates.values())
    print(f"# Archive candidates: {total} variants "
          f"(never-live or >{STALE_MONTHS}mo stale, excluding region-fix manifests)")
    print(f"# Generated {NOW.date()} -- review and delete any line you do NOT want archived.")
    print(f"# Feed to: python -m ota_backend.worker --archive-models <this-file> --dry-run")
    print()
    for group in sorted(candidates, key=lambda g: g.lower()):
        rows = sorted(candidates[group])
        print(f"# === {group} ({len(rows)}) ===")
        for _model, line in rows:
            print(line)
        print()

    if waiting:
        print(f"# === WAIT FOR REGION FIX: {len(waiting)} variants on manifest "
              f"{'/'.join(sorted(REGION_FIX_MANIFESTS))} with no release yet ===")
        print("# Do NOT archive these until the region-suffix fix has run >=1 cycle.")
        for model, manifest, name in sorted(waiting):
            print(f"# {model}  ({manifest} / {name})")


if __name__ == "__main__":
    main()
