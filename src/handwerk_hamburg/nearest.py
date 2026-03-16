"""
Nearest-business logic: Haversine distance and selection of n nearest businesses by location.

Reusable for any endpoint or script that needs distance-based ranking.
"""

import math
from typing import Any


# Earth radius in meters (WGS84 approximation)
EARTH_RADIUS_M = 6_371_000


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Compute great-circle distance between two WGS84 coordinates in meters.

    Uses the Haversine formula. Suitable for short to medium distances.

    Args:
        lat1: Latitude of first point (degrees).
        lon1: Longitude of first point (degrees).
        lat2: Latitude of second point (degrees).
        lon2: Longitude of second point (degrees).

    Returns:
        Distance in meters (>= 0).
    """
    # Convert degrees to radians for trig functions
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    # Haversine formula: a = sin²(Δφ/2) + cos φ1 cos φ2 sin²(Δλ/2)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    # Central angle: c = 2 atan2(√a, √(1−a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def get_nearest_businesses(
    lat: float,
    lon: float,
    businesses: list[dict[str, Any]],
    n: int = 5,
    trade: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return the n nearest businesses to (lat, lon), optionally filtered by trade.

    Sorts by distance ascending and adds a distance_m field to each result.
    Businesses without valid lat/lon are skipped.

    Args:
        lat: Reference latitude (WGS84).
        lon: Reference longitude (WGS84).
        businesses: List of business dicts with at least 'lat', 'lon', and optional 'trade'.
        n: Maximum number of results (default 5).
        trade: If set, only include businesses whose 'trade' equals this value.

    Returns:
        List of up to n dicts with id, name, address, lat, lon, distance_m (rounded to 1 decimal).
    """
    # Filter by trade if requested (e.g. "electrician")
    candidates = businesses
    if trade is not None and trade.strip() != "":
        candidates = [b for b in candidates if (b.get("trade") or "").strip() == trade.strip()]
    # Build list of (business, distance_m) for those with valid coordinates
    with_distance: list[tuple[dict, float]] = []
    for b in candidates:
        blat = b.get("lat")
        blon = b.get("lon")
        if blat is None or blon is None:
            continue
        try:
            d = haversine_distance_m(lat, lon, float(blat), float(blon))
        except (TypeError, ValueError):
            continue
        with_distance.append((b, d))
    # Sort by distance ascending
    with_distance.sort(key=lambda x: x[1])
    # Take first n and format as response records with distance_m
    results: list[dict[str, Any]] = []
    for b, dist_m in with_distance[:n]:
        results.append({
            "id": b.get("id", ""),
            "name": b.get("name") or "Unbenannt",
            "address": b.get("address"),
            "lat": float(b["lat"]),
            "lon": float(b["lon"]),
            "distance_m": round(dist_m, 1),
        })
    return results
