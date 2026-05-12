"""Aggregate MEDSL precinct-level 2024 U.S. House returns to state-level CSV.

Input (data/raw/, gitignored due to size):
  - 2024-house-precinct.csv : MEDSL precinct-level returns
    Source: Harvard Dataverse, doi:10.7910/DVN/USBYR4
    Download manually from https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/USBYR4
  - candidate_party_2024.json : manual party tags for candidates whose
    party_simplified is blank in the MEDSL CSV (some states leave both party
    fields empty for real D/R candidates; without this map they would be
    bucketed as Other and inflate the "other" share).

Output:
  - 2024-house-state.csv : 50 rows, columns
    state_usps,votes_dem,votes_rep,votes_other,votes_total

Filters House-office rows, drops administrative meta rows (undervotes,
overvotes, ballot totals, etc.), then sums `votes` grouped by
(state_po, party). Multiple voting modes per precinct are summed as-is.

Usage: uv run python data/aggregate_house_2024.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
SRC = RAW / "2024-house-precinct.csv"
PARTY_MAP_PATH = RAW / "candidate_party_2024.json"
OUT = RAW / "2024-house-state.csv"

HOUSE_OFFICE_RE = r"U\.?S\.? HOUSE|HOUSE OF REPRESENTATIVES"

# Administrative rows in the precinct CSV that are NOT candidate votes.
# Counting these as Other inflates the third-party share (esp. AZ, NJ, VT).
DROP_CANDIDATES = {
    "UNDERVOTES", "UNDER VOTES", "UNDERVOTE", "UNDERVOTES-VOIDS",
    "OVERVOTES", "OVER VOTES", "OVERVOTE",
    "TOTAL VOTES CAST", "TOTAL BALLOTS CAST", "CAST VOTES", "CONTEST TOTAL",
    "BLANKS", "BLANK BALLOTS", "SPOILED", "VOID",
    "WRITE-IN", "WRITEIN", "WRITE IN",
    "SCATTER",
    "ALL OTHERS", "OTHERS",
    "",
}


def main() -> int:
    if not SRC.exists():
        sys.stderr.write(
            f"ERROR: missing {SRC}\n"
            "Download the precinct CSV from Harvard Dataverse "
            "(doi:10.7910/DVN/USBYR4) and place it at that path.\n"
        )
        return 1

    df = pd.read_csv(
        SRC,
        usecols=["state_po", "office", "party_simplified", "party_detailed",
                 "candidate", "votes", "mode", "county_name", "precinct"],
        dtype=str,
        low_memory=False,
    )

    df["office"] = df["office"].fillna("").str.upper()
    df = df[df["office"].str.contains(HOUSE_OFFICE_RE, regex=True, na=False)]
    matched_house = len(df)

    df["state_po"] = df["state_po"].fillna("").str.upper().str.strip()
    df = df[df["state_po"].str.len() == 2]

    df["candidate"] = df["candidate"].fillna("").str.upper().str.strip()
    df = df[~df["candidate"].isin(DROP_CANDIDATES)]

    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0).clip(lower=0).astype(int)
    df["party_simplified"] = df["party_simplified"].fillna("").str.upper().str.strip()

    # De-duplicate mode rows. MEDSL precincts in NJ (and partially NY) report
    # the same votes twice: once as mode=TOTAL and once split across mode
    # breakdowns (ELECTION DAY / EARLY VOTING / MAIL-IN / PROVISIONAL). Summing
    # all rows double-counts those precincts. For any
    # (state, county, precinct, candidate, party_detailed) group that has BOTH
    # a TOTAL row and breakdown rows, keep only the TOTAL row.
    df["mode"] = df["mode"].fillna("").str.upper().str.strip()
    df["county_name"] = df["county_name"].fillna("")
    df["precinct"] = df["precinct"].fillna("")
    df["party_detailed"] = df["party_detailed"].fillna("")
    grp_keys = ["state_po", "county_name", "precinct", "candidate", "party_detailed"]
    has_total = df.groupby(grp_keys)["mode"].transform(lambda s: (s == "TOTAL").any())
    df = df[(~has_total) | (df["mode"] == "TOTAL")].copy()

    # Resolve each ROW to a party bucket. Priority:
    #   1. JSON map entry: human override applies to the candidate's entire
    #      vote total (all rows). Used for state-quirk mis-labels (e.g., VT
    #      tags all non-D candidates as OTHER; Mark Coester is mapped to
    #      REPUBLICAN) and for fusion candidates whose Wikipedia state page
    #      aggregates fusion-line votes into their major party (e.g., OR's
    #      Andrea Salinas with Independent Party of Oregon endorsement).
    #   2. No JSON entry: trust party_simplified row-level. This is the
    #      fusion fix for states whose Wikipedia pages report fusion lines
    #      as separate Other parties (e.g., NY Conservative/WFP). A fusion
    #      candidate not in JSON keeps their major-party rows in D/R and
    #      their fusion-line rows in OTHER.
    #   3. Blank party_simplified + no JSON entry: vote-weighted dominant
    #      D/R from the candidate's D/R rows, else OTHER.
    party_map_raw = json.loads(PARTY_MAP_PATH.read_text())
    party_map = {(s, c): p for s, candidates in party_map_raw.items()
                 if not s.startswith("_")
                 for c, p in candidates.items()}

    dr_rows = df[df["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"])]
    dr_votes = (dr_rows.groupby(["state_po", "candidate", "party_simplified"])["votes"]
                       .sum().unstack("party_simplified", fill_value=0))
    if not dr_votes.empty:
        dominant = dr_votes.idxmax(axis=1).to_dict()
    else:
        dominant = {}

    def resolve_row(state, cand, party_simp):
        key = (state, cand)
        if key in party_map:
            return party_map[key]
        if party_simp in ("DEMOCRAT", "REPUBLICAN", "OTHER"):
            return party_simp
        return dominant.get(key, "OTHER")

    df["party_bucket"] = [
        resolve_row(s, c, p)
        for s, c, p in zip(df["state_po"], df["candidate"], df["party_simplified"])
    ]

    # Warn about blank-party candidates not covered by the manual map or by a
    # D/R reference row — they default to OTHER and may need a map entry.
    blank = (
        (df["party_simplified"] == "")
        & (df["party_bucket"] == "OTHER")
        & ~df.set_index(["state_po", "candidate"]).index.isin(party_map.keys())
    )
    unmapped = (df.loc[blank].groupby(["state_po", "candidate"])["votes"].sum()
                .loc[lambda s: s >= 10000]
                .sort_values(ascending=False))

    agg = (df.groupby(["state_po", "party_bucket"])["votes"].sum()
             .unstack("party_bucket", fill_value=0)
             .reindex(columns=["DEMOCRAT", "REPUBLICAN", "OTHER"], fill_value=0))
    agg.columns = ["votes_dem", "votes_rep", "votes_other"]
    agg["votes_total"] = agg.sum(axis=1)
    agg.index.name = "state_usps"

    if agg.empty:
        sys.stderr.write("ERROR: no House rows matched. Inspect unique `office` values in source.\n")
        return 1

    agg.to_csv(OUT)

    nat = agg.sum()
    print(f"Wrote {OUT} ({len(agg)} states).")
    print(f"National House totals: D {nat['votes_dem']:,} | R {nat['votes_rep']:,} | "
          f"Other {nat['votes_other']:,} | Total {nat['votes_total']:,}")
    print(f"Matched {matched_house:,} House precinct rows.")

    if not unmapped.empty:
        print("\nWARNING: candidates with blank party_simplified and no entry in "
              f"{PARTY_MAP_PATH.name} (≥10,000 votes). Add them to keep them out of Other:",
              file=sys.stderr)
        for (state, cand), votes in unmapped.items():
            print(f"  {state}  {cand}: {votes:,}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
