"""Adapter tests using httpx.MockTransport - no live network calls, per
plantpal_soil_data_scraper_spec.md's "tests must not depend on live services"."""

import httpx
import pytest

from app.services.soil_enrichment.lris_client import LrisClient, LrisConfigError, LrisRequestError

LAYER_ID = 48102


def _client(handler, **kwargs) -> LrisClient:
    return LrisClient(
        api_key="test-key",
        base_url="https://lris.scinfo.org.nz/services/query/v1/vector.json",
        max_retries=kwargs.pop("max_retries", 2),
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_query_point_parses_documented_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "vectorQuery": {
                    "layers": {
                        str(LAYER_ID): {
                            "features": [
                                {"id": 42, "type": "Feature", "properties": {"PH_MID": 5.9}},
                            ]
                        }
                    }
                }
            },
        )

    with _client(handler) as client:
        features = client.query_point(LAYER_ID, 172.6, -43.5)

    assert len(features) == 1
    assert features[0].properties == {"PH_MID": 5.9}
    assert features[0].source_record_id == "42"


def test_query_point_returns_empty_list_when_no_feature_at_point():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"vectorQuery": {"layers": {str(LAYER_ID): {"features": []}}}})

    with _client(handler) as client:
        assert client.query_point(LAYER_ID, 172.6, -43.5) == []


def test_query_point_requires_api_key():
    client = LrisClient(api_key=None, base_url="https://example.invalid", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(LrisConfigError):
        client.query_point(LAYER_ID, 172.6, -43.5)


def test_query_point_raises_config_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid-api-key")

    with _client(handler) as client:
        with pytest.raises(LrisConfigError):
            client.query_point(LAYER_ID, 172.6, -43.5)


def test_query_point_retries_on_500_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"vectorQuery": {"layers": {str(LAYER_ID): {"features": []}}}})

    with _client(handler) as client:
        client.query_point(LAYER_ID, 172.6, -43.5)
    assert calls["n"] == 2


def test_query_point_gives_up_after_max_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client(handler, max_retries=2) as client:
        with pytest.raises(LrisRequestError):
            client.query_point(LAYER_ID, 172.6, -43.5)


def test_query_point_raises_on_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with _client(handler) as client:
        with pytest.raises(LrisRequestError):
            client.query_point(LAYER_ID, 172.6, -43.5)


def test_query_point_validates_coordinate_bounds():
    with _client(lambda r: httpx.Response(200)) as client:
        with pytest.raises(ValueError):
            client.query_point(LAYER_ID, 999, -43.5)
