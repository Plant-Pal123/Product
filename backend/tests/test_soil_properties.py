"""Integration tests against a real Postgres (see tests/conftest.py's module
docstring) for the /plots/{id}/soil-properties endpoints and the ingestion
pipeline's DB-facing behaviour (upsert idempotency, missing-key handling)."""

from datetime import datetime, timezone

import pytest

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


def _settings_with_smap(enabled):
    """S-map is off by default (SMAP_ENABLED); these force it either way,
    regardless of the developer's own .env."""
    return get_settings().model_copy(update={"lris_api_key": None, "smap_enabled": enabled})


@pytest.fixture
def smap_on():
    app.dependency_overrides[get_settings] = lambda: _settings_with_smap(True)
    yield
    del app.dependency_overrides[get_settings]


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


def _add_observation(plot_id, property_code, source_dataset, value_numeric=None, value_text=None):
    db = SessionLocal()
    try:
        db.add(
            SoilObservation(
                plot_id=plot_id,
                property_code=property_code,
                value_numeric=value_numeric,
                value_text=value_text,
                unit=None,
                depth_top_cm=None,
                depth_bottom_cm=None,
                observation_date=None,
                retrieved_at=datetime.now(timezone.utc),
                provenance_type="mapped",
                source_name=SOURCE_NAME,
                source_dataset=source_dataset,
                source_record_id=None,
                source_url="https://lris.scinfo.org.nz/",
                source_version_or_vintage=None,
                spatial_resolution_m=None,
                geometry_method="centroid",
                quality_flag="estimated" if value_text or value_numeric is not None else "missing",
                uncertainty=None,
                raw_properties_json={},
            )
        )
        db.commit()
    finally:
        db.close()


def test_soil_properties_credits_smap_when_smap_values_are_shown(client, test_plot, smap_on):
    _add_observation(test_plot, "available_water_capacity", "FSL Profile Available Water", value_numeric=120)
    _add_observation(test_plot, "smap_drainage", "S-map Soil Drainage August 2026", value_text="Poorly drained")

    body = client.get(f"/api/v1/plots/{test_plot}/soil-properties").json()
    drainage = next(p for p in body["soil_properties"] if p["property"] == "smap_drainage")
    assert drainage["value_text"] == "Poorly drained"
    assert drainage["value"] is None
    assert body["attribution"] == [
        "Data reproduced with the permission of Landcare Research New Zealand Limited",
        "Soil data: S-map © Manaaki Whenua – Landcare Research (CC BY-NC-ND)",
    ]


def test_soil_properties_no_smap_credit_when_smap_has_no_data(client, test_plot, smap_on):
    _add_observation(test_plot, "smap_drainage", "S-map Soil Drainage August 2026")

    body = client.get(f"/api/v1/plots/{test_plot}/soil-properties").json()
    assert body["attribution"] == []


def test_soil_properties_hides_smap_values_when_smap_disabled(client, test_plot):
    _add_observation(test_plot, "available_water_capacity", "FSL Profile Available Water", value_numeric=120)
    _add_observation(test_plot, "smap_drainage", "S-map Soil Drainage August 2026", value_text="Poorly drained")
    app.dependency_overrides[get_settings] = lambda: _settings_with_smap(False)
    try:
        body = client.get(f"/api/v1/plots/{test_plot}/soil-properties").json()
    finally:
        del app.dependency_overrides[get_settings]
    assert [p["property"] for p in body["soil_properties"]] == ["available_water_capacity"]
    assert body["attribution"] == [
        "Data reproduced with the permission of Landcare Research New Zealand Limited",
    ]


def test_refresh_skips_smap_layers_when_smap_disabled(test_plot):
    from app.db.models import Plot

    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        summary = refresh_soil_observations(db, plot, settings=_settings_with_smap(False), dry_run=True)
    finally:
        db.close()
    codes = {r.property_code for r in summary.results}
    assert codes and not codes & {"smap_drainage", "smap_texture", "smap_depth_class"}


def test_refresh_includes_smap_layers_when_smap_enabled(test_plot):
    from app.db.models import Plot

    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        summary = refresh_soil_observations(db, plot, settings=_settings_with_smap(True), dry_run=True)
    finally:
        db.close()
    codes = {r.property_code for r in summary.results}
    assert {"smap_drainage", "smap_texture", "smap_depth_class"} <= codes


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
