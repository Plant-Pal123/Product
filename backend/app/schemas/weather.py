from datetime import date

from pydantic import BaseModel


class WeatherReadingOut(BaseModel):
    date: date
    temp: float | None
    rainfall: float | None
    humidity: float | None


class WeatherHistoryOut(BaseModel):
    plot_id: int
    readings: list[WeatherReadingOut]


class WeatherRefreshResultOut(BaseModel):
    date: str
    status: str
    detail: str | None = None


class WeatherRefreshOut(BaseModel):
    plot_id: int
    results: list[WeatherRefreshResultOut]
