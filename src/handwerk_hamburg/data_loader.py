"""
Load PLZ GeoJSON, population CSV, electrician lists, and fetch businesses from Overpass API.
"""

import csv
import json
from pathlib import Path

import requests
from shapely.geometry import shape

from handwerk_hamburg.config import OVERPASS_URL, HAMBURG_BBOX, TRADES, get_raw_dir


def load_geojson(path: Path | None = None) -> dict:
    """
    Load GeoJSON from file; return the full GeoJSON dict.

    Args:
        path: Path to GeoJSON file. If None, uses get_raw_dir() / "plz_hamburg.geojson".

    Returns:
        Parsed GeoJSON dict.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    # Resolve path: use provided path or default raw PLZ GeoJSON
    p = path if path is not None else get_raw_dir() / "plz_hamburg.geojson"
    if not p.exists():
        raise FileNotFoundError(f"PLZ GeoJSON not found: {p}")
    # Read and parse JSON with UTF-8 encoding
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_population(path: Path | None = None) -> dict[str, int]:
    """
    Load population per PLZ from CSV. Returns dict plz -> inhabitants.

    Args:
        path: Path to CSV. If None, uses get_raw_dir() / "plz_einwohner.csv".

    Returns:
        Dict mapping PLZ string to inhabitant count. Empty dict if file missing.
    """
    # Resolve path: use provided path or default raw population CSV
    p = path if path is not None else get_raw_dir() / "plz_einwohner.csv"
    if not p.exists():
        return {}
    result = {}
    # Open CSV and iterate rows
    with open(p, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Accept 'plz' or 'postcode', 'einwohner' or 'inhabitants'
            plz = (row.get("plz") or row.get("postcode") or "").strip()
            if not plz:
                continue
            raw = row.get("einwohner") or row.get("inhabitants") or "0"
            try:
                # Strip thousands separators and parse integer
                result[plz] = int(raw.replace(".", "").replace(",", ""))
            except ValueError:
                result[plz] = 0
    return result


def load_stadtteil(path: Path | None = None) -> dict[str, str]:
    """
    Load optional PLZ -> Stadtteil (city district) mapping from CSV.

    Args:
        path: Path to CSV. If None, uses get_raw_dir() / "plz_stadtteil.csv".

    Returns:
        Dict mapping PLZ string to stadtteil name. Empty dict if file missing.
    """
    # Resolve path: use provided path or default raw stadtteil CSV
    p = path if path is not None else get_raw_dir() / "plz_stadtteil.csv"
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
    """
    Get postal code string from a GeoJSON feature's properties.

    Args:
        feature: GeoJSON feature dict with optional properties.plz, postcode, PLZ, postal_code.

    Returns:
        PLZ string or None if not found.
    """
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
    Load PLZ GeoJSON and population CSV, merge inhabitants into each feature.

    Args:
        geojson_path: Path to PLZ GeoJSON. If None, uses default from get_raw_dir().
        population_path: Path to population CSV. If None, uses default from get_raw_dir().

    Returns:
        List of feature dicts with geometry and properties including 'plz', 'inhabitants', 'stadtteil'.
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

    Args:
        geojson_path: Path to PLZ GeoJSON. If None, uses default from get_raw_dir().

    Returns:
        Dict mapping PLZ string to (lon, lat) for use when geocoding addresses by PLZ only.
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
            poly = shape(geom)
            c = poly.centroid
            result[str(plz).strip()] = (float(c.x), float(c.y))
        except Exception:
            continue
    return result


def load_elektriker_org_list(path: Path | None = None) -> list[dict]:
    """
    Load the JSON list of electricians from elektriker.org (name, address, phone, plz).

    Args:
        path: Path to JSON file. If None, uses get_raw_dir() / "elektriker_org_hamburg.json".

    Returns:
        List of entry dicts. Empty list if file missing or not a list.
    """
    p = path if path is not None else get_raw_dir() / "elektriker_org_hamburg.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _build_overpass_query(bbox: tuple, tag_key: str, tag_value: str) -> str:
    """Build Overpass QL query for nodes/ways with the given tag inside bbox."""
    min_lon, min_lat, max_lon, max_lat = bbox
    bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    query = f"""
    [out:json][timeout:25];
    (
      node["{tag_key}"="{tag_value}"]({bbox_str});
      way["{tag_key}"="{tag_value}"]({bbox_str});
    );
    out center;
    """
    return query


def fetch_businesses_overpass(trade_id: str = "electrician") -> list[dict]:
    """
    Fetch businesses for the given trade from OpenStreetMap via Overpass API.

    Args:
        trade_id: Trade key from config TRADES (e.g. 'electrician').

    Returns:
        List of dicts with 'lon', 'lat', 'osm_type', 'osm_id'.

    Raises:
        ValueError: If trade_id is not in TRADES.
    """
    if trade_id not in TRADES:
        raise ValueError(f"Unknown trade: {trade_id}")
    conf = TRADES[trade_id]
    tag_key = conf["overpass_key"]
    tag_value = conf["overpass_value"]
    query = _build_overpass_query(HAMBURG_BBOX, tag_key, tag_value)
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    features = []
    for el in data.get("elements", []):
        lon, lat = None, None
        if el.get("type") == "node":
            lon = el.get("lon")
            lat = el.get("lat")
        elif el.get("type") == "way" and "center" in el:
            lon = el["center"].get("lon")
            lat = el["center"].get("lat")
        if lon is not None and lat is not None:
            features.append({
                "lon": float(lon),
                "lat": float(lat),
                "osm_type": el.get("type"),
                "osm_id": el.get("id"),
            })
    return features
