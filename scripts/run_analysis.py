"""
Run the main White-Spot analysis workflow.

Fetches electricians from Overpass and elektriker.org, loads PLZ + population,
scores areas, writes the result GeoJSON to data/processed/, and generates
the interactive handcraft map at outputs/handwerk_map.html.

Usage (from project root):
    python scripts/run_analysis.py
"""

import sys
from pathlib import Path

# Add project root and src to path so handwerk_hamburg can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from handwerk_hamburg.pipeline import run_pipeline


def main() -> None:
    # Run full pipeline (fetch, analyze, write GeoJSON, create interactive map)
    print("Fetching electricians from Overpass API...")
    print("Loading electricians from elektriker.org list...")
    print("Loading PLZ data and computing scores...")
    result = run_pipeline(project_root=PROJECT_ROOT)
    print(f"Wrote {result['geojson_path']}")
    print(f"Wrote {result['map_path']}")


if __name__ == "__main__":
    main()
