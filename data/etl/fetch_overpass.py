"""
Fetch craft businesses (e.g. electricians) in Hamburg from OpenStreetMap via Overpass API.
Returns a list of GeoJSON-style point features with lon/lat.
"""

import requests
from data.etl.config import OVERPASS_URL, HAMBURG_BBOX, TRADES


def build_overpass_query(bbox: tuple, tag_key: str, tag_value: str) -> str:
    """Build Overpass QL query for nodes/ways with the given tag inside bbox."""
    # Format bbox as min_lat, min_lon, max_lat, max_lon for Overpass
    min_lon, min_lat, max_lon, max_lat = bbox
    bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    # Query nodes and way centroids with the craft=electrician (or other) tag
    # timeout 25s is the server limit for overpass-api.de
    query = f"""
    [out:json][timeout:25];
    (
      node["{tag_key}"="{tag_value}"]({bbox_str});
      way["{tag_key}"="{tag_value}"]({bbox_str});
    );
    out center;
    """
    return query


def fetch_businesses(trade_id: str = "electrician") -> list[dict]:
    """
    Fetch businesses for the given trade from Overpass.
    Returns list of dicts with 'lon', 'lat', 'osm_type', 'osm_id'.
    """
    if trade_id not in TRADES:
        raise ValueError(f"Unknown trade: {trade_id}")
    conf = TRADES[trade_id]
    tag_key = conf["overpass_key"]
    tag_value = conf["overpass_value"]
    query = build_overpass_query(HAMBURG_BBOX, tag_key, tag_value)
    # POST request to Overpass API
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    features = []
    for el in data.get("elements", []):
        lon, lat = None, None
        if el.get("type") == "node":
            lon = el.get("lon")
            lat = el.get("lat")
        elif el.get("type") == "way" and "center" in el:
            lon = el["center"].get("lon")
            lat = el["center"].get("lat")
        if lon is not None and lat is not None:
            features.append({
                "lon": float(lon),
                "lat": float(lat),
                "osm_type": el.get("type"),
                "osm_id": el.get("id"),
            })
    return features
