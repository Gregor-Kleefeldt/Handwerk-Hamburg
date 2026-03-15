# White-Spot Map Handwerk (MVP)

A small web dashboard that shows which postal code areas in Hamburg are under-served for certain craft trades (starting with electricians). Renders a choropleth map of "white spots" based on population vs. number of businesses.

## Project structure

```
├── data/                    # Data and ETL
│   ├── raw/                 # Raw inputs (PLZ GeoJSON, population CSV)
│   ├── processed/           # ETL output (scored GeoJSON)
│   └── etl/                 # ETL Python scripts
├── app/                     # Web application
│   ├── main.py              # FastAPI app
│   ├── templates/           # HTML (Jinja2)
│   └── static/              # CSS, JS (Leaflet)
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

2. Run the ETL once to fetch OSM data and build the scored GeoJSON:

   ```bash
   python data/etl/run_etl.py
   ```

   If the Overpass API times out, the script still writes a GeoJSON with zero businesses (all areas will show as under-served). Run the script again later to refresh with live OSM data.

3. Start the web app:

   ```bash
   uvicorn app.main:app --reload
   ```

4. Open http://127.0.0.1:8000 in your browser.

## Data sources

- **Craft businesses:** OpenStreetMap via Overpass API (`craft=electrician` in Hamburg).
- **PLZ boundaries:** Official Hamburg data from [Transparenzportal Hamburg](https://suche.transparenz.hamburg.de/dataset/postleitzahlen-hamburg2) (Postleitzahlen GeoJSON). The project uses the file in `data/raw/plz_extract/`; to refresh it, download the zip from the portal and extract `de_hh_up_postleitzahlen_EPSG_4326.json` into `data/raw/plz_extract/`, then run `python data/etl/fetch_hamburg_plz_data.py` to regenerate `plz_hamburg.geojson` and `plz_einwohner.csv`.
- **Population:** No official open data exists for inhabitants per PLZ in Hamburg. The ETL uses an area-weighted estimate (total Hamburg population distributed by PLZ area). See `data/etl/fetch_hamburg_plz_data.py`.

## Adding more trades later

- Extend `data/etl/config.py` with new trade keys and Overpass tag config.
- The UI is prepared for a trade dropdown; only "Electricians" is implemented for the MVP.

## License / data

- Code: use as you like.
- OSM data: © OpenStreetMap contributors, ODbL.
- PLZ/population: replace with your chosen dataset and respect its licence.
