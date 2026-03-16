"""
FastAPI app: serves the White-Spot Map dashboard and the scored GeoJSON.
"""

import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Paths relative to this file
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
# Ensure handwerk_hamburg can be imported when running uvicorn from project root
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
# Scored GeoJSON for electricians (MVP)
GEOJSON_PATH = PROCESSED_DIR / "white_spot_electrician.geojson"
# Hamburg outline (union of PLZ) for map border
HAMBURG_BOUNDARY_PATH = PROCESSED_DIR / "hamburg_boundary.geojson"
# ALKIS Verwaltungsgrenzen Stadtteile (LGV Hamburg) for hover-based Stadtteil display
ALKIS_STADTTEILE_PATH = PROCESSED_DIR / "alkis_stadtteile.geojson"
# Electricians list for address-based district analysis
ELECTRICIANS_PATH = PROCESSED_DIR / "electricians.json"

app = FastAPI(title="White-Spot Map Handwerk", description="MVP für Hamburg Handwerks-White-Spots")

# Mount static files (CSS, JS) under /static
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
# Jinja2 templates for HTML
templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main dashboard page with the map."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


@app.get("/api/geojson")
async def get_geojson():
    """
    Return the scored GeoJSON for the map.
    For MVP we only have electricians; later this can take ?trade=electrician.
    """
    if not GEOJSON_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    return FileResponse(
        GEOJSON_PATH,
        media_type="application/geo+json",
    )


@app.get("/api/hamburg-boundary")
async def get_hamburg_boundary():
    """Return Hamburg outline GeoJSON (union of PLZ) for map border / future extensions."""
    if not HAMBURG_BOUNDARY_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    return FileResponse(
        HAMBURG_BOUNDARY_PATH,
        media_type="application/geo+json",
    )


@app.get("/api/alkis-stadtteile")
async def get_alkis_stadtteile():
    """
    Return ALKIS Verwaltungsgrenzen Stadtteile (LGV Hamburg) GeoJSON.
    Used for hover: show the official Stadtteil at cursor position (can vary within one PLZ).
    """
    if not ALKIS_STADTTEILE_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    return FileResponse(
        ALKIS_STADTTEILE_PATH,
        media_type="application/geo+json",
    )


@app.get("/api/address-suggestions")
async def address_suggestions(q: str = ""):
    """
    Return address suggestions for autocomplete (e.g. while user types).
    Uses Nominatim (OSM) search; results are biased toward Hamburg, Germany.
    """
    from handwerk_hamburg.geocoding import nominatim_search

    # Run blocking Nominatim HTTP + sleep in thread pool so the event loop is not blocked
    raw = await asyncio.to_thread(nominatim_search, q.strip(), 8)
    # Return list of { "label": "Street, City", "display_name": "..." } – label for dropdown, display_name for analysis
    return [{"label": r.get("label", r["display_name"]), "display_name": r["display_name"]} for r in raw]


@app.get("/api/address-analysis")
async def address_analysis(address: str = ""):
    """
    Geocode the given Hamburg address, determine the district (Stadtteil),
    and return electrician count and list for that district.
    """
    from handwerk_hamburg.address_analysis import run_district_analysis

    # Run blocking geocode + file I/O in thread pool so the event loop is not blocked
    result = await asyncio.to_thread(
        run_district_analysis,
        address=address.strip(),
        geojson_path=GEOJSON_PATH,
        businesses_path=ELECTRICIANS_PATH,
    )
    return result
