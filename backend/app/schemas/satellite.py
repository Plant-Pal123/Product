from datetime import date

from pydantic import BaseModel

ATTRIBUTION_TEXT = "Contains modified Copernicus Sentinel data, processed by Sentinel Hub"


class SatelliteReadingOut(BaseModel):
    date: date
    ndvi_mean: float


class SatelliteHistoryOut(BaseModel):
    plot_id: int
    readings: list[SatelliteReadingOut]
    attribution: list[str]


class SatelliteRefreshResultOut(BaseModel):
    date_from: str
    status: str
    detail: str | None = None


class SatelliteRefreshOut(BaseModel):
    plot_id: int
    results: list[SatelliteRefreshResultOut]
