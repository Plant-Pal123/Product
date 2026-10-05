from pydantic import BaseModel


class PreferencesIn(BaseModel):
    budget: float | None = None
    timeframe_days: int | None = None
    excluded_crops: list[str] = []


class PreferencesOut(PreferencesIn):
    model_config = {"from_attributes": True}
