"""
Pipeline: run load → clean/transform → analyze → visualize and optionally generate the interactive map.
"""

import json
import re
from datetime import datetime, timezone
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
# Pipeline run metadata (generated_at, source counts, geocode stats) for trust/debugging
OUTPUT_METADATA_FILENAME = "pipeline_metadata.json"
# Output path for the interactive business map (relative to project root)
OUTPUT_MAP_PATH = "outputs/handwerk_map.html"
# Output path for the electrician density heatmap (relative to project root)
OUTPUT_HEATMAP_PATH = "outputs/electrician_heatmap.html"

# Coordinate rounding for dedupe key (5 decimals ≈ 1.1 m; same location → same key)
_DEDUPE_COORD_DECIMALS = 5


def _normalize_text(s: str | None) -> str:
    """
    Normalize text for deterministic dedupe key: lowercase, strip, collapse whitespace.
    """
    if s is None or not isinstance(s, str):
        return ""
    # Strip and lowercase
    t = s.strip().lower()
    # Collapse runs of whitespace to a single space
    t = re.sub(r"\s+", " ", t)
    return t


def _business_dedupe_key(b: dict) -> str:
    """
    Build a deterministic key for a business: normalized name + address or coordinates.

    Same shop from Overpass and elektriker.org will get the same key so we can deduplicate.
    """
    name_part = _normalize_text(b.get("name"))
    address = b.get("address")
    lat = b.get("lat")
    lon = b.get("lon")
    # Use normalized address if present; otherwise use rounded coordinates
    if address and _normalize_text(address):
        loc_part = _normalize_text(address)
    elif lat is not None and lon is not None:
        try:
            rlat = round(float(lat), _DEDUPE_COORD_DECIMALS)
            rlon = round(float(lon), _DEDUPE_COORD_DECIMALS)
            loc_part = f"{rlat}_{rlon}"
        except (TypeError, ValueError):
            loc_part = ""
    else:
        loc_part = ""
    return f"{name_part}|{loc_part}"


def deduplicate_businesses(businesses: list[dict]) -> list[dict]:
    """
    Remove duplicates by deterministic key (normalized name + address/coordinates).

    First occurrence is kept (e.g. Overpass before elektriker.org when combined in that order).
    """
    seen: set[str] = set()
    result = []
    for b in businesses:
        key = _business_dedupe_key(b)
        if key in seen:
            continue
        seen.add(key)
        result.append(b)
    return result


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
        overpass_businesses = fetch_businesses_overpass(DEFAULT_TRADE)
    except Exception:
        overpass_businesses = []
    overpass_count = len(overpass_businesses)

    # Add electricians from elektriker.org Hamburg list (PLZ-based placement); get list + geocode stats
    elektriker_org, elektriker_geocode_stats = businesses_from_elektriker_org()
    elektriker_count = len(elektriker_org)
    businesses = overpass_businesses + elektriker_org
    # Deduplicate: same shop can appear from both sources (normalized name + address/coords)
    businesses = deduplicate_businesses(businesses)
    total_after_dedupe = len(businesses)

    # Build data freshness metadata for trust/debugging (generated_at, source counts, geocode hit/miss)
    generated_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "generated_at": generated_at,
        "source_counts": {
            "overpass": overpass_count,
            "elektriker_org": elektriker_count,
            "total_after_dedupe": total_after_dedupe,
        },
        "geocode": {
            "elektriker_org": {
                "hit": elektriker_geocode_stats["geocoded"],
                "miss": elektriker_geocode_stats["plz_fallback"],
            },
        },
    }

    # Analyze: load PLZ + population and score each area
    geojson = run_scoring(businesses)
    map_geojson = build_map_geojson(geojson)
    # Attach metadata to GeoJSON so the file is self-describing (frontend can show "Data as of ...")
    map_geojson["metadata"] = {
        "generated_at": metadata["generated_at"],
        "source_counts": metadata["source_counts"],
        "geocode": metadata["geocode"],
    }

    # Write scored GeoJSON to data/processed
    geojson_path = processed_dir / OUTPUT_GEOJSON_FILENAME
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(map_geojson, f, ensure_ascii=False, indent=2)

    # Write pipeline metadata to data/processed for debugging and trust
    metadata_path = processed_dir / OUTPUT_METADATA_FILENAME
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Build DataFrame from businesses and generate interactive Folium map (visualization step)
    df = businesses_to_dataframe(businesses)
    map_path = root / OUTPUT_MAP_PATH
    create_handwerk_map(df, output_path=map_path)
    # Generate electrician density heatmap after the main map
    heatmap_path = root / OUTPUT_HEATMAP_PATH
    create_electrician_heatmap(df, output_path=heatmap_path)

    # Write electricians list for web app address-based district analysis (lat, lon, name, address); include metadata
    electricians_path = processed_dir / OUTPUT_ELECTRICIANS_FILENAME
    electricians_list = [
        {"lat": b.get("lat"), "lon": b.get("lon"), "name": b.get("name"), "address": b.get("address")}
        for b in businesses
    ]
    electricians_export = {"metadata": metadata, "electricians": electricians_list}
    with open(electricians_path, "w", encoding="utf-8") as f:
        json.dump(electricians_export, f, ensure_ascii=False, indent=2)

    return {
        "geojson": map_geojson,
        "geojson_path": geojson_path,
        "metadata_path": metadata_path,
        "map_path": map_path,
        "heatmap_path": heatmap_path,
    }
