"""Crop classifier wrapper - loads the versioned decision tree model (trained by
scripts/train_classifier.py) and turns predict_proba output into ranked
CropPrediction objects. Any scikit-learn classifier with predict_proba and
feature_importances_ works here unchanged (design.md §5.1 proposed a Random
Forest; a single DecisionTreeClassifier is enough while the training dataset
is synthetic - see scripts/train_classifier.py)."""

from dataclasses import dataclass
from pathlib import Path

import joblib

from app.core.config import get_settings
from app.services.feature_builder import FeatureVector

settings = get_settings()


@dataclass
class CropPrediction:
    crop: str
    confidence: float
    top_factors: list[str]


class CropClassifier:
    def __init__(self, version: str | None = None):
        self.version = version or settings.crop_classifier_version
        self._model = None
        self._classes: list[str] = []

    def _artifact_path(self) -> Path:
        return Path(settings.model_artifact_dir) / f"{self.version}.joblib"

    def load(self) -> None:
        path = self._artifact_path()
        if not path.exists():
            raise FileNotFoundError(
                f"No trained model artifact at {path}. Train and save one first "
                "(see design.md §5.3 - models are trained offline and versioned)."
            )
        bundle = joblib.load(path)
        self._model = bundle["model"]
        self._classes = bundle["classes"]

    def predict(self, features: FeatureVector, top_n: int = 5) -> list[CropPrediction]:
        if self._model is None:
            self.load()

        probs = self._model.predict_proba([features.as_list()])[0]
        ranked = sorted(zip(self._classes, probs), key=lambda pair: pair[1], reverse=True)[:top_n]

        # Global feature importance stands in for per-prediction explainability
        # until SHAP is wired up (design.md §5.1).
        importances = getattr(self._model, "feature_importances_", None)
        top_factors = []
        if importances is not None:
            from app.services.feature_builder import FEATURE_ORDER

            ranked_features = sorted(zip(FEATURE_ORDER, importances), key=lambda p: p[1], reverse=True)
            top_factors = [name for name, _ in ranked_features[:3]]

        return [CropPrediction(crop=name, confidence=float(prob), top_factors=top_factors) for name, prob in ranked]
