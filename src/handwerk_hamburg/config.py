"""
Configuration: trade definitions, Overpass/OSM settings, and project paths.
"""

from pathlib import Path

# Hamburg bounding box (approx.) for Overpass queries (min_lon, min_lat, max_lon, max_lat)
HAMBURG_BBOX = (9.7, 53.4, 10.2, 53.65)

# Overpass API endpoint (public OSM query service)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Trade definitions: id -> { overpass_key, overpass_value, label_de } for dropdown/extensibility
TRADES = {
    "electrician": {
        "overpass_key": "craft",
        "overpass_value": "electrician",
        "label_de": "Elektro-Handwerk / Elektriker",
    },
}

# Default trade for MVP
DEFAULT_TRADE = "electrician"

# Project root; set by scripts so package can resolve data/ paths
_project_root: Path | None = None


def set_project_root(root: Path) -> None:
    """Set the project root directory (e.g. parent of scripts/). Used to resolve data paths."""
    global _project_root
    _project_root = Path(root).resolve()


def get_project_root() -> Path | None:
    """Return the currently set project root, or None if not set."""
    return _project_root


def get_raw_dir() -> Path:
    """Return data/raw directory under project root. Requires set_project_root() to have been called."""
    if _project_root is None:
        raise RuntimeError("Project root not set. Call set_project_root() first (e.g. in scripts/run_analysis.py).")
    return _project_root / "data" / "raw"


def get_processed_dir() -> Path:
    """Return data/processed directory under project root. Requires set_project_root() to have been called."""
    if _project_root is None:
        raise RuntimeError("Project root not set. Call set_project_root() first (e.g. in scripts/run_analysis.py).")
    return _project_root / "data" / "processed"


# ── Geocoding helpers ────────────────────────────────────────────────────────

# Street-name variants to normalize before sending to Nominatim.
# Each entry is (wrong_variant, canonical_form).
# Extend this list when users report addresses that Nominatim fails to resolve.
STREET_NORMALIZATIONS: list[tuple[str, str]] = [
    ("Max Brauer Alle", "Max-Brauer-Allee"),
    ("Max Brauer Allee", "Max-Brauer-Allee"),
]

# Known fallback coordinates for addresses that Nominatim frequently mis-resolves
# or fails on (e.g. when the service is down).
# Keys: normalized address string (lowercase, no commas, single spaces).
# Values: (lat, lon) tuples.
# Extend this dict to add more reliable fallback addresses.
_KNOWN_MAX_BRAUER_ALLEE_10: tuple[float, float] = (53.5506, 9.9292)
KNOWN_ADDRESS_COORDS: dict[str, tuple[float, float]] = {
    "max-brauer-allee 10 hamburg":       _KNOWN_MAX_BRAUER_ALLEE_10,
    "max-brauer-allee 10 22765 hamburg": _KNOWN_MAX_BRAUER_ALLEE_10,
    "max brauer allee 10 hamburg":       _KNOWN_MAX_BRAUER_ALLEE_10,
    "max brauer alle 10 hamburg":        _KNOWN_MAX_BRAUER_ALLEE_10,
}
