"""Shared fixtures for the integration tests below.

These hit the real Postgres configured in .env (no sqlite/mock swap - see
README.md) via the app's own session factory, so a running database is a
prerequisite for anything beyond test_health.py. Tests that need a trained
model artifact skip themselves with a clear reason instead of failing when one
hasn't been trained yet (see `require_model`).
"""

import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import Crop, Plot, Preferences, SatelliteReading, SoilReading, User, WeatherReading
from app.db.session import SessionLocal
from app.main import app

# Mirrors sql/seed.sql's crop table - duplicated here (rather than imported)
# because seed.sql is the source of truth for dev/manual use, while tests need
# to guarantee these rows exist regardless of whether seed.sql was ever run.
CROPS = [
    ("rice", 120, 1200, 0.40), ("maize", 90, 800, 0.25), ("chickpea", 100, 700, 0.90),
    ("kidneybeans", 100, 750, 1.10), ("pigeonpeas", 150, 700, 0.85), ("mothbeans", 75, 600, 0.80),
    ("mungbean", 65, 650, 1.00), ("blackgram", 90, 650, 0.95), ("lentil", 100, 650, 1.20),
    ("pomegranate", 180, 3000, 1.50), ("banana", 300, 2500, 0.35), ("mango", 365, 2800, 0.60),
    ("grapes", 150, 4000, 1.80), ("watermelon", 90, 1500, 0.30), ("muskmelon", 90, 1400, 0.35),
    ("apple", 365, 3500, 1.00), ("orange", 270, 2600, 0.55), ("papaya", 270, 1800, 0.40),
    ("coconut", 365, 2200, 0.50), ("cotton", 180, 1600, 1.60), ("jute", 120, 900, 0.45),
    ("coffee", 270, 3200, 2.50),
]


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def ensure_crops():
    """The classifier can predict any of the 22 standard crop labels; make sure
    every one of them exists as a Crop row so recommend/plan lookups by name
    always resolve, regardless of whether sql/seed.sql was run."""
    db = SessionLocal()
    try:
        existing = {c.name for c in db.query(Crop).all()}
        for name, days, cost, price in CROPS:
            if name not in existing:
                db.add(Crop(name=name, days_to_harvest=days, cost_per_ha=cost, price_per_kg=price))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def test_plot():
    """A fresh user + plot + one reading per source, isolated from any seed
    data (a random email avoids colliding with rows sql/seed.sql may have
    already created). Yields the plot id."""
    db = SessionLocal()
    try:
        user = User(email=f"test-{uuid.uuid4().hex[:10]}@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)

        db.add(Preferences(user_id=user.id, budget=None, timeframe_days=None, excluded_crops=""))

        plot = Plot(
            user_id=user.id,
            name="Test plot",
            boundary={"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
        )
        db.add(plot)
        db.commit()
        db.refresh(plot)

        db.add(SoilReading(plot_id=plot.id, date=date.today(), ph=6.5, n=90, p=42, k=43, moisture=20.5, source="manual"))
        db.add(WeatherReading(plot_id=plot.id, date=date.today(), temp=20.9, rainfall=202.9, humidity=82.0))
        db.add(SatelliteReading(plot_id=plot.id, date=date.today(), ndvi_mean=0.62))
        db.commit()

        yield plot.id
    finally:
        db.close()


def _artifact_exists(version: str) -> bool:
    settings = get_settings()
    return (Path(settings.model_artifact_dir) / f"{version}.joblib").exists()


requires_classifier = pytest.mark.skipif(
    not _artifact_exists(get_settings().crop_classifier_version),
    reason="No trained classifier artifact - run scripts/train_classifier.py first",
)
requires_regressor = pytest.mark.skipif(
    not _artifact_exists(get_settings().soil_regressor_version),
    reason="No trained regressor artifact - run scripts/train_regressor.py first",
)
