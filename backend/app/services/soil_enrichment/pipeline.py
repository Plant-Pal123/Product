"""Orchestrates: locate a plot -> query LRIS FSL layers -> normalize -> store.

Kept deliberately thin and adapter-agnostic per the spec ("keep source-specific
adapters separate from common normalization and storage code") - swapping in
S-map or another provider later means adding a new spec table + adapter
module, not touching this file's upsert/logging logic.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Plot, SoilObservation
from app.services.soil_enrichment.crs import LonLat, geojson_centroid_lonlat
from app.services.soil_enrichment.lris_client import LrisClient, LrisConfigError, LrisRequestError
from app.services.soil_enrichment.normalize import NormalizedObservation, normalize_fsl_feature
from app.services.soil_enrichment.specs import FSL_PROPERTIES, SOURCE_NAME, FslPropertySpec

logger = logging.getLogger("soil_enrichment.pipeline")


@dataclass(frozen=True)
class PropertyIngestResult:
    property_code: str
    status: str  # "stored" | "skipped_fresh" | "dry_run" | "error"
    detail: str | None = None


@dataclass(frozen=True)
class IngestionSummary:
    plot_id: int
    location: LonLat
    results: list[PropertyIngestResult]


def _existing_observation(db: Session, plot_id: int, spec: FslPropertySpec) -> SoilObservation | None:
    """Looks up the row `_upsert` would touch for this property, matching the
    same columns as `uq_soil_observations_identity` in sql/schema.sql."""
    return (
        db.query(SoilObservation)
        .filter(
            SoilObservation.plot_id == plot_id,
            SoilObservation.property_code == spec.property_code,
            SoilObservation.source_name == SOURCE_NAME,
            SoilObservation.source_dataset == spec.source_dataset,
            SoilObservation.depth_top_cm == spec.depth_top_cm,
            SoilObservation.depth_bottom_cm == spec.depth_bottom_cm,
        )
        .one_or_none()
    )


def _is_fresh(existing: SoilObservation, ttl_hours: int) -> bool:
    if existing.retrieved_at is None:
        return False
    age = datetime.now(timezone.utc) - existing.retrieved_at.replace(tzinfo=timezone.utc)
    return age < timedelta(hours=ttl_hours)


def _upsert(db: Session, obs: NormalizedObservation, existing: SoilObservation | None) -> None:
    if existing is not None:
        for field in obs.__dataclass_fields__:
            if field == "plot_id":
                continue
            setattr(existing, field, getattr(obs, field))
    else:
        db.add(SoilObservation(**obs.__dict__))


def refresh_soil_observations(
    db: Session,
    plot: Plot,
    settings: Settings | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> IngestionSummary:
    """Fetches (or reuses fresh cached) FSL soil properties for `plot`'s
    centroid and upserts them. Never raises on a per-property source error -
    that property is recorded with quality_flag="missing" and the error is
    logged, so one bad response doesn't block the rest."""
    settings = settings or get_settings()
    location = geojson_centroid_lonlat(plot.boundary)

    results: list[PropertyIngestResult] = []
    with LrisClient(
        api_key=settings.lris_api_key,
        base_url=settings.lris_api_base,
        timeout_seconds=settings.lris_request_timeout_seconds,
        max_retries=settings.lris_max_retries,
    ) as client:
        for i, spec in enumerate(FSL_PROPERTIES):
            existing = _existing_observation(db, plot.id, spec)
            if not force and existing is not None and _is_fresh(existing, settings.soil_observation_ttl_hours):
                results.append(PropertyIngestResult(spec.property_code, "skipped_fresh"))
                continue

            if i > 0 and settings.lris_request_pacing_seconds > 0:
                time.sleep(settings.lris_request_pacing_seconds)

            try:
                features = client.query_point(spec.layer_id, location.lon, location.lat)
                feature = features[0] if features else None
                obs = normalize_fsl_feature(plot.id, spec, feature, geometry_method="centroid")
            except LrisConfigError as exc:
                logger.warning("soil_enrichment plot=%s property=%s config error", plot.id, spec.property_code)
                results.append(PropertyIngestResult(spec.property_code, "error", str(exc)))
                continue
            except (LrisRequestError, httpx.HTTPError) as exc:
                logger.warning(
                    "soil_enrichment plot=%s property=%s layer=%s request failed: %s",
                    plot.id, spec.property_code, spec.layer_id, exc,
                )
                results.append(PropertyIngestResult(spec.property_code, "error", "source request failed"))
                continue

            logger.info(
                "soil_enrichment plot=%s property=%s layer=%s quality=%s dry_run=%s",
                plot.id, spec.property_code, spec.layer_id, obs.quality_flag, dry_run,
            )

            if dry_run:
                results.append(PropertyIngestResult(spec.property_code, "dry_run"))
                continue

            _upsert(db, obs, existing)
            results.append(PropertyIngestResult(spec.property_code, "stored"))

        if not dry_run:
            db.commit()

    return IngestionSummary(plot_id=plot.id, location=location, results=results)
