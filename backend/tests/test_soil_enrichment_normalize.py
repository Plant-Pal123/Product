from app.services.soil_enrichment.lris_client import LrisFeature
from app.services.soil_enrichment.normalize import normalize_fsl_feature, normalize_smap_feature
from app.services.soil_enrichment.specs import FSL_PROPERTIES_BY_CODE, SMAP_PROPERTIES

SMAP_PROPERTIES_BY_CODE = {spec.property_code: spec for spec in SMAP_PROPERTIES}

PH_SPEC = FSL_PROPERTIES_BY_CODE["ph"]


def test_normalize_valid_feature_uses_mid_value():
    feature = LrisFeature(
        properties={
            "PH_CLASS": "Slightly acid",
            "PH_MIN": 5.5, "PH_MAX": 6.0, "PH_MID": 5.75, "PH_MOD": 5.8,
            "PH_VAR": "Low", "PH_EST": "u",
        },
        source_record_id="123",
    )
    obs = normalize_fsl_feature(plot_id=1, spec=PH_SPEC, feature=feature, geometry_method="centroid")

    assert obs.value_numeric == 5.75
    assert obs.value_text == "Slightly acid"
    # Every real FSL value is labelled "estimated" - see normalize.py's
    # docstring for why "valid" is never used for this source.
    assert obs.quality_flag == "estimated"
    assert obs.provenance_type == "mapped"
    assert obs.source_record_id == "123"
    assert "5.5" in obs.uncertainty and "6.0" in obs.uncertainty
    assert "'u'" in obs.uncertainty
    assert obs.raw_properties_json == feature.properties


def test_normalize_falls_back_to_mod_when_mid_missing():
    feature = LrisFeature(properties={"PH_MOD": 6.2, "PH_EST": "m"}, source_record_id=None)
    obs = normalize_fsl_feature(plot_id=1, spec=PH_SPEC, feature=feature, geometry_method="centroid")
    assert obs.value_numeric == 6.2


def test_normalize_missing_feature_never_fabricates_a_value():
    obs = normalize_fsl_feature(plot_id=1, spec=PH_SPEC, feature=None, geometry_method="centroid")
    assert obs.value_numeric is None
    assert obs.value_text is None
    assert obs.quality_flag == "missing"


def test_normalize_feature_with_no_relevant_fields_is_missing_not_zero():
    feature = LrisFeature(properties={"SOME_OTHER_FIELD": "x"}, source_record_id="9")
    obs = normalize_fsl_feature(plot_id=1, spec=PH_SPEC, feature=feature, geometry_method="centroid")
    assert obs.value_numeric is None
    assert obs.quality_flag == "missing"


def test_normalize_zero_filled_non_soil_polygon_is_missing_not_a_real_zero():
    """Confirmed live on 2026-09-27: an urban ("town") polygon returns
    PH_MID=0.0 with CLASS/VAR/EST all null - a sentinel, not a real pH of
    zero. EST being null is what actually signals "not a real soil record"."""
    feature = LrisFeature(
        properties={
            "DOMSOI": "!town", "MAINSOIL": "town", "SOIL": "town",
            "PH_CLASS": None, "PH_MIN": 0.0, "PH_MAX": 0.0, "PH_MID": 0.0, "PH_MOD": 0.0,
            "PH_VAR": None, "PH_EST": None,
        },
        source_record_id="58485",
    )
    obs = normalize_fsl_feature(plot_id=1, spec=PH_SPEC, feature=feature, geometry_method="centroid")
    assert obs.value_numeric is None
    assert obs.value_text is None
    assert obs.quality_flag == "missing"


# --- S-map (categorical layers) ---------------------------------------------

DRAINAGE_SPEC = SMAP_PROPERTIES_BY_CODE["smap_drainage"]


def test_normalize_smap_stores_class_verbatim_and_never_a_number():
    feature = LrisFeature(properties={"Drainage": "Moderately well drained"}, source_record_id="77")
    obs = normalize_smap_feature(plot_id=1, spec=DRAINAGE_SPEC, feature=feature, geometry_method="centroid")

    assert obs.value_text == "Moderately well drained"
    assert obs.value_numeric is None
    assert obs.unit is None
    assert obs.provenance_type == "mapped"
    assert obs.quality_flag == "estimated"
    assert obs.source_dataset == "S-map Soil Drainage August 2026"
    assert obs.source_url == "https://lris.scinfo.org.nz/layer/125063/"
    assert obs.source_version_or_vintage == "S-map August 2026"
    assert obs.raw_properties_json == feature.properties


def test_normalize_smap_missing_feature_is_missing():
    obs = normalize_smap_feature(plot_id=1, spec=DRAINAGE_SPEC, feature=None, geometry_method="centroid")
    assert obs.value_text is None
    assert obs.value_numeric is None
    assert obs.quality_flag == "missing"
    assert obs.source_version_or_vintage == "S-map August 2026"


def test_normalize_smap_blank_value_is_missing():
    feature = LrisFeature(properties={"Drainage": "  "}, source_record_id="78")
    obs = normalize_smap_feature(plot_id=1, spec=DRAINAGE_SPEC, feature=feature, geometry_method="centroid")
    assert obs.value_text is None
    assert obs.quality_flag == "missing"
