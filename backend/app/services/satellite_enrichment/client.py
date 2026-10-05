"""HTTP client for the Copernicus Data Space Ecosystem's Statistical API.

Endpoint confirmed live on 2026-09-27 (returns a clean 401 without a token,
not a 404/connection error):

    curl -X POST https://sh.dataspace.copernicus.eu/api/v1/statistics
    -> HTTP 401 {"error":{"code":"COMMON_UNAUTHORIZED", ...}}

and the `sentinel-2-l2a` collection id was confirmed via the API's own public
STAC catalog (no auth needed for that part):

    curl https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/collections
    -> includes {"id":"sentinel-2-l2a", ..., "license":"proprietary",
       "sci:citation":"Modified Copernicus Sentinel data [Year]/Sentinel Hub"}

("proprietary" here is Sentinel Hub's STAC license field for data it hosts,
not a paywall - actual terms are the Copernicus Sentinel Data legal notice,
which is free/open for any use with attribution; see
backend/README.md#satellite-ndvi-enrichment.)

The request/response body shape below is the Sentinel Hub Statistical API's
documented v1 schema (same platform LINZ/LRIS's Koordinates isn't, this is a
different vendor - Sentinel Hub / Planet). Confirmed against a live
authenticated request on 2026-09-27 (real OAuth client, small AOI over
Hastings NZ, 30-day/10-day-aggregated NDVI query) - one correction from the
docs found while building this: resolution goes in `aggregation.resolution`
as `[resx, resy]`, not top-level `resx`/`resy` keys (those are silently
ignored, and the API falls back to a single pixel spanning the whole AOI,
which trips its max-pixel-size guard on anything but a tiny bbox).
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.services.satellite_enrichment.auth import CdseAuthError, CdseConfigError, CdseTokenProvider
from app.services.satellite_enrichment.evalscript import NDVI_EVALSCRIPT

logger = logging.getLogger("satellite_enrichment.client")


class NdviRequestError(Exception):
    """The request failed after retries, or the response could not be parsed."""


@dataclass(frozen=True)
class NdviInterval:
    date_from: date
    date_to: date
    mean: float | None
    std_dev: float | None
    sample_count: int
    no_data_count: int


class CdseStatisticsClient:
    def __init__(
        self,
        token_provider: CdseTokenProvider,
        statistics_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ):
        self._token_provider = token_provider
        self._statistics_url = statistics_url
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CdseStatisticsClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def query_ndvi(
        self,
        geometry_wgs84: dict[str, Any],
        date_from: date,
        date_to: date,
        aggregation_days: int,
        max_cloud_coverage_pct: int,
    ) -> list[NdviInterval]:
        """Ten-day (by default) NDVI aggregates for `geometry_wgs84` between
        date_from/date_to. Raises CdseConfigError if no OAuth client is
        configured or it was rejected; raises NdviRequestError for any other
        failure. Never fabricates a value - an interval with no valid
        (cloud-free) pixels comes back with mean=None, not 0."""
        body = {
            "input": {
                "bounds": {
                    "geometry": geometry_wgs84,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {"maxCloudCoverage": max_cloud_coverage_pct},
                    }
                ],
            },
            "aggregation": {
                "timeRange": {
                    "from": f"{date_from.isoformat()}T00:00:00Z",
                    "to": f"{date_to.isoformat()}T23:59:59Z",
                },
                "aggregationInterval": {"of": f"P{aggregation_days}D"},
                "evalscript": NDVI_EVALSCRIPT,
                "resolution": [10, 10],
            },
            "calculations": {"default": {}},
        }

        response_json = self._post_with_retries(body)
        return self._parse_intervals(response_json)

    def _post_with_retries(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            token = self._token_provider.get_token(self._client)  # raises CdseConfigError/CdseAuthError
            try:
                response = self._client.post(
                    self._statistics_url,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("cdse statistics timeout attempt=%s/%s", attempt, self._max_retries)
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning("cdse statistics transport error attempt=%s/%s: %s", attempt, self._max_retries, exc)
            else:
                if response.status_code in (401, 403):
                    raise CdseConfigError(f"CDSE rejected the request (HTTP {response.status_code}): {response.text[:200]}")
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = NdviRequestError(f"HTTP {response.status_code}")
                    logger.warning(
                        "cdse statistics retryable status attempt=%s/%s status=%s",
                        attempt, self._max_retries, response.status_code,
                    )
                elif response.status_code != 200:
                    raise NdviRequestError(f"HTTP {response.status_code}: {response.text[:200]}")
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise NdviRequestError(f"Non-JSON response: {exc}") from exc

            if attempt < self._max_retries:
                time.sleep(2 ** (attempt - 1))

        raise NdviRequestError(f"Giving up after {self._max_retries} attempts") from last_error

    @staticmethod
    def _parse_intervals(response_json: dict[str, Any]) -> list[NdviInterval]:
        intervals = response_json.get("data")
        if intervals is None:
            raise NdviRequestError(f"Unexpected response shape: missing 'data' - {list(response_json.keys())}")

        results: list[NdviInterval] = []
        for entry in intervals:
            try:
                interval = entry["interval"]
                date_from = date.fromisoformat(interval["from"][:10])
                date_to = date.fromisoformat(interval["to"][:10])
            except (KeyError, ValueError) as exc:
                raise NdviRequestError(f"Unexpected interval shape: {exc}") from exc

            if entry.get("outputs") is None:
                # Sentinel Hub returns an interval entry with no `outputs` key
                # (rather than omitting the interval) when a request errored
                # for just that window - treat as no data, not a hard failure.
                results.append(NdviInterval(date_from, date_to, None, None, 0, 0))
                continue

            try:
                stats = entry["outputs"]["ndvi"]["bands"]["B0"]["stats"]
            except (KeyError, TypeError) as exc:
                raise NdviRequestError(f"Unexpected outputs shape: {exc}") from exc

            sample_count = stats.get("sampleCount", 0)
            no_data_count = stats.get("noDataCount", 0)
            valid_pixels = sample_count - no_data_count
            mean = stats.get("mean") if valid_pixels > 0 else None

            results.append(NdviInterval(
                date_from=date_from,
                date_to=date_to,
                mean=mean,
                std_dev=stats.get("stDev") if valid_pixels > 0 else None,
                sample_count=sample_count,
                no_data_count=no_data_count,
            ))

        return results
