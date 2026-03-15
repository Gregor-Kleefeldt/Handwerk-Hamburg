"""
Data cleaning and normalization: merge PLZ geometries, normalize strings.
"""

import json
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.geometry import mapping


def merge_features_by_plz(features: list[dict]) -> list[dict]:
    """
    Group GeoJSON features by PLZ and merge geometries so there is one feature per PLZ.

    Args:
        features: List of GeoJSON feature dicts with properties.plz (or postcode/PLZ) and geometry.

    Returns:
        List of feature dicts, one per unique PLZ, with merged polygon geometry.
    """
    by_plz = {}
    for f in features:
        plz = (f.get("properties") or {}).get("plz") or (f.get("properties") or {}).get("postcode") or (f.get("properties") or {}).get("PLZ")
        if plz is None:
            continue
        plz_key = str(plz).strip()
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


def normalize_plz(plz: str | None) -> str | None:
    """
    Normalize a PLZ string: strip whitespace and return None for empty.

    Args:
        plz: Raw PLZ value (string or None).

    Returns:
        Stripped string or None if missing/empty.
    """
    if plz is None:
        return None
    s = str(plz).strip()
    return s if s else None
