"""Property specs for the LRIS Portal Fundamental Soil Layers (FSL) adapter.

Verified against https://lris.scinfo.org.nz/services/api/v1.x/layers/<id>/
(the LRIS Portal's public, unauthenticated metadata API) on 2026-09-27. Do not
add a property here without checking that layer's metadata first - see
backend/README.md#soil-property-enrichment for the verification method.

FSL is the *fallback* national-coverage layer set: Landcare Research state
its soil property data "have not been updated since the late 1990s" and
recommend S-map Online as the current source where it has coverage. S-map's
newer per-property layers (e.g. "S-map Predicted pH August 2020", layer
120518) are licensed CC BY-NC-ND 4.0 - No-Derivatives forbids the kind of
normalisation/re-expression this pipeline does, and No-Commercial needs a
call on whether PlantPal counts as commercial use, so they are deliberately
NOT wired up here. See the completion report for that open decision.

Each FSL layer shares one schema shape: `{PREFIX}_MIN/MAX/MID/MOD` (a range
plus Landcare's chosen "modal"/representative value), `{PREFIX}_CLASS` (the
categorical class the numeric range was binned from) and `{PREFIX}_EST`
('Y'/'N' - whether the polygon's value is a direct NSD match or a
professional estimate against a similar soil).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FslPropertySpec:
    property_code: str
    layer_id: int
    field_prefix: str
    unit: str | None
    depth_top_cm: float | None
    depth_bottom_cm: float | None
    source_dataset: str
    description: str


LICENSE_NAME = "Landcare Data Use License"
LICENSE_URL = "https://lris.scinfo.org.nz/license/landcare-data-use-licence-v1/"
ATTRIBUTION_TEXT = "Data reproduced with the permission of Landcare Research New Zealand Limited"
SOURCE_NAME = "Manaaki Whenua - Landcare Research (LRIS Portal)"
SOURCE_VINTAGE = "FSL best-available data as at 2000 (dataset last republished 2026-04-01)"
# FSL polygons come from the NZLRI's 1:50,000-scale soil unit delineation.
SPATIAL_RESOLUTION_M = None  # polygon map product, not a fixed-resolution raster

FSL_PROPERTIES: list[FslPropertySpec] = [
    FslPropertySpec(
        property_code="ph",
        layer_id=48102,
        field_prefix="PH",
        unit="pH",
        depth_top_cm=None,
        depth_bottom_cm=None,
        source_dataset="FSL pH",
        description="Soil pH (acidity/alkalinity); depth interval not stated in source metadata.",
    ),
    FslPropertySpec(
        property_code="organic_carbon",
        layer_id=48098,
        field_prefix="CARBON",
        unit="%",
        depth_top_cm=0,
        depth_bottom_cm=20,
        source_dataset="FSL Soil Carbon",
        description="Total carbon (organic matter content), weighted average 0-0.2 m.",
    ),
    FslPropertySpec(
        property_code="cec",
        layer_id=48099,
        field_prefix="CEC",
        unit="cmol(+)/kg",
        depth_top_cm=0,
        depth_bottom_cm=60,
        source_dataset="FSL Cation Exchange Capacity",
        description="Cation exchange capacity, weighted average 0-0.6 m.",
    ),
    FslPropertySpec(
        property_code="available_water_capacity",
        layer_id=48100,
        field_prefix="PAW",
        unit="mm",
        depth_top_cm=0,
        depth_bottom_cm=90,
        source_dataset="FSL Profile Available Water",
        description=(
            "Profile available water to 0.9 m depth or potential rooting depth "
            "(whichever is less), weighted average."
        ),
    ),
    FslPropertySpec(
        property_code="potential_rooting_depth",
        layer_id=48110,
        field_prefix="PRD",
        unit="m",
        depth_top_cm=None,
        depth_bottom_cm=None,
        source_dataset="FSL Potential Rooting Depth",
        description="Min/max depth to a layer that may impede root extension.",
    ),
    FslPropertySpec(
        property_code="phosphate_retention",
        layer_id=48111,
        field_prefix="PRET",
        unit="%",
        depth_top_cm=0,
        depth_bottom_cm=20,
        source_dataset="FSL Phosphate Retention",
        description="Phosphate retention, weighted average 0-0.2 m.",
    ),
]

FSL_PROPERTIES_BY_CODE = {spec.property_code: spec for spec in FSL_PROPERTIES}
