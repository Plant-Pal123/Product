"""Preference Manager endpoints (FR-4.4, FR-6.x)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Preferences
from app.db.session import get_db
from app.schemas.preferences import PreferencesIn, PreferencesOut

router = APIRouter(prefix="/preferences", tags=["preferences"])


def _to_out(prefs: Preferences) -> PreferencesOut:
    excluded = prefs.excluded_crops.split(",") if prefs.excluded_crops else []
    return PreferencesOut(budget=prefs.budget, timeframe_days=prefs.timeframe_days, excluded_crops=excluded)


@router.get("/{user_id}", response_model=PreferencesOut)
def get_preferences(user_id: int, db: Session = Depends(get_db)):
    prefs = db.get(Preferences, user_id)
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not set")
    return _to_out(prefs)


@router.put("/{user_id}", response_model=PreferencesOut)
def update_preferences(user_id: int, payload: PreferencesIn, db: Session = Depends(get_db)):
    prefs = db.get(Preferences, user_id)
    if not prefs:
        prefs = Preferences(user_id=user_id)
        db.add(prefs)

    prefs.budget = payload.budget
    prefs.timeframe_days = payload.timeframe_days
    prefs.excluded_crops = ",".join(payload.excluded_crops)
    db.commit()
    db.refresh(prefs)
    return _to_out(prefs)
