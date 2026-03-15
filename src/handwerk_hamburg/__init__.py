"""
Handwerk Hamburg — White-Spot Map analysis package.

Reusable logic for loading PLZ/business data, geocoding, scoring, and visualization.
"""

from handwerk_hamburg.config import (
    DEFAULT_TRADE,
    HAMBURG_BBOX,
    OVERPASS_URL,
    TRADES,
    get_processed_dir,
    get_raw_dir,
    set_project_root,
)
from handwerk_hamburg.data_loader import (
    load_elektriker_org_list,
    load_geojson,
    load_population,
    load_stadtteil,
    plz_centroids,
    plz_features_with_population,
    fetch_businesses_overpass,
)
from handwerk_hamburg.geocoding import businesses_from_elektriker_org
from handwerk_hamburg.analysis import run_scoring
from handwerk_hamburg.visualization import build_map_geojson

__all__ = [
    "DEFAULT_TRADE",
    "HAMBURG_BBOX",
    "OVERPASS_URL",
    "TRADES",
    "get_processed_dir",
    "get_raw_dir",
    "set_project_root",
    "load_elektriker_org_list",
    "load_geojson",
    "load_population",
    "load_stadtteil",
    "plz_centroids",
    "plz_features_with_population",
    "fetch_businesses_overpass",
    "businesses_from_elektriker_org",
    "run_scoring",
    "build_map_geojson",
]
