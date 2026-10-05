"""Offline training script for the soil optimiser (design.md §5.2, §5.3).

Predicts target N/P/K/pH for a crop given current conditions. Trained on the
same synthetic per-crop ranges as the classifier (app/ml/crop_catalog.py) - see
that module's docstring for why these are placeholders, not a real dataset.

The target for each sample is the midpoint of that crop's ideal N/P/K/pH range
plus a little noise, i.e. "what N/P/K/pH this crop generally wants", nudged
slightly so the model isn't a pure per-crop constant. Which crop is being asked
about is encoded as that crop's index in CROP_NAMES, appended after the usual
feature vector - see app/ml/regressor.py's `_crop_index` for the inference-side
half of this contract.

Usage (from backend/):
    ./.venv/Scripts/python scripts/train_regressor.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.ml.crop_catalog import CROP_NAMES, CROP_RANGES
from app.ml.regressor import SOIL_TARGET_KEYS
from app.services.feature_builder import FEATURE_ORDER

SEED = 42
SAMPLES_PER_CROP = 120
# Jitter on N/P/K/pH targets, scaled per key since N/P/K span tens of units but
# pH spans about 1-2 - a single noise std would swamp pH's signal.
TARGET_NOISE_STD = {"n": 2.0, "p": 2.0, "k": 2.0, "ph": 0.15}


def sample_dataset(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    rows = []
    targets = []
    for crop_index, crop in enumerate(CROP_NAMES):
        ranges = CROP_RANGES[crop]
        midpoints = {key: sum(ranges[key]) / 2 for key in SOIL_TARGET_KEYS}
        for _ in range(SAMPLES_PER_CROP):
            conditions = [rng.uniform(*ranges[key]) for key in ("n", "p", "k", "ph", "temperature", "humidity", "rainfall")]
            conditions.append(rng.uniform(*ranges["ndvi"]))
            rows.append(conditions + [crop_index])

            target = [midpoints[key] + rng.normal(0, TARGET_NOISE_STD[key]) for key in SOIL_TARGET_KEYS]
            targets.append(target)

    assert [r for r in ("n", "p", "k", "ph", "temperature", "humidity", "rainfall")] + ["ndvi_mean"] == FEATURE_ORDER
    return np.array(rows), np.array(targets)


def main() -> None:
    settings = get_settings()
    rng = np.random.default_rng(SEED)

    X, y = sample_dataset(rng)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=SEED)

    model = DecisionTreeRegressor(max_depth=8, min_samples_leaf=3, random_state=SEED)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    for i, key in enumerate(SOIL_TARGET_KEYS):
        mae = mean_absolute_error(y_test[:, i], y_pred[:, i])
        r2 = r2_score(y_test[:, i], y_pred[:, i])
        print(f"{key}: MAE={mae:.2f}  R2={r2:.3f}")

    # sample_dataset() builds rows one crop at a time (120 consecutive rows per
    # crop) - plain KFold's default cv=5 doesn't shuffle, so it slices those
    # crop-sized blocks into folds that under/overrepresent individual crops
    # (some folds barely see a crop's own values), producing wildly negative
    # R2 that has nothing to do with real model quality. shuffle=True fixes it.
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_scores = cross_val_score(DecisionTreeRegressor(max_depth=8, min_samples_leaf=3, random_state=SEED), X, y, cv=cv, scoring="r2")
    print(f"5-fold CV R2 (uniform-averaged across n/p/k/ph): {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

    # Unlike the classifier, expect crop_index to dominate here: the synthetic
    # target *is* "that crop's midpoint + noise" (see sample_dataset above), so
    # the other features - including ndvi_mean, even with its own per-crop
    # range now - have nothing to add once the crop is already known. That's
    # a property of this placeholder data-generating function, not a bug to
    # chase; it'll change once a real dataset ties targets to conditions.
    feature_names = FEATURE_ORDER + ["crop_index"]
    print("Feature importances:")
    for name, importance in sorted(zip(feature_names, model.feature_importances_), key=lambda p: p[1], reverse=True):
        print(f"  {name}: {importance:.3f}")

    out_dir = Path(settings.model_artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = settings.soil_regressor_version
    out_path = out_dir / f"{version}.joblib"
    joblib.dump({"model": model}, out_path)
    print(f"Saved {out_path} (version={version})")


if __name__ == "__main__":
    main()
