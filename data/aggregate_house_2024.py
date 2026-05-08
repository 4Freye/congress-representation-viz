"""Aggregate MEDSL precinct-level 2024 U.S. House returns to state-level CSV.

Input (data/raw/, gitignored due to size):
  - 2024-house-precinct.csv : MEDSL precinct-level returns
    Source: Harvard Dataverse, doi:10.7910/DVN/USBYR4
    Download manually from https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/USBYR4

Output:
  - 2024-house-state.csv : 50 rows, columns
    state_usps,votes_dem,votes_rep,votes_other,votes_total

Filters: rows whose `office` field looks like a U.S. House race. Sums `votes`
grouped by (state_po, party_simplified). Multiple voting modes per precinct
(early, mail, election-day) are summed as-is.

Usage: python data/aggregate_house_2024.py
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
SRC = RAW / "2024-house-precinct.csv"
OUT = RAW / "2024-house-state.csv"

# MEDSL `office` values vary slightly. Match anything that looks like House.
HOUSE_OFFICE_TOKENS = ("U.S. HOUSE", "US HOUSE", "U.S HOUSE", "HOUSE OF REPRESENTATIVES")


def is_house_office(office: str) -> bool:
    o = (office or "").upper()
    return any(tok in o for tok in HOUSE_OFFICE_TOKENS)


def main() -> int:
    if not SRC.exists():
        sys.stderr.write(
            f"ERROR: missing {SRC}\n"
            "Download the precinct CSV from Harvard Dataverse "
            "(doi:10.7910/DVN/USBYR4) and place it at that path.\n"
        )
        return 1

    totals = defaultdict(lambda: {"DEMOCRAT": 0, "REPUBLICAN": 0, "OTHER": 0})
    seen_offices = defaultdict(int)
    skipped_no_state = 0
    skipped_bad_votes = 0

    with open(SRC, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"state_po", "office", "party_simplified", "votes"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            sys.stderr.write(
                f"ERROR: precinct CSV missing required columns: {sorted(missing)}\n"
                f"Found columns: {reader.fieldnames}\n"
            )
            return 1

        for row in reader:
            office = row.get("office", "")
            if not is_house_office(office):
                continue
            seen_offices[office] += 1

            usps = (row.get("state_po") or "").strip().upper()
            if len(usps) != 2:
                skipped_no_state += 1
                continue

            try:
                votes = int(float(row.get("votes") or 0))
            except ValueError:
                skipped_bad_votes += 1
                continue
            if votes < 0:
                continue

            party = (row.get("party_simplified") or "").strip().upper()
            if party in ("DEMOCRAT", "REPUBLICAN"):
                totals[usps][party] += votes
            else:
                totals[usps]["OTHER"] += votes

    if not totals:
        sys.stderr.write(
            "ERROR: no House rows matched. Inspect unique `office` values in source.\n"
        )
        return 1

    rows = []
    for usps in sorted(totals):
        t = totals[usps]
        d, r, o = t["DEMOCRAT"], t["REPUBLICAN"], t["OTHER"]
        rows.append({
            "state_usps": usps,
            "votes_dem": d,
            "votes_rep": r,
            "votes_other": o,
            "votes_total": d + r + o,
        })

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["state_usps", "votes_dem", "votes_rep", "votes_other", "votes_total"],
        )
        writer.writeheader()
        writer.writerows(rows)

    nat_d = sum(r["votes_dem"] for r in rows)
    nat_r = sum(r["votes_rep"] for r in rows)
    nat_o = sum(r["votes_other"] for r in rows)
    nat_t = nat_d + nat_r + nat_o
    print(f"Wrote {OUT} ({len(rows)} states).")
    print(f"National House totals: D {nat_d:,} | R {nat_r:,} | Other {nat_o:,} | Total {nat_t:,}")
    print(f"Matched {sum(seen_offices.values()):,} House rows across {len(seen_offices)} office labels.")
    if skipped_no_state or skipped_bad_votes:
        print(
            f"Skipped: {skipped_no_state} bad-state, {skipped_bad_votes} bad-votes rows.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
