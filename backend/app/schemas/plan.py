from pydantic import BaseModel


class FuturePlanOut(BaseModel):
    id: int
    recommendation_id: int
    content: dict  # heuristics, timeline/graph data, soil effect, yield/finance (design.md §6)
    pdf_path: str | None

    model_config = {"from_attributes": True}
