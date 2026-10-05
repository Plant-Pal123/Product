"""Turns a raw LRIS feature + property spec into a normalized observation.

Never invents a numeric value: if the source has no feature at the queried
point, or the expected fields are missing/null, the result carries
value_numeric=None and quality_flag="missing" rather than a fabricated 0 or a
class-to-number mapping (see plantpal_soil_data_scraper_spec.md "Important
scope distinction").
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from app.services.soil_enrichment.lris_client import LrisFeature
from app.services.soil_enrichment.specs import (
    ATTRIBUTION_TEXT,
    LICENSE_NAME,
    LICENSE_URL,
    SOURCE_NAME,
    SOURCE_VINTAGE,
    SPATIAL_RESOLUTION_M,
    FslPropertySpec,
)


@dataclass(frozen=True)
class NormalizedObservation:
    plot_id: int
    property_code: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    depth_top_cm: float | None
    depth_bottom_cm: float | None
    observation_date: date | None
    retrieved_at: datetime
    provenance_type: str
    source_name: str
    source_dataset: str
    source_record_id: str | None
    source_url: str
    source_version_or_vintage: str | None
    spatial_resolution_m: float | None
    geometry_method: str
    quality_flag: str
    uncertainty: str | None
    raw_properties_json: dict[str, Any]


def _missing_observation(plot_id: int, spec: FslPropertySpec, geometry_method: str) -> NormalizedObservation:
    return NormalizedObservation(
        plot_id=plot_id,
        property_code=spec.property_code,
        value_numeric=None,
        value_text=None,
        unit=spec.unit,
        depth_top_cm=spec.depth_top_cm,
        depth_bottom_cm=spec.depth_bottom_cm,
        observation_date=None,
        retrieved_at=datetime.now(timezone.utc),
        provenance_type="mapped",
        source_name=SOURCE_NAME,
        source_dataset=spec.source_dataset,
        source_record_id=None,
        source_url=f"https://lris.scinfo.org.nz/layer/{spec.layer_id}/",
        source_version_or_vintage=SOURCE_VINTAGE,
        spatial_resolution_m=SPATIAL_RESOLUTION_M,
        geometry_method=geometry_method,
        quality_flag="missing",
        uncertainty=None,
        raw_properties_json={},
    )


def normalize_fsl_feature(
    plot_id: int,
    spec: FslPropertySpec,
    feature: LrisFeature | None,
    geometry_method: str,
) -> NormalizedObservation:
    """`feature` is None when the point query returned no polygon at all
    (e.g. it falls in an area FSL has no soil unit for).

    Confirmed live on 2026-09-27 against a real query: a polygon that isn't a
    real soil unit at all (e.g. "town") comes back with every numeric field
    (MIN/MAX/MID/MOD) zero-filled, while CLASS/VAR/EST are all null - so a
    zero here is a "not applicable" sentinel, not a measurement of zero.
    _EST present (any value) is the reliable "this is a real soil record"
    signal; checking whether the numeric fields are non-null is not enough.

    Also confirmed live: _EST is NOT the simple Y/N flag the layer's
    plain-English description implies (real records return codes like "u",
    not "Y"/"N") - it documents a graded "origin of estimate" scale from
    measured to general inference, but the exact code table wasn't published
    anywhere reachable. Rather than guess which codes mean "measured", every
    real FSL value is conservatively labelled "estimated" (true for the
    entire scale it actually is), with the raw code kept in `uncertainty`."""
    if feature is None:
        return _missing_observation(plot_id, spec, geometry_method)

    props = feature.properties
    mid_key = f"{spec.field_prefix}_MID"
    mod_key = f"{spec.field_prefix}_MOD"
    min_key = f"{spec.field_prefix}_MIN"
    max_key = f"{spec.field_prefix}_MAX"
    class_key = f"{spec.field_prefix}_CLASS"
    var_key = f"{spec.field_prefix}_VAR"
    est_key = f"{spec.field_prefix}_EST"

    est_code = props.get(est_key)
    if est_code is None:
        return _missing_observation(plot_id, spec, geometry_method)

    # Prefer the MID (midpoint of the reported range) as the point estimate;
    # fall back to MOD (Landcare's chosen representative/modal value) if MID
    # is absent. Never average MIN/MAX ourselves beyond that documented pair.
    value_numeric = props.get(mid_key)
    if value_numeric is None:
        value_numeric = props.get(mod_key)
    value_text = props.get(class_key)

    if value_numeric is None and value_text is None:
        return _missing_observation(plot_id, spec, geometry_method)

    uncertainty_parts = [f"source estimate-origin code: {est_code!r} (exact code table not published anywhere we could find)"]
    if props.get(min_key) is not None and props.get(max_key) is not None:
        uncertainty_parts.insert(0, f"source-reported range [{props[min_key]}, {props[max_key]}] {spec.unit or ''}".strip())
    if props.get(var_key) is not None:
        uncertainty_parts.append(f"variability code: {props[var_key]!r}")

    return NormalizedObservation(
        plot_id=plot_id,
        property_code=spec.property_code,
        value_numeric=float(value_numeric) if value_numeric is not None else None,
        value_text=str(value_text) if value_text is not None else None,
        unit=spec.unit,
        depth_top_cm=spec.depth_top_cm,
        depth_bottom_cm=spec.depth_bottom_cm,
        observation_date=None,  # FSL has no per-feature sample date; vintage carries this instead
        retrieved_at=datetime.now(timezone.utc),
        provenance_type="mapped",
        source_name=SOURCE_NAME,
        source_dataset=spec.source_dataset,
        source_record_id=feature.source_record_id,
        source_url=f"https://lris.scinfo.org.nz/layer/{spec.layer_id}/",
        source_version_or_vintage=SOURCE_VINTAGE,
        spatial_resolution_m=SPATIAL_RESOLUTION_M,
        geometry_method=geometry_method,
        quality_flag="estimated",
        uncertainty="; ".join(uncertainty_parts),
        raw_properties_json=props,
    )


__all__ = [
    "NormalizedObservation",
    "normalize_fsl_feature",
    "ATTRIBUTION_TEXT",
    "LICENSE_NAME",
    "LICENSE_URL",
]
