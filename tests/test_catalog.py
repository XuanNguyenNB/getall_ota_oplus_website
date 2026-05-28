from __future__ import annotations

import pytest

from types import SimpleNamespace
from uuid import UUID

from ota_backend.catalog import (
    CatalogImporter,
    DomesticCatalogFetch,
    LsctoolArchiveFetch,
    ReleaseArchiveImporter,
    load_domestic_cn_seed,
    parse_coloros_rom_product_rows,
    parse_default_regions_text,
    parse_lsctool_cn_catalog,
    parse_lsctool_archive,
    parse_lsctool_release_row,
    parse_oppo_cn_specs_page,
    parse_oppo_cn_specs_urls,
    parse_opposhop_product_page,
    split_product_models,
)
from ota_backend.domain.models import CatalogDeviceCandidate, Device
from ota_backend.repositories.memory import (
    InMemoryCatalogImportRepository,
    InMemoryDeviceRepository,
    InMemoryReleaseRepository,
)


def test_split_product_models_normalizes_multiple_catalog_values():
    assert split_product_models(" RMX3301, CPH2659IN ; CPH2805EU ") == [
        "RMX3301",
        "CPH2659IN",
        "CPH2805EU",
    ]


def test_split_product_models_skips_unusable_legacy_aliases():
    assert split_product_models("OnePlus6T, OnePlus 6T, ONEPLUS A6010") == [
        "ONEPLUS6T"
    ]


def test_catalog_import_normalizes_rows_infers_values_and_preserves_override():
    overridden = Device(
        id=UUID("99999999-9999-4999-8999-999999999999"),
        catalog_id=None,
        brand="oppo",
        name="Manual",
        product_model="CPH2659IN",
        manifest_code="A7",
        scan_enabled=True,
        active_track="H",
        manual_override=True,
    )
    devices = InMemoryDeviceRepository([overridden])
    imports = InMemoryCatalogImportRepository()
    importer = CatalogImporter(
        device_repository=devices,
        import_repository=imports,
        fetch_rows=lambda: [
            {"id": 1, "name": "OPPO Find X8 Pro", "product_names": "CPH2659IN", "enabled": 1},
            {"id": 5, "name": "OPPO Find X8 Pro", "product_names": "CPH2659ID, CPH2659MY", "enabled": 1},
            {"id": 2, "name": "Realme GT", "product_names": "RMX3301, RMX3840IN", "enabled": "1"},
            {"id": 6, "name": "OnePlus 10T (IN)", "product_names": "CPH2413", "enabled": 1},
            {"id": 4, "name": "OnePlus 6T", "product_names": "OnePlus6T, ONEPLUS A6010", "enabled": 1},
            {"id": 3, "name": "Old device", "product_names": "CPH9999", "enabled": 0},
        ],
    )

    summary = importer.import_oxygen()

    assert summary.fetched_count == 6
    assert summary.upserted_count == 7
    assert summary.disabled_count == 1
    assert devices.get_by_product_model("CPH2659IN").manifest_code == "A7"
    assert devices.get_by_product_model("CPH2659ID").manifest_code == "33"
    assert devices.get_by_product_model("CPH2659MY").manifest_code == "38"
    assert devices.get_by_product_model("CPH2413").manifest_code == "1B"
    assert devices.get_by_product_model("RMX3840IN").manifest_code == "1B"
    assert devices.get_by_product_model("RMX3301").brand == "realme"
    assert imports.imports[0].status == "completed"


def test_import_candidates_dry_run_does_not_write_repository():
    devices = InMemoryDeviceRepository()
    importer = CatalogImporter(
        device_repository=devices,
        import_repository=InMemoryCatalogImportRepository(),
        fetch_rows=lambda: [],
    )
    summary = importer.import_candidates(
        source="domestic_cn",
        candidates=[
            CatalogDeviceCandidate(
                catalog_id=None,
                brand="oppo",
                name="OPPO Find X8 Pro (CN)",
                product_model="PKC110",
                manifest_code="97",
                scan_enabled=True,
                source="oppo_cn_specs",
            )
        ],
        dry_run=True,
    )

    assert summary.dry_run is True
    assert summary.fetched_count == 1
    assert summary.upserted_count == 0
    assert devices.get_by_product_model("PKC110") is None


