from pydantic import BaseModel


class PlotCreate(BaseModel):
    name: str
    boundary: dict  # GeoJSON geometry


class PlotOut(BaseModel):
    id: int
    name: str
    boundary: dict

    model_config = {"from_attributes": True}


class PlotDataOut(BaseModel):
    """Latest soil, weather and satellite readings for a plot (GET /plots/{id}/data)."""

    soil: dict | None
    weather: dict | None
    satellite: dict | None
    as_of: dict  # per-source timestamp so the UI can show a "data as of" banner (NFR-5)
