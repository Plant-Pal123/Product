"""Experiment: read S-map / FSL soil values at one point from LRIS via WFS.

Not used by the app. Usage:

    python smap_test.py                      # default farm point west of Palmerston North, all layers
    python smap_test.py -40.35 175.61        # lat lon
    python smap_test.py --only drainage      # just one layer

Needs LRIS_KEY in experiments/smap/.env (see .env.example).
"""

import argparse
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_URLS = [
    ("LRIS", "https://lris.scinfo.org.nz/services;key={key}/wfs/"),
    ("Koordinates", "https://koordinates.com/services;key={key}/wfs/"),
]

LAYERS = {
    "drainage": {"id": 125063, "title": "S-map Soil Drainage"},
    "texture": {"id": 125064, "title": "S-map Soil Texture"},
    "depth": {"id": 125062, "title": "S-map Soil Depth"},
    "paw": {"id": 48100, "title": "FSL Profile Available Water"},
}

# Half-width of the search box around the point, in degrees (~11 m).
BOX = 0.0001
TIMEOUT = 30


class WfsError(Exception):
    """A request failed; the message is a plain-English explanation."""


def describe(name, props):
    """One plain-English line for the value(s) at the point."""
    if name == "drainage":
        return f"Soil drainage: {props.get('Drainage')}"
    if name == "texture":
        return f"Soil texture: {props.get('Texture')}"
    if name == "depth":
        return f"Soil depth: {props.get('SibDepth')}"
    if name == "paw":
        # FSL marks urban areas (and some other land types) with a soil name and
        # no PAW class; their 0 mm values aren't real readings.
        if props.get("PAW_CLASS") is None and not props.get("PAW_MAX"):
            return f"No data at this point - FSL maps it as '{props.get('SOIL')}', with no available-water reading"
        return (f"Profile available water: {props.get('PAW_MIN')}–{props.get('PAW_MAX')} mm "
                f"(middle estimate {props.get('PAW_MID')} mm, class {props.get('PAW_CLASS')}) "
                f"· soil series: {props.get('SERIES')}")
    return str(props)


def mask(text, key):
    return text.replace(key, "<LRIS_KEY>") if key else text


