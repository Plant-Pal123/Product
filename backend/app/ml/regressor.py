"""Soil optimiser wrapper - loads the versioned regression model(s) predicting
numeric soil targets (N/P/K/pH) for a given crop, and computes the gap against
current soil values (design.md §5.2)."""

from pathlib import Path

import joblib

from app.core.config import get_settings
from app.ml.crop_catalog import CROP_NAMES
from app.services.feature_builder import FeatureVector

settings = get_settings()

SOIL_TARGET_KEYS = ["n", "p", "k", "ph"]


class UnknownCropError(ValueError):
    """Raised when asked to predict targets for a crop outside CROP_NAMES -
    the model has no index to encode it with."""


class SoilRegressor:
    def __init__(self, version: str | None = None):
        self.version = version or settings.soil_regressor_version
        self._model = None

    def _artifact_path(self) -> Path:
        return Path(settings.model_artifact_dir) / f"{self.version}.joblib"

    def load(self) -> None:
        path = self._artifact_path()
        if not path.exists():
            raise FileNotFoundError(
                f"No trained model artifact at {path}. Train and save one first "
                "(see design.md §5.3)."
            )
        bundle = joblib.load(path)
        self._model = bundle["model"]

    def predict_targets(self, features: FeatureVector, crop_name: str) -> dict[str, float]:
        """Predicts target N/P/K/pH for the given crop under current conditions.

        `crop_name` is encoded as its index in CROP_NAMES and appended after the
        usual feature vector - this must match how scripts/train_regressor.py
        built its training rows.
        """
        if self._model is None:
            self.load()

        crop_index = self._crop_index(crop_name)
        vector = features.as_list() + [crop_index]

        prediction = self._model.predict([vector])[0]
        return dict(zip(SOIL_TARGET_KEYS, (round(float(v), 2) for v in prediction)))

    @staticmethod
    def _crop_index(crop_name: str) -> int:
        try:
            return CROP_NAMES.index(crop_name)
        except ValueError as exc:
            raise UnknownCropError(
                f"'{crop_name}' is not in CROP_NAMES (app/ml/crop_catalog.py); "
                "the regressor has no index to encode it with."
            ) from exc


def compute_soil_gap(current: dict[str, float], targets: dict[str, float]) -> dict[str, float]:
    return {key: round(targets[key] - current.get(key, 0.0), 2) for key in targets}
