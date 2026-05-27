from ota_backend.domain.manifest import (
    ACCEPTED_MANIFEST_CODES,
    AUTHORITATIVE_MANIFEST_TARGETS,
    get_authoritative_manifest_target,
    live_manifest_map_complete,
    manifest_blockers,
)
import pytest

from ota_backend.domain.ota import build_seed_ota_version, derive_ota_model, infer_manifest_code


def test_manifest_accepts_all_product_contract_codes():
    assert ACCEPTED_MANIFEST_CODES == (
        "00",
        "A4",
        "A5",
        "A6",
        "A7",
        "1A",
        "1B",
        "1E",
        "2C",
        "33",
        "37",
        "38",
        "39",
        "3B",
        "3C",
        "3E",
        "44",
        "51",
        "75",
        "7B",
        "82",
        "83",
        "8D",
        "97",
        "9A",
        "9E",
    )


def test_approved_live_manifest_targets_match_universal_ota_map():
    assert set(AUTHORITATIVE_MANIFEST_TARGETS) == set(ACCEPTED_MANIFEST_CODES)
    assert get_authoritative_manifest_target("00").nv_id == "00000000"
    assert get_authoritative_manifest_target("A7").nv_id == "10100111"
    assert get_authoritative_manifest_target("1B").nv_id == "00011011"
    assert get_authoritative_manifest_target("1B").server_region == 3
    assert get_authoritative_manifest_target("33").nv_id == "00110011"
    assert get_authoritative_manifest_target("38").server_region == 3
    assert get_authoritative_manifest_target("7B").nv_id == "01111011"
    assert get_authoritative_manifest_target("44").nv_id == "01000100"
    assert get_authoritative_manifest_target("44").server_region == 0
    assert get_authoritative_manifest_target("51").server_region == 0
    assert get_authoritative_manifest_target("97").nv_id == "10010111"
    assert get_authoritative_manifest_target("97").server_region == 1
    assert live_manifest_map_complete() is True
    assert manifest_blockers() == []


@pytest.mark.parametrize(
    ("product_model", "manifest_code"),
    (
        ("CPH2659EEA", "44"),
        ("CPH2659ID", "33"),
        ("CPH2659IN", "1B"),
        ("CPH2659MX", "7B"),
        ("CPH2659MY", "38"),
        ("CPH2659OCA", "A5"),
        ("CPH2659SG", "2C"),
        ("CPH2659TH", "39"),
        ("CPH2659TW", "1A"),
    ),
)
def test_catalog_suffixes_infer_find_x8_pro_manifest(product_model, manifest_code):
    assert infer_manifest_code(product_model) == manifest_code
    assert derive_ota_model(product_model) == "CPH2659"


@pytest.mark.parametrize(
    ("name", "manifest_code"),
    (
        ("OnePlus 10T (IN)", "1B"),
        ("OnePlus Nord 2 (EU)", "44"),
        ("OnePlus 10 Pro (GLO)", "A7"),
    ),
)
def test_catalog_region_label_infers_manifest_for_models_without_suffix(name, manifest_code):
    assert infer_manifest_code("CPH2413", name) == manifest_code


def test_seed_ota_version_uses_base_model_and_track():
    assert derive_ota_model("CPH2805IN") == "CPH2805"
    assert build_seed_ota_version("CPH2805IN", "H") == (
        "CPH2805_11.H.00_0000_000000000000"
    )


@pytest.mark.parametrize(
    ("product_model", "base_model"),
    (
        ("RMX5120KZ", "RMX5120"),
        ("RMX3081LK", "RMX3081"),
        ("DN2101IND", "DN2101"),
        ("IV2201_IND", "IV2201"),
    ),
)
def test_upstream_base_model_strips_catalog_aliases_without_guessing_manifest(
    product_model, base_model
):
    assert derive_ota_model(product_model) == base_model
