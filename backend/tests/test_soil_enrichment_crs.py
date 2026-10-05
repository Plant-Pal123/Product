import pytest

from app.services.soil_enrichment.crs import geojson_centroid_lonlat, nztm_to_lonlat


def test_nztm_to_lonlat_round_trips_and_stays_in_nz():
    # A workbook centroid (data/plant_pal_soil_crop_suitability.xlsx, Field ID 1).
    x, y = 1756394, 5415528.5
    result = nztm_to_lonlat(x, y)

    # New Zealand's rough lon/lat bounding box - a wrong CRS (e.g. treating
    # these as already-WGS84, or using the wrong UTM zone) would fail this.
    assert 166 < result.lon < 179
    assert -47 < result.lat < -34


def test_nztm_to_lonlat_is_deterministic():
    a = nztm_to_lonlat(1756394, 5415528.5)
    b = nztm_to_lonlat(1756394, 5415528.5)
    assert a == b


def test_geojson_centroid_point():
    centroid = geojson_centroid_lonlat({"type": "Point", "coordinates": [174.77, -41.29]})
    assert centroid.lon == pytest.approx(174.77)
    assert centroid.lat == pytest.approx(-41.29)


def test_geojson_centroid_polygon_is_mean_of_ring_points():
    boundary = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]],
    }
    centroid = geojson_centroid_lonlat(boundary)
    assert centroid.lon == pytest.approx(0.8)  # (0+0+2+2+0)/5
    assert centroid.lat == pytest.approx(0.8)


def test_geojson_centroid_rejects_unsupported_geometry():
    with pytest.raises(ValueError):
        geojson_centroid_lonlat({"type": "LineString", "coordinates": [[0, 0], [1, 1]]})
