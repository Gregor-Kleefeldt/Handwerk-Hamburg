"""
Load electricians from elektriker.org Hamburg list (data/raw/elektriker_org_hamburg.json).
Convert to business points using PLZ centroid from Hamburg GeoJSON (only PLZs that exist
in our PLZ layer are included, so businesses outside Hamburg are skipped).
Returns list of dicts with 'lon', 'lat', and optional 'name', 'source'.
"""

import json
from pathlib import Path

from data.etl.load_plz import plz_centroids

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
ELEKTRIKER_JSON_PATH = RAW_DIR / "elektriker_org_hamburg.json"


def load_elektriker_org_list(path: Path | None = None) -> list[dict]:
    """Load the JSON list of electricians from elektriker.org (name, address, phone, plz)."""
    # Use provided path or default raw data path
    p = path or ELEKTRIKER_JSON_PATH
    # Return empty list if file missing
    if not p.exists():
        return []
    # Read and parse JSON
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    # Ensure we return a list (in case JSON is object)
    return data if isinstance(data, list) else []


def fetch_elektriker_org_businesses(
    list_path: Path | None = None,
    geojson_path: Path | None = None,
) -> list[dict]:
    """
    Load electricians from elektriker_org_hamburg.json and convert to business points.
    Each entry must have 'plz'; we look up the PLZ centroid from Hamburg GeoJSON.
    Only entries whose PLZ exists in our PLZ layer get a point (Hamburg + included suburbs).
    Returns list of { lon, lat, name?, source: "elektriker_org" }.
    """
    # Load raw electrician entries from JSON
    entries = load_elektriker_org_list(list_path)
    # Get PLZ -> (lon, lat) centroid mapping from Hamburg GeoJSON
    centroids = plz_centroids(geojson_path)
    features = []
    for entry in entries:
        # Extract and normalize PLZ
        plz = (entry.get("plz") or "").strip()
        if not plz:
            continue
        # Skip if PLZ not in our Hamburg PLZ layer (e.g. outside area)
        if plz not in centroids:
            continue
        # Use PLZ centroid as approximate location
        lon, lat = centroids[plz]
        features.append({
            "lon": lon,
            "lat": lat,
            "name": entry.get("name"),
            "source": "elektriker_org",
        })
    return features
