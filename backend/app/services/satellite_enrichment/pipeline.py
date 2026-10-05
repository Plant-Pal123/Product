"""Orchestrates: locate a plot -> query CDSE Statistical API for NDVI over a
lookback window -> upsert into the existing `satellite_readings` table.

Reuses `SatelliteReading` (plot_id, date, ndvi_mean) rather than adding a new
table, per the spec's "use the project's existing database and conventions
if present" - this is the same table `app/services/ingestion.py`'s
`get_latest_satellite` and the `/plots/{id}/data` endpoint already read from.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Plot, SatelliteReading
from app.services.satellite_enrichment.auth import CdseAuthError, CdseConfigError, CdseTokenProvider
from app.services.satellite_enrichment.client import CdseStatisticsClient, NdviRequestError

logger = logging.getLogger("satellite_enrichment.pipeline")


class BoundaryError(Exception):
    """The plot's boundary isn't a shape the Statistics API can accept."""


@dataclass(frozen=True)
class IntervalIngestResult:
    date_from: str
    status: str  # "stored" | "no_data" | "error"
    detail: str | None = None


@dataclass(frozen=True)
class SatelliteIngestionSummary:
    plot_id: int
    results: list[IntervalIngestResult]


def _plot_geometry_wgs84(plot: Plot) -> dict:
    """Plot boundaries are stored as GeoJSON, which is WGS84 by the GeoJSON
    spec (RFC 7946 §4) - same assumption app/services/soil_enrichment/crs.py
    makes. A bare Point isn't a valid area for the Statistics API, so buffer
    it into a small square (~200m) around the point instead of failing."""
    boundary = plot.boundary
    geom_type = boundary.get("type")
    if geom_type in ("Polygon", "MultiPolygon"):
        return boundary
    if geom_type == "Point":
        lon, lat = boundary["coordinates"]
        d = 0.001  # ~110m at the equator; good enough for a single-pixel-ish AOI
        return {
            "type": "Polygon",
            "coordinates": [[[lon - d, lat - d], [lon - d, lat + d], [lon + d, lat + d], [lon + d, lat - d], [lon - d, lat - d]]],
        }
    raise BoundaryError(f"Unsupported boundary geometry type: {geom_type!r}")


def _existing_reading(db: Session, plot_id: int, reading_date: date) -> SatelliteReading | None:
    return (
        db.query(SatelliteReading)
        .filter(SatelliteReading.plot_id == plot_id, SatelliteReading.date == reading_date)
        .one_or_none()
    )


def _latest_reading_is_fresh(db: Session, plot_id: int, ttl_hours: int) -> bool:
    latest = (
        db.query(SatelliteReading)
        .filter(SatelliteReading.plot_id == plot_id)
        .order_by(SatelliteReading.date.desc())
        .first()
    )
    if latest is None:
        return False
    age = datetime.now(timezone.utc).date() - latest.date
    return age < timedelta(hours=ttl_hours)


def refresh_satellite_readings(
    db: Session,
    plot: Plot,
    settings: Settings | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> SatelliteIngestionSummary:
    """Fetches (or reuses fresh cached) NDVI aggregates for `plot`'s boundary
    and upserts one `satellite_readings` row per interval. Never raises on a
    source error - each interval is recorded as an error/no_data result and
    logged, so one bad response doesn't block the rest."""
    settings = settings or get_settings()

    if not force and _latest_reading_is_fresh(db, plot.id, settings.satellite_reading_ttl_hours):
        return SatelliteIngestionSummary(plot_id=plot.id, results=[IntervalIngestResult("", "skipped_fresh")])

    try:
        geometry = _plot_geometry_wgs84(plot)
    except BoundaryError as exc:
        return SatelliteIngestionSummary(plot_id=plot.id, results=[IntervalIngestResult("", "error", str(exc))])

    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=settings.ndvi_lookback_days)

    token_provider = CdseTokenProvider(
        client_id=settings.cdse_client_id,
        client_secret=settings.cdse_client_secret,
        token_url=settings.cdse_token_url,
    )
    results: list[IntervalIngestResult] = []
    with CdseStatisticsClient(
        token_provider=token_provider,
        statistics_url=settings.cdse_statistics_url,
        timeout_seconds=settings.cdse_request_timeout_seconds,
        max_retries=settings.cdse_max_retries,
    ) as client:
        try:
            intervals = client.query_ndvi(
                geometry_wgs84=geometry,
                date_from=date_from,
                date_to=today,
                aggregation_days=settings.ndvi_aggregation_days,
                max_cloud_coverage_pct=settings.ndvi_max_cloud_coverage_pct,
            )
        except CdseConfigError as exc:
            logger.warning("satellite_enrichment plot=%s config error", plot.id)
            return SatelliteIngestionSummary(plot_id=plot.id, results=[IntervalIngestResult("", "error", str(exc))])
        except (NdviRequestError, CdseAuthError, httpx.HTTPError) as exc:
            logger.warning("satellite_enrichment plot=%s request failed: %s", plot.id, exc)
            return SatelliteIngestionSummary(plot_id=plot.id, results=[IntervalIngestResult("", "error", "source request failed")])

        for interval in intervals:
            label = interval.date_from.isoformat()
            if interval.mean is None:
                logger.info("satellite_enrichment plot=%s interval=%s no valid pixels", plot.id, label)
                results.append(IntervalIngestResult(label, "no_data"))
                continue

            logger.info("satellite_enrichment plot=%s interval=%s ndvi_mean=%.3f samples=%s", plot.id, label, interval.mean, interval.sample_count)
            if dry_run:
                results.append(IntervalIngestResult(label, "dry_run"))
                continue

            existing = _existing_reading(db, plot.id, interval.date_from)
            if existing is not None:
                existing.ndvi_mean = interval.mean
            else:
                db.add(SatelliteReading(plot_id=plot.id, date=interval.date_from, ndvi_mean=interval.mean))
            results.append(IntervalIngestResult(label, "stored"))

        if not dry_run:
            db.commit()

    return SatelliteIngestionSummary(plot_id=plot.id, results=results)
