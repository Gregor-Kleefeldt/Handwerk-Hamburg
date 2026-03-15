"""
Address-based district analysis: geocode an address, find the Hamburg district (Stadtteil),
and return electrician statistics for that district.
"""

import json
import re
from pathlib import Path
from typing import Any

from shapely.geometry import shape, Point

# Optional geopy import so pipeline can run without it if only batch export is used
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False


# User-Agent required by Nominatim usage policy
GEOCODE_USER_AGENT = "handwerk-hamburg"

# Common street-name variants in Hamburg (user input -> canonical form for geocoding)
STREET_NORMALIZATIONS = [
    ("Max Brauer Alle", "Max-Brauer-Allee"),
    ("Max Brauer Allee", "Max-Brauer-Allee"),
]

# Known coordinates for frequent addresses when geocoding fails (e.g. Nominatim down/SSL)
# Key: normalized for lookup (lowercase, single spaces, no punctuation); value: (lat, lon)
_MAX_BRAUER_ALLEE_10 = (53.5506, 9.9292)
KNOWN_ADDRESS_COORDS: dict[str, tuple[float, float]] = {
    "max-brauer-allee 10 hamburg": _MAX_BRAUER_ALLEE_10,
    "max-brauer-allee 10, hamburg": _MAX_BRAUER_ALLEE_10,
    "max-brauer-allee 10, 22765 hamburg": _MAX_BRAUER_ALLEE_10,
    "max brauer allee 10 hamburg": _MAX_BRAUER_ALLEE_10,
    "max brauer alle 10 hamburg": _MAX_BRAUER_ALLEE_10,
}


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


