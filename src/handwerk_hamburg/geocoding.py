"""
Geocoding: resolve PLZ to coordinates (e.g. PLZ centroid) and build business points from lists.
"""

from pathlib import Path

from handwerk_hamburg.data_loader import plz_centroids, load_elektriker_org_list


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
    Load electricians from elektriker.org JSON and convert to business points by PLZ centroid.

    Each entry must have 'plz'; we look up the PLZ centroid from the Hamburg PLZ GeoJSON.
    Only entries whose PLZ exists in our PLZ layer get a point (Hamburg + included suburbs).

    Args:
        list_path: Path to elektriker_org_hamburg.json. If None, uses default raw path.
        geojson_path: Path to PLZ GeoJSON for centroids. If None, uses default raw path.

    Returns:
        List of dicts with lon, lat, optional name, and source="elektriker_org".
    """
    entries = load_elektriker_org_list(list_path)
    centroids = plz_centroids(geojson_path)
    features = []
    for entry in entries:
        plz = (entry.get("plz") or "").strip()
        if not plz:
            continue
        if plz not in centroids:
            continue
        lon, lat = centroids[plz]
        features.append({
            "lon": lon,
            "lat": lat,
            "name": entry.get("name"),
            "source": "elektriker_org",
        })
    return features
