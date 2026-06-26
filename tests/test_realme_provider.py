from __future__ import annotations

import json
from datetime import timezone

import httpx
import pytest

from ota_backend.config import Settings
from ota_backend.domain.models import OtaQuery
from ota_backend.providers.interfaces import OtaNotFoundError, OtaProviderTimeoutError
from ota_backend.providers.realme import RealmeOtaProvider


class Response:
    content = json.dumps({"body": "encrypted"}).encode()
    status_code = 200


class Request:
    constructions: list[dict[str, object]] = []
    decrypted: dict[str, object] = {}
    resp_key = "body"
    body = "encrypted-request"
    headers = {"protectedKey": "redacted-at-boundary"}
    url = "https://component-otapc-eu.allawnos.com/update/v3"

    def __init__(self, **kwargs):
        self.constructions.append(kwargs)

    def set_vars(self):
        return None

    def set_body_headers(self):
        return self.body, self.headers, {}

    def validate_response(self, response):
        assert response.status_code == 200

    def decrypt(self, _value):
        return json.dumps(self.decrypted)


def _query() -> OtaQuery:
    return OtaQuery(
        product_model="RMX3301",
        manifest_code="1B",
        ota_track="H",
        rui_candidates=[8, 7],
        language="en-EN",
        beta=False,
        brand="realme",
    )


def _regional_query() -> OtaQuery:
    return OtaQuery(
        product_model="CPH2651ID",
        manifest_code="33",
        ota_track="A",
        rui_candidates=[8],
        language="en-EN",
        beta=False,
        brand="oppo",
    )


def test_live_provider_builds_request_decrypts_and_parses_release():
    Request.constructions = []
    Request.decrypted = {
        "realOtaVersion": "RMX3301_11.H.21_4210_202602281641",
        "realVersionName": "RMX3301_15.0.0.1410(EX01)",
        "versionTypeId": "non_display",
        "panelUrl": "https://example.com/update.html",
        "downloadUrl": "https://componentotacostmanual.example/update.zip",
    }
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=Request,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(_query())

    assert Request.constructions[0]["nv_identifier"] == "00011011"
    assert Request.constructions[0]["region"] == 3
    assert result.rui_version == 8
    assert result.computed_ota_version == "RMX3301_11.H.21_IN_202602281641"
    assert result.download_url == "https://opexcostmanual.example/update.zip"


def test_live_provider_prefers_cn_manual_url_over_auto_url_and_preserves_host():
    Request.constructions = []
    Request.decrypted = {
        "realOtaVersion": "PKJ110_11.A.63_0630_202509191808",
        "realVersionName": "PKJ110_15.0.1.622(CN01)",
        "url": "https://gauss-compotacostauto-cn.allawnfs.com/remove-id/component-ota/file.zip",
        "manualUrl": "https://gauss-componentotacostmanual-cn.allawnfs.com/remove-id/component-ota/file.zip",
    }
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=Request,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(
        OtaQuery(
            product_model="PKJ110",
            manifest_code="97",
            ota_track="A",
            rui_candidates=[6],
            language="en-EN",
            beta=False,
            brand="oppo",
        )
    )

    assert (
        result.download_url
        == "https://gauss-componentotacostmanual-cn.allawnfs.com/remove-id/component-ota/file.zip"
    )


def test_live_provider_normalizes_cn_auto_url_when_manual_url_is_absent():
    Request.constructions = []
    Request.decrypted = {
        "realOtaVersion": "PKJ110_11.A.63_0630_202509191808",
        "realVersionName": "PKJ110_15.0.1.622(CN01)",
        "downloadUrl": "https://gauss-compotacostauto-cn.allawnfs.com/remove-id/component-ota/file.zip",
    }
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=Request,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(
        OtaQuery(
            product_model="PKJ110",
            manifest_code="97",
            ota_track="A",
            rui_candidates=[6],
            language="en-EN",
            beta=False,
            brand="oppo",
        )
    )

    assert (
        result.download_url
        == "https://gauss-componentotacostmanual-cn.allawnfs.com/remove-id/component-ota/file.zip"
    )


