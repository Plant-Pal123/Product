"""Plan generator - combines model outputs, preferences (P), timeframes and cost
data into a future plan (design.md §6, FR-5.x). Output is stored as JSON and
rendered both in the dashboard and as a PDF from the same content.

Amendment costs, uptake fractions and rotation advice below are heuristic
placeholders (round per-unit costs, a flat depletion fraction) rather than a
sourced agronomic dataset - requirements.md doesn't pin one down yet. They give
the pipeline a real, non-trivial plan to work with; swap the tables for sourced
figures once available.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.db.models import Crop, Recommendation
from app.ml.regressor import SOIL_TARGET_KEYS, compute_soil_gap

# Illustrative cost per unit of amendment, per hectare.
AMENDMENT_COST_PER_KG = {"n": 1.5, "p": 2.0, "k": 1.8}  # NPK fertiliser, $/kg/ha
AMENDMENT_COST_PER_PH_UNIT = 60.0  # lime/sulfur, $/pH unit/ha
GAP_THRESHOLD = 1.0  # kg/ha (or pH units, scaled below) below which a gap is ignored as noise
PH_GAP_THRESHOLD = 0.2

# Flat fraction of standing N/P/K assumed drawn down by the growing crop; pH is
# treated as unaffected by growth alone (only amendments move it).
SOIL_UPTAKE_FRACTION = 0.15


@dataclass
class FinanceProjection:
    estimated_yield: float
    revenue: float
    crop_cost: float
    amendment_cost: float
    margin: float


def project_finances(crop: Crop, area_ha: float, suitability_factor: float, amendment_cost: float) -> FinanceProjection:
    """yield ~= base_yield(crop) x suitability_factor x area; margin = revenue -
    (crop cost + amendment cost), per design.md §6."""

    # TODO: base_yield per crop is not modelled yet - placeholder until a yield
    # table/model is defined (requirements.md FR-5.8 is a "Should", not MVP-blocking).
    base_yield_per_ha = 1.0
    estimated_yield = base_yield_per_ha * suitability_factor * area_ha
    revenue = estimated_yield * crop.price_per_kg
    crop_cost = crop.cost_per_ha * area_ha
    margin = revenue - (crop_cost + amendment_cost)
    return FinanceProjection(estimated_yield, revenue, crop_cost, amendment_cost, margin)


def compute_amendments(soil_gap: dict[str, float], area_ha: float) -> tuple[list[dict], float]:
    """Turns a soil gap into concrete actions + an estimated cost (FR-3.3)."""
    amendments = []
    total_cost = 0.0

    for nutrient in ("n", "p", "k"):
        gap = soil_gap[nutrient]
        if gap > GAP_THRESHOLD:
            cost = round(gap * area_ha * AMENDMENT_COST_PER_KG[nutrient], 2)
            amendments.append({"nutrient": nutrient, "action": "add", "amount_kg_per_ha": round(gap, 1), "cost": cost})
            total_cost += cost
        elif gap < -GAP_THRESHOLD:
            amendments.append({"nutrient": nutrient, "action": "reduce", "amount_kg_per_ha": round(-gap, 1), "cost": 0.0})

    ph_gap = soil_gap["ph"]
    if abs(ph_gap) > PH_GAP_THRESHOLD:
        cost = round(abs(ph_gap) * area_ha * AMENDMENT_COST_PER_PH_UNIT, 2)
        amendments.append({
            "nutrient": "ph",
            "action": "raise" if ph_gap > 0 else "lower",
            "amount_units": round(abs(ph_gap), 2),
            "cost": cost,
        })
        total_cost += cost

    return amendments, round(total_cost, 2)


def build_heuristics(crop: Crop, soil_gap: dict[str, float]) -> list[str]:
    """Rule-based guidance for the plan panel (FR-5.5): sowing window, nutrient
    prep, rotation advice."""
    tips = [
        f"Sow within the next 14 days for a {crop.days_to_harvest}-day cycle to {crop.name}."
    ]

    for nutrient in ("n", "p", "k"):
        gap = soil_gap[nutrient]
        label = nutrient.upper()
        if gap > GAP_THRESHOLD:
            tips.append(f"Soil {label} is below what {crop.name} needs - add about {gap:.0f} kg/ha before sowing.")
        elif gap < -GAP_THRESHOLD:
            tips.append(f"Soil {label} already exceeds what {crop.name} needs - skip additional {label}.")

    ph_gap = soil_gap["ph"]
    if abs(ph_gap) > PH_GAP_THRESHOLD:
        direction = "raise (lime)" if ph_gap > 0 else "lower (sulfur)"
        tips.append(f"Adjust soil pH: {direction} it by about {abs(ph_gap):.1f} before sowing.")

    tips.append(
        f"Avoid repeating {crop.name} in the same plot next season - rotate with a "
        "different crop family to manage soil-borne pests and nutrient depletion."
    )
    return tips


def project_soil_effect(current_soil: dict[str, float]) -> dict[str, float]:
    """Projected post-harvest soil values (FR-5.7): a flat uptake fraction on
    N/P/K, pH held constant (growth alone doesn't move pH - amendments do)."""
    return {
        "n": round(current_soil["n"] * (1 - SOIL_UPTAKE_FRACTION), 2),
        "p": round(current_soil["p"] * (1 - SOIL_UPTAKE_FRACTION), 2),
        "k": round(current_soil["k"] * (1 - SOIL_UPTAKE_FRACTION), 2),
        "ph": current_soil["ph"],
    }


def generate_plan(recommendation: Recommendation, crop: Crop, current_soil: dict[str, float], area_ha: float = 1.0) -> dict:
    """Builds the JSON future-plan content for a recommendation (design.md §6)."""

    soil_gap = compute_soil_gap(current=current_soil, targets=recommendation.soil_targets)
    amendments, amendment_cost = compute_amendments(soil_gap, area_ha)

    today = date.today()
    harvest_date = today + timedelta(days=crop.days_to_harvest)

    finances = project_finances(crop, area_ha, suitability_factor=recommendation.confidence, amendment_cost=amendment_cost)

    return {
        "heuristics": build_heuristics(crop, soil_gap),
        "timeline": {
            "sow_date": today.isoformat(),
            "harvest_date": harvest_date.isoformat(),
            "days_to_harvest": crop.days_to_harvest,
        },
        "soil_effect": {
            "current": {k: current_soil[k] for k in SOIL_TARGET_KEYS},
            "target": recommendation.soil_targets,
            "projected_post_harvest": project_soil_effect(current_soil),
        },
        "amendments": amendments,
        "finances": vars(finances),
    }
