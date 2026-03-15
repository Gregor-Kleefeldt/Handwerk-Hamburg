"""
Geocoding: resolve PLZ to coordinates (e.g. PLZ centroid), geocode full addresses,
and build business points from lists.
"""

import json
import time
from pathlib import Path

import requests

from handwerk_hamburg.config import HAMBURG_BBOX
from handwerk_hamburg.data_loader import plz_centroids, load_elektriker_org_list

# Filename for persistent geocode cache (avoids re-querying Nominatim every run)
GEOCODE_CACHE_FILENAME = "geocode_cache.json"

# Nominatim (OSM) geocoding: required by usage policy
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Identify the application (Nominatim usage policy)
GEOCODE_USER_AGENT = "WhiteSpotMapHandwerk/1.0 (Hamburg Handwerk map; contact via OSM)"
# Minimum delay between Nominatim requests (seconds) to respect 1 req/s policy
NOMINATIM_DELAY_SECONDS = 1.1

# Module-level cache so we don't re-query the same address in one run
_geocode_cache: dict[str, tuple[float, float] | None] = {}


def _load_geocode_cache() -> None:
    """Load persisted geocode cache from data/processed if project root is set."""
    try:
        from handwerk_hamburg.config import get_processed_dir
        cache_path = get_processed_dir() / GEOCODE_CACHE_FILENAME
    except Exception:
        return
    if not cache_path.exists():
        return
    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        for addr, coords in (data or {}).items():
            if coords is not None and isinstance(coords, (list, tuple)) and len(coords) == 2:
                _geocode_cache[addr] = (float(coords[0]), float(coords[1]))
            else:
                _geocode_cache[addr] = None
    except Exception:
        pass


def _save_geocode_cache() -> None:
    """Persist geocode cache to data/processed so next run can skip API calls."""
    try:
        from handwerk_hamburg.config import get_processed_dir
        processed = get_processed_dir()
        processed.mkdir(parents=True, exist_ok=True)
        cache_path = processed / GEOCODE_CACHE_FILENAME
    except Exception:
        return
    data = {}
    for addr, coords in _geocode_cache.items():
        data[addr] = list(coords) if coords is not None else None
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
    except Exception:
        pass


def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Geocode a full address string to (lat, lon) using Nominatim (OpenStreetMap).
    Results are cached per address. Respects 1 request/second policy via delay.

    Args:
        address: Full address string (e.g. "Walther-Kunze-Str. 16, 22765 Hamburg").

    Returns:
        (lat, lon) if found, else None.
    """
    address = (address or "").strip()
    if not address:
        return None
    # Return cached result if we already looked up this address
    if address in _geocode_cache:
        return _geocode_cache[address]
    # Query Nominatim with a polite User-Agent
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": GEOCODE_USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        _geocode_cache[address] = None
        return None
    if not data or not isinstance(data, list):
        _geocode_cache[address] = None
        return None
    first = data[0]
    try:
        lat = float(first.get("lat"))
        lon = float(first.get("lon"))
    except (TypeError, ValueError):
        _geocode_cache[address] = None
        return None
    # Optionally restrict to Hamburg area (avoid far-away matches)
    min_lon, min_lat, max_lon, max_lat = HAMBURG_BBOX
    if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
        # Slightly expand box for suburbs; use ~0.2 degree margin
        margin = 0.2
        if not (min_lat - margin <= lat <= max_lat + margin and min_lon - margin <= lon <= max_lon + margin):
            _geocode_cache[address] = None
            return None
    _geocode_cache[address] = (lat, lon)
    # Rate-limit: wait before next Nominatim request (1 req/s policy)
    time.sleep(NOMINATIM_DELAY_SECONDS)
    return (lat, lon)


def resolve_plz_to_coords(
    plz: str,
    centroids: dict[str, tuple[float, float]] | None = None,
    geojson_path: Path | None = None,
) -> tuple[float, float] | None:
    """
    Resolve a postal code (PLZ) to (lon, lat) using PLZ polygon centroids.

    Args:
        plz: Postal code string.
        centroids: Optional pre-computed dict plz -> (lon, lat). If None, computed from geojson_path.
        geojson_path: Path to PLZ GeoJSON (used only if centroids is None).

    Returns:
        (lon, lat) or None if PLZ not found.
    """
    if centroids is None:
        centroids = plz_centroids(geojson_path)
    return centroids.get(str(plz).strip())


def businesses_from_elektriker_org(
    list_path: Path | None = None,
    geojson_path: Path | None = None,
) -> list[dict]:
    """
    Load electricians from elektriker.org JSON and convert to business points.

    For each entry with an address, the full address is geocoded so the marker is placed
    at the correct location. If geocoding fails or no address is given, the PLZ centroid
    is used. Only entries whose PLZ exists in our PLZ layer are included (Hamburg area).

    Args:
        list_path: Path to elektriker_org_hamburg.json. If None, uses default raw path.
        geojson_path: Path to PLZ GeoJSON for centroids. If None, uses default raw path.

    Returns:
        List of dicts with lon, lat, optional name, address, and source="elektriker_org".
    """
    entries = load_elektriker_org_list(list_path)
    centroids = plz_centroids(geojson_path)
    # Load persisted geocode cache so we don't re-query addresses every run
    _load_geocode_cache()
    features = []
    for entry in entries:
        plz = (entry.get("plz") or "").strip()
        if not plz:
            continue
        if plz not in centroids:
            continue
        # Prefer geocoded address so the marker is at the real location, not PLZ centre
        address = entry.get("address")
        lat, lon = None, None
        if address:
            coords = geocode_address(address)
            if coords is not None:
                lat, lon = coords
        if lat is None or lon is None:
            lon, lat = centroids[plz]
        features.append({
            "lon": lon,
            "lat": lat,
            "name": entry.get("name"),
            "address": address,
            "source": "elektriker_org",
        })
    # Persist cache for next run (speeds up future pipeline runs)
    _save_geocode_cache()
    return features
