"""
FastAPI app: serves the White-Spot Map dashboard and the scored GeoJSON.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Paths relative to this file
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
# Scored GeoJSON for electricians (MVP)
GEOJSON_PATH = PROCESSED_DIR / "white_spot_electrician.geojson"
# Hamburg outline (union of PLZ) for map border
HAMBURG_BOUNDARY_PATH = PROCESSED_DIR / "hamburg_boundary.geojson"

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
