"""Applies user preferences (P) to ranked crop predictions - filtering out
excluded crops and those exceeding budget/timeframe, then re-ranking (FR-2.3)."""

from app.db.models import Crop, Preferences
from app.ml.classifier import CropPrediction


class NoCropsPassedFilter(Exception):
    """Raised when every candidate crop is filtered out, so the caller can tell
    the user which preference excluded them (design.md §10)."""

    def __init__(self, excluded_by: dict[str, list[str]]):
        self.excluded_by = excluded_by
        super().__init__(f"No crops passed preference filters: {excluded_by}")


def apply_preferences(
    predictions: list[CropPrediction],
    preferences: Preferences | None,
    crops_by_name: dict[str, Crop],
) -> list[CropPrediction]:
    if preferences is None:
        return predictions

    excluded_names = {c.strip().lower() for c in (preferences.excluded_crops or "").split(",") if c}

    kept: list[CropPrediction] = []
    excluded_by: dict[str, list[str]] = {"excluded_crop": [], "over_budget": [], "over_timeframe": []}

    for pred in predictions:
        crop = crops_by_name.get(pred.crop)
        if pred.crop.lower() in excluded_names:
            excluded_by["excluded_crop"].append(pred.crop)
            continue
        if crop and preferences.budget is not None and crop.cost_per_ha > preferences.budget:
            excluded_by["over_budget"].append(pred.crop)
            continue
        if crop and preferences.timeframe_days is not None and crop.days_to_harvest > preferences.timeframe_days:
            excluded_by["over_timeframe"].append(pred.crop)
            continue
        kept.append(pred)

    if not kept:
        raise NoCropsPassedFilter(excluded_by)

    return sorted(kept, key=lambda p: p.confidence, reverse=True)
