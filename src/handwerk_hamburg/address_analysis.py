"""
Address-based district analysis: geocode an address, find the Hamburg district (Stadtteil),
and return electrician statistics for that district.

Geocoding is delegated to handwerk_hamburg.geocoding (single source of truth).
"""

import json
from pathlib import Path
from typing import Any

from shapely import STRtree
from shapely.geometry import shape, Point

from handwerk_hamburg.geocoding import geocode_address_with_fallbacks


def _build_district_tree(geojson: dict) -> tuple[STRtree | None, list[tuple[str | None, int]]]:
    """
    Build an STRtree from GeoJSON features and a list of (stadtteil, feature_index) for lookup.

    Returns:
        (tree, district_list) where district_list[i] is (stadtteil, original_feature_index)
        for the i-th polygon in the tree. tree is None if no valid features.
    """
    features = geojson.get("features") or []
    polygons = []
    district_list = []
    for i, feat in enumerate(features):
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            poly = shape(geom)
        except Exception:
            continue
        props = feat.get("properties") or {}
        stadtteil = props.get("stadtteil") or props.get("district")
        if stadtteil:
            stadtteil = str(stadtteil).strip()
        polygons.append(poly)
        district_list.append((stadtteil, i))
    if not polygons:
        return None, []
    return STRtree(polygons), district_list


def get_district_from_coordinates(lat: float, lon: float, geojson: dict) -> str | None:
    """
    Determine the Hamburg district (Stadtteil) for a given point using the PLZ GeoJSON.

    Uses a spatial index (STRtree): first finds polygons containing the point via
    predicate "within"; if none, uses query_nearest for the nearest polygon.

    Args:
        lat: Latitude of the point.
        lon: Longitude of the point (GeoJSON and Shapely use x=lon, y=lat).
        geojson: GeoJSON FeatureCollection with features that have geometry and
                 properties.stadtteil (district name).

    Returns:
        The district name (stadtteil) string, or None if the GeoJSON has no features.
    """
    tree, district_list = _build_district_tree(geojson)
    if tree is None or not district_list:
        return None
    point = Point(lon, lat)
    # Find polygons that contain the point (point within polygon)
    candidate_indices = tree.query(point, predicate="within")
    if candidate_indices.size > 0:
        stadtteil = district_list[int(candidate_indices[0])][0]
        return stadtteil or None
    # Fallback: nearest polygon (e.g. point outside Hamburg)
    nearest_idx = tree.query_nearest(point, all_matches=False)
    if nearest_idx is not None:
        stadtteil = district_list[int(nearest_idx)][0]
        return stadtteil or None
    return None


def get_businesses_with_district(
    businesses: list[dict],
    geojson: dict,
) -> list[dict]:
    """
    Assign a district (Stadtteil) to each business by point-in-polygon using the GeoJSON.

    Uses a spatial index (STRtree): one tree is built over all polygons, then each
    business point is queried with predicate "within" so only candidate polygons
    are considered instead of looping over all features.

    Args:
        businesses: List of dicts with "lat" and "lon" (and optionally "name", "address").
        geojson: GeoJSON FeatureCollection with PLZ polygons and properties.stadtteil.

    Returns:
        List of the same business dicts with an added "district" key (stadtteil name).
        Businesses outside all polygons get district None and are still included.
    """
    tree, district_list = _build_district_tree(geojson)
    result = []
    if tree is None or not district_list:
        return [{**b, "district": None} for b in businesses]
    for b in businesses:
        lat = b.get("lat")
        lon = b.get("lon")
        if lat is None or lon is None:
            result.append({**b, "district": None})
            continue
        point = Point(lon, lat)
        candidate_indices = tree.query(point, predicate="within")
        district = None
        if candidate_indices.size > 0:
            district = district_list[int(candidate_indices[0])][0]
        result.append({**b, "district": district})
    return result


def run_district_analysis(
    address: str,
    geojson_path: Path,
    businesses_path: Path | None = None,
) -> dict[str, Any]:
    """
    Geocode the address, find the district, and return electrician statistics for that district.

    Args:
        address: Full address string (e.g. "Max-Brauer-Allee 10, Hamburg").
        geojson_path: Path to the scored white-spot GeoJSON (PLZ features with stadtteil).
        businesses_path: Path to electricians JSON (list of {lat, lon, name, address}).
                        If None or file missing, businesses list will be empty.

    Returns:
        Dict with keys: district (str or None), count (int), businesses (list of {name, address}),
        user_lat, user_lon (float or None), error (str or None if no error).
    """
    # Load GeoJSON for district lookup and business assignment
    if not geojson_path.exists():
        return {
            "district": None,
            "count": 0,
            "businesses": [],
            "user_lat": None,
            "user_lon": None,
            "error": "GeoJSON data not found.",
        }
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)

    # Single geocoding path: known-address fallback + normalized variants via Nominatim (geocoding.py)
    coords = geocode_address_with_fallbacks(address)
    if coords is None:
        return {
            "district": None,
            "count": 0,
            "businesses": [],
            "user_lat": None,
            "user_lon": None,
            "error": "Adresse konnte nicht gefunden werden. Tipp: „Max-Brauer-Allee“ mit Bindestrichen und Doppel-e schreiben.",
        }
    user_lat, user_lon = coords

    # Resolve district from coordinates
    district_name = get_district_from_coordinates(user_lat, user_lon, geojson)
    if not district_name:
        return {
            "district": None,
            "count": 0,
            "businesses": [],
            "user_lat": user_lat,
            "user_lon": user_lon,
            "error": "Kein Stadtteil für diese Adresse gefunden (außerhalb Hamburg?).",
        }

    # Load businesses and assign district (support both array and { metadata, electricians } format)
    businesses = []
    if businesses_path and businesses_path.exists():
        with open(businesses_path, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            businesses = raw
        elif isinstance(raw, dict) and "electricians" in raw:
            businesses = raw["electricians"]
        else:
            businesses = []

    # Assign district to each business and filter by the resolved district name
    with_district = get_businesses_with_district(businesses, geojson)
    district_businesses = [b for b in with_district if b.get("district") == district_name]

    # Build list of {name, address} for display (name optional)
    business_list = []
    for b in district_businesses:
        name = b.get("name") or "Unbenannt"
        business_list.append({"name": name, "address": b.get("address")})

    return {
        "district": district_name,
        "count": len(district_businesses),
        "businesses": business_list,
        "user_lat": user_lat,
        "user_lon": user_lon,
        "error": None,
    }
