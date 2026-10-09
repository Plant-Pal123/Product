"""Plot endpoints (FR-1.1, FR-7.2)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Plot, SatelliteReading, SoilObservation, WeatherReading
from app.db.session import get_db
from app.schemas.plot import PlotCreate, PlotDataOut, PlotOut
from app.schemas.satellite import (
    ATTRIBUTION_TEXT as SATELLITE_ATTRIBUTION_TEXT,
    SatelliteHistoryOut,
    SatelliteReadingOut,
    SatelliteRefreshOut,
    SatelliteRefreshResultOut,
)
from app.schemas.soil import DepthOut, SoilPropertiesOut, SoilPropertyOut, SoilRefreshOut, SoilRefreshResultOut
from app.schemas.weather import WeatherHistoryOut, WeatherReadingOut, WeatherRefreshOut, WeatherRefreshResultOut
from app.services.ingestion import get_latest_plot_data
from app.services.satellite_enrichment.pipeline import refresh_satellite_readings
from app.services.soil_enrichment.normalize import ATTRIBUTION_TEXT
from app.services.soil_enrichment.specs import SMAP_ATTRIBUTION_TEXT, SMAP_PROPERTY_CODES
from app.services.soil_enrichment.pipeline import refresh_soil_observations
from app.services.weather_enrichment.pipeline import refresh_weather_readings

router = APIRouter(prefix="/plots", tags=["plots"])


def _get_plot_or_404(plot_id: int, db: Session) -> Plot:
    plot = db.get(Plot, plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
    return plot


def _observation_to_schema(obs: SoilObservation) -> SoilPropertyOut:
    return SoilPropertyOut(
        property=obs.property_code,
        value=obs.value_numeric,
        value_text=obs.value_text,
        unit=obs.unit,
        depth_cm=DepthOut(top=obs.depth_top_cm, bottom=obs.depth_bottom_cm),
        observation_date=obs.observation_date,
        provenance=obs.provenance_type,
        source=obs.source_name,
        source_dataset=obs.source_dataset,
        source_url=obs.source_url,
        source_vintage=obs.source_version_or_vintage,
        retrieved_at=obs.retrieved_at,
        spatial_resolution_m=obs.spatial_resolution_m,
        quality=obs.quality_flag,
        uncertainty=obs.uncertainty,
    )


def _reading_to_dict(reading) -> dict | None:
    """Column values only - `reading.__dict__` also carries SQLAlchemy's
    internal `_sa_instance_state`, which isn't JSON-serialisable."""
    if reading is None:
        return None
    return {k: v for k, v in reading.__dict__.items() if not k.startswith("_")}


@router.post("", response_model=PlotOut, status_code=201)
def create_plot(payload: PlotCreate, db: Session = Depends(get_db)):
    # TODO: derive user_id from the authenticated session once auth is wired up.
    plot = Plot(name=payload.name, boundary=payload.boundary, user_id=1)
    db.add(plot)
    db.commit()
    db.refresh(plot)
    return plot


@router.get("/{plot_id}/data", response_model=PlotDataOut)
def get_plot_data(plot_id: int, db: Session = Depends(get_db)):
    plot = _get_plot_or_404(plot_id, db)

    data = get_latest_plot_data(db, plot)
    return PlotDataOut(
        soil=_reading_to_dict(data["soil"]),
        weather=_reading_to_dict(data["weather"]),
        satellite=_reading_to_dict(data["satellite"]),
        as_of=data["as_of"],
    )


