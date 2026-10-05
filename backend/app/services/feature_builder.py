"""Feature builder - turns raw soil/weather/satellite readings into the single
feature vector consumed by both ML models (design.md §2.1, §5.1).

This is the shared contract between ingestion and the ML layer: keep the feature
names/order here in sync with whatever the trained model artifacts expect.
"""

from dataclasses import dataclass

from app.db.models import SatelliteReading, SoilReading, WeatherReading

FEATURE_ORDER = ["n", "p", "k", "ph", "temperature", "humidity", "rainfall", "ndvi_mean"]


@dataclass
class FeatureVector:
    n: float
    p: float
    k: float
    ph: float
    temperature: float
    humidity: float
    rainfall: float
    ndvi_mean: float
    imputed_fields: list[str]  # fields filled with regional defaults (design.md §10)

    def as_list(self) -> list[float]:
        return [getattr(self, name) for name in FEATURE_ORDER]

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in FEATURE_ORDER}


# Regional defaults used to impute missing readings (design.md §10). Placeholder
# values - replace with real regional baselines before relying on this in prod.
REGIONAL_DEFAULTS = {
    "n": 50.0,
    "p": 30.0,
    "k": 30.0,
    "ph": 6.5,
    "temperature": 20.0,
    "humidity": 60.0,
    "rainfall": 100.0,
    "ndvi_mean": 0.5,
}


def build_feature_vector(
    soil: SoilReading | None,
    weather: WeatherReading | None,
    satellite: SatelliteReading | None,
) -> FeatureVector:
    imputed: list[str] = []

    def pick(value: float | None, key: str) -> float:
        if value is None:
            imputed.append(key)
            return REGIONAL_DEFAULTS[key]
        return value

    return FeatureVector(
        n=pick(soil.n if soil else None, "n"),
        p=pick(soil.p if soil else None, "p"),
        k=pick(soil.k if soil else None, "k"),
        ph=pick(soil.ph if soil else None, "ph"),
        temperature=pick(weather.temp if weather else None, "temperature"),
        humidity=pick(weather.humidity if weather else None, "humidity"),
        rainfall=pick(weather.rainfall if weather else None, "rainfall"),
        ndvi_mean=pick(satellite.ndvi_mean if satellite else None, "ndvi_mean"),
        imputed_fields=imputed,
    )
