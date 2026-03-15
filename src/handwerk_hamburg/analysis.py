"""
Analysis: assign businesses to PLZ, compute people-per-business and white-spot scores.
"""

from pathlib import Path

from shapely.geometry import shape, Point

from handwerk_hamburg.data_loader import plz_features_with_population


def assign_businesses_to_plz(
    plz_features: list[dict],
    business_points: list[dict],
) -> list[dict]:
    """
    For each PLZ polygon, count how many business points fall inside.

    Args:
        plz_features: List of GeoJSON-style feature dicts with geometry and properties.
        business_points: List of dicts with 'lon', 'lat' (and optional extra keys).

    Returns:
        Same plz_features with added property business_count on each feature.
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
    For each feature set people_per_business and white_spot_score (0–1, higher = more under-served).

    Args:
        features: List of feature dicts with properties.inhabitants and properties.business_count.

    Returns:
        Same features with added people_per_business and white_spot_score (normalized 0–1).
    """
    ppb_list = []
    for f in features:
        props = f["properties"]
        inhabitants = props.get("inhabitants") or 0
        count = max((props.get("business_count") or 0), 1)
        people_per_business = inhabitants / count
        props["people_per_business"] = round(people_per_business, 1)
        ppb_list.append(people_per_business)
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
    """
    Build a GeoJSON FeatureCollection from a list of features.

    Args:
        features: List of GeoJSON feature dicts.

    Returns:
        Dict with type "FeatureCollection" and "features" key.
    """
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
    Load PLZ + population, assign businesses to PLZ, compute scores, return GeoJSON dict.

    Args:
        business_points: List of dicts with 'lon', 'lat' (from Overpass and/or elektriker.org).
        geojson_path: Path to PLZ GeoJSON. If None, uses default from config.
        population_path: Path to population CSV. If None, uses default from config.

    Returns:
        GeoJSON dict (FeatureCollection) with scored PLZ features.
    """
    plz_features = plz_features_with_population(geojson_path, population_path)
    plz_features = assign_businesses_to_plz(plz_features, business_points)
    plz_features = compute_scores(plz_features)
    return build_output_geojson(plz_features)
