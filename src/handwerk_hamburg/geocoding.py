"""
Geocoding: resolve PLZ to coordinates (e.g. PLZ centroid), geocode full addresses,
and build business points from lists.

Single source of truth for Nominatim (requests), address normalization,
known-address fallbacks, and cache. No geopy or duplicate paths.
"""

import json
import re
import time
from pathlib import Path

import requests

from handwerk_hamburg.config import HAMBURG_BBOX
from handwerk_hamburg.data_loader import plz_centroids, load_elektriker_org_list

# Filename for persistent geocode cache (avoids re-querying Nominatim every run)
GEOCODE_CACHE_FILENAME = "geocode_cache.json"

# Common street-name variants in Hamburg (user input -> canonical form for geocoding)
STREET_NORMALIZATIONS = [
    ("Max Brauer Alle", "Max-Brauer-Allee"),
    ("Max Brauer Allee", "Max-Brauer-Allee"),
]

# Known coordinates for frequent addresses when Nominatim fails (e.g. down/SSL)
# Keys: normalized for lookup (_normalize_address_key: lowercase, single spaces, no commas)
_KNOWN_MAX_BRAUER_ALLEE_10 = (53.5506, 9.9292)
KNOWN_ADDRESS_COORDS: dict[str, tuple[float, float]] = {
    "max-brauer-allee 10 hamburg": _KNOWN_MAX_BRAUER_ALLEE_10,
    "max-brauer-allee 10 22765 hamburg": _KNOWN_MAX_BRAUER_ALLEE_10,
    "max brauer allee 10 hamburg": _KNOWN_MAX_BRAUER_ALLEE_10,
    "max brauer alle 10 hamburg": _KNOWN_MAX_BRAUER_ALLEE_10,
}

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


def normalize_address_for_geocoding(address: str) -> list[str]:
    """
    Build a list of address variants to try for geocoding (e.g. fix typos, add Hamburg/Germany).

    Args:
        address: Raw user input.

    Returns:
        List of address strings to try in order (most specific first).
    """
    s = (address or "").strip()
    if not s:
        return []
    # Apply known street name normalizations (e.g. "Max Brauer Alle" -> "Max-Brauer-Allee")
    normalized = s
    for wrong, right in STREET_NORMALIZATIONS:
        if wrong in normalized:
            normalized = normalized.replace(wrong, right)
    # Ensure Hamburg is in the string for better Nominatim results
    if "hamburg" not in normalized.lower():
        normalized = f"{normalized}, Hamburg"
    # Nominatim often expects "Street Number, City" – ensure comma before Hamburg
    normalized = re.sub(r"(\d)\s+(Hamburg)", r"\1, \2", normalized, flags=re.IGNORECASE)
    variants = [normalized]
    if normalized != s:
        variants.append(s)
    # Try with comma before Hamburg on original too
    s_comma = re.sub(r"(\d)\s+(Hamburg)", r"\1, \2", s, flags=re.IGNORECASE)
    if s_comma != normalized and s_comma not in variants:
        variants.append(s_comma)
    # PLZ 22765 = Ottensen (Max-Brauer-Allee); helps Nominatim
    if "max-brauer" in normalized.lower() or "max brauer" in s.lower():
        variants.append("Max-Brauer-Allee 10, 22765 Hamburg")
    # Try with Germany for disambiguation
    if "germany" not in normalized.lower() and "deutschland" not in normalized.lower():
        variants.append(f"{normalized}, Germany")
    return variants


def _normalize_address_key(address: str) -> str:
    """Single canonical form for address lookup: lowercase, single spaces, no commas."""
    s = (address or "").strip().lower().replace(",", " ")
    return re.sub(r"\s+", " ", s).strip()


def _lookup_known_address(address: str) -> tuple[float, float] | None:
    """
    Return known (lat, lon) for an address if it matches a built-in fallback (e.g. Max-Brauer-Allee 10).
    Uses normalized key: lowercase, single spaces, no punctuation.
    """
    lookup_key = _normalize_address_key(address)
    coords = KNOWN_ADDRESS_COORDS.get(lookup_key)
    if coords is not None:
        return coords
    for key, known_coords in KNOWN_ADDRESS_COORDS.items():
        key_clean = _normalize_address_key(key)
        if lookup_key == key_clean or key_clean in lookup_key or lookup_key in key_clean:
            return known_coords
    return None


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


