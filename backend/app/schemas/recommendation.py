from pydantic import BaseModel


class CropSuggestion(BaseModel):
    crop: str
    confidence: float
    top_factors: list[str]


class RecommendationOut(BaseModel):
    """Shape matches the example response in design.md §7."""

    recommendation_id: int
    model_version: str
    crops: list[CropSuggestion]
    soil_targets: dict[str, float]
    soil_gap: dict[str, float]
