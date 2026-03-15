"""
Fetch Hamburg Stadtteil (city district) boundaries from OSM and assign to each PLZ
by point-in-polygon (PLZ centroid). Adds 'stadtteil' to each feature's properties.
"""

import json
import requests
from pathlib import Path

from shapely.geometry import shape, Point
from shapely.ops import unary_union

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Hamburg bbox
BBOX = (9.7, 53.4, 10.2, 53.65)


def fetch_hamburg_stadtteile() -> list[dict]:
    """Fetch admin_level=10 boundaries (Stadtteile) in Hamburg from Overpass. Return list of {name, geometry}."""
    # Query: administrative boundaries at admin_level=10 (Stadtteil in Germany) inside Hamburg bbox
    min_lon, min_lat, max_lon, max_lat = BBOX
    query = f"""
    [out:json][timeout:30];
    (
      relation(area.searchArea)["boundary"="administrative"]["admin_level"="10"];
    );
    out geom;
    """
    # Use area id for Hamburg (Nominatim: 3600066278) or bbox
    area_query = f"""
    [out:json][timeout:30];
    area(3600066278)->.searchArea;
    (
      relation(area.searchArea)["boundary"="administrative"]["admin_level"="10"];
    );
    out geom;
    """
    # Fallback: use bbox and filter by type
    bbox_query = f"""
    [out:json][timeout:30];
    (
      relation({min_lat},{min_lon},{max_lat},{max_lon})["boundary"="administrative"]["admin_level"="10"];
    );
    out geom;
    """
    try:
        resp = requests.post(OVERPASS_URL, data={"data": area_query}, timeout=60)
        if resp.status_code != 200 or not resp.json().get("elements"):
            resp = requests.post(OVERPASS_URL, data={"data": bbox_query}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Overpass stadtteil query failed: {e}")
        return []
    # Build polygons from relation ways
    elements = data.get("elements", [])
    stadtteile = []
    for el in elements:
        if el.get("type") != "relation":
            continue
        name = (el.get("tags") or {}).get("name")
        if not name:
            continue
        # Collect way geometries into a multipolygon
        members = el.get("members", [])
        polygons = []
        for m in members:
            if m.get("type") != "way" or "geometry" not in m:
                continue
            coords = [(p["lon"], p["lat"]) for p in m["geometry"]]
            if len(coords) < 3:
                continue
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            try:
                from shapely.geometry import Polygon
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if not poly.is_empty:
                    polygons.append(poly)
            except Exception:
                continue
        if not polygons:
            continue
        try:
            merged = unary_union(polygons)
            if merged.is_empty:
                continue
            stadtteile.append({"name": name, "geometry": merged})
        except Exception:
            continue
    return stadtteile


def assign_stadtteil_to_features(features: list[dict], stadtteile: list[dict]) -> list[dict]:
    """For each feature, get centroid, find which Stadtteil(s) contain it, set properties.stadtteil."""
    from shapely.geometry import shape as geom_shape
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            feat["properties"]["stadtteil"] = ""
            continue
        try:
            poly = geom_shape(geom)
            pt = poly.representative_point()
        except Exception:
            feat["properties"]["stadtteil"] = ""
            continue
        names = []
        for st in stadtteile:
            try:
                if st["geometry"].contains(pt):
                    names.append(st["name"])
            except Exception:
                pass
        feat["properties"]["stadtteil"] = ", ".join(names) if names else ""
    return features


def add_stadtteil_to_plz_geojson(geojson_path: Path, stadtteile_cache_path: Path | None = None) -> None:
    """
    Load GeoJSON at geojson_path, fetch Hamburg Stadtteile, assign to each feature, write back.
    Optionally cache stadtteile to avoid repeated Overpass calls.
    """
    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)
    features = fc.get("features", [])
    if not features:
        return
    cache = stadtteile_cache_path or (geojson_path.parent / "stadtteile_cache.json")
    if cache.exists():
        try:
            with open(cache, encoding="utf-8") as f:
                cached = json.load(f)
            stadtteile = [{"name": s["name"], "geometry": shape(s["geometry"])} for s in cached]
        except Exception:
            stadtteile = fetch_hamburg_stadtteile()
    else:
        stadtteile = fetch_hamburg_stadtteile()
        if stadtteile and cache:
            try:
                with open(cache, "w", encoding="utf-8") as f:
                    json.dump([{"name": s["name"], "geometry": s["geometry"].__geo_interface__} for s in stadtteile], f, ensure_ascii=False)
            except Exception:
                pass
    if not stadtteile:
        for f in features:
            f.setdefault("properties", {})["stadtteil"] = ""
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, indent=2)
        return
    assign_stadtteil_to_features(features, stadtteile)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
