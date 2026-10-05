"""HTTP client for the LRIS Portal's Vector Query API.

Endpoint confirmed from the layer's own public services listing, e.g.
https://lris.scinfo.org.nz/services/api/v1.x/layers/48102/services/ ->

    https://lris.scinfo.org.nz/services/query/v1/vector.json
        ?key=[api_token]&layer=48102&x=[x]&y=[y]
        &max_results=3&radius=10000&geometry=true&with_field_names=true

This is Koordinates' standard "Vector Query API" (the same platform backs the
LINZ Data Service), which returns:

    {"vectorQuery": {"layers": {"<layer_id>": {"features": [...]}}}}

where each feature is a GeoJSON Feature with a `properties` dict of the
layer's named fields. This has NOT been confirmed against a live response
(no API key was available while building this) - run
`scripts/ingest_soil_data.py --dry-run` first against a real key and diff the
raw response shape against `_extract_features` below before any bulk run.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("soil_enrichment.lris")


class LrisConfigError(Exception):
    """Missing/invalid client configuration (e.g. no API key set)."""


class LrisRequestError(Exception):
    """The request failed after retries, or the response could not be parsed."""


@dataclass(frozen=True)
class LrisFeature:
    properties: dict[str, Any]
    source_record_id: str | None


class LrisClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LrisClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def query_point(self, layer_id: int, lon: float, lat: float, radius_m: int = 100) -> list[LrisFeature]:
        """Point-in-polygon (falling back to nearest-within-radius) lookup for
        one FSL layer at one location. Returns an empty list when the source
        has no feature there (never fabricates a result)."""
        if not self._api_key:
            raise LrisConfigError(
                "LRIS_API_KEY is not set - register a free account and web service "
                "key at https://lris.scinfo.org.nz/ (see backend/README.md)."
            )
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"lon/lat out of range: ({lon}, {lat})")

        params = {
            "key": self._api_key,
            "layer": layer_id,
            "x": lon,
            "y": lat,
            "max_results": 1,
            "radius": radius_m,
            "geometry": "false",
            "with_field_names": "true",
        }

        response_json = self._get_with_retries(params, layer_id=layer_id)
        return self._extract_features(response_json, layer_id)

    def _get_with_retries(self, params: dict[str, Any], layer_id: int) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.get(self._base_url, params=params)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("lris timeout layer=%s attempt=%s/%s", layer_id, attempt, self._max_retries)
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning("lris transport error layer=%s attempt=%s/%s: %s", layer_id, attempt, self._max_retries, exc)
            else:
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = LrisRequestError(f"HTTP {response.status_code}")
                    logger.warning(
                        "lris retryable status layer=%s attempt=%s/%s status=%s",
                        layer_id, attempt, self._max_retries, response.status_code,
                    )
                elif response.status_code == 401 or response.status_code == 403:
                    raise LrisConfigError(f"LRIS rejected the API key (HTTP {response.status_code})")
                elif response.status_code != 200:
                    raise LrisRequestError(f"HTTP {response.status_code}: {response.text[:200]}")
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise LrisRequestError(f"Non-JSON response: {exc}") from exc

            if attempt < self._max_retries:
                time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s, ...

        raise LrisRequestError(f"Giving up after {self._max_retries} attempts") from last_error

    @staticmethod
    def _extract_features(response_json: dict[str, Any], layer_id: int) -> list[LrisFeature]:
        try:
            layer_result = response_json["vectorQuery"]["layers"][str(layer_id)]
        except (KeyError, TypeError) as exc:
            raise LrisRequestError(
                f"Unexpected response shape for layer {layer_id}: missing "
                f"vectorQuery.layers.{layer_id} - {exc}"
            ) from exc

        features = layer_result.get("features", [])
        return [
            LrisFeature(
                properties=feature.get("properties", {}),
                source_record_id=str(feature.get("id")) if feature.get("id") is not None else None,
            )
            for feature in features
        ]
