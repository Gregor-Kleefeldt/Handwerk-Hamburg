"""
Build plz_einwohner.csv from official Stadtteil population (Statistik Nord 31.12.2024)
using area-weighted distribution: each PLZ gets a share of its Stadtteil's population
proportional to that PLZ's polygon area. Uses largest-remainder method for rounding.

Source: Statistik Nord, "Bevölkerung in Hamburg am 31.12.2024", A I / S 1 - j 24 HH
(Melderegister). Run from project root: python data/etl/build_plz_einwohner_from_stadtteil.py
"""

import csv
import json
from pathlib import Path

from shapely.geometry import shape

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
GEOJSON_PATH = RAW_DIR / "plz_hamburg.geojson"
STADTTEIL_CSV_PATH = RAW_DIR / "plz_stadtteil.csv"
OUTPUT_CSV_PATH = RAW_DIR / "plz_einwohner.csv"

# Official Hamburg total (Statistik Nord 31.12.2024) for final scaling
HAMBURG_TOTAL_OFFICIAL = 1_973_896

# Official population per Stadtteil (Statistik Nord, 31.12.2024, Melderegister)
# Names as in the report; we map our plz_stadtteil names to these
OFFICIAL_POPULATION = {
    "Altstadt": 2549,
    "HafenCity": 8062,
    "Neustadt": 12710,
    "St. Pauli": 22377,
    "St. Georg": 12508,
    "Hammerbrook": 6943,
    "Borgfelde": 8880,
    "Hamm": 38871,
    "Horn": 39186,
    "Billstedt": 73098,
    "Billbrook": 1851,
    "Rothenburgsort": 11236,
    "Veddel": 4328,
    "Wilhelmsburg": 54073,
    "Kl. Grasbrook u. Steinwerder": 1098,
    "Finkenwerder u. Waltershof": 11662,
    "Altona-Altstadt": 29680,
    "Sternschanze": 7669,
    "Altona-Nord": 26777,
    "Ottensen": 35925,
    "Bahrenfeld": 31051,
    "Groß Flottbek": 11319,
    "Othmarschen": 16528,
    "Lurup": 37755,
    "Osdorf": 26601,
    "Nienstedten": 7062,
    "Blankenese": 13487,
    "Iserbrook": 11523,
    "Sülldorf": 9330,
    "Rissen": 16429,
    "Eimsbüttel": 57798,
    "Rotherbaum": 17253,
    "Harvestehude": 17962,
    "Hoheluft-West": 13641,
    "Lokstedt": 31666,
    "Niendorf": 42496,
    "Schnelsen": 31323,
    "Eidelstedt": 36705,
    "Stellingen": 28812,
    "Hoheluft-Ost": 9853,
    "Eppendorf": 25234,
    "Groß Borstel": 10939,
    "Alsterdorf": 15644,
    "Winterhude": 61192,
    "Uhlenhorst": 19251,
    "Hohenfelde": 10097,
    "Barmbek-Süd": 37091,
    "Dulsberg": 17230,
    "Barmbek-Nord": 44062,
    "Ohlsdorf": 17813,
    "Fuhlsbüttel": 13984,
    "Langenhorn": 48901,
    "Eilbek": 22694,
    "Wandsbek": 38397,
    "Marienthal": 13779,
    "Jenfeld": 29391,
    "Tonndorf": 15580,
    "Farmsen-Berne": 39266,
    "Bramfeld": 53543,
    "Steilshoop": 19902,
    "Wellingsbüttel": 11168,
    "Sasel": 24287,
    "Poppenbüttel": 24598,
    "Hummelsbüttel": 18731,
    "Lemsahl-Mellingstedt": 7031,
    "Duvenstedt": 5940,
    "Wohldorf-Ohlstedt": 4839,
    "Bergstedt": 10822,
    "Volksdorf": 20608,
    "Rahlstedt": 95836,
    "Lohbrügge": 41400,
    "Bergedorf": 37560,
    "Curslack": 4269,
    "Altengamme": 2332,
    "Neuengamme": 3731,
    "Kirchwerder": 10398,
    "Ochsenwerder": 3015,
    "Reitbrook": 497,
    "Allermöhe": 1411,
    "Billwerder": 4117,
    "Moorfleet": 1203,
    "Tatenberg": 560,
    "Spadenland": 537,
    "Neuallermöhe": 23233,
    "Harburg": 29237,
    "Neuland u. Gut Moor": 1821,
    "Wilstorf": 17930,
    "Rönneburg": 3243,
    "Langenbek": 4075,
    "Sinstorf": 4329,
    "Marmstorf": 9290,
    "Eißendorf": 25557,
    "Heimfeld": 22995,
    "Altenwerder u. Moorburg": 729,
    "Hausbruch": 16919,
    "Neugraben-Fischbek": 35295,
    "Francop": 749,
    "Neuenfelde": 5314,
    "Cranz": 858,
}