def test_import_candidates_persists_candidate_source():
    devices = InMemoryDeviceRepository()
    importer = CatalogImporter(
        device_repository=devices,
        import_repository=InMemoryCatalogImportRepository(),
        fetch_rows=lambda: [],
    )

    summary = importer.import_candidates(
        source="domestic_cn",
        candidates=[
            CatalogDeviceCandidate(
                catalog_id=None,
                brand="oppo",
                name="OPPO Find X8 Pro (CN)",
                product_model="PKC110",
                manifest_code="97",
                scan_enabled=True,
                source="oppo_cn_specs",
            )
        ],
    )

    assert summary.upserted_count == 1
    assert devices.get_by_product_model("PKC110").source == "oppo_cn_specs"


def test_parse_oppo_cn_sitemap_and_specs_page_extracts_pkc110():
    sitemap = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://www.oppo.com/cn/smartphones/series-find-x/find-x8-pro/specs/</loc></url>
      <url><loc>https://www.oppo.com/cn/about/</loc></url>
    </urlset>
    """
    html = (
        "<title>OPPO Find X8 Pro &#20135;&#21697;&#21442;&#25968; | OPPO</title>"
        "PKC110 PRISM PJ3E7P8IF"
    )

    assert parse_oppo_cn_specs_urls(sitemap) == [
        "https://www.oppo.com/cn/smartphones/series-find-x/find-x8-pro/specs/"
    ]
    candidates = parse_oppo_cn_specs_page(
        html,
        "https://www.oppo.com/cn/smartphones/series-find-x/find-x8-pro/specs/",
    )

    assert candidates[0].brand == "oppo"
    assert candidates[0].name == "OPPO Find X8 Pro (CN)"
    assert candidates[0].product_model == "PKC110"
    assert candidates[0].manifest_code == "97"
    assert candidates[0].source == "oppo_cn_specs"
    assert [candidate.product_model for candidate in candidates] == ["PKC110"]


def test_parse_coloros_rom_product_rows_extracts_domestic_model():
    candidates = parse_coloros_rom_product_rows(
        [{"productName": "OPPO Find X2 Pro", "productCode": "PDEM30"}]
    )

    assert candidates[0].name == "OPPO Find X2 Pro (CN)"
    assert candidates[0].product_model == "PDEM30"
    assert candidates[0].source == "coloros_rom"


def test_parse_opposhop_product_page_extracts_oneplus_and_realme_models():
    oneplus = parse_opposhop_product_page(
        '<title>&#19968;&#21152; Ace 5</title> related PLC999 name:"&#20837;&#32593;&#22411;&#21495;",value:["PLC110"]',
        brand="oneplus",
        source="opposhop_cn",
        url="https://www.opposhop.cn/cn/m/product/index?skuId=1",
    )
    realme = parse_opposhop_product_page(
        '<title>&#30495;&#25105;GT8 Pro</title> related RMX9999 name:"&#20837;&#32593;&#22411;&#21495;",value:["RMX5200"]',
        brand="realme",
        source="opposhop_cn",
        url="https://www.opposhop.cn/cn/web/products/1.html",
    )

    assert oneplus[0].name == "OnePlus Ace 5 (CN)"
    assert oneplus[0].product_model == "PLC110"
    assert realme[0].name == "realme GT8 Pro (CN)"
    assert realme[0].product_model == "RMX5200"


def test_parse_lsctool_cn_catalog_imports_visible_china_models():
    parsed = parse_lsctool_cn_catalog(
        device_data={
            "RMX3800": {"device_name": "REALME GT6"},
            "RMX3888": {"device_name": "REALME GT5 PRO"},
            "RMX5010": {"device_name": "REALME GT7 PRO"},
            "PKC110": {"device_name": "OPPO FIND X8 PRO"},
            "PKG110": {"device_name": "ONEPLUS ACE 5"},
            "XMI110": {"device_name": "XIAOMI 15"},
            "RMX9999": {"device_name": "REALME GLOBAL"},
        },
        default_regions_text=(
            "RMX3800 cn\n"
            "RMX3888 cn\n"
            "RMX5010 cn\n"
            "PKC110 cn\n"
            "PKG110 cn\n"
            "XMI110 cn\n"
            "RMX9999 gl\n"
        ),
    )

    by_model = {candidate.product_model: candidate for candidate in parsed.candidates}
    assert set(by_model) == {"RMX3800", "RMX3888", "RMX5010", "PKC110", "PKG110"}
    assert by_model["RMX3800"].name == "realme GT 6 (CN)"
    assert by_model["RMX3800"].brand == "realme"
    assert by_model["RMX3800"].manifest_code == "97"
    assert by_model["RMX3800"].scan_enabled is True
    assert by_model["RMX3800"].source == "lsctool_cn_catalog"
    assert by_model["PKC110"].name == "OPPO Find X8 Pro (CN)"
    assert by_model["PKG110"].name == "OnePlus Ace 5 (CN)"
    assert parsed.skipped_count == 1


def test_load_domestic_seed_validates_required_fields(tmp_path):
    path = tmp_path / "domestic.csv"
    path.write_text(
        "brand,name,product_model,manifest_code,source,source_url,scan_enabled\n"
        "oppo,OPPO Find X8 Pro (CN),PKC110,44,domestic_cn_seed,https://example.test,true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="manifest 97"):
        load_domestic_cn_seed(path)


def test_cli_domestic_dry_run_does_not_require_supabase(monkeypatch, capsys):
    from ota_backend import catalog

    monkeypatch.setattr(
        catalog,
        "fetch_domestic_cn_candidates",
        lambda timeout_seconds: DomesticCatalogFetch(
            candidates=[
                CatalogDeviceCandidate(
                    catalog_id=None,
                    brand="oppo",
                    name="OPPO Find X8 Pro (CN)",
                    product_model="PKC110",
                    manifest_code="97",
                    scan_enabled=True,
                    source="oppo_cn_specs",
                )
            ]
        ),
    )
    monkeypatch.setattr("sys.argv", ["catalog", "import-domestic-cn", "--dry-run"])

    catalog.main()

    output = capsys.readouterr().out
    assert "dry_run=true" in output
    assert "fetched=1" in output


def _lsctool_row(
    *,
    version_name: str = "PKC110_16.0.7.200(CN01)",
    ota_version: str = "PKC110_11.C.75_1750_202605052105",
    link: str = "https://component-ota-cn.allawntech.com/downloadCheck?id=1",
    region: str = "CN",
    is_gray: bool = False,
) -> dict[str, object]:
    return {
        "download_check_link": link,
        "version_name": version_name,
        "ota_version": ota_version,
        "region_code": region,
        "security_os": "2026-05-01",
        "published_time": "2026-05-25 21:04:03",
        "about_update_url": "https://example.test/about.html",
        "is_gray": is_gray,
    }


def test_parse_lsctool_archive_imports_multi_release_device_rows():
    ota_data = {
        "PKC110": [
            _lsctool_row(version_name=f"PKC110_16.0.{idx}.200(CN01)")
            for idx in range(1, 7)
        ]
    }
    device_data = {
        "PKC110": {
            "device_name": "OPPO FIND X8 PRO",
            "abbreviation": "x8p",
        }
    }

    parsed = parse_lsctool_archive(
        ota_data=ota_data,
        device_data=device_data,
        default_regions_text="PKC110 cn",
    )

    assert len(parsed.devices) == 1
    assert parsed.devices[0].name == "OPPO Find X8 Pro"
    assert len(parsed.releases) == 6
    assert {release.manifest_code for release in parsed.releases} == {"97"}
    assert {release.region_code for release in parsed.releases} == {"CN"}
    assert {release.source for release in parsed.releases} == {"lsctool_archive"}


def test_parse_lsctool_archive_keeps_official_and_beta_downloadcheck_links():
    ota_data = {
        "PKG110": [
            _lsctool_row(
                version_name="PKG110_16.0.3.500(CN01)",
                ota_version="PKG110_11.F.32_2320_202601090217",
                link="https://component-ota-cn.allawntech.com/downloadCheck?id=official",
            ),
            _lsctool_row(
                version_name="PKG110_16.0.3.500(CN01)",
                ota_version="PKG110_11.F.32_2320_202601090217",
                link="https://component-ota-gray.coloros.com/downloadCheck?id=beta",
                is_gray=True,
            ),
        ]
    }
    device_data = {"PKG110": {"device_name": "ONEPLUS ACE 5"}}

    parsed = parse_lsctool_archive(ota_data=ota_data, device_data=device_data)

    assert [release.release_type for release in parsed.releases] == ["official", "beta"]
    assert all("downloadCheck" in release.download_url for release in parsed.releases)
    assert {release.ota_track for release in parsed.releases} == {"F"}


def test_parse_lsctool_release_row_skips_invalid_rows_and_maps_manifest():
    assert parse_default_regions_text("PKC110 cn\nCPH2585 in\nCPH2651 th") == {
        "PKC110": "CN",
        "CPH2585": "IN",
        "CPH2651": "TH",
    }
    cn = parse_lsctool_release_row(
        _lsctool_row(region="CN"),
        product_model="PKC110",
        brand="oppo",
    )
    in_row = parse_lsctool_release_row(
        _lsctool_row(
            version_name="CPH2585_15.0.0.870(EX01)",
            ota_version="CPH2585_11.A.48_1480_202509281425",
            region="IN",
        ),
        product_model="CPH2585",
        brand="oppo",
    )
    th = parse_lsctool_release_row(
        _lsctool_row(
            version_name="CPH2651_15.0.0.860(EX01)",
            ota_version="CPH2651_11.A.49_0490_202508282004",
            region="TH",
        ),
        product_model="CPH2651",
        brand="oppo",
    )

    assert cn is not None and cn.manifest_code == "97"
    assert in_row is not None and in_row.manifest_code == "1B"
    assert th is not None and th.manifest_code == "39"
    assert parse_lsctool_release_row(
        _lsctool_row(link=""),
        product_model="PKC110",
        brand="oppo",
    ) is None
    assert parse_lsctool_release_row(
        _lsctool_row(region="UNKNOWN"),
        product_model="PKC110",
        brand="oppo",
    ) is None


def test_lsctool_archive_importer_creates_missing_devices_and_updates_track_state():
    devices = InMemoryDeviceRepository([])
    releases = InMemoryReleaseRepository()
    importer = ReleaseArchiveImporter(
        device_repository=devices,
        release_repository=releases,
        import_repository=InMemoryCatalogImportRepository(),
    )
    archive = LsctoolArchiveFetch(
        devices=[
            CatalogDeviceCandidate(
                catalog_id=None,
                brand="oppo",
                name="OPPO Find X8 Pro",
                product_model="PKC110",
                manifest_code="97",
                scan_enabled=False,
                source="lsctool_archive",
            )
        ],
        releases=[
            parse_lsctool_release_row(
                _lsctool_row(),
                product_model="PKC110",
                brand="oppo",
            ),
            parse_lsctool_release_row(
                _lsctool_row(
                    version_name="PKC110_16.0.9.100(CN01)",
                    ota_version="PKC110_11.H.80_1800_202606010000",
                ),
                product_model="PKC110",
                brand="oppo",
            ),
        ],
    )

    summary = importer.import_lsctool_archive(archive)
    device = devices.get_by_product_model("PKC110")

    assert summary.upserted_count == 2
    assert device is not None
    assert device.scan_enabled is True
    assert device.source == "lsctool_cn_catalog"
    assert device.active_track == "H"
    assert device.bootstrap_done is True
    assert releases.list_releases(product_model="PKC110").total == 2


def test_lsctool_archive_importer_keeps_non_cn_archive_devices_hidden():
    devices = InMemoryDeviceRepository([])
    releases = InMemoryReleaseRepository()
    importer = ReleaseArchiveImporter(
        device_repository=devices,
        release_repository=releases,
        import_repository=InMemoryCatalogImportRepository(),
    )
    archive = LsctoolArchiveFetch(
        devices=[
            CatalogDeviceCandidate(
                catalog_id=None,
                brand="oneplus",
                name="OnePlus 15 (GLO)",
                product_model="CPH2747",
                manifest_code="A7",
                scan_enabled=False,
                source="lsctool_archive",
            )
        ],
        releases=[
            parse_lsctool_release_row(
                _lsctool_row(
                    version_name="CPH2747_16.0.5.703(EX01)",
                    ota_version="CPH2747_11.A.33_0330_202604102049",
                    region="GL",
                ),
                product_model="CPH2747",
                brand="oneplus",
            )
        ],
    )

    importer.import_lsctool_archive(archive)
    device = devices.get_by_product_model("CPH2747")

    assert device is not None
    assert device.scan_enabled is False
    assert device.source == "lsctool_archive"


def test_lsctool_archive_routes_region_rows_to_existing_variant_device():
    devices = InMemoryDeviceRepository(
        [
            Device(
                id=UUID("11111111-1111-4111-8111-111111111111"),
                catalog_id=1,
                brand="oneplus",
                name="OnePlus 15 (GLO)",
                product_model="CPH2747",
                manifest_code="A7",
                scan_enabled=True,
                active_track="A",
            ),
            Device(
                id=UUID("22222222-2222-4222-8222-222222222222"),
                catalog_id=2,
                brand="oneplus",
                name="OnePlus 15 (EU)",
                product_model="CPH2747EEA",
                manifest_code="44",
                scan_enabled=True,
                active_track="A",
            ),
        ]
    )
    releases = InMemoryReleaseRepository()
    importer = ReleaseArchiveImporter(
        device_repository=devices,
        release_repository=releases,
        import_repository=InMemoryCatalogImportRepository(),
    )
    archive = LsctoolArchiveFetch(
        devices=[],
        releases=[
            parse_lsctool_release_row(
                _lsctool_row(
                    version_name="CPH2747_16.0.5.703(EX01)",
                    ota_version="CPH2747_11.A.33_0330_202604102049",
                    region="EEA",
                ),
                product_model="CPH2747",
                brand="oneplus",
            )
        ],
    )

    importer.import_lsctool_archive(archive)

    assert releases.list_releases(product_model="CPH2747").total == 0
    page = releases.list_releases(product_model="CPH2747EEA")
    assert page.total == 1
    assert page.items[0].manifest_code == "44"
    assert page.items[0].region_code == "EEA"


def test_cli_lsctool_archive_dry_run_does_not_require_supabase(monkeypatch, capsys):
    from ota_backend import catalog

    monkeypatch.setattr(
        catalog,
        "fetch_lsctool_archive",
        lambda timeout_seconds: LsctoolArchiveFetch(
            devices=[],
            releases=[
                parse_lsctool_release_row(
                    _lsctool_row(),
                    product_model="PKC110",
                    brand="oppo",
                )
            ],
            skipped_count=2,
        ),
    )
    monkeypatch.setattr("sys.argv", ["catalog", "import-lsctool-archive", "--dry-run"])

    catalog.main()

    output = capsys.readouterr().out
    assert "command=import-lsctool-archive" in output
    assert "dry_run=true" in output
    assert "fetched=1" in output
    assert "skipped=2" in output


def test_cli_import_all_runs_oxygen_domestic_and_archive(monkeypatch, capsys):
    from ota_backend import catalog

    devices = InMemoryDeviceRepository([])
    releases = InMemoryReleaseRepository()
    imports = InMemoryCatalogImportRepository()
    app = SimpleNamespace(
        state=SimpleNamespace(
            device_repository=devices,
            release_repository=releases,
            catalog_import_repository=imports,
        )
    )
    monkeypatch.setattr(
        catalog,
        "get_settings",
        lambda: SimpleNamespace(
            repository_backend="supabase",
            realme_ota_timeout_seconds=30,
        ),
    )
    monkeypatch.setattr(catalog, "create_app", lambda settings: app)
    monkeypatch.setattr(
        catalog,
        "fetch_oxygen_rows",
        lambda timeout_seconds: [
            {
                "id": 1,
                "name": "OPPO Find X8 Pro",
                "product_names": "CPH2659IN",
                "enabled": 1,
            }
        ],
    )
    monkeypatch.setattr(
        catalog,
        "fetch_domestic_cn_candidates",
        lambda timeout_seconds: DomesticCatalogFetch(
            candidates=[
                CatalogDeviceCandidate(
                    catalog_id=None,
                    brand="realme",
                    name="realme GT 6 (CN)",
                    product_model="RMX3800",
                    manifest_code="97",
                    scan_enabled=True,
                    source="lsctool_cn_catalog",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        catalog,
        "fetch_lsctool_archive",
        lambda timeout_seconds: LsctoolArchiveFetch(
            devices=[],
            releases=[
                parse_lsctool_release_row(
                    _lsctool_row(
                        version_name="RMX3800_16.0.5.740(CN01)",
                        ota_version="RMX3800_11.F.28_2280_202604141141",
                    ),
                    product_model="RMX3800",
                    brand="realme",
                )
            ],
        ),
    )
    monkeypatch.setattr("sys.argv", ["catalog", "import-all"])

    catalog.main()

    output = capsys.readouterr().out
    assert output.index("command=import-oxygen") < output.index("command=import-domestic-cn")
    assert output.index("command=import-domestic-cn") < output.index("command=import-lsctool-archive")
    assert devices.get_by_product_model("RMX3800").scan_enabled is True
    assert releases.list_releases(product_model="RMX3800").total == 1
