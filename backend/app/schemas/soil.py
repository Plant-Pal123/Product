from datetime import date, datetime

from pydantic import BaseModel


class DepthOut(BaseModel):
    top: float | None
    bottom: float | None


class SoilPropertyOut(BaseModel):
    """One soil_observations row, shaped per plantpal_soil_data_scraper_spec.md's
    website/API integration section."""

    property: str
    value: float | None
    value_text: str | None
    unit: str | None
    depth_cm: DepthOut
    observation_date: date | None
    provenance: str
    source: str
    source_dataset: str
    source_url: str
    source_vintage: str | None
    retrieved_at: datetime
    spatial_resolution_m: float | None
    quality: str
    uncertainty: str | None

    model_config = {"from_attributes": False}


class SoilPropertiesOut(BaseModel):
    plot_id: int
    soil_properties: list[SoilPropertyOut]
    attribution: list[str]


class SoilRefreshResultOut(BaseModel):
    property_code: str
    status: str
    detail: str | None = None


class SoilRefreshOut(BaseModel):
    plot_id: int
    results: list[SoilRefreshResultOut]
