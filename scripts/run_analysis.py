"""
Run the main White-Spot analysis workflow.

Fetches electricians from Overpass and elektriker.org, loads PLZ + population,
scores areas, writes the result GeoJSON to data/processed/, and generates
the interactive handcraft map (outputs/handwerk_map.html) and the electrician
density heatmap (outputs/electrician_heatmap.html).

Usage (from project root, after editable install):
    pip install -e .
    python scripts/run_analysis.py
"""

import logging
from pathlib import Path

from handwerk_hamburg.pipeline import run_pipeline

# Configure root logger for script output (timestamp, level, message)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # Run full pipeline (fetch, analyze, write GeoJSON, create interactive map)
    logger.info("Fetching electricians from Overpass API...")
    logger.info("Loading electricians from elektriker.org list...")
    logger.info("Loading PLZ data and computing scores...")
    result = run_pipeline(project_root=PROJECT_ROOT)
    logger.info("Wrote %s", result["geojson_path"])
    logger.info("Wrote electricians list to data/processed/electricians.json (for web address analysis)")
    logger.info("Wrote %s", result["map_path"])
    logger.info("Wrote %s", result["heatmap_path"])


if __name__ == "__main__":
    main()
