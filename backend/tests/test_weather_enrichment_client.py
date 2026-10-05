"""Adapter tests using httpx.MockTransport - no live network calls."""

import httpx
import pytest

from app.services.weather_enrichment.client import OpenMeteoClient, OpenMeteoRequestError

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def _client(handler, max_retries=2) -> OpenMeteoClient:
    return OpenMeteoClient(base_url=BASE_URL, max_retries=max_retries, transport=httpx.MockTransport(handler))


def test_get_recent_daily_parses_documented_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "daily": {
                "time": ["2026-09-26", "2026-09-27"],
                "temperature_2m_mean": [11.2, 11.0],
                "precipitation_sum": [0.60, 7.80],
                "relative_humidity_2m_mean": [86, 83],
            }
        })

    with _client(handler) as client:
        days = client.get_recent_daily(174.77, -41.29)

    assert len(days) == 2
    assert days[1].reading_date.isoformat() == "2026-09-27"
    assert days[1].temp == 11.0
    assert days[1].rainfall == 7.80
    assert days[1].humidity == 83


def test_get_recent_daily_preserves_nulls_rather_than_fabricating():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "daily": {
                "time": ["2026-09-27"],
                "temperature_2m_mean": [None],
                "precipitation_sum": [3.2],
                "relative_humidity_2m_mean": [None],
            }
        })

    with _client(handler) as client:
        days = client.get_recent_daily(174.77, -41.29)

    assert days[0].temp is None
    assert days[0].rainfall == 3.2
    assert days[0].humidity is None


def test_get_recent_daily_raises_on_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with _client(handler) as client:
        with pytest.raises(OpenMeteoRequestError):
            client.get_recent_daily(174.77, -41.29)


def test_get_recent_daily_retries_on_500_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"daily": {"time": ["2026-09-27"], "temperature_2m_mean": [11.0], "precipitation_sum": [0.0], "relative_humidity_2m_mean": [80]}})

    with _client(handler) as client:
        client.get_recent_daily(174.77, -41.29)
    assert calls["n"] == 2


def test_get_recent_daily_gives_up_after_max_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client(handler, max_retries=2) as client:
        with pytest.raises(OpenMeteoRequestError):
            client.get_recent_daily(174.77, -41.29)


def test_get_recent_daily_raises_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    with _client(handler) as client:
        with pytest.raises(OpenMeteoRequestError):
            client.get_recent_daily(174.77, -41.29)
