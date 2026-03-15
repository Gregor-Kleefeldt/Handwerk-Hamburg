# ETL configuration: trade types and Overpass/OSM tag mapping.
# Add new trades here to keep the pipeline extensible.

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
    # Example for future trades (not used in MVP):
    # "plumber": {
    #     "overpass_key": "craft",
    #     "overpass_value": "plumber",
    #     "label_de": "Klempner / Sanitär",
    # },
}

# Default trade for MVP
DEFAULT_TRADE = "electrician"
