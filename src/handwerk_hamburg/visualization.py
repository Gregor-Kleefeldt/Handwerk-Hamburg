"""
Visualization: prepare map-ready GeoJSON and choropleth data for the dashboard.
"""


def build_map_geojson(geojson_dict: dict) -> dict:
    """
    Prepare scored GeoJSON for map display (choropleth).

    Pass-through that returns the same structure; use this as the single entry point
    for "data for the map" so future filtering or formatting can be added here.

    Args:
        geojson_dict: GeoJSON FeatureCollection from analysis.run_scoring (with white_spot_score, etc.).

    Returns:
        The same GeoJSON dict, ready to be served to the frontend (e.g. /api/geojson).
    """
    return geojson_dict
