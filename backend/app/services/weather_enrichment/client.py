"""HTTP client for Open-Meteo's free forecast API - no key, no signup, CORS-open.

Endpoint and field names confirmed live on 2026-09-27:

    curl "https://api.open-meteo.com/v1/forecast?latitude=-41.29&longitude=174.77
        &daily=temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean
        &timezone=auto&past_days=1&forecast_days=1"
    -> {"daily": {"time": ["2026-09-26","2026-09-27"],
                  "temperature_2m_mean": [11.2, 11.0],
                  "precipitation_sum": [0.60, 7.80],
                  "relative_humidity_2m_mean": [86, 83]}}

Same provider and same daily variables the frontend's js/weather.js already
uses (that one requests max/min/weathercode for a forecast chart; this one
requests the daily mean for a single "current" reading to match
WeatherReading's (date, temp, rainfall, humidity) shape).
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger("weather_enrichment.client")

DAILY_VARS = "temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean"


class OpenMeteoRequestError(Exception):
    """The request failed after retries, or the response could not be parsed."""


@dataclass(frozen=True)
class DailyWeather:
    reading_date: date
    temp: float | None
    rainfall: float | None
    humidity: float | None


class OpenMeteoClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenMeteoClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_recent_daily(self, lon: float, lat: float, past_days: int = 1) -> list[DailyWeather]:
        """Yesterday + today's daily aggregates (`past_days=1, forecast_days=1`)
        - "today" from a forecast API is Open-Meteo's best current estimate,
        blending recent observations with the model, which is what its own
        frontend forecast chart already relies on too."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": DAILY_VARS,
            "timezone": "auto",
            "past_days": past_days,
            "forecast_days": 1,
        }
        response_json = self._get_with_retries(params)
        return self._parse_daily(response_json)

    def _get_with_retries(self, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.get(self._base_url, params=params)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("open-meteo timeout attempt=%s/%s", attempt, self._max_retries)
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning("open-meteo transport error attempt=%s/%s: %s", attempt, self._max_retries, exc)
            else:
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = OpenMeteoRequestError(f"HTTP {response.status_code}")
                    logger.warning("open-meteo retryable status attempt=%s/%s status=%s", attempt, self._max_retries, response.status_code)
                elif response.status_code != 200:
                    raise OpenMeteoRequestError(f"HTTP {response.status_code}: {response.text[:200]}")
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise OpenMeteoRequestError(f"Non-JSON response: {exc}") from exc

            if attempt < self._max_retries:
                time.sleep(2 ** (attempt - 1))

        raise OpenMeteoRequestError(f"Giving up after {self._max_retries} attempts") from last_error

    @staticmethod
    def _parse_daily(response_json: dict[str, Any]) -> list[DailyWeather]:
        daily = response_json.get("daily")
        if daily is None or "time" not in daily:
            raise OpenMeteoRequestError(f"Unexpected response shape: missing 'daily.time' - {list(response_json.keys())}")

        times = daily["time"]
        temps = daily.get("temperature_2m_mean", [None] * len(times))
        rain = daily.get("precipitation_sum", [None] * len(times))
        humidity = daily.get("relative_humidity_2m_mean", [None] * len(times))

        return [
            DailyWeather(
                reading_date=date.fromisoformat(t),
                temp=temps[i] if i < len(temps) else None,
                rainfall=rain[i] if i < len(rain) else None,
                humidity=humidity[i] if i < len(humidity) else None,
            )
            for i, t in enumerate(times)
        ]
