"""
Pipeline: run load → clean/transform → analyze → visualize and optionally generate the interactive map.
"""

import json
from pathlib import Path

import pandas as pd

from handwerk_hamburg.config import (
    DEFAULT_TRADE,
    TRADES,
    get_processed_dir,
    get_project_root,
    set_project_root,
)
from handwerk_hamburg.data_loader import fetch_businesses_overpass
from handwerk_hamburg.geocoding import businesses_from_elektriker_org
from handwerk_hamburg.analysis import run_scoring
from handwerk_hamburg.visualization import (
    build_map_geojson,
    create_electrician_heatmap,
    create_handwerk_map,
)

# Output file name for scored GeoJSON under data/processed
OUTPUT_GEOJSON_FILENAME = "white_spot_electrician.geojson"
# Output file for electricians list (used by web app address analysis)
OUTPUT_ELECTRICIANS_FILENAME = "electricians.json"
# Output path for the interactive business map (relative to project root)
OUTPUT_MAP_PATH = "outputs/handwerk_map.html"
# Output path for the electrician density heatmap (relative to project root)
OUTPUT_HEATMAP_PATH = "outputs/electrician_heatmap.html"


def businesses_to_dataframe(businesses: list[dict]) -> pd.DataFrame:
    """
    Convert a list of business point dicts (lon, lat, optional name, etc.) into a DataFrame
    suitable for create_handwerk_map (columns: lat, lon, name, category, address).

    Args:
        businesses: List of dicts with at least 'lon' and 'lat'. May contain 'name', 'address', 'source'.

    Returns:
        DataFrame with columns lat, lon, and optionally name, category, address.
    """
    if not businesses:
        return pd.DataFrame(columns=["lat", "lon", "name", "category", "address"])

    # Get human-readable category label for the default trade (e.g. "Elektro-Handwerk / Elektriker")
    trade_label = TRADES.get(DEFAULT_TRADE, {}).get("label_de", DEFAULT_TRADE)

    rows = []
    for b in businesses:
        # Build one row per business; use trade label as category if not provided
        row = {
            "lat": b.get("lat"),
            "lon": b.get("lon"),
            "name": b.get("name"),
            "category": b.get("category") or trade_label,
            "address": b.get("address"),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def run_pipeline(project_root: Path | None = None) -> dict:
    """
    Run the full pipeline: fetch businesses, score PLZ areas, write GeoJSON, generate interactive map.

    Args:
        project_root: Project root directory. If None, uses get_project_root() (must have been set).

    Returns:
        Dict with keys 'geojson' (the scored GeoJSON), 'geojson_path', 'map_path', 'heatmap_path'.
    """
    # Set project root so config can resolve data/raw and data/processed
    if project_root is not None:
        set_project_root(project_root)
    root = get_project_root()
    if root is None:
        raise RuntimeError("Project root not set. Pass project_root or call set_project_root() first.")

    processed_dir = get_processed_dir()
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Fetch electricians from Overpass (continue with empty list if API times out)
    try:
        businesses = fetch_businesses_overpass(DEFAULT_TRADE)
    except Exception:
        businesses = []

    # Add electricians from elektriker.org Hamburg list (PLZ-based placement)
    elektriker_org = businesses_from_elektriker_org()
    businesses = businesses + elektriker_org

    # Analyze: load PLZ + population and score each area
    geojson = run_scoring(businesses)
    map_geojson = build_map_geojson(geojson)

    # Write scored GeoJSON to data/processed
    geojson_path = processed_dir / OUTPUT_GEOJSON_FILENAME
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(map_geojson, f, ensure_ascii=False, indent=2)

    # Build DataFrame from businesses and generate interactive Folium map (visualization step)
    df = businesses_to_dataframe(businesses)
    map_path = root / OUTPUT_MAP_PATH
    create_handwerk_map(df, output_path=map_path)
    # Generate electrician density heatmap after the main map
    heatmap_path = root / OUTPUT_HEATMAP_PATH
    create_electrician_heatmap(df, output_path=heatmap_path)

    # Write electricians list for web app address-based district analysis (lat, lon, name, address)
    electricians_path = processed_dir / OUTPUT_ELECTRICIANS_FILENAME
    electricians_export = [
        {"lat": b.get("lat"), "lon": b.get("lon"), "name": b.get("name"), "address": b.get("address")}
        for b in businesses
    ]
    with open(electricians_path, "w", encoding="utf-8") as f:
        json.dump(electricians_export, f, ensure_ascii=False, indent=2)

    return {
        "geojson": map_geojson,
        "geojson_path": geojson_path,
        "map_path": map_path,
        "heatmap_path": heatmap_path,
    }
