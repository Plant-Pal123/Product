"""Adapter tests using httpx.MockTransport - no live network calls."""

from datetime import date

import httpx
import pytest

from app.services.satellite_enrichment.auth import CdseConfigError, CdseTokenProvider
from app.services.satellite_enrichment.client import CdseStatisticsClient, NdviRequestError

STATISTICS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
SQUARE = {"type": "Polygon", "coordinates": [[[174.77, -41.29], [174.78, -41.29], [174.78, -41.28], [174.77, -41.28], [174.77, -41.29]]]}
FROM, TO = date(2026, 8, 1), date(2026, 8, 11)


def _token_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"access_token": "test-token", "expires_in": 3600})


def _make_client(handler, token_handler=_token_response, max_retries=2) -> CdseStatisticsClient:
    def router(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-connect/token"):
            return token_handler(request)
        return handler(request)

    provider = CdseTokenProvider(client_id="id", client_secret="secret", token_url=TOKEN_URL)
    return CdseStatisticsClient(
        token_provider=provider,
        statistics_url=STATISTICS_URL,
        max_retries=max_retries,
        transport=httpx.MockTransport(router),
    )


def test_query_ndvi_parses_documented_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json={
            "data": [
                {
                    "interval": {"from": "2026-08-01T00:00:00Z", "to": "2026-08-11T00:00:00Z"},
                    "outputs": {"ndvi": {"bands": {"B0": {"stats": {
                        "min": 0.1, "max": 0.9, "mean": 0.62, "stDev": 0.05,
                        "sampleCount": 400, "noDataCount": 40,
                    }}}}},
                },
            ]
        })

    with _make_client(handler) as client:
        intervals = client.query_ndvi(SQUARE, FROM, TO, 10, 60)

    assert len(intervals) == 1
    assert intervals[0].mean == 0.62
    assert intervals[0].sample_count == 400
    assert intervals[0].no_data_count == 40


def test_query_ndvi_treats_fully_masked_interval_as_no_data_not_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": [
                {
                    "interval": {"from": "2026-08-01T00:00:00Z", "to": "2026-08-11T00:00:00Z"},
                    "outputs": {"ndvi": {"bands": {"B0": {"stats": {
                        "mean": 0.0, "stDev": 0.0, "sampleCount": 100, "noDataCount": 100,
                    }}}}},
                },
            ]
        })

    with _make_client(handler) as client:
        intervals = client.query_ndvi(SQUARE, FROM, TO, 10, 60)

    assert intervals[0].mean is None


def test_query_ndvi_treats_missing_outputs_as_no_data():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"interval": {"from": "2026-08-01T00:00:00Z", "to": "2026-08-11T00:00:00Z"}}]})

    with _make_client(handler) as client:
        intervals = client.query_ndvi(SQUARE, FROM, TO, 10, 60)

    assert intervals[0].mean is None
    assert intervals[0].sample_count == 0


def test_query_ndvi_requires_credentials():
    provider = CdseTokenProvider(client_id=None, client_secret=None, token_url=TOKEN_URL)
    client = CdseStatisticsClient(token_provider=provider, statistics_url=STATISTICS_URL, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(CdseConfigError):
        client.query_ndvi(SQUARE, FROM, TO, 10, 60)


def test_query_ndvi_raises_config_error_on_401_from_statistics_endpoint():
    def token_ok(request):
        return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "COMMON_UNAUTHORIZED"}})

    with _make_client(handler, token_handler=token_ok) as client:
        with pytest.raises(CdseConfigError):
            client.query_ndvi(SQUARE, FROM, TO, 10, 60)


def test_token_provider_rejects_bad_credentials():
    def token_handler(request):
        return httpx.Response(401, json={"error": "invalid_client"})

    provider = CdseTokenProvider(client_id="bad", client_secret="bad", token_url=TOKEN_URL)
    with httpx.Client(transport=httpx.MockTransport(token_handler)) as http_client:
        with pytest.raises(CdseConfigError):
            provider.get_token(http_client)


def test_token_provider_caches_token_across_calls():
    calls = {"n": 0}

    def token_handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"access_token": f"token-{calls['n']}", "expires_in": 3600})

    provider = CdseTokenProvider(client_id="id", client_secret="secret", token_url=TOKEN_URL)
    with httpx.Client(transport=httpx.MockTransport(token_handler)) as http_client:
        first = provider.get_token(http_client)
        second = provider.get_token(http_client)

    assert first == second == "token-1"
    assert calls["n"] == 1


def test_query_ndvi_retries_on_500_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"data": []})

    with _make_client(handler) as client:
        client.query_ndvi(SQUARE, FROM, TO, 10, 60)
    assert calls["n"] == 2


def test_query_ndvi_raises_on_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with _make_client(handler) as client:
        with pytest.raises(NdviRequestError):
            client.query_ndvi(SQUARE, FROM, TO, 10, 60)
