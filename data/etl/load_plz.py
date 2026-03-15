"""
Load Hamburg postal code (PLZ) polygons and population per PLZ.
Expects:
  - data/raw/plz_hamburg.geojson: GeoJSON with PLZ polygons (feature.properties.plz or postcode)
  - data/raw/plz_einwohner.csv: CSV with columns plz, einwohner (or inhabitants)
"""

import csv
import json
from pathlib import Path

from shapely.geometry import shape

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
GEOJSON_PATH = RAW_DIR / "plz_hamburg.geojson"
POPULATION_CSV_PATH = RAW_DIR / "plz_einwohner.csv"
STADTTEIL_CSV_PATH = RAW_DIR / "plz_stadtteil.csv"


def load_geojson(path: Path | None = None) -> dict:
    """Load GeoJSON from file; return the full GeoJSON dict."""
    p = path or GEOJSON_PATH
    if not p.exists():
        raise FileNotFoundError(f"PLZ GeoJSON not found: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_population(path: Path | None = None) -> dict[str, int]:
    """Load population per PLZ from CSV. Returns dict plz -> inhabitants."""
    p = path or POPULATION_CSV_PATH
    if not p.exists():
        return {}
    result = {}
    with open(p, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Accept 'plz' or 'postcode', 'einwohner' or 'inhabitants'
            plz = (row.get("plz") or row.get("postcode") or "").strip()
            if not plz:
                continue
            raw = row.get("einwohner") or row.get("inhabitants") or "0"
            try:
                result[plz] = int(raw.replace(".", "").replace(",", ""))
            except ValueError:
                result[plz] = 0
    return result


def load_stadtteil(path: Path | None = None) -> dict[str, str]:
    """Load optional PLZ -> Stadtteil (city district) mapping from CSV. Returns dict plz -> stadtteil."""
    p = path or STADTTEIL_CSV_PATH
    if not p.exists():
        return {}
    result = {}
    with open(p, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            plz = (row.get("plz") or row.get("postcode") or "").strip()
            if not plz:
                continue
            result[plz] = (row.get("stadtteil") or row.get("district") or "").strip()
    return result


def get_plz_from_feature(feature: dict) -> str | None:
    """Get postal code string from a GeoJSON feature's properties."""
    props = feature.get("properties") or {}
    return (
        props.get("plz")
        or props.get("postcode")
        or props.get("PLZ")
        or props.get("postal_code")
    )


def plz_features_with_population(
    geojson_path: Path | None = None,
    population_path: Path | None = None,
) -> list[dict]:
    """
    Load GeoJSON and population CSV, merge inhabitants into each feature.
    Returns list of feature dicts with geometry and properties including 'plz', 'inhabitants'.
    """
    geojson = load_geojson(geojson_path)
    population = load_population(population_path)
    stadtteil = load_stadtteil()
    features = []
    for f in geojson.get("features", []):
        plz = get_plz_from_feature(f)
        if plz is None:
            continue
        plz = str(plz).strip()
        inhabitants = population.get(plz, 0)
        props = dict(f.get("properties") or {})
        props["plz"] = plz
        props["inhabitants"] = inhabitants
        props["stadtteil"] = stadtteil.get(plz, "")
        features.append({
            "type": "Feature",
            "geometry": f.get("geometry"),
            "properties": props,
        })
    return features


def plz_centroids(geojson_path: Path | None = None) -> dict[str, tuple[float, float]]:
    """
    Load PLZ GeoJSON and compute centroid (lon, lat) for each polygon.
    Returns dict plz -> (lon, lat) for use when geocoding addresses by PLZ only.
    """
    geojson = load_geojson(geojson_path)
    result = {}
    for f in geojson.get("features", []):
        plz = get_plz_from_feature(f)
        if plz is None:
            continue
        geom = f.get("geometry")
        if not geom:
            continue
        try:
            # Convert GeoJSON geometry to Shapely polygon
            poly = shape(geom)
            # Centroid as (x, y) where x=lon, y=lat in GeoJSON
            c = poly.centroid
            # Store (lon, lat) for this PLZ
            result[str(plz).strip()] = (float(c.x), float(c.y))
        except Exception:
            continue
    return result