@router.get("/{plot_id}/soil-properties", response_model=SoilPropertiesOut)
def get_soil_properties(plot_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Reads whatever soil_observations are already stored - never makes a
    live call to the source (see POST .../soil-properties/refresh for that),
    so this always responds even if the source is down (FR: stale/error
    states - plantpal_soil_data_scraper_spec.md's website requirements)."""
    plot = _get_plot_or_404(plot_id, db)
    observations = (
        db.query(SoilObservation)
        .filter(SoilObservation.plot_id == plot.id)
        .order_by(SoilObservation.property_code)
        .all()
    )
    # With S-map off, rows stored while it was on aren't shown either.
    if not settings.smap_enabled:
        observations = [o for o in observations if o.property_code not in SMAP_PROPERTY_CODES]
    # Each source gets its own credit line: FSL whenever FSL rows exist (as
    # before), S-map only when an S-map value is actually being shown.
    attribution = []
    if any(o.property_code not in SMAP_PROPERTY_CODES for o in observations):
        attribution.append(ATTRIBUTION_TEXT)
    if any(o.property_code in SMAP_PROPERTY_CODES and o.value_text for o in observations):
        attribution.append(SMAP_ATTRIBUTION_TEXT)
    return SoilPropertiesOut(
        plot_id=plot.id,
        soil_properties=[_observation_to_schema(o) for o in observations],
        attribution=attribution,
    )


@router.post("/{plot_id}/soil-properties/refresh", response_model=SoilRefreshOut)
def refresh_soil_properties(plot_id: int, force: bool = False, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Queries the LRIS Portal for this plot's centroid and upserts results.
    Requires LRIS_API_KEY (see backend/README.md#soil-property-enrichment);
    without it every property comes back with status="error"."""
    plot = _get_plot_or_404(plot_id, db)
    summary = refresh_soil_observations(db, plot, settings=settings, force=force)
    return SoilRefreshOut(
        plot_id=plot.id,
        results=[SoilRefreshResultOut(property_code=r.property_code, status=r.status, detail=r.detail) for r in summary.results],
    )


@router.get("/{plot_id}/satellite-history", response_model=SatelliteHistoryOut)
def get_satellite_history(plot_id: int, db: Session = Depends(get_db)):
    """Reads whatever satellite_readings are already stored (FR-4.5's NDVI
    trend) - never makes a live call to the source; see
    POST .../satellite/refresh for that."""
    plot = _get_plot_or_404(plot_id, db)
    readings = (
        db.query(SatelliteReading)
        .filter(SatelliteReading.plot_id == plot.id)
        .order_by(SatelliteReading.date)
        .all()
    )
    return SatelliteHistoryOut(
        plot_id=plot.id,
        readings=[SatelliteReadingOut(date=r.date, ndvi_mean=r.ndvi_mean) for r in readings],
        attribution=[SATELLITE_ATTRIBUTION_TEXT] if readings else [],
    )


@router.post("/{plot_id}/satellite/refresh", response_model=SatelliteRefreshOut)
def refresh_satellite(plot_id: int, force: bool = False, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Queries the Copernicus Data Space Ecosystem for this plot's boundary
    and upserts NDVI results. Requires CDSE_CLIENT_ID/CDSE_CLIENT_SECRET (see
    backend/README.md#satellite-ndvi-enrichment); without them every interval
    comes back with status="error"."""
    plot = _get_plot_or_404(plot_id, db)
    summary = refresh_satellite_readings(db, plot, settings=settings, force=force)
    return SatelliteRefreshOut(
        plot_id=plot.id,
        results=[SatelliteRefreshResultOut(date_from=r.date_from, status=r.status, detail=r.detail) for r in summary.results],
    )


@router.get("/{plot_id}/weather-history", response_model=WeatherHistoryOut)
def get_weather_history(plot_id: int, db: Session = Depends(get_db)):
    """Reads whatever weather_readings are already stored - never makes a
    live call to the source; see POST .../weather/refresh for that. This is
    the same table the crop classifier/soil regressor's feature vector reads
    temperature/humidity/rainfall from (app/services/feature_builder.py)."""
    plot = _get_plot_or_404(plot_id, db)
    readings = (
        db.query(WeatherReading)
        .filter(WeatherReading.plot_id == plot.id)
        .order_by(WeatherReading.date)
        .all()
    )
    return WeatherHistoryOut(
        plot_id=plot.id,
        readings=[WeatherReadingOut(date=r.date, temp=r.temp, rainfall=r.rainfall, humidity=r.humidity) for r in readings],
    )


@router.post("/{plot_id}/weather/refresh", response_model=WeatherRefreshOut)
def refresh_weather(plot_id: int, force: bool = False, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Queries Open-Meteo (free, no key) for this plot's centroid and upserts
    yesterday+today's daily weather. See
    backend/README.md#weather-enrichment."""
    plot = _get_plot_or_404(plot_id, db)
    summary = refresh_weather_readings(db, plot, settings=settings, force=force)
    return WeatherRefreshOut(
        plot_id=plot.id,
        results=[WeatherRefreshResultOut(date=r.date, status=r.status, detail=r.detail) for r in summary.results],
    )
