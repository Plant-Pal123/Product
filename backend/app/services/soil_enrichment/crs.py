"""Explicit coordinate transforms for soil enrichment queries.

The workbook's field centroids (data/plant_pal_soil_crop_suitability.xlsx) are
NZTM2000 / EPSG:2193, confirmed by its "Legend & Assumptions" sheet. The LRIS
Portal's spatial query API takes plain WGS84 longitude/latitude (EPSG:4326).
Plot boundaries drawn in the app are stored as GeoJSON, which is WGS84 by the
GeoJSON spec (RFC 7946 §4) unless a CRS is otherwise declared, so those need
no transform.
"""

from dataclasses import dataclass

from pyproj import Transformer

NZTM2000 = "EPSG:2193"
WGS84 = "EPSG:4326"

_nztm_to_wgs84 = Transformer.from_crs(NZTM2000, WGS84, always_xy=True)


@dataclass(frozen=True)
class LonLat:
    lon: float
    lat: float


def nztm_to_lonlat(x: float, y: float) -> LonLat:
    """Converts an NZTM2000 (EPSG:2193) easting/northing to WGS84 lon/lat."""
    lon, lat = _nztm_to_wgs84.transform(x, y)
    return LonLat(lon=lon, lat=lat)


def geojson_centroid_lonlat(boundary: dict) -> LonLat:
    """Un-weighted centroid of a GeoJSON Point/Polygon/MultiPolygon boundary.

    Good enough for picking which 100m/1:50,000 map cell a plot falls in -
    not a substitute for a proper area-weighted centroid on very large or
    concave plots. Assumes WGS84 coordinates (see module docstring).
    """
    geom_type = boundary.get("type")
    coords = boundary.get("coordinates")
    if geom_type == "Point":
        lon, lat = coords
        return LonLat(lon=lon, lat=lat)

    if geom_type == "Polygon":
        rings = coords
    elif geom_type == "MultiPolygon":
        rings = [ring for polygon in coords for ring in polygon]
    else:
        raise ValueError(f"Unsupported boundary geometry type: {geom_type!r}")

    points = [pt for ring in rings for pt in ring]
    if not points:
        raise ValueError("Boundary has no coordinates")
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return LonLat(lon=lon, lat=lat)
