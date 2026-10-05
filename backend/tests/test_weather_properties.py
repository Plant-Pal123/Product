"""Integration tests against the real Postgres (see tests/conftest.py) for
the weather endpoints and the ingestion pipeline's DB-facing behaviour.

Note: the shared `test_plot` fixture already seeds one WeatherReading
(today's date, temp=20.9/rainfall=202.9/humidity=82.0) - so freshness-skip
tests build on that, and the "stores real data" test injects a mock
transport (Open-Meteo needs no API key, so there's no "missing credentials"
state to test against here, unlike soil/satellite)."""

import httpx

from app.db.models import Plot, WeatherReading
from app.db.session import SessionLocal
from app.services.weather_enrichment.pipeline import refresh_weather_readings


def test_weather_history_reflects_the_seeded_reading(client, test_plot):
    response = client.get(f"/api/v1/plots/{test_plot}/weather-history")
    assert response.status_code == 200
    body = response.json()
    assert len(body["readings"]) == 1
    assert body["readings"][0]["temp"] == 20.9
    assert body["readings"][0]["rainfall"] == 202.9
    assert body["readings"][0]["humidity"] == 82.0


def test_weather_history_missing_plot_404s(client):
    response = client.get("/api/v1/plots/999999/weather-history")
    assert response.status_code == 404


def test_refresh_skips_when_todays_reading_exists(test_plot):
    """The shared fixture already seeded a today-dated reading, so a
    non-forced refresh should short-circuit without touching the source."""
    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        summary = refresh_weather_readings(db, plot)
        assert len(summary.results) == 1
        assert summary.results[0].status == "skipped_fresh"
    finally:
        db.close()


def test_refresh_dry_run_does_not_persist(test_plot):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "daily": {
                "time": ["2026-09-26", "2026-09-27"],
                "temperature_2m_mean": [11.2, 11.0],
                "precipitation_sum": [0.60, 7.80],
                "relative_humidity_2m_mean": [86, 83],
            }
        })

    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        before = db.query(WeatherReading).filter(WeatherReading.plot_id == test_plot).count()
        summary = refresh_weather_readings(db, plot, force=True, dry_run=True, transport=httpx.MockTransport(handler))
        assert all(r.status == "stored" for r in summary.results)
        after = db.query(WeatherReading).filter(WeatherReading.plot_id == test_plot).count()
        assert after == before
    finally:
        db.close()


def test_refresh_forced_stores_real_response_and_is_idempotent():
    """A fresh plot (no seeded reading) so this exercises the real
    insert-then-update upsert path deterministically against a mocked
    Open-Meteo response."""
    import uuid

    from app.db.models import Preferences, User

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "daily": {
                "time": ["2026-09-26", "2026-09-27"],
                "temperature_2m_mean": [11.2, 11.0],
                "precipitation_sum": [0.60, 7.80],
                "relative_humidity_2m_mean": [86, 83],
            }
        })

    db = SessionLocal()
    try:
        user = User(email=f"weather-{uuid.uuid4().hex[:10]}@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(Preferences(user_id=user.id, budget=None, timeframe_days=None, excluded_crops=""))
        plot = Plot(user_id=user.id, name="Weather test plot", boundary={"type": "Point", "coordinates": [174.77, -41.29]})
        db.add(plot)
        db.commit()
        db.refresh(plot)

        summary = refresh_weather_readings(db, plot, transport=httpx.MockTransport(handler))
        assert len(summary.results) == 2
        assert all(r.status == "stored" for r in summary.results)

        rows = db.query(WeatherReading).filter(WeatherReading.plot_id == plot.id).order_by(WeatherReading.date).all()
        assert len(rows) == 2
        assert rows[1].temp == 11.0
        assert rows[1].rainfall == 7.80
        assert rows[1].humidity == 83

        # Re-running (forced) with the same response should update, not duplicate.
        refresh_weather_readings(db, plot, force=True, transport=httpx.MockTransport(handler))
        rows_after = db.query(WeatherReading).filter(WeatherReading.plot_id == plot.id).all()
        assert len(rows_after) == 2
    finally:
        db.close()


def test_refresh_reports_error_on_transport_failure(test_plot):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    db = SessionLocal()
    try:
        plot = db.get(Plot, test_plot)
        summary = refresh_weather_readings(db, plot, force=True, transport=httpx.MockTransport(handler))
        assert summary.results[0].status == "error"
    finally:
        db.close()
