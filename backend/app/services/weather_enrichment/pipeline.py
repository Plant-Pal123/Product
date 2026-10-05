"""Orchestrates: locate a plot -> query Open-Meteo for its centroid -> upsert
into the existing `weather_readings` table.

Freshness is simpler here than soil/satellite's TTL: `weather_readings` is
one row per calendar day, so "fresh" just means today's row already exists.
"""

import logging
from dataclasses import dataclass
from datetime import date as date_

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Plot, WeatherReading
from app.services.soil_enrichment.crs import geojson_centroid_lonlat
from app.services.weather_enrichment.client import OpenMeteoClient, OpenMeteoRequestError

logger = logging.getLogger("weather_enrichment.pipeline")


@dataclass(frozen=True)
class WeatherIngestResult:
    date: str
    status: str  # "stored" | "skipped_fresh" | "error"
    detail: str | None = None


@dataclass(frozen=True)
class WeatherIngestionSummary:
    plot_id: int
    results: list[WeatherIngestResult]


def _today_reading_exists(db: Session, plot_id: int) -> bool:
    # Local date, not UTC - matches how every other date in this codebase is
    # stored (date.today() in seed data/fixtures, CURRENT_DATE in SQL). Using
    # UTC here caused a real off-by-one-day bug in NZ's own UTC+12/13 timezone
    # around local midnight - see this file's tests for the reproduction.
    today = date_.today()
    return (
        db.query(WeatherReading)
        .filter(WeatherReading.plot_id == plot_id, WeatherReading.date == today)
        .count()
        > 0
    )


def refresh_weather_readings(
    db: Session,
    plot: Plot,
    settings: Settings | None = None,
    force: bool = False,
    dry_run: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> WeatherIngestionSummary:
    """Fetches (or skips, if today's row already exists) yesterday+today's
    daily weather for `plot`'s centroid and upserts them. Never fabricates a
    value - a field Open-Meteo doesn't report for a day is stored as NULL,
    not 0 (feature_builder.py already imputes NULLs with regional
    defaults). `transport` is test-only, for injecting an httpx.MockTransport
    (see tests/test_weather_properties.py) - Open-Meteo needs no API key, so
    there's no config-error path to test against otherwise."""
    settings = settings or get_settings()

    if not force and _today_reading_exists(db, plot.id):
        return WeatherIngestionSummary(plot_id=plot.id, results=[WeatherIngestResult("", "skipped_fresh")])

    try:
        location = geojson_centroid_lonlat(plot.boundary)
    except ValueError as exc:
        return WeatherIngestionSummary(plot_id=plot.id, results=[WeatherIngestResult("", "error", str(exc))])

    results: list[WeatherIngestResult] = []
    with OpenMeteoClient(
        base_url=settings.open_meteo_base_url,
        timeout_seconds=settings.open_meteo_request_timeout_seconds,
        max_retries=settings.open_meteo_max_retries,
        transport=transport,
    ) as client:
        try:
            days = client.get_recent_daily(location.lon, location.lat, past_days=1)
        except (OpenMeteoRequestError, httpx.HTTPError) as exc:
            logger.warning("weather_enrichment plot=%s request failed: %s", plot.id, exc)
            return WeatherIngestionSummary(plot_id=plot.id, results=[WeatherIngestResult("", "error", "source request failed")])

        for day in days:
            label = day.reading_date.isoformat()
            logger.info(
                "weather_enrichment plot=%s date=%s temp=%s rainfall=%s humidity=%s",
                plot.id, label, day.temp, day.rainfall, day.humidity,
            )
            if dry_run:
                results.append(WeatherIngestResult(label, "stored"))
                continue

            existing = (
                db.query(WeatherReading)
                .filter(WeatherReading.plot_id == plot.id, WeatherReading.date == day.reading_date)
                .one_or_none()
            )
            if existing is not None:
                existing.temp = day.temp
                existing.rainfall = day.rainfall
                existing.humidity = day.humidity
            else:
                db.add(WeatherReading(plot_id=plot.id, date=day.reading_date, temp=day.temp, rainfall=day.rainfall, humidity=day.humidity))
            results.append(WeatherIngestResult(label, "stored"))

        if not dry_run:
            db.commit()

    return WeatherIngestionSummary(plot_id=plot.id, results=results)
