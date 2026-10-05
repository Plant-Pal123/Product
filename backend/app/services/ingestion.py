"""Ingestion service - fetches soil/weather/satellite data for a plot, normalises
units, and caches results (design.md §2.1). Falls back to last cached reading when
an external source is unavailable (NFR-5).

Concrete data source clients are not wired up yet - final providers are an open
decision (design.md §13: SoilGrids / Open-Meteo / Sentinel Hub are candidates).
"""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Plot, SatelliteReading, SoilReading, WeatherReading


class DataUnavailableError(Exception):
    """Raised when a source has no data at all (not even cached)."""


def get_latest_soil(db: Session, plot: Plot) -> SoilReading | None:
    return (
        db.query(SoilReading)
        .filter(SoilReading.plot_id == plot.id, SoilReading.date <= date.today())
        .order_by(SoilReading.date.desc())
        .first()
    )


def get_latest_weather(db: Session, plot: Plot) -> WeatherReading | None:
    # date <= today, not just "highest date on record": a forecast source
    # (weather_enrichment) or stray test data can leave future-dated rows,
    # and those aren't "the latest observation" in any meaningful sense.
    return (
        db.query(WeatherReading)
        .filter(WeatherReading.plot_id == plot.id, WeatherReading.date <= date.today())
        .order_by(WeatherReading.date.desc())
        .first()
    )


def get_latest_satellite(db: Session, plot: Plot) -> SatelliteReading | None:
    return (
        db.query(SatelliteReading)
        .filter(SatelliteReading.plot_id == plot.id, SatelliteReading.date <= date.today())
        .order_by(SatelliteReading.date.desc())
        .first()
    )


def get_latest_plot_data(db: Session, plot: Plot) -> dict[str, Any]:
    """Returns the latest cached reading per source plus an "as of" timestamp per
    source, so the API/UI can show a "data as of <date>" banner (design.md §10)."""

    soil = get_latest_soil(db, plot)
    weather = get_latest_weather(db, plot)
    satellite = get_latest_satellite(db, plot)

    return {
        "soil": soil,
        "weather": weather,
        "satellite": satellite,
        "as_of": {
            "soil": soil.date if soil else None,
            "weather": weather.date if weather else None,
            "satellite": satellite.date if satellite else None,
        },
    }


def refresh_plot_data(db: Session, plot: Plot) -> None:
    """Superseded by dedicated per-source pipelines - see
    app/services/weather_enrichment (Open-Meteo, live) and
    app/services/satellite_enrichment (Copernicus/Sentinel Hub, live), each
    with their own POST /plots/{id}/{source}/refresh endpoint
    (app/api/routes/plots.py).

    `soil_readings` (n/p/k, this table - not app/services/soil_enrichment's
    richer `soil_observations`) has no dedicated pipeline: no source found so
    far reports real, current nitrogen/phosphorus/potassium for a point
    without a lab test (FR-1.5 already covers manual entry as the intended
    path for these). pH could reuse soil_enrichment's LRIS data once that has
    a key configured, but n/p/k remain an open decision (design.md §13).
    """
    raise NotImplementedError("No source for soil_readings (n/p/k) yet - see this function's docstring")
