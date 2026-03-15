"""
Orchestrate ETL: fetch businesses from Overpass, load PLZ+population, score, write GeoJSON.
Run from project root: python data/etl/run_etl.py
"""

import sys
from pathlib import Path

# Add project root so "data.etl" imports work
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from data.etl.config import DEFAULT_TRADE
from data.etl.fetch_overpass import fetch_businesses
from data.etl.fetch_elektriker_org import fetch_elektriker_org_businesses
from data.etl.score_white_spot import run_scoring

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILENAME = "white_spot_electrician.geojson"


def main():
    # Ensure output dir exists
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    # Fetch electricians from OSM (continue with empty list if API times out)
    print("Fetching electricians from Overpass API...")
    try:
        businesses = fetch_businesses(DEFAULT_TRADE)
        print(f"Found {len(businesses)} from Overpass.")
    except Exception as e:
        print(f"Overpass API failed ({e}). Using empty list from Overpass.")
        businesses = []
    # Add electricians from elektriker.org Hamburg list (PLZ-based placement)
    print("Loading electricians from elektriker.org list...")
    elektriker_org = fetch_elektriker_org_businesses()
    print(f"Found {len(elektriker_org)} from elektriker.org (Hamburg PLZ only).")
    businesses = businesses + elektriker_org
    print(f"Total businesses: {len(businesses)}.")
    # Load PLZ + population and score
    print("Loading PLZ data and computing scores...")
    geojson = run_scoring(businesses)
    # Write output
    out_path = PROCESSED_DIR / OUTPUT_FILENAME
    with open(out_path, "w", encoding="utf-8") as f:
        import json
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