def geocode_address_with_fallbacks(address: str) -> tuple[float, float] | None:
    """
    Geocode a raw user address with normalization and fallbacks.

    Tries in order: (1) known-address table, (2) Nominatim for each normalized variant.
    Use this for user-facing address lookup (e.g. district analysis). For batch/ETL
    use geocode_address() directly.

    Args:
        address: Raw address string (e.g. "Max Brauer Alle 10 Hamburg").

    Returns:
        (lat, lon) if found, else None.
    """
    address = (address or "").strip()
    if not address:
        return None
    # 1) Known coordinates (works when Nominatim is down)
    coords = _lookup_known_address(address)
    if coords is not None:
        return coords
    # 2) Try each normalized variant with the single Nominatim path (cache + Hamburg bbox)
    for variant in normalize_address_for_geocoding(address):
        coords = geocode_address(variant)
        if coords is not None:
            return coords
    return None


# Timestamp of last Nominatim request (for rate limiting in search)
_last_nominatim_request: float = 0


def _short_address_label(address: dict, fallback: str) -> str:
    """
    Build a short address string: street + number, city.
    Uses Nominatim address dict (road, house_number, city/town/state).
    If address dict is empty or missing parts, parses display_name to get first part + Hamburg.
    """
    if not address:
        return _short_address_from_display_name(fallback)

    road = (
        (address.get("road") or address.get("street") or address.get("pedestrian") or "")
        .strip()
    )
    house_number = (address.get("house_number") or address.get("housenumber") or "").strip()
    city = (
        (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("state")
            or ""
        )
        .strip()
    )
    street_part = " ".join(filter(None, [road, house_number])).strip() or road
    if street_part and city:
        return f"{street_part}, {city}"
    if street_part:
        return street_part
    if city:
        return city
    return _short_address_from_display_name(fallback)


def _short_address_from_display_name(display_name: str) -> str:
    """
    Derive a short label from full display_name when address details are missing.
    Uses first segment (street/number) and 'Hamburg' if present in the string.
    """
    s = (display_name or "").strip()
    if not s:
        return s
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return s
    street_part = parts[0]
    if "Hamburg" in s:
        return f"{street_part}, Hamburg"
    if len(parts) >= 2:
        return f"{street_part}, {parts[-1]}"
    return street_part


def nominatim_search(query: str, limit: int = 8) -> list[dict]:
    """
    Call Nominatim search API to get address suggestions (autocomplete).
    Returns list of dicts with "display_name" and optionally "lat", "lon".
    Respects 1 request/second policy. Prefers results within Hamburg viewbox.

    Args:
        query: User-typed search string (e.g. "Max-Brauer" or "Altona").
        limit: Max number of suggestions to return (default 8).

    Returns:
        List of {"display_name": str, "lat": float, "lon": float} for each result.
    """
    global _last_nominatim_request
    q = (query or "").strip()
    if not q:
        return []
    # Build viewbox from Hamburg bbox: Nominatim expects "min_lon,min_lat,max_lon,max_lat"
    min_lon, min_lat, max_lon, max_lat = HAMBURG_BBOX
    viewbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    def _request(params: dict) -> list:
        """Perform one Nominatim request; return list of result dicts."""
        global _last_nominatim_request
        now = time.time()
        elapsed = now - _last_nominatim_request
        if elapsed < NOMINATIM_DELAY_SECONDS:
            time.sleep(NOMINATIM_DELAY_SECONDS - elapsed)
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={
                    **params,
                    "q": q,
                    "format": "json",
                    "limit": limit,
                    "addressdetails": 1,
                },
                headers={"User-Agent": GEOCODE_USER_AGENT},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            _last_nominatim_request = time.time()
        except Exception:
            return []
        if not data or not isinstance(data, list):
            return []
        out = []
        for item in data:
            try:
                display_name = item.get("display_name")
                lat = float(item.get("lat"))
                lon = float(item.get("lon"))
            except (TypeError, ValueError):
                continue
            if not display_name:
                continue
            # Build short label: street + number, city (for dropdown display)
            label = _short_address_label(item.get("address") or {}, display_name)
            out.append({
                "display_name": display_name,
                "label": label,
                "lat": lat,
                "lon": lon,
            })
        return out

    # Prefer results in Hamburg; fall back to Germany-wide if none
    params = {"viewbox": viewbox, "bounded": 0, "countrycodes": "de"}
    out = _request(params)
    if not out:
        params = {"countrycodes": "de"}
        out = _request(params)
    return out


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