# Map our plz_stadtteil.csv district name (or part after " / ") to official key
NAME_TO_OFFICIAL = {
    "Hamburg-Altstadt": "Altstadt",
    "HafenCity": "HafenCity",
    "St. Georg": "St. Georg",
    "Eimsbüttel": "Eimsbüttel",
    "Rotherbaum": "Rotherbaum",
    "Hoheluft-Ost": "Hoheluft-Ost",
    "Hoheluft-West": "Hoheluft-West",
    "Neustadt": "Neustadt",
    "St. Pauli": "St. Pauli",
    "Veddel": "Veddel",
    "Hamm": "Hamm",
    "Horn": "Horn",
    "Curslack": "Curslack",
    "Altengamme": "Altengamme",
    "Kirchwerder": "Kirchwerder",
    "Bergedorf": "Bergedorf",
    "Harburg": "Harburg",
    "Eißendorf": "Eißendorf",
    "Wilhelmsburg": "Wilhelmsburg",
    "Neugraben-Fischbek": "Neugraben-Fischbek",
    "Barmbek-Nord": "Barmbek-Nord",
    "Wandsbek": "Wandsbek",
    "Dulsberg": "Dulsberg",
    "Eilbek": "Eilbek",
    "Hohenfelde": "Hohenfelde",
    "Uhlenhorst": "Uhlenhorst",
    "Billstedt": "Billstedt",
    "Marienthal": "Marienthal",
    "Rahlstedt": "Rahlstedt",
    "Tonndorf": "Tonndorf",
    "Bramfeld": "Bramfeld",
    "Steilshoop": "Steilshoop",
    "Sasel": "Sasel",
    "Winterhude": "Winterhude",
    "Fuhlsbüttel": "Fuhlsbüttel",
    "Langenhorn": "Langenhorn",
    "Poppenbüttel": "Poppenbüttel",
    "Alsterdorf": "Alsterdorf",
    "Volksdorf": "Volksdorf",
    "Eppendorf": "Eppendorf",
    "Schnelsen": "Schnelsen",
    "Lurup": "Lurup",
    "Eidelstedt": "Eidelstedt",
    "Stellingen": "Stellingen",
    "Niendorf": "Niendorf",
    "Sülldorf": "Sülldorf",
    "Blankenese": "Blankenese",
    "Othmarschen": "Othmarschen",
    "Altona-Altstadt": "Altona-Altstadt",
    "Bahrenfeld": "Bahrenfeld",
    "Altona-Nord": "Altona-Nord",
    "Sternschanze": "Sternschanze",
}


def get_plz_from_feature(feature: dict) -> str | None:
    """Extract PLZ string from a GeoJSON feature's properties."""
    props = feature.get("properties") or {}
    plz = (
        props.get("plz")
        or props.get("postcode")
        or props.get("PLZ")
        or props.get("postal_code")
    )
    return str(plz).strip() if plz is not None else None


def stadtteil_to_population(stadtteil_str: str) -> int:
    """Map our stadtteil name (possibly composite with ' / ') to total population."""
    # Normalize: strip "Stadtteil " prefix
    s = stadtteil_str.replace("Stadtteil ", "").strip()
    # Walddörfer = aggregate of five report areas (no single report name)
    if s == "Walddörfer":
        return sum(
            OFFICIAL_POPULATION[k]
            for k in ("Lemsahl-Mellingstedt", "Duvenstedt", "Wohldorf-Ohlstedt", "Bergstedt", "Volksdorf")
        )
    total = 0
    for part in s.split(" / "):
        part = part.strip()
        official_key = NAME_TO_OFFICIAL.get(part)
        if official_key and official_key in OFFICIAL_POPULATION:
            total += OFFICIAL_POPULATION[official_key]
    return total


def plz_areas_from_geojson(path: Path) -> dict[str, float]:
    """Load GeoJSON and return PLZ -> relative area (for weighting; proportional to m² in Hamburg)."""
    with open(path, encoding="utf-8") as f:
        geojson = json.load(f)
    result = {}
    for f in geojson.get("features", []):
        plz = get_plz_from_feature(f)
        if not plz:
            continue
        geom = f.get("geometry")
        if not geom:
            continue
        try:
            poly = shape(geom)
            # Area in degree²; ratio between PLZs is valid for weighting in small region
            result[plz] = max(poly.area, 0.0)
        except Exception:
            result[plz] = 0.0
    return result


