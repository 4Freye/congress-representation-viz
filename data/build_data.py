"""Build data/data.json from raw inputs.

Inputs (data/raw/):
  - 2024-pres-county.csv : county-level 2024 presidential results (tonmcg)
  - legislators-current.json : unitedstates/congress-legislators

Output: data/data.json keyed by USPS state code.

Usage: python data/build_data.py
"""

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUT = ROOT / "data.json"

STATE_NAME_TO_USPS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

USPS_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}


def load_pres_state_totals():
    totals = defaultdict(lambda: {"dem": 0, "rep": 0})
    with open(RAW / "2024-pres-county.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            usps = STATE_NAME_TO_USPS.get(row["state_name"])
            if not usps:
                continue
            totals[usps]["dem"] += int(row["votes_dem"])
            totals[usps]["rep"] += int(row["votes_gop"])
    return totals


def load_house_119th():
    """Count current Reps per state by party. 119th Congress seated 2025-01-03."""
    with open(RAW / "legislators-current.json", encoding="utf-8") as f:
        legs = json.load(f)
    counts = defaultdict(lambda: {"dem": 0, "rep": 0, "ind": 0})
    for leg in legs:
        current = leg["terms"][-1]
        if current["type"] != "rep":
            continue
        state = current["state"]
        party = current.get("party", "")
        if party == "Democrat":
            counts[state]["dem"] += 1
        elif party == "Republican":
            counts[state]["rep"] += 1
        else:
            counts[state]["ind"] += 1
    return counts


def main():
    pres = load_pres_state_totals()
    house = load_house_119th()

    out = {}
    usps_to_name = {v: k for k, v in STATE_NAME_TO_USPS.items()}

    for usps in USPS_TO_FIPS:
        if usps == "DC":
            continue  # no voting House rep
        p = pres.get(usps, {"dem": 0, "rep": 0})
        h = house.get(usps, {"dem": 0, "rep": 0, "ind": 0})

        two_party = p["dem"] + p["rep"]
        citizen_dem = p["dem"] / two_party if two_party else 0.0
        citizen_rep = p["rep"] / two_party if two_party else 0.0

        h_two = h["dem"] + h["rep"]
        house_dem_share = h["dem"] / h_two if h_two else None
        house_rep_share = h["rep"] / h_two if h_two else None

        deviation = (
            house_dem_share - citizen_dem if house_dem_share is not None else None
        )

        out[usps] = {
            "name": usps_to_name[usps],
            "fips": USPS_TO_FIPS[usps],
            "citizen_dem": round(citizen_dem, 4),
            "citizen_rep": round(citizen_rep, 4),
            "citizen_dem_votes": p["dem"],
            "citizen_rep_votes": p["rep"],
            "house_dem": h["dem"],
            "house_rep": h["rep"],
            "house_ind": h["ind"],
            "house_total": h["dem"] + h["rep"] + h["ind"],
            "house_dem_share": round(house_dem_share, 4) if house_dem_share is not None else None,
            "house_rep_share": round(house_rep_share, 4) if house_rep_share is not None else None,
            "deviation": round(deviation, 4) if deviation is not None else None,
        }

    payload = {
        "generated": date.today().isoformat(),
        "congress": 119,
        "presidential_year": 2024,
        "states": out,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    total_reps = sum(s["house_total"] for s in out.values())
    print(f"Wrote {OUT} ({len(out)} states). Total House seats counted: {total_reps}")


if __name__ == "__main__":
    main()
