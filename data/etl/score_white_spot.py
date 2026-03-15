"""
Assign each business (point) to a PLZ polygon via point-in-polygon.
Compute per-PLZ: business_count, people_per_business, white_spot_score.
Output GeoJSON with these attributes.
"""

import json
from pathlib import Path

from shapely.geometry import shape, Point

from data.etl.load_plz import plz_features_with_population

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def assign_businesses_to_plz(
    plz_features: list[dict],
    business_points: list[dict],
) -> list[dict]:
    """
    For each PLZ polygon, count how many business points fall inside.
    business_points: list of { 'lon', 'lat', ... }.
    Returns same features with added property business_count.
    """
    for feat in plz_features:
        geom = feat.get("geometry")
        if not geom:
            feat["properties"]["business_count"] = 0
            continue
        try:
            poly = shape(geom)
        except Exception:
            feat["properties"]["business_count"] = 0
            continue
        count = 0
        for b in business_points:
            pt = Point(b["lon"], b["lat"])
            if poly.contains(pt):
                count += 1
        feat["properties"]["business_count"] = count
    return plz_features


def compute_scores(features: list[dict]) -> list[dict]:
    """
    For each feature set: people_per_business, white_spot_score (0–1, higher = more under-served).
    """
    # Collect people_per_business to normalize score
    ppb_list = []
    for f in features:
        props = f["properties"]
        inhabitants = props.get("inhabitants") or 0
        count = max((props.get("business_count") or 0), 1)
        people_per_business = inhabitants / count
        props["people_per_business"] = round(people_per_business, 1)
        ppb_list.append(people_per_business)
    # Normalize to 0–1: higher people_per_business -> higher white_spot_score
    max_ppb = max(ppb_list) if ppb_list else 1
    min_ppb = min(ppb_list) if ppb_list else 0
    for f in features:
        ppb = f["properties"].get("people_per_business") or 0
        if max_ppb > min_ppb:
            score = (ppb - min_ppb) / (max_ppb - min_ppb)
        else:
            score = 0.0
        f["properties"]["white_spot_score"] = round(score, 4)
    return features


def build_output_geojson(features: list[dict]) -> dict:
    """Build GeoJSON FeatureCollection from list of features."""
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def run_scoring(
    business_points: list[dict],
    geojson_path: Path | None = None,
    population_path: Path | None = None,
) -> dict:
    """
    Load PLZ + population, assign businesses, compute scores, return GeoJSON dict.
    """
    plz_features = plz_features_with_population(geojson_path, population_path)
    plz_features = assign_businesses_to_plz(plz_features, business_points)
    plz_features = compute_scores(plz_features)
    return build_output_geojson(plz_features)