def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Convert an address string to (latitude, longitude) using Nominatim (OpenStreetMap).

    Args:
        address: Full address string, e.g. "Max-Brauer-Allee 10, Hamburg".

    Returns:
        (lat, lon) if the address was found, else None.
    """
    if not GEOPY_AVAILABLE:
        return None
    address = (address or "").strip()
    if not address:
        return None
    try:
        # Create Nominatim geolocator with a unique user agent (required by usage policy)
        geolocator = Nominatim(user_agent=GEOCODE_USER_AGENT)
        # Query Nominatim for the given address; returns first result or None
        location = geolocator.geocode(address)
        if location is None:
            return None
        # Return (latitude, longitude) as floats
        return (location.latitude, location.longitude)
    except (GeocoderTimedOut, GeocoderServiceError, AttributeError):
        return None


def get_district_from_coordinates(lat: float, lon: float, geojson: dict) -> str | None:
    """
    Determine the Hamburg district (Stadtteil) for a given point using the PLZ GeoJSON.

    If the point falls inside a PLZ polygon, that feature's "stadtteil" property is returned.
    If the point is outside all polygons (e.g. outside Hamburg), the nearest polygon's
    stadtteil is returned.

    Args:
        lat: Latitude of the point.
        lon: Longitude of the point (GeoJSON and Shapely use x=lon, y=lat).
        geojson: GeoJSON FeatureCollection with features that have geometry and
                 properties.stadtteil (district name).

    Returns:
        The district name (stadtteil) string, or None if the GeoJSON has no features.
    """
    features = geojson.get("features") or []
    if not features:
        return None
    point = Point(lon, lat)
    # First try: find a polygon that contains the point
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            poly = shape(geom)
            if poly.contains(point):
                # Return the district (stadtteil) from this feature's properties
                props = feat.get("properties") or {}
                stadtteil = props.get("stadtteil") or props.get("district")
                if stadtteil:
                    return str(stadtteil).strip()
                return None
        except Exception:
            continue
    # Fallback: find the nearest polygon by distance to its boundary/centroid
    min_dist = float("inf")
    nearest_stadtteil = None
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            poly = shape(geom)
            # Distance from point to polygon (boundary or interior)
            d = point.distance(poly)
            if d < min_dist:
                min_dist = d
                props = feat.get("properties") or {}
                stadtteil = props.get("stadtteil") or props.get("district")
                if stadtteil:
                    nearest_stadtteil = str(stadtteil).strip()
        except Exception:
            continue
    return nearest_stadtteil


def get_businesses_with_district(
    businesses: list[dict],
    geojson: dict,
) -> list[dict]:
    """
    Assign a district (Stadtteil) to each business by point-in-polygon using the GeoJSON.

    Args:
        businesses: List of dicts with "lat" and "lon" (and optionally "name", "address").
        geojson: GeoJSON FeatureCollection with PLZ polygons and properties.stadtteil.

    Returns:
        List of the same business dicts with an added "district" key (stadtteil name).
        Businesses outside all polygons get district None and are still included.
    """
    features = geojson.get("features") or []
    result = []
    for b in businesses:
        lat = b.get("lat")
        lon = b.get("lon")
        if lat is None or lon is None:
            result.append({**b, "district": None})
            continue
        point = Point(lon, lat)
        district = None
        for feat in features:
            geom = feat.get("geometry")
            if not geom:
                continue
            try:
                poly = shape(geom)
                if poly.contains(point):
                    props = feat.get("properties") or {}
                    district = props.get("stadtteil") or props.get("district")
                    if district:
                        district = str(district).strip()
                    break
            except Exception:
                continue
        result.append({**b, "district": district})
    return result


def run_district_analysis(
    address: str,
    geojson_path: Path,
    businesses_path: Path | None = None,
) -> dict[str, Any]:
    """
    Geocode the address, find the district, and return electrician statistics for that district.

    Args:
        address: Full address string (e.g. "Max-Brauer-Allee 10, Hamburg").
        geojson_path: Path to the scored white-spot GeoJSON (PLZ features with stadtteil).
        businesses_path: Path to electricians JSON (list of {lat, lon, name, address}).
                        If None or file missing, businesses list will be empty.

    Returns:
        Dict with keys: district (str or None), count (int), businesses (list of {name, address}),
        user_lat, user_lon (float or None), error (str or None if no error).
    """
    # Load GeoJSON for district lookup and business assignment
    if not geojson_path.exists():
        return {
            "district": None,
            "count": 0,
            "businesses": [],
            "user_lat": None,
            "user_lon": None,
            "error": "GeoJSON data not found.",
        }
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)

    # Optional: use known coordinates for this address (works even when Nominatim is down)
    lookup_key = re.sub(r"\s+", " ", address.strip().lower()).replace(",", " ")
    lookup_key = re.sub(r"\s+", " ", lookup_key).strip()
    coords = KNOWN_ADDRESS_COORDS.get(lookup_key)
    if coords is None:
        for key, known_coords in KNOWN_ADDRESS_COORDS.items():
            key_clean = key.replace(",", " ")
            if lookup_key == key_clean or key_clean in lookup_key or lookup_key in key_clean:
                coords = known_coords
                break
        else:
            coords = None
    if coords is None:
        # Geocode: try requests-based geocoder first (Hamburg bbox), then geopy
        try:
            from handwerk_hamburg.geocoding import geocode_address as geocode_address_requests
            for variant in normalize_address_for_geocoding(address):
                coords = geocode_address_requests(variant)
                if coords is not None:
                    break
        except Exception:
            pass
        if coords is None:
            for variant in normalize_address_for_geocoding(address):
                coords = geocode_address(variant)
                if coords is not None:
                    break
    if coords is None:
        return {
            "district": None,
            "count": 0,
            "businesses": [],
            "user_lat": None,
            "user_lon": None,
            "error": "Adresse konnte nicht gefunden werden. Tipp: „Max-Brauer-Allee“ mit Bindestrichen und Doppel-e schreiben.",
        }
    user_lat, user_lon = coords

    # Resolve district from coordinates
    district_name = get_district_from_coordinates(user_lat, user_lon, geojson)
    if not district_name:
        return {
            "district": None,
            "count": 0,
            "businesses": [],
            "user_lat": user_lat,
            "user_lon": user_lon,
            "error": "Kein Stadtteil für diese Adresse gefunden (außerhalb Hamburg?).",
        }

    # Load businesses and assign district
    businesses = []
    if businesses_path and businesses_path.exists():
        with open(businesses_path, encoding="utf-8") as f:
            raw = json.load(f)
        businesses = raw if isinstance(raw, list) else []

    # Assign district to each business and filter by the resolved district name
    with_district = get_businesses_with_district(businesses, geojson)
    district_businesses = [b for b in with_district if b.get("district") == district_name]

    # Build list of {name, address} for display (name optional)
    business_list = []
    for b in district_businesses:
        name = b.get("name") or "Unbenannt"
        business_list.append({"name": name, "address": b.get("address")})

    return {
        "district": district_name,
        "count": len(district_businesses),
        "businesses": business_list,
        "user_lat": user_lat,
        "user_lon": user_lon,
        "error": None,
    }