def get_capabilities(base, key):
    """Return the set of feature type names this key can see, or raise WfsError."""
    url = base.format(key=key)
    try:
        r = requests.get(url, params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"}, timeout=TIMEOUT)
    except requests.RequestException as err:
        raise WfsError(f"Couldn't reach the server (wrong URL or no internet): {mask(str(err), key)}")
    if r.status_code == 401:
        raise WfsError("The server didn't accept the key (HTTP 401). Either the key is wrong, "
                       "or it was created on the other website.")
    if r.status_code == 403:
        raise WfsError("The key was recognised but isn't allowed to use WFS (HTTP 403). "
                       "Edit the key's permissions and enable web services (WFS).")
    if r.status_code != 200:
        raise WfsError(f"Unexpected reply from the server (HTTP {r.status_code}): {mask(r.text[:300], key)}")
    return set(re.findall(r"<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>", r.text))


def find_type_name(names, layer_id):
    """Match 'layer-<id>' with or without a namespace prefix (e.g. 'lris.scinfo.org.nz:layer-125063')."""
    for name in sorted(names):
        if name == f"layer-{layer_id}" or name.endswith(f":layer-{layer_id}"):
            return name
    return None


def point_in_ring(lon, lat, ring):
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def contains(geometry, lon, lat):
    """True if a GeoJSON Polygon/MultiPolygon contains the point (holes respected)."""
    if not geometry:
        return False
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"] if geometry["type"] == "MultiPolygon" else []
    for rings in polygons:
        if rings and point_in_ring(lon, lat, rings[0]) and not any(point_in_ring(lon, lat, hole) for hole in rings[1:]):
            return True
    return False


def get_features(base, key, type_name, lat, lon):
    url = base.format(key=key)
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": type_name, "outputFormat": "json", "srsName": "EPSG:4326",
        # WFS 2.0 with the urn CRS uses latitude,longitude axis order.
        "bbox": f"{lat - BOX},{lon - BOX},{lat + BOX},{lon + BOX},urn:ogc:def:crs:EPSG::4326",
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
    except requests.RequestException as err:
        raise WfsError(f"Couldn't reach the server (wrong URL or no internet): {mask(str(err), key)}")
    if r.status_code in (401, 403):
        raise WfsError(f"The key isn't allowed to read this layer (HTTP {r.status_code}). "
                       "Make sure you've accepted the layer's licence on the website and the key has WFS access.")
    if "unknown" in r.text.lower() and "feature type" in r.text.lower():
        raise WfsError(f"The server says layer name '{type_name}' doesn't exist for this key. "
                       "Usually this means the layer's licence hasn't been accepted yet.")
    if r.status_code != 200:
        raise WfsError(f"Unexpected reply from the server (HTTP {r.status_code}): {mask(r.text[:300], key)}")
    try:
        return r.json().get("features", [])
    except ValueError:
        raise WfsError(f"The server didn't send JSON back: {mask(r.text[:300], key)}")


def pick_feature(features, lat, lon):
    """Return (feature, contains_point): the polygon containing the point, else the first one in the box."""
    for feature in features:
        if contains(feature.get("geometry"), lon, lat):
            return feature, True
    return (features[0] if features else None), False


def main():
    parser = argparse.ArgumentParser(description="Test reading S-map/FSL soil layers from LRIS via WFS.")
    parser.add_argument("lat", nargs="?", type=float, default=-40.30)
    parser.add_argument("lon", nargs="?", type=float, default=175.52)
    parser.add_argument("--only", choices=LAYERS, help="test just one layer")
    args = parser.parse_args()

    load_dotenv(Path(__file__).with_name(".env"))
    key = os.getenv("LRIS_KEY", "").strip()
    if not key or key == "your-key-here":
        sys.exit("No API key found. Create experiments/smap/.env containing LRIS_KEY=<your key> (see .env.example).")

    print(f"Point: lat {args.lat}, lon {args.lon}\n")

    # Find which website accepts the key and actually gives it some layers.
    site, base, names, accepted = None, None, None, False
    for site_name, site_base in BASE_URLS:
        try:
            site_names = get_capabilities(site_base, key)
        except WfsError as err:
            print(f"[{site_name}] {err}")
            continue
        accepted = True
        print(f"[{site_name}] Key accepted - it can see {len(site_names)} layers via WFS.")
        if site_names:
            site, base, names = site_name, site_base, site_names
            break
    print()
    if not accepted:
        sys.exit("Neither website accepted the key. Check it was copied correctly into .env with no spaces or quotes.")
    if not base:
        sys.exit("The key is valid, but it doesn't have access to any layers at all. Usually that means the key was "
                 "created without the right permissions: on the website, go to your profile -> API keys, edit (or "
                 "re-create) the key and tick 'Query layer data' and 'Access to ... web services (WFS)'. Also accept "
                 "each layer's licence on its page.")

    selected = {args.only: LAYERS[args.only]} if args.only else LAYERS
    for name, layer in selected.items():
        print(f"=== {layer['title']} (layer {layer['id']}) ===")
        type_name = find_type_name(names, layer["id"])
        if not type_name:
            print(f"  Not available to this key on {site}. Usually that means you haven't accepted this layer's "
                  f"licence yet - open https://lris.scinfo.org.nz/layer/{layer['id']}/ while signed in and accept it.\n")
            continue
        if type_name != f"layer-{layer['id']}":
            print(f"  (GetCapabilities lists it as '{type_name}', using that name)")
        try:
            features = get_features(base, key, type_name, args.lat, args.lon)
        except WfsError as err:
            print(f"  Request failed: {err}\n")
            continue
        feature, exact = pick_feature(features, args.lat, args.lon)
        if not feature:
            print("  No data at this point (the layer doesn't cover it).\n")
            continue
        props = feature.get("properties", {})
        print(f"  {describe(name, props)}")
        if not exact:
            print(f"  (No polygon contains the exact point; showing the nearest of {len(features)} within ~11 m)")
        elif len(features) > 1:
            print(f"  ({len(features)} polygons within ~11 m of the point; showing the one containing it)")
        print(f"  Fields returned: {', '.join(props)}")
        print(f"  Raw values: {props}\n")
    print(f"Used: {site} ({base.format(key='<LRIS_KEY>')})")


if __name__ == "__main__":
    main()
