from __future__ import annotations

import json

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

    assert provider.query(_query()).rui_version == 7


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
