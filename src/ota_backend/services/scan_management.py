from __future__ import annotations

from dataclasses import dataclass

from ota_backend.domain.models import Brand, Device
from ota_backend.domain.ota import normalize_product_model
from ota_backend.repositories.interfaces import DeviceRepository


@dataclass(frozen=True)
class ScanGroup:
    key: str
    name: str
    brand: Brand
    variants: list[Device]

    @property
    def enabled_count(self) -> int:
        return sum(1 for device in self.variants if device.scan_enabled)


class ScanManagementService:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def search(self, query: str, *, limit: int = 200) -> list[ScanGroup]:
        page = self._repository.list_devices(
            q=query,
            brand=None,
            enabled_only=True,
            limit=limit,
            offset=0,
        )
        return group_devices(page.items)

    def enable_group(self, scan_group_key: str, enabled: bool) -> list[Device]:
        devices = self._repository.list_devices_by_scan_group(scan_group_key)
        candidates = [
            device.product_model
            for device in devices
            if device.manifest_code is not None or not enabled
        ]
        return self._repository.set_scan_enabled(candidates, enabled) if candidates else []

    def set_models(
        self, product_models: list[str], enabled: bool
    ) -> tuple[list[Device], list[str], list[str]]:
        known: list[str] = []
        missing: list[str] = []
        without_manifest: list[str] = []
        for value in product_models:
            try:
                model = normalize_product_model(value)
            except ValueError:
                missing.append(value)
                continue
            device = self._repository.get_by_product_model(model)
            if device is None:
                missing.append(model)
                continue
            if enabled and device.manifest_code is None:
                without_manifest.append(model)
                continue
            known.append(model)
        updated = self._repository.set_scan_enabled(known, enabled) if known else []
        return updated, missing, without_manifest

    def list_enabled_groups(
        self, *, brand: str | None = None, limit: int = 1000
    ) -> list[ScanGroup]:
        devices: list[Device] = []
        offset = 0
        while len(devices) < limit:
            page = self._repository.list_scan_enabled_devices(
                brand=brand,
                limit=min(200, limit - len(devices)),
                offset=offset,
            )
            devices.extend(page.items)
            offset += len(page.items)
            if not page.items or offset >= page.total:
                break
        return group_devices(devices)

    def disable_all(self) -> int:
        return self._repository.set_all_scan_enabled(False)

    def enabled_count(self) -> int:
        return self._repository.count_scan_enabled()


def group_devices(devices: list[Device]) -> list[ScanGroup]:
    grouped: dict[str, ScanGroup] = {}
    for device in sorted(
        devices,
        key=lambda item: (item.scan_group_name.lower(), item.product_model),
    ):
        group = grouped.get(device.scan_group_key)
        if group is None:
            grouped[device.scan_group_key] = ScanGroup(
                key=device.scan_group_key,
                name=device.scan_group_name,
                brand=device.brand,
                variants=[device],
            )
        else:
            group.variants.append(device)
    return list(grouped.values())


def format_scan_groups(groups: list[ScanGroup], *, title: str, max_groups: int = 10) -> str:
    if not groups:
        return f"{title}\nNo matching scan groups."
    lines = [title]
    for group in groups[:max_groups]:
        lines.append(f"{group.name}: {group.enabled_count}/{len(group.variants)} variants ON")
        lines.append(f"Key: {group.key}")
        for device in group.variants[:8]:
            status = "ON" if device.scan_enabled else "OFF"
            manifest = device.manifest_code or "manifest needed"
            lines.append(f"- {device.product_model} {manifest} {status}")
        if len(group.variants) > 8:
            lines.append(f"- ...and {len(group.variants) - 8} more variants")
    if len(groups) > max_groups:
        lines.append(f"...and {len(groups) - max_groups} more groups")
    return "\n".join(lines)


def format_scan_update(
    *,
    action: str,
    updated: list[Device],
    missing: list[str] | None = None,
    without_manifest: list[str] | None = None,
) -> str:
    groups = group_devices(updated)
    lines = [f"Scan {action}: {len(updated)} variants updated"]
    if groups:
        lines.append(format_scan_groups(groups, title="Updated groups"))
    if missing:
        lines.append("Missing/invalid: " + ", ".join(missing[:20]))
    if without_manifest:
        lines.append("Skipped without manifest: " + ", ".join(without_manifest[:20]))
    return "\n".join(lines)


def scan_help() -> str:
    return "\n".join(
        (
            "Scan management commands",
            "/scan search <query>",
            "/scan on-group <scan_group_key>",
            "/scan off-group <scan_group_key>",
            "/scan on <model...>",
            "/scan off <model...>",
            "/scan list on [oppo|realme|oneplus]",
            "/scan off-all CONFIRM",
            "/notify backfill-run <scan_run_id> [limit]",
        )
    )
