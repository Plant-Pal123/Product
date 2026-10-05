"""Future plan generation and PDF export endpoints (FR-5.x, FR-5.10)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import FuturePlan, Recommendation
from app.db.session import get_db
from app.services.ingestion import get_latest_soil
from app.schemas.plan import FuturePlanOut
from app.services.pdf_exporter import render_plan_pdf
from app.services.plan_generator import generate_plan
from app.services.plan_summary import DeepseekConfigError, DeepseekRequestError, generate_ai_summary

logger = logging.getLogger("routes.plans")

router = APIRouter(tags=["plans"])


@router.post("/recommendations/{recommendation_id}/plan", response_model=FuturePlanOut)
def create_plan(recommendation_id: int, db: Session = Depends(get_db)):
    recommendation = db.get(Recommendation, recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    crop = recommendation.crop
    soil = get_latest_soil(db, recommendation.plot)
    if not soil:
        raise HTTPException(status_code=422, detail="No soil reading on record for this plot")

    current_soil = {"n": soil.n, "p": soil.p, "k": soil.k, "ph": soil.ph}
    content = generate_plan(recommendation, crop, current_soil)

    plan = FuturePlan(recommendation_id=recommendation.id, content=content, pdf_path=None)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _ensure_ai_summary(plan: FuturePlan, db: Session, force: bool = False) -> None:
    """Populates plan.content["ai_summary"] (generating it via DeepSeek if
    missing or forced) and commits. force_ai_summary=true re-requests the
    summary even if one (including a cached null from a past failure/missing
    key) is already stored - see backend/README.md#ai-plan-summary."""
    if "ai_summary" in plan.content and not force:
        return

    settings = get_settings()
    try:
        ai_summary = generate_ai_summary(
            crop_name=plan.recommendation.crop.name,
            content=plan.content,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_api_base,
            model=settings.deepseek_model,
            timeout_seconds=settings.deepseek_request_timeout_seconds,
            max_retries=settings.deepseek_max_retries,
        )
    except (DeepseekConfigError, DeepseekRequestError) as exc:
        logger.warning("plan %s: skipping AI summary (%s)", plan.id, exc)
        ai_summary = None
    plan.content = {**plan.content, "ai_summary": ai_summary}
    plan.pdf_path = None  # force a re-render so the PDF picks up the summary
    db.commit()
    db.refresh(plan)


@router.get("/plans/{plan_id}", response_model=FuturePlanOut)
def get_plan(plan_id: int, force_ai_summary: bool = False, db: Session = Depends(get_db)):
    """JSON fetch of a plan's content (including ai_summary), without
    rendering a PDF - for UI surfaces (e.g. the frontend Report builder) that
    just need the AI summary text, not the file."""
    plan = db.get(FuturePlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    _ensure_ai_summary(plan, db, force=force_ai_summary)
    return plan


@router.get("/plans/{plan_id}/pdf")
def download_plan_pdf(plan_id: int, force_ai_summary: bool = False, db: Session = Depends(get_db)):
    plan = db.get(FuturePlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    _ensure_ai_summary(plan, db, force=force_ai_summary)

    if not plan.pdf_path:
        plan.pdf_path = render_plan_pdf(plan.id, plan.content)
        db.commit()

    return FileResponse(plan.pdf_path, media_type="application/pdf", filename=f"plan-{plan.id}.pdf")
