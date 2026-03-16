# White Spot Map Handwerk

**Analyzing and visualizing handcraft businesses in Hamburg with a Python data pipeline.**

---

## Project Description

This project analyzes and visualizes handcraft businesses in Hamburg using a **modular Python data pipeline**. It identifies postal code areas (PLZ) that are under-served for certain craft trades (e.g. electricians) by combining business locations with population data and rendering a choropleth “white spot” map. The pipeline is designed for reuse and extension to additional trades.

---

## Project Structure

| Folder | Purpose |
|--------|---------|
| **`data/raw`** | Raw input data: PLZ boundaries (GeoJSON), population estimates (CSV), and external business lists (e.g. elektriker.org). |
| **`data/processed`** | Pipeline output: scored GeoJSON for the map, Hamburg boundary, and other derived datasets. |
| **`notebooks`** | Exploration and ad-hoc analysis in Jupyter notebooks. |
| **`src/handwerk_hamburg`** | Reusable Python package: data loading, cleaning, geocoding, analysis, and map-ready visualization. |
| **`scripts`** | Entry points to run the pipeline (e.g. `run_analysis.py`) and one-off tasks. |

---

## How the White-Spot Score is Computed

The **white_spot_score** (0–1) indicates how under-served a postal code area (PLZ) is for a given trade (e.g. electricians). Higher values mean relatively fewer businesses per inhabitant.

**Formula:**

1. For each PLZ: **people_per_business** = inhabitants ÷ max(business_count, 1).
2. **white_spot_score** = min–max normalization of people_per_business over all PLZ:  
   score = (people_per_business − min) / (max − min), so the PLZ with the fewest businesses per capita gets 1, the best-served gets 0.

**Limitations:**

- **PLZ granularity:** The score is per postal code area. Within one PLZ we do not know which streets or neighbourhoods are under-served; the map cannot show sub-PLZ variation.
- **Source completeness:** Business counts come from **OpenStreetMap (Overpass)** and **elektriker.org**. Not all businesses are listed in these sources, so we may undercount and overstate “white spots”. The map is best used as a relative comparison between PLZ, not as an absolute measure of coverage.

---

## Data Pipeline

The pipeline runs in five stages:

1. **Load** — Read raw PLZ boundaries, population, and fetch businesses (e.g. Overpass API, elektriker.org).
2. **Clean** — Merge and normalize PLZ data; geocode and validate business locations.
3. **Transform** — Assign businesses to PLZ and prepare structures for scoring.
4. **Analyze** — Score each area (e.g. population vs. number of businesses) to identify white spots.
5. **Visualize** — Build map-ready GeoJSON (choropleth) for the dashboard or export.

```
Raw Data
   ↓
Load
   ↓
Clean
   ↓
Transform
   ↓
Analyze
   ↓
Visualize
```

---

## Installation

1. Clone the repository and go into the project folder:

   ```bash
   git clone https://github.com/<your-org>/white-spot-map-handwerk.git
   cd white-spot-map-handwerk
   ```

2. (Recommended) Create and activate a virtual environment (macOS/Linux):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the package in editable mode (recommended; installs dependencies and enables clean imports):

   ```bash
   pip install -e .
   ```

   Alternatively, install dependencies only: `pip install -r requirements.txt` and ensure the project root is on `PYTHONPATH` when running scripts or the app.

---

## Usage

Run the full pipeline from the project root (after `pip install -e .`):

```bash
python scripts/run_analysis.py
```

**What it does:**

- Fetches electricians from the Overpass API and from the elektriker.org Hamburg list.
- Loads PLZ boundaries and population data from `data/raw`.
- Scores each PLZ and writes map-ready GeoJSON to `data/processed/`.

**Output:**

- **`data/processed/white_spot_electrician.geojson`** — Choropleth-ready GeoJSON with white-spot scores per PLZ.
- Optional: Hamburg boundary and other derived files in `data/processed/`.

To view the map in the browser, start the web app (if available):

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000**.

---

## Example Output

After running the pipeline you can expect:

- **Console:** Logs of businesses found (Overpass + elektriker.org), total count, and the path to the written GeoJSON.
- **Map (web app):** A choropleth of Hamburg PLZ areas where under-served regions (“white spots”) are highlighted (e.g. by color intensity or a dedicated color scale).
- **Processed data:** GeoJSON files in `data/processed/` suitable for further analysis or import into other GIS tools.

---

## Future Improvements

- **Interactive map** — Full interactive map of all handcraft businesses (e.g. Leaflet/Mapbox) with tooltips and filters.
- **Filtering by category** — Support multiple trades (plumbers, carpenters, etc.) with a category/trade selector.
- **District-level analysis** — Aggregate and compare at district (Stadtteil) level in addition to PLZ.
- **Web interface** — Optional Streamlit (or similar) app for running the pipeline and exploring results without the command line.

---

## License & Data

- **Code:** Use as you like.
- **OSM data:** © OpenStreetMap contributors, ODbL.
- **PLZ/population:** Replace with your chosen dataset and respect its licence.