def test_live_provider_derives_cn_display_version_from_update_notes():
    Request.constructions = []
    Request.decrypted = {
        "realOtaVersion": "PKJ110_11.C.65_1650_202604091920",
        "versionTypeId": "non_display",
        "panelUrl": "https://gauss-compotacostauto-cn.allawnfs.com/remove-id/component-ota/26/05/07/update.html",
        "downloadUrl": "https://component-ota-cn.allawntech.com/downloadCheck?id=1",
    }

    def note_response(*_args, **_kwargs):
        return httpx.Response(200, text="<dt>update package（16.0.5.702Patch01）</dt>")

    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=Request,
        post=lambda *args, **kwargs: Response(),
        get=note_response,
    )

    result = provider.query(
        OtaQuery(
            product_model="PKJ110",
            manifest_code="97",
            ota_track="C",
            rui_candidates=[8],
            language="en-EN",
            beta=False,
            brand="oppo",
        )
    )

    assert result.real_version_name == "PKJ110_16.0.5.702(CN01)"
    assert result.published_at is not None
    assert result.published_at.astimezone(timezone.utc).isoformat().startswith("2026-05-07")
    assert result.region_code == "CN"


def test_live_provider_tries_next_candidate_after_valid_no_update():
    class CandidateRequest(Request):
        calls = 0

        def decrypt(self, _value):
            CandidateRequest.calls += 1
            if CandidateRequest.calls == 1:
                return json.dumps({"checkFailReason": "no version"})
            return json.dumps(
                {
                    "realOtaVersion": "RMX3301_11.H.21_4210_202602281641",
                    "realVersionName": "release",
                    "downloadUrl": "https://example.com/update.zip",
                }
            )

    CandidateRequest.calls = 0
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=CandidateRequest,
        post=lambda *args, **kwargs: Response(),
    )

    # Manifest 39 (TH) has no region model variant, so this isolates the
    # rui-candidate fallback from the region-suffix retry path.
    no_variant_query = OtaQuery(
        product_model="RMX3301",
        manifest_code="39",
        ota_track="H",
        rui_candidates=[8, 7],
        language="en-EN",
        beta=False,
        brand="realme",
    )
    assert provider.query(no_variant_query).rui_version == 7


def test_live_provider_retries_upstream_fallback_seed_after_rejected_primary_seed():
    class SeedRetryRequest(Request):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.ota_version = kwargs["ota_version"]

        def validate_response(self, response):
            if "_0000_000000000000" in self.ota_version:
                raise RuntimeError("primary seed rejected")

        def decrypt(self, _value):
            return json.dumps(
                {
                    "realOtaVersion": "RMX3301_11.H.21_4210_202602281641",
                    "realVersionName": "release",
                    "downloadUrl": "https://example.com/update.zip",
                }
            )

    SeedRetryRequest.constructions = []
    calls = 0

    def fallback_response(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            response = Response()
            response.content = json.dumps({"body": None}).encode()
            return response
        return Response()

    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=SeedRetryRequest,
        post=fallback_response,
    )

    result = provider.query(_query())

    assert result.rui_version == 8
    assert [row["ota_version"] for row in SeedRetryRequest.constructions] == [
        "RMX3301_11.H.00_0000_000000000000",
        "RMX3301_11.H.00_0001_000000000001",
    ]


def test_live_provider_maps_decryptable_non_release_response_to_no_update():
    class NoUpdateRequest(Request):
        def validate_response(self, _response):
            raise RuntimeError("non-200 responseCode with encrypted payload")

        def decrypt(self, _value):
            return json.dumps({"decentralize": {}, "paramFlag": "0"})

    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=NoUpdateRequest,
        post=lambda *args, **kwargs: Response(),
    )

    with pytest.raises(OtaNotFoundError, match="no OTA found"):
        provider.query(_query())


def test_live_provider_retries_base_model_when_regional_model_has_no_release():
    class BaseModelFallbackRequest(Request):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.model = kwargs["model"]

        def decrypt(self, _value):
            if self.model == "CPH2651ID":
                return json.dumps({"checkFailReason": "no version"})
            return json.dumps(
                {
                    "realOtaVersion": "CPH2651_11.A.49_0490_202508282004",
                    "realVersionName": "CPH2651_15.0.0.860(EX01)",
                    "downloadUrl": "https://example.com/update.zip",
                }
            )

    BaseModelFallbackRequest.constructions = []
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=BaseModelFallbackRequest,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(_regional_query())

    assert [row["model"] for row in BaseModelFallbackRequest.constructions] == [
        "CPH2651ID",
        "CPH2651",
    ]
    assert result.product_model == "CPH2651ID"
    assert result.computed_ota_version == "CPH2651_11.A.49_ID_202508282004"


