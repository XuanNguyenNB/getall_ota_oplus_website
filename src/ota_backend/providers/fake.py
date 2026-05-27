from __future__ import annotations

from ota_backend.domain.models import OtaProviderRelease, OtaQuery
from ota_backend.domain.ota import build_seed_ota_version
from ota_backend.providers.interfaces import OtaNotFoundError, OtaProvider


class FakeOtaProvider(OtaProvider):
    def query(self, request: OtaQuery) -> OtaProviderRelease:
        if request.product_model != "RMX3301":
            raise OtaNotFoundError("fake provider has no fixture for this model")

        return OtaProviderRelease(
            brand="realme",
            product_model=request.product_model,
            manifest_code=request.manifest_code,
            ota_track=request.ota_track,
            rui_version=request.rui_candidates[-1],
            real_ota_version="RMX3301_11.H.21_4210_202602281641",
            real_version_name="RMX3301_15.0.0.1410(EX01)",
            computed_ota_version=build_seed_ota_version(
                request.product_model, request.ota_track
            ).replace(".00_0000_000000000000", ".21_IN_202602281641"),
            version_type_id="non_display",
            about_update_url="https://example.com/update.html",
            download_url="https://example.com/update.zip",
            raw_response={"fixture": "fake-realme-success"},
        )
