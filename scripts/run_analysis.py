"""
Run the main White-Spot analysis workflow.

Fetches electricians from Overpass and elektriker.org, loads PLZ + population,
scores areas, and writes the result GeoJSON to data/processed/.

Usage (from project root):
    python scripts/run_analysis.py
"""

import json
import sys
from pathlib import Path

# Add project root and src to path so handwerk_hamburg can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from handwerk_hamburg.config import DEFAULT_TRADE, set_project_root, get_processed_dir
from handwerk_hamburg.data_loader import fetch_businesses_overpass
from handwerk_hamburg.geocoding import businesses_from_elektriker_org
from handwerk_hamburg.analysis import run_scoring
from handwerk_hamburg.visualization import build_map_geojson

# Output file name under data/processed
OUTPUT_FILENAME = "white_spot_electrician.geojson"


def main() -> None:
    # Set project root so package can resolve data/raw and data/processed
    set_project_root(PROJECT_ROOT)
    processed_dir = get_processed_dir()
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Fetch electricians from OSM (continue with empty list if API times out)
    print("Fetching electricians from Overpass API...")
    try:
        businesses = fetch_businesses_overpass(DEFAULT_TRADE)
        print(f"Found {len(businesses)} from Overpass.")
    except Exception as e:
        print(f"Overpass API failed ({e}). Using empty list from Overpass.")
        businesses = []

    # Add electricians from elektriker.org Hamburg list (PLZ-based placement)
    print("Loading electricians from elektriker.org list...")
    elektriker_org = businesses_from_elektriker_org()
    print(f"Found {len(elektriker_org)} from elektriker.org (Hamburg PLZ only).")
    businesses = businesses + elektriker_org
    print(f"Total businesses: {len(businesses)}.")

    # Load PLZ + population and score
    print("Loading PLZ data and computing scores...")
    geojson = run_scoring(businesses)
    map_geojson = build_map_geojson(geojson)

    # Write output to data/processed
    out_path = processed_dir / OUTPUT_FILENAME
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(map_geojson, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
