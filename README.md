# White-Spot Map Handwerk (MVP)

A small web dashboard that shows which postal code areas in Hamburg are under-served for certain craft trades (starting with electricians). Renders a choropleth map of "white spots" based on population vs. number of businesses.

## Project structure

```
project-root/
├── data/
│   ├── raw/                 # Raw inputs (PLZ GeoJSON, population CSV, elektriker.org list)
│   └── processed/            # Analysis output (scored GeoJSON, Hamburg boundary)
├── notebooks/                # Exploration notebooks only
├── src/
│   └── handwerk_hamburg/     # Reusable Python package
│       ├── __init__.py
│       ├── config.py         # Trades, Overpass, paths
│       ├── data_loader.py    # Load PLZ, population, electricians; fetch Overpass
│       ├── cleaning.py       # Merge/normalize PLZ data
│       ├── geocoding.py      # PLZ → coordinates, elektriker.org → points
│       ├── analysis.py       # Assign businesses to PLZ, score white spots
│       └── visualization.py  # Map-ready GeoJSON
├── scripts/
│   └── run_analysis.py       # Main workflow entry point
├── tests/
├── app/                      # Web application (FastAPI)
│   ├── main.py
│   ├── templates/
│   └── static/
├── requirements.txt
└── README.md
```

## Setup (macOS)

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the main analysis workflow (fetches OSM + elektriker.org, scores PLZ, writes GeoJSON):

   ```bash
   python scripts/run_analysis.py
   ```

   If the Overpass API times out, the script still writes a GeoJSON with zero businesses (all areas will show as under-served). Run the script again later to refresh with live OSM data.

3. Start the web app:

   ```bash
   uvicorn app.main:app --reload
   ```

4. Open http://127.0.0.1:8000 in your browser.

## Running tests

From project root (with `venv` activated):

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

## Data sources

- **Craft businesses:** OpenStreetMap via Overpass API (`craft=electrician` in Hamburg).
- **PLZ boundaries:** Official Hamburg data from [Transparenzportal Hamburg](https://suche.transparenz.hamburg.de/dataset/postleitzahlen-hamburg2) (Postleitzahlen GeoJSON). The project uses the file in `data/raw/plz_extract/`; to refresh it, download the zip from the portal and extract `de_hh_up_postleitzahlen_EPSG_4326.json` into `data/raw/plz_extract/`, then run the data-prep script in `data/etl/fetch_hamburg_plz_data.py` to regenerate `plz_hamburg.geojson` and `plz_einwohner.csv`.
- **Population:** No official open data exists for inhabitants per PLZ in Hamburg. The ETL uses an area-weighted estimate (total Hamburg population distributed by PLZ area). See `data/etl/fetch_hamburg_plz_data.py`.

## Adding more trades later

- Extend `src/handwerk_hamburg/config.py` with new trade keys and Overpass tag config.
- The UI is prepared for a trade dropdown; only "Electricians" is implemented for the MVP.

## License / data

- Code: use as you like.
- OSM data: © OpenStreetMap contributors, ODbL.
- PLZ/population: replace with your chosen dataset and respect its licence.