def test_live_provider_accepts_non_display_release_without_display_version():
    class NonDisplayRequest(Request):
        def decrypt(self, _value):
            return json.dumps(
                {
                    "realOtaVersion": "PMA110_11.A.46_0460_202605192330",
                    "versionTypeId": "non_display",
                    "downloadUrl": "https://example.com/downloadCheck/path",
                }
            )

    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=NonDisplayRequest,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(
        OtaQuery(
            product_model="PMA110",
            manifest_code="97",
            ota_track="A",
            rui_candidates=[6],
            language="en-EN",
            beta=False,
            brand="oppo",
        )
    )

    assert result.real_version_name == "PMA110_11.A.46_0460_202605192330"
    assert result.version_type_id == "non_display"
    assert result.computed_ota_version == "PMA110_11.A.46_CN_202605192330"


def test_live_provider_uses_controlled_alias_after_base_model_no_release():
    class IndiaAliasRequest(Request):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.model = kwargs["model"]

        def decrypt(self, _value):
            if self.model == "CPH2659":
                return json.dumps({"checkFailReason": "no version"})
            return json.dumps(
                {
                    "realOtaVersion": "CPH2659IN_11.H.10_0100_202605270000",
                    "realVersionName": "CPH2659IN_15.0.0.100(EX01)",
                    "downloadUrl": "https://example.com/update.zip",
                }
            )

    IndiaAliasRequest.constructions = []
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=IndiaAliasRequest,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(
        OtaQuery(
            product_model="CPH2659",
            manifest_code="1B",
            ota_track="H",
            rui_candidates=[8],
            language="en-EN",
            beta=False,
            brand="oppo",
        )
    )

    assert [row["model"] for row in IndiaAliasRequest.constructions] == [
        "CPH2659",
        "CPH2659IN",
    ]
    assert result.product_model == "CPH2659"
    assert result.computed_ota_version == "CPH2659_11.H.10_IN_202605270000"


def test_live_provider_tries_india_variant_for_any_model_under_manifest_1b():
    class NordVariantRequest(Request):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.model = kwargs["model"]

        def decrypt(self, _value):
            if self.model in ("DN2101", "DN2101IN"):
                return json.dumps({"checkFailReason": "no version"})
            return json.dumps(
                {
                    "realOtaVersion": "DN2101IND_11.C.18_0180_202605270000",
                    "realVersionName": "DN2101IND_11.3.0.180(EX01)",
                    "downloadUrl": "https://example.com/update.zip",
                }
            )

    NordVariantRequest.constructions = []
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=NordVariantRequest,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(
        OtaQuery(
            product_model="DN2101",
            manifest_code="1B",
            ota_track="C",
            rui_candidates=[8],
            language="en-EN",
            beta=False,
            brand="oneplus",
        )
    )

    assert [row["model"] for row in NordVariantRequest.constructions] == [
        "DN2101",
        "DN2101IN",
        "DN2101IND",
    ]
    assert result.product_model == "DN2101"


def test_live_provider_tries_eu_variant_under_manifest_44():
    class EuVariantRequest(Request):
        url = "https://component-otapc-eu.allawnos.com/update/v3"

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.model = kwargs["model"]

        def decrypt(self, _value):
            if self.model == "DN2103":
                return json.dumps({"checkFailReason": "no version"})
            return json.dumps(
                {
                    "realOtaVersion": "DN2103EEA_11.C.18_0180_202605270000",
                    "realVersionName": "DN2103EEA_11.3.0.180(EX01)",
                    "downloadUrl": "https://example.com/update.zip",
                }
            )

    EuVariantRequest.constructions = []
    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=EuVariantRequest,
        post=lambda *args, **kwargs: Response(),
    )

    result = provider.query(
        OtaQuery(
            product_model="DN2103",
            manifest_code="44",
            ota_track="C",
            rui_candidates=[8],
            language="en-EN",
            beta=False,
            brand="oneplus",
        )
    )

    assert [row["model"] for row in EuVariantRequest.constructions] == [
        "DN2103",
        "DN2103EEA",
    ]
    assert result.product_model == "DN2103"


def test_live_provider_maps_timeout_without_leaking_request_content():
    def timeout(*_args, **_kwargs):
        raise httpx.ReadTimeout("timeout")

    provider = RealmeOtaProvider(
        Settings(allow_live_ota=True),
        request_cls=Request,
        post=timeout,
    )

    with pytest.raises(OtaProviderTimeoutError, match="timed out"):
        provider.query(_query())
