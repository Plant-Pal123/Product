"""Integration tests against a real Postgres (see tests/conftest.py's module
docstring) for the /plots/{id}/soil-properties endpoints and the ingestion
pipeline's DB-facing behaviour (upsert idempotency, missing-key handling)."""

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.models import SoilObservation
from app.db.session import SessionLocal
from app.main import app
from app.services.soil_enrichment.pipeline import refresh_soil_observations
from app.services.soil_enrichment.specs import SOURCE_NAME


def _settings_without_lris_key():
    """A Settings instance with the LRIS key forced blank, regardless of
    what's in the developer's local .env - see the equivalent helper in
    test_satellite_properties.py for why this matters."""
    settings = get_settings()
    return settings.model_copy(update={"lris_api_key": None})


def test_soil_properties_empty_before_any_ingestion(client, test_plot):
    response = client.get(f"/api/v1/plots/{test_plot}/soil-properties")
    assert response.status_code == 200
    body = response.json()
    assert body["soil_properties"] == []
    assert body["attribution"] == []


def test_soil_properties_reflects_stored_observations(client, test_plot):
    db = SessionLocal()
    try:
        db.add(
            SoilObservation(
                plot_id=test_plot,
                property_code="ph",
                value_numeric=5.9,
                value_text="Slightly acid",
                unit="pH",
                depth_top_cm=None,
                depth_bottom_cm=None,
                observation_date=None,
                retrieved_at=datetime.now(timezone.utc),
                provenance_type="mapped",
                source_name=SOURCE_NAME,
                source_dataset="FSL pH",
                source_record_id="1",
                source_url="https://lris.scinfo.org.nz/layer/48102/",
                source_version_or_vintage="FSL best-available data as at 2000",
                spatial_resolution_m=None,
                geometry_method="centroid",
                quality_flag="valid",
                uncertainty=None,
                raw_properties_json={"PH_MID": 5.9},
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/plots/{test_plot}/soil-properties")
    assert response.status_code == 200
    body = response.json()
    assert len(body["soil_properties"]) == 1
    prop = body["soil_properties"][0]
    assert prop["property"] == "ph"
    assert prop["value"] == 5.9
    assert prop["provenance"] == "mapped"
    assert prop["quality"] == "valid"
    assert body["attribution"] == ["Data reproduced with the permission of Landcare Research New Zealand Limited"]


def test_soil_properties_missing_plot_404s(client):
    response = client.get("/api/v1/plots/999999/soil-properties")
    assert response.status_code == 404


def test_refresh_without_api_key_reports_error_per_property_and_stores_nothing(client, test_plot):
    """Without an LRIS API key, the pipeline must report a clear per-property
    error instead of fabricating data or crashing the endpoint. Overrides the
    settings dependency so this holds regardless of whatever real
    LRIS_API_KEY is configured in the developer's own .env."""
    app.dependency_overrides[get_settings] = _settings_without_lris_key
    try:
        response = client.post(f"/api/v1/plots/{test_plot}/soil-properties/refresh")
    finally:
        del app.dependency_overrides[get_settings]
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) > 0
    assert all(r["status"] == "error" for r in body["results"])

    db = SessionLocal()
    try:
        stored = db.query(SoilObservation).filter(SoilObservation.plot_id == test_plot).count()
    finally:
        db.close()
    assert stored == 0


def test_refresh_soil_observations_dry_run_does_not_persist(test_plot):
    from app.db.models import Plot

    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        summary = refresh_soil_observations(db, plot, dry_run=True)
        assert len(summary.results) > 0
        stored = db.query(SoilObservation).filter(SoilObservation.plot_id == test_plot).count()
        assert stored == 0
    finally:
        db.close()
