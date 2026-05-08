"""Build data/data.json from raw inputs.

Inputs (data/raw/):
  - 2024-house-state.csv : state-level 2024 U.S. House vote totals
    (produced by data/aggregate_house_2024.py from MEDSL precinct returns)
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

USPS_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
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


def load_house_state_totals():
    """Load 2024 U.S. House state-level vote totals produced by aggregate_house_2024.py."""
    totals = defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0, "total": 0})
    src = RAW / "2024-house-state.csv"
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            usps = (row.get("state_usps") or "").strip().upper()
            if usps not in USPS_TO_FIPS:
                continue
            totals[usps]["dem"] += int(row["votes_dem"])
            totals[usps]["rep"] += int(row["votes_rep"])
            totals[usps]["other"] += int(row["votes_other"])
            totals[usps]["total"] += int(row["votes_total"])
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
    votes = load_house_state_totals()
    house = load_house_119th()

    out = {}

    for usps in USPS_TO_FIPS:
        if usps == "DC":
            continue  # no voting House rep
        v = votes.get(usps, {"dem": 0, "rep": 0, "other": 0, "total": 0})
        h = house.get(usps, {"dem": 0, "rep": 0, "ind": 0})

        total_votes = v["total"] or (v["dem"] + v["rep"] + v["other"])
        votes_other = v["other"] if v["other"] else max(total_votes - v["dem"] - v["rep"], 0)
        house_vote_dem = v["dem"] / total_votes if total_votes else 0.0
        house_vote_rep = v["rep"] / total_votes if total_votes else 0.0
        house_vote_other = votes_other / total_votes if total_votes else 0.0

        # 2-party House vote share, parity with 2-party house_dem_share.
        two_party = v["dem"] + v["rep"]
        house_vote_dem_2p = v["dem"] / two_party if two_party else 0.0

        h_two = h["dem"] + h["rep"]
        house_dem_share = h["dem"] / h_two if h_two else None
        house_rep_share = h["rep"] / h_two if h_two else None

        deviation = (
            house_dem_share - house_vote_dem_2p if house_dem_share is not None else None
        )

        out[usps] = {
            "name": USPS_TO_NAME[usps],
            "fips": USPS_TO_FIPS[usps],
            "house_vote_dem": round(house_vote_dem, 4),
            "house_vote_rep": round(house_vote_rep, 4),
            "house_vote_other": round(house_vote_other, 4),
            "house_vote_dem_votes": v["dem"],
            "house_vote_rep_votes": v["rep"],
            "house_vote_other_votes": votes_other,
            "house_vote_total_votes": total_votes,
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
        "house_election_year": 2024,
        "states": out,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    total_reps = sum(s["house_total"] for s in out.values())
    print(f"Wrote {OUT} ({len(out)} states). Total House seats counted: {total_reps}")


if __name__ == "__main__":
    main()
