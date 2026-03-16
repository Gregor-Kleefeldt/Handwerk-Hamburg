"""
FastAPI app: serves the White-Spot Map dashboard and the scored GeoJSON.

Requires the handwerk_hamburg package to be installed (e.g. pip install -e . from project root).
"""

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from handwerk_hamburg.config import set_project_root, get_processed_dir

# API guardrails: protect Nominatim usage and app stability
MAX_SUGGESTION_QUERY_LENGTH = 200
MAX_ADDRESS_ANALYSIS_LENGTH = 500
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW_SECONDS = 60

# Paths relative to this file (app runs from project root)
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
set_project_root(PROJECT_ROOT)          # register root so config can resolve paths
PROCESSED_DIR = get_processed_dir()     # single source of truth from config.py
# Scored GeoJSON for electricians (MVP)
GEOJSON_PATH = PROCESSED_DIR / "white_spot_electrician.geojson"
# Hamburg outline (union of PLZ) for map border
HAMBURG_BOUNDARY_PATH = PROCESSED_DIR / "hamburg_boundary.geojson"
# ALKIS Verwaltungsgrenzen Stadtteile (LGV Hamburg) for hover-based Stadtteil display
ALKIS_STADTTEILE_PATH = PROCESSED_DIR / "alkis_stadtteile.geojson"
# Electricians list for address-based district analysis
ELECTRICIANS_PATH = PROCESSED_DIR / "electricians.json"

# In-memory rate limit: per-IP timestamps for Nominatim-backed endpoints (pruned each check)
_rate_limit_store: dict[str, list[float]] = {}


def _get_client_ip(request: Request) -> str:
    """Prefer X-Forwarded-For when behind a proxy, else request.client.host."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    """
    Raise 429 if this client has exceeded RATE_LIMIT_REQUESTS in the last RATE_LIMIT_WINDOW_SECONDS.
    Otherwise append current time and continue.
    """
    ip = _get_client_ip(request)
    now = time.monotonic()
    # Keep only timestamps inside the current window
    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > window_start]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Zu viele Anfragen. Bitte kurz warten (Rate-Limit für Adress-Suche).",
        )
    _rate_limit_store[ip].append(now)


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
async def address_suggestions(request: Request, q: str = ""):
    """
    Return address suggestions for autocomplete (e.g. while user types).
    Uses Nominatim (OSM) search; results are biased toward Hamburg, Germany.
    Guardrails: query length limit, rate limit per IP.
    """
    # Rate limit to protect Nominatim (1 req/s policy) and app stability
    _check_rate_limit(request)
    # Reject overly long queries to avoid abuse and huge Nominatim requests
    if len(q) > MAX_SUGGESTION_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Suchanfrage zu lang (max. {MAX_SUGGESTION_QUERY_LENGTH} Zeichen).",
        )
    from handwerk_hamburg.geocoding import nominatim_search

    # Run blocking Nominatim HTTP + sleep in thread pool so the event loop is not blocked
    raw = await asyncio.to_thread(nominatim_search, q.strip(), 8)
    # Return list of { "label": "Street, City", "display_name": "..." } – label for dropdown, display_name for analysis
    return [{"label": r.get("label", r["display_name"]), "display_name": r["display_name"]} for r in raw]


@app.get("/api/address-analysis")
async def address_analysis(request: Request, address: str = ""):
    """
    Geocode the given Hamburg address, determine the district (Stadtteil),
    and return electrician count and list for that district.
    Guardrails: non-empty address, length limit, rate limit per IP.
    """
    # Rate limit to protect Nominatim and app stability
    _check_rate_limit(request)
    address = address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Bitte eine Adresse angeben.")
    if len(address) > MAX_ADDRESS_ANALYSIS_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Adresse zu lang (max. {MAX_ADDRESS_ANALYSIS_LENGTH} Zeichen).",
        )
    from handwerk_hamburg.address_analysis import run_district_analysis

    # Run blocking geocode + file I/O in thread pool so the event loop is not blocked
    result = await asyncio.to_thread(
        run_district_analysis,
        address=address,
        geojson_path=GEOJSON_PATH,
        businesses_path=ELECTRICIANS_PATH,
    )
    return result
