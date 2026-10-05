"""Recommendation + future-plan endpoints (design.md §7, §9 sequence flow)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Crop, Plot, Preferences, Recommendation
from app.db.session import get_db
from app.ml.classifier import CropClassifier
from app.ml.regressor import SoilRegressor, compute_soil_gap
from app.schemas.recommendation import CropSuggestion, RecommendationOut
from app.services.feature_builder import build_feature_vector
from app.services.ingestion import get_latest_plot_data
from app.services.preference_filter import NoCropsPassedFilter, apply_preferences

router = APIRouter(tags=["recommendations"])


@router.post("/plots/{plot_id}/recommend", response_model=RecommendationOut)
def recommend(plot_id: int, db: Session = Depends(get_db)):
    plot = db.get(Plot, plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")

    data = get_latest_plot_data(db, plot)
    features = build_feature_vector(data["soil"], data["weather"], data["satellite"])

    classifier = CropClassifier()
    predictions = classifier.predict(features)

    preferences = db.get(Preferences, plot.user_id)
    crops_by_name = {c.name: c for c in db.query(Crop).all()}

    try:
        predictions = apply_preferences(predictions, preferences, crops_by_name)
    except NoCropsPassedFilter as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "No crops passed preference filters", "excluded_by": exc.excluded_by},
        ) from exc

    top_crop = crops_by_name.get(predictions[0].crop)
    regressor = SoilRegressor()
    soil_targets = regressor.predict_targets(features, crop_name=predictions[0].crop)
    soil_gap = compute_soil_gap(current=features.as_dict(), targets=soil_targets)

    recommendation = Recommendation(
        plot_id=plot.id,
        crop_id=top_crop.id if top_crop else None,
        confidence=predictions[0].confidence,
        soil_targets=soil_targets,
        model_version=classifier.version,
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)

    return RecommendationOut(
        recommendation_id=recommendation.id,
        model_version=recommendation.model_version,
        crops=[CropSuggestion(crop=p.crop, confidence=p.confidence, top_factors=p.top_factors) for p in predictions],
        soil_targets=soil_targets,
        soil_gap=soil_gap,
    )
