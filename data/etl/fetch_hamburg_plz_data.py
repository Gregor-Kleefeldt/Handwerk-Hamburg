"""
Download official Hamburg PLZ GeoJSON from Transparenzportal and generate
population CSV (area-weighted estimate; no official per-PLZ population open data).
Run from project root: python data/etl/fetch_hamburg_plz_data.py
"""

import json
import sys
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

RAW_DIR = PROJECT_ROOT / "data" / "raw"
# Official Hamburg PLZ GeoJSON (WGS84) - downloaded manually or via curl in this script
HAMBURG_PLZ_URL = "http://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK/postleitzahlen_json_220900_snap_3.zip"
# Approximate total population of Hamburg (for area-based estimate)
HAMBURG_TOTAL_POPULATION = 1_910_000


def download_and_extract_geojson():
    """Download zip from Transparenzportal and return path to extracted GeoJSON (EPSG:4326)."""
    import subprocess
    import tempfile
    import zipfile
    # Download to temp file
    raw_zip = PROJECT_ROOT / "data" / "raw" / "plz_hamburg_official.zip"
    if not raw_zip.exists():
        import urllib.request
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(HAMBURG_PLZ_URL, raw_zip)
    extract_dir = RAW_DIR / "plz_extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(raw_zip, "r") as z:
        z.extractall(extract_dir)
    # Prefer WGS84 version for web maps
    geojson_path = extract_dir / "de_hh_up_postleitzahlen_EPSG_4326.json"
    if not geojson_path.exists():
        geojson_path = next(extract_dir.glob("*.json"), None)
    return geojson_path


def merge_features_by_plz(features: list) -> list:
    """Group features by PLZ and merge geometries so we have one feature per PLZ."""
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.geometry import mapping

    by_plz = {}
    for f in features:
        plz = f.get("properties") or {}
        plz_val = plz.get("plz") or plz.get("postcode") or plz.get("PLZ")
        if plz_val is None:
            continue
        plz_key = str(plz_val).strip()
        geom = f.get("geometry")
        if not geom:
            continue
        try:
            shp = shape(geom)
        except Exception:
            continue
        if plz_key not in by_plz:
            by_plz[plz_key] = []
        by_plz[plz_key].append(shp)
    out = []
    for plz_key, shapes in by_plz.items():
        merged = unary_union(shapes)
        if merged.is_empty:
            continue
        out.append({
            "type": "Feature",
            "properties": {"plz": plz_key},
            "geometry": mapping(merged),
        })
    return out


def area_based_population(features: list) -> dict[str, int]:
    """Compute area per PLZ and distribute HAMBURG_TOTAL_POPULATION by area share."""
    from shapely.geometry import shape

    areas = []
    for f in features:
        plz = (f.get("properties") or {}).get("plz")
        if plz is None:
            continue
        plz = str(plz).strip()
        geom = f.get("geometry")
        if not geom:
            areas.append((plz, 0.0))
            continue
        try:
            poly = shape(geom)
            a = poly.area
        except Exception:
            a = 0.0
        areas.append((plz, a))
    total_area = sum(a for _, a in areas)
    result = {}
    for plz, a in areas:
        if total_area and total_area > 0:
            share = a / total_area
            result[plz] = int(HAMBURG_TOTAL_POPULATION * share)
        else:
            result[plz] = 0
    return result


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # Use pre-downloaded file if present
    extracted = RAW_DIR / "plz_extract" / "de_hh_up_postleitzahlen_EPSG_4326.json"
    if not extracted.exists():
        geojson_path = download_and_extract_geojson()
    else:
        geojson_path = extracted
    if not geojson_path or not geojson_path.exists():
        print("Could not find Hamburg PLZ GeoJSON. Download from:")
        print("  https://suche.transparenz.hamburg.de/dataset/postleitzahlen-hamburg2")
        print("  and extract de_hh_up_postleitzahlen_EPSG_4326.json to data/raw/plz_extract/")
        sys.exit(1)
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    print(f"Loaded {len(features)} PLZ features from official Hamburg data.")
    # Merge so one feature per PLZ (some PLZ have multiple polygons)
    merged = merge_features_by_plz(features)
    print(f"Merged to {len(merged)} unique PLZ areas.")
    # Area-based population estimate
    population = area_based_population(merged)
    # Write plz_hamburg.geojson (one feature per PLZ)
    out_geojson = RAW_DIR / "plz_hamburg.geojson"
    fc = {"type": "FeatureCollection", "features": merged}
    with open(out_geojson, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_geojson}")
    # Write plz_einwohner.csv
    out_csv = RAW_DIR / "plz_einwohner.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        import csv
        w = csv.writer(f)
        w.writerow(["plz", "einwohner"])
        for plz in sorted(population.keys(), key=lambda x: (x or "")):
            w.writerow([plz, population[plz]])
    print(f"Wrote {out_csv} (area-weighted population estimate, total={sum(population.values())})")
    # Write Hamburg outline (union of all PLZ) for map border / future extensions
    write_hamburg_boundary(merged)


def write_hamburg_boundary(merged_features: list) -> None:
    """Union all PLZ polygons into one Hamburg boundary and write to data/processed/hamburg_boundary.geojson."""
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.geometry import mapping

    PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    shapes = []
    for f in merged_features:
        geom = f.get("geometry")
        if not geom:
            continue
        try:
            shapes.append(shape(geom))
        except Exception:
            continue
    if not shapes:
        return
    boundary = unary_union(shapes)
    if boundary.is_empty:
        return
    fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Hamburg"},
            "geometry": mapping(boundary),
        }],
    }
    out_path = PROCESSED_DIR / "hamburg_boundary.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path} (Hamburg border for map)")


if __name__ == "__main__":
    main()
