"""Offline training script for the crop classifier (design.md §5.3: models are
trained offline and saved with joblib, versioned).

No real labelled crop-suitability dataset exists in this repo yet -
requirements.md §7 lists "Where will crop training data come from?" as an open
question. This script generates a synthetic dataset from per-crop agronomic
ranges (N/P/K/pH/temperature/humidity/rainfall) so the pipeline has something
concrete to run end-to-end against. It is a placeholder for bootstrapping, not
a substitute for real data - swap `sample_dataset()` for a loader over a real
dataset once one is chosen, keeping the same (X, y) shape.

Usage (from backend/):
    ./.venv/Scripts/python scripts/train_classifier.py
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# `python scripts/train_classifier.py` puts scripts/ on sys.path[0], not the
# backend root, so `app` wouldn't otherwise be importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.ml.crop_catalog import CROP_RANGES
from app.services.feature_builder import FEATURE_ORDER

SEED = 42
SAMPLES_PER_CROP = 120


def sample_dataset(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    rows = []
    labels = []
    for crop, ranges in CROP_RANGES.items():
        for _ in range(SAMPLES_PER_CROP):
            row = [rng.uniform(*ranges[key]) for key in ("n", "p", "k", "ph", "temperature", "humidity", "rainfall")]
            row.append(rng.uniform(*ranges["ndvi"]))
            rows.append(row)
            labels.append(crop)
    assert [r for r in ("n", "p", "k", "ph", "temperature", "humidity", "rainfall")] + ["ndvi_mean"] == FEATURE_ORDER
    return np.array(rows), np.array(labels)


def main() -> None:
    settings = get_settings()
    rng = np.random.default_rng(SEED)

    X, y = sample_dataset(rng)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)

    # max_depth=8 (this repo's original value) was tuned back when ndvi_mean
    # carried no signal at all; cleanly separating 22 crops now needs a few
    # more splits to exploit ndvi_mean's per-crop bands - max_depth=8 measured
    # 0.45 held-out accuracy (it ran out of depth before finishing), 12 gets to
    # 0.996 and the tree naturally stops there (deeper values don't add splits).
    model = DecisionTreeClassifier(max_depth=12, min_samples_leaf=3, random_state=SEED)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print(f"Held-out accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    # A single train/test split can look good or bad by luck with only ~2,600
    # samples - 5-fold CV gives a steadier read on how much that split mattered.
    cv_scores = cross_val_score(DecisionTreeClassifier(max_depth=12, min_samples_leaf=3, random_state=SEED), X, y, cv=5)
    print(f"5-fold CV accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

    # Sanity check that every feature - especially ndvi_mean, previously sampled
    # from one global range shared by every crop and therefore unusable - is
    # actually contributing. A near-zero importance here means a feature isn't
    # earning its place in FEATURE_ORDER (or the synthetic ranges need revisiting).
    print("Feature importances:")
    for name, importance in sorted(zip(FEATURE_ORDER, model.feature_importances_), key=lambda p: p[1], reverse=True):
        print(f"  {name}: {importance:.3f}")

    out_dir = Path(settings.model_artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = "crop_dt_v1"
    out_path = out_dir / f"{version}.joblib"
    joblib.dump({"model": model, "classes": list(model.classes_)}, out_path)
    print(f"Saved {out_path} (version={version})")


if __name__ == "__main__":
    main()