def distribute_by_area(plz_area_list: list[tuple[str, float]], total_pop: int) -> dict[str, int]:
    """Distribute total_pop across PLZs proportionally to area; use largest-remainder for rounding."""
    if not plz_area_list or total_pop <= 0:
        return {plz: 0 for plz, _ in plz_area_list}
    total_area = sum(a for _, a in plz_area_list)
    if total_area <= 0:
        return {plz: 0 for plz, _ in plz_area_list}
    # Exact share per PLZ
    shares = [(plz, (area / total_area) * total_pop) for plz, area in plz_area_list]
    # Integer part and remainder
    floored = [(plz, int(s), s - int(s)) for plz, s in shares]
    assigned = sum(f for _, f, _ in floored)
    remainder = total_pop - assigned
    # Sort by fractional part descending and assign one extra to the first 'remainder' PLZs
    floored.sort(key=lambda x: -x[2])
    result = {}
    for i, (plz, floor, _) in enumerate(floored):
        result[plz] = floor + (1 if i < remainder else 0)
    return result


def main():
    from collections import defaultdict

    # Load PLZ -> stadtteil from CSV
    plz_to_stadtteil = {}
    with open(STADTTEIL_CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            plz = (row.get("plz") or row.get("postcode") or "").strip()
            stadtteil = (row.get("stadtteil") or row.get("district") or "").strip()
            if plz:
                plz_to_stadtteil[plz] = stadtteil

    # Load PLZ areas from GeoJSON
    plz_area = plz_areas_from_geojson(GEOJSON_PATH)

    # Build reverse: for each official area name, which PLZs reference it (via our stadtteil string)
    # Our stadtteil strings can be "A", "A / B", etc. Map each part to official key, then for each
    # official key collect PLZs whose stadtteil string contains a part mapping to that key.
    official_to_plzs = defaultdict(list)
    for plz, stadtteil in plz_to_stadtteil.items():
        if plz not in plz_area:
            continue
        s = stadtteil.replace("Stadtteil ", "").strip()
        if s == "Walddörfer":
            for k in ("Lemsahl-Mellingstedt", "Duvenstedt", "Wohldorf-Ohlstedt", "Bergstedt", "Volksdorf"):
                official_to_plzs[k].append(plz)
            continue
        for part in s.split(" / "):
            part = part.strip()
            official_key = NAME_TO_OFFICIAL.get(part)
            if official_key and official_key in OFFICIAL_POPULATION:
                official_to_plzs[official_key].append(plz)

    # Each official area is distributed once to its PLZs (by area)
    plz_pop = defaultdict(int)
    all_plz_area = [(p, plz_area[p]) for p in plz_area if plz_area[p] > 0]
    for official_key, pop in OFFICIAL_POPULATION.items():
        plz_list = list(dict.fromkeys(official_to_plzs[official_key]))  # unique, order preserved
        if plz_list:
            area_list = [(p, plz_area[p]) for p in plz_list]
            dist = distribute_by_area(area_list, pop)
        else:
            # No PLZ references this area (e.g. name not in our CSV); distribute by area over all PLZs
            dist = distribute_by_area(all_plz_area, pop)
        for p, n in dist.items():
            plz_pop[p] += n

    # Ensure every PLZ in GeoJSON has an entry (even if 0)
    for plz in plz_area:
        if plz not in plz_pop:
            plz_pop[plz] = 0

    # Scale to official Hamburg total (corrects for rounding)
    total = sum(plz_pop.values())
    if total > 0 and total != HAMBURG_TOTAL_OFFICIAL:
        scale = HAMBURG_TOTAL_OFFICIAL / total
        plz_pop = {p: max(0, round(plz_pop[p] * scale)) for p in plz_pop}
        # Largest-remainder to hit exact total
        new_total = sum(plz_pop.values())
        diff = HAMBURG_TOTAL_OFFICIAL - new_total
        if diff != 0:
            sorted_plz = sorted(plz_pop.keys(), key=lambda p: -plz_pop[p])
            for i, p in enumerate(sorted_plz):
                if diff > 0:
                    plz_pop[p] += 1
                    diff -= 1
                elif diff < 0 and plz_pop[p] > 0:
                    plz_pop[p] -= 1
                    diff += 1
                if diff == 0:
                    break

    # Write CSV
    rows = sorted(plz_pop.items(), key=lambda x: x[0])
    with open(OUTPUT_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["plz", "einwohner"])
        w.writerows(rows)

    total = sum(plz_pop.values())
    print(f"Wrote {OUTPUT_CSV_PATH} with {len(rows)} PLZs, total inhabitants {total}")


if __name__ == "__main__":
    main()
