"""Integration tests against the real Postgres (see tests/conftest.py) for
the satellite endpoints and the ingestion pipeline's DB-facing behaviour.

Note: the shared `test_plot` fixture already seeds one SatelliteReading
(today's date, ndvi_mean=0.62) for its plot, matching the app's existing
"latest reading" contract at GET /plots/{id}/data - so these tests build on
top of that single row rather than assuming an empty table."""

from datetime import date, timedelta

from app.core.config import get_settings
from app.db.models import SatelliteReading
from app.db.session import SessionLocal
from app.main import app
from app.services.satellite_enrichment.pipeline import refresh_satellite_readings


def _settings_without_cdse_credentials():
    """A Settings instance with CDSE credentials forced blank, regardless of
    what's in the developer's local .env - these tests assert the no-key
    behaviour deterministically and must not depend on (or make a real call
    to) whatever real credentials happen to be configured locally."""
    settings = get_settings()
    return settings.model_copy(update={"cdse_client_id": None, "cdse_client_secret": None})


def test_satellite_history_reflects_the_seeded_reading(client, test_plot):
    response = client.get(f"/api/v1/plots/{test_plot}/satellite-history")
    assert response.status_code == 200
    body = response.json()
    assert len(body["readings"]) == 1
    assert body["readings"][0]["ndvi_mean"] == 0.62
    assert body["attribution"] == ["Contains modified Copernicus Sentinel data, processed by Sentinel Hub"]


def test_satellite_history_missing_plot_404s(client):
    response = client.get("/api/v1/plots/999999/satellite-history")
    assert response.status_code == 404


def test_refresh_without_credentials_reports_error_and_does_not_add_rows(client, test_plot):
    """Without CDSE credentials, the pipeline must report a clear error
    instead of fabricating data. force=true bypasses the freshness cache so
    this exercises the real request path rather than short-circuiting on the
    fixture's fresh seeded reading. Overrides the settings dependency so this
    holds regardless of whatever real CDSE_CLIENT_ID/SECRET is configured in
    the developer's own .env."""
    before = SessionLocal()
    try:
        count_before = before.query(SatelliteReading).filter(SatelliteReading.plot_id == test_plot).count()
    finally:
        before.close()

    app.dependency_overrides[get_settings] = _settings_without_cdse_credentials
    try:
        response = client.post(f"/api/v1/plots/{test_plot}/satellite/refresh?force=true")
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "error"

    after = SessionLocal()
    try:
        count_after = after.query(SatelliteReading).filter(SatelliteReading.plot_id == test_plot).count()
    finally:
        after.close()
    assert count_after == count_before


def test_refresh_satellite_readings_skips_when_fresh_reading_exists(test_plot):
    """The shared fixture already seeded a today-dated reading, so a
    non-forced refresh should short-circuit without touching the source."""
    from app.db.models import Plot

    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        summary = refresh_satellite_readings(db, plot)
        assert len(summary.results) == 1
        assert summary.results[0].status == "skipped_fresh"
    finally:
        db.close()


def test_refresh_satellite_readings_reruns_when_stale():
    """A plot whose latest reading is older than the TTL should attempt a
    real refresh (and, with no credentials configured, report an error
    rather than silently doing nothing)."""
    from app.db.models import Plot, Preferences, User
    import uuid

    db = SessionLocal()
    try:
        user = User(email=f"stale-{uuid.uuid4().hex[:10]}@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(Preferences(user_id=user.id, budget=None, timeframe_days=None, excluded_crops=""))
        plot = Plot(user_id=user.id, name="Stale satellite plot", boundary={"type": "Point", "coordinates": [174.77, -41.29]})
        db.add(plot)
        db.commit()
        db.refresh(plot)
        db.add(SatelliteReading(plot_id=plot.id, date=date.today() - timedelta(days=30), ndvi_mean=0.4))
        db.commit()

        summary = refresh_satellite_readings(db, plot, settings=_settings_without_cdse_credentials())
        assert summary.results[0].status == "error"
    finally:
        db.close()
