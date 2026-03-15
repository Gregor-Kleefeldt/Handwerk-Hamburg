"""
Visualization: prepare map-ready GeoJSON and choropleth data for the dashboard,
and generate interactive Folium maps of handcraft businesses.
"""

from pathlib import Path

import pandas as pd

# Hamburg center (lat, lon) for map centering
HAMBURG_CENTER = (53.5503, 9.9916)
# Default zoom level for Hamburg city view
HAMBURG_ZOOM = 12
# Above this number of markers, use MarkerCluster to group
MARKER_CLUSTER_THRESHOLD = 50


def _normalize_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names so we can accept lat/latitude, lon/longitude, and optional name, category, address.

    Returns a DataFrame with columns lat, lon, and optionally name, category, address.
    Does not modify the original DataFrame.
    """
    # Work on a copy to avoid modifying the input
    out = df.copy()
    # Detect which column holds latitude (accept common variants)
    lat_col = None
    for c in ["lat", "latitude", "Lat", "Latitude"]:
        if c in out.columns:
            lat_col = c
            break
    # Detect which column holds longitude (accept common variants)
    lon_col = None
    for c in ["lon", "lng", "longitude", "Lon", "Longitude"]:
        if c in out.columns:
            lon_col = c
            break
    # Standardize to "lat" / "lon" if stored under another name
    if lat_col and lat_col != "lat":
        out["lat"] = out[lat_col]
    if lon_col and lon_col != "lon":
        out["lon"] = out[lon_col]
    # Standardize business name column if present
    name_col = next((c for c in ["name", "Name", "business_name"] if c in out.columns), None)
    if name_col and name_col != "name":
        out["name"] = out[name_col]
    # Standardize category/trade column if present
    cat_col = next((c for c in ["category", "Category", "trade", "craft", "source"] if c in out.columns), None)
    if cat_col and cat_col != "category":
        out["category"] = out[cat_col]
    # Standardize address column if present
    addr_col = next((c for c in ["address", "Address", "addr"] if c in out.columns), None)
    if addr_col and addr_col != "address":
        out["address"] = out[addr_col]
    return out


def _build_popup_html(name: str | None, category: str | None, address: str | None) -> str:
    """
    Build HTML snippet for a marker popup: Business Name, Category, Address (each only if available).
    """
    lines = []
    # First line: business name (bold), or em-dash if missing
    lines.append(f"<b>{_escape_html(name) or '—'}</b>")
    # Second line: category or placeholder
    lines.append(_escape_html(category) or "—")
    # Third line: address or placeholder
    lines.append(_escape_html(address) or "—")
    # Join with line breaks for popup display
    return "<br>".join(lines)


def _escape_html(s: str | None) -> str | None:
    """Return None for None, otherwise escape HTML entities in the string."""
    # Treat None and NaN as missing
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    # Convert to string and strip whitespace
    s = str(s).strip()
    if not s:
        return None
    # Escape characters that are special in HTML to prevent XSS
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def create_handwerk_map(
    df: pd.DataFrame,
    output_path: str | Path = "outputs/handwerk_map.html",
) -> Path:
    """
    Create an interactive Folium map of handcraft businesses in Hamburg and save to HTML.

    Adds one marker per business with valid latitude/longitude. Popups show business name,
    category, and address when available. Uses MarkerCluster when the dataset is large
    for better performance and readability.

    Args:
        df: DataFrame with at least latitude and longitude (columns 'lat'/'latitude' and 'lon'/'longitude').
            Optional columns: 'name', 'category', 'address' for popup content.
        output_path: Path for the output HTML file. Defaults to outputs/handwerk_map.html.

    Returns:
        Resolved Path where the map was saved.

    Raises:
        ImportError: If folium is not installed.
    """
    # Lazy import so folium is only required when creating the map
    import folium
    from folium.plugins import MarkerCluster

    # Resolve output path and ensure parent directory exists
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize column names so we can use lat, lon, name, category, address
    normalized = _normalize_df_columns(df)

    # Require standard lat/lon columns after normalization
    if "lat" not in normalized.columns or "lon" not in normalized.columns:
        raise ValueError("DataFrame must contain latitude and longitude columns (e.g. 'lat'/'latitude', 'lon'/'longitude').")

    # Drop rows with missing or invalid coordinates (safe handling of missing lat/lon)
    with_coords = normalized.dropna(subset=["lat", "lon"])
    # Ensure numeric and filter out invalid values (non-numeric lat/lon become NaN and are dropped)
    with_coords = with_coords[
        pd.to_numeric(with_coords["lat"], errors="coerce").notna()
        & pd.to_numeric(with_coords["lon"], errors="coerce").notna()
    ]
    if with_coords.empty:
        # Still create a map centered on Hamburg, with no markers
        m = folium.Map(location=HAMBURG_CENTER, zoom_start=HAMBURG_ZOOM)
        m.save(str(out_path))
        return out_path

    # Create map centered on Hamburg with a reasonable zoom level (11–12)
    m = folium.Map(location=HAMBURG_CENTER, zoom_start=HAMBURG_ZOOM)

    # Use MarkerCluster if the dataset is large for better performance and readability
    use_cluster = len(with_coords) > MARKER_CLUSTER_THRESHOLD
    if use_cluster:
        marker_cluster = MarkerCluster().add_to(m)

    for _, row in with_coords.iterrows():
        lat, lon = float(row["lat"]), float(row["lon"])
        name = row.get("name")
        category = row.get("category")
        address = row.get("address")
        popup_html = _build_popup_html(name, category, address)
        marker = folium.Marker(location=(lat, lon), popup=folium.Popup(popup_html, max_width=300))
        if use_cluster:
            marker.add_to(marker_cluster)
        else:
            marker.add_to(m)

    m.save(str(out_path))
    return out_path


def create_electrician_heatmap(
    df: pd.DataFrame,
    output_path: str | Path = "outputs/electrician_heatmap.html",
) -> Path:
    """
    Create a density heatmap of electrician businesses in Hamburg and save to HTML.

    Uses folium and folium.plugins.HeatMap to show where electricians are concentrated.
    Rows with missing or non-numeric latitude/longitude are dropped before building
    the heatmap. The map is centered on Hamburg with zoom level 11–12.

    Args:
        df: DataFrame with latitude and longitude (columns 'lat'/'latitude' and 'lon'/'longitude').
        output_path: Path for the output HTML file. Defaults to outputs/electrician_heatmap.html.

    Returns:
        Resolved Path where the map was saved.

    Raises:
        ImportError: If folium is not installed.
    """
    # Lazy import so folium is only required when creating the map
    import folium
    from folium.plugins import HeatMap

    # Resolve output path and ensure parent directory (e.g. outputs/) exists
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize column names so we can use lat/lon (same logic as create_handwerk_map)
    normalized = _normalize_df_columns(df)

    # Require standard lat/lon columns after normalization
    if "lat" not in normalized.columns or "lon" not in normalized.columns:
        raise ValueError(
            "DataFrame must contain latitude and longitude columns (e.g. 'lat'/'latitude', 'lon'/'longitude')."
        )

    # Drop rows where latitude or longitude is missing
    with_coords = normalized.dropna(subset=["lat", "lon"])
    # Ensure coordinates are numeric (non-numeric become NaN and are dropped)
    with_coords = with_coords.loc[
        pd.to_numeric(with_coords["lat"], errors="coerce").notna()
        & pd.to_numeric(with_coords["lon"], errors="coerce").notna()
    ]
    # Build list of [lat, lon] for HeatMap; empty list is safe (folium still creates the map)
    heat_data = with_coords[["lat", "lon"]].astype(float).values.tolist()

    # Create map centered on Hamburg with zoom level 11–12
    m = folium.Map(location=HAMBURG_CENTER, zoom_start=HAMBURG_ZOOM)
    # Add heatmap layer showing density of electricians
    HeatMap(heat_data).add_to(m)

    m.save(str(out_path))
    return out_path


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
