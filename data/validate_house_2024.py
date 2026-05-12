"""Validate aggregated 2024 U.S. House totals against Wikipedia.

Samples a deterministic 10-state subset from data/raw/2024-house-state.csv,
fetches each state's '2024 United States House of Representatives elections in
[State]' Wikipedia page, parses the by-party results table, and diffs the
3-way D/R/Other vote percentages against the computed totals.

Exit code: 0 if all checks pass, 1 if any fail.

Usage: uv run python data/validate_house_2024.py
"""

from __future__ import annotations

import argparse
import io
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from build_data import USPS_TO_NAME

ROOT = Path(__file__).resolve().parent
STATE_CSV = ROOT / "raw" / "2024-house-state.csv"

SEED = 20240101
SAMPLE_SIZE = 10
TOL_MAJOR_PP = 0.5
TOL_OTHER_PP = 1.0
REQUEST_SLEEP_S = 0.5
HTTP_TIMEOUT_S = 20
TOTAL_SANITY_TOLERANCE_VOTES = 100

USER_AGENT = "congress-representation-viz validator (eric.frey@bse.eu)"
WIKI_URL_FMT = (
    "https://en.wikipedia.org/wiki/"
    "2024_United_States_House_of_Representatives_elections_in_{name}"
)


def load_computed_totals() -> dict[str, dict]:
    df = pd.read_csv(STATE_CSV, dtype={"state_usps": str})
    df = df[df["state_usps"] != "DC"]
    return {
        row.state_usps: {
            "dem": int(row.votes_dem),
            "rep": int(row.votes_rep),
            "other": int(row.votes_other),
            "total": int(row.votes_total),
        }
        for row in df.itertuples()
    }


def sample_states(usps_list: list[str], k: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    return sorted(rng.sample(usps_list, k))


def fetch_wiki_html(state_name: str) -> str:
    # At-large states (AK, DE, MT, ND, SD, VT, WY) use singular "election".
    name = state_name.replace(" ", "_")
    for variant in ("elections", "election"):
        url = (
            "https://en.wikipedia.org/wiki/"
            f"2024_United_States_House_of_Representatives_{variant}_in_{name}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404 and variant == "elections":
                continue
            raise
    raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)


def _flatten_col(col) -> str:
    if isinstance(col, tuple):
        return " ".join(str(c) for c in col if str(c) != "nan").lower().strip()
    return str(col).lower().strip()


def _to_int(value) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in {"nan", "—", "-", "–"}:
        return None
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    return int(s)


def parse_state_totals(html: str) -> dict | None:
    """Extract {dem, rep, other, total} from a state Wikipedia article.

    Walks every table on the page collecting tallies that have BOTH a
    Democratic and Republican row (filters out predictions, single-party
    primaries, infobox summaries). Then:

      - If one table's total ~= sum of the other tables' totals, it's the
        state-level summary; return it.
      - Otherwise the article has no state summary (e.g., small states like
        ID); sum across the per-district general-election tables.
    """
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return None

    candidates: list[dict] = []
    for raw in tables:
        cols = [_flatten_col(c) for c in raw.columns]
        if not cols:
            continue
        party_idxs = [i for i, c in enumerate(cols) if "party" in c]
        votes_idxs = [
            i for i, c in enumerate(cols) if "vote" in c and "%" not in c
        ]
        pct_idxs = [i for i, c in enumerate(cols) if "%" in c or "percent" in c]
        if not party_idxs or not votes_idxs or not pct_idxs:
            continue

        has_seats_col = any("seat" in c for c in cols)
        for party_idx in party_idxs:
            for votes_idx in votes_idxs:
                result = _try_parse(raw, party_idx, votes_idx, has_seats_col)
                if result is not None:
                    candidates.append(result)
                    break
            if candidates and candidates[-1].get("_table_id") == id(raw):
                break

    if not candidates:
        return None

    if len(candidates) == 1:
        return _strip_meta(candidates[0])

    candidates.sort(key=lambda c: c["total"], reverse=True)
    biggest = candidates[0]
    rest_total = sum(c["total"] for c in candidates[1:])
    # Summary table heuristic: its total ~= sum of per-district tables.
    if rest_total > 0 and abs(biggest["total"] - rest_total) / biggest["total"] < 0.01:
        return _strip_meta(biggest)

    # No summary: aggregate across per-district tables.
    agg = {
        "dem": sum(c["dem"] for c in candidates),
        "rep": sum(c["rep"] for c in candidates),
        "other": sum(c["other"] for c in candidates),
    }
    agg["total"] = agg["dem"] + agg["rep"] + agg["other"]
    return agg


def _strip_meta(c: dict) -> dict:
    return {k: v for k, v in c.items() if not k.startswith("_")}


def _try_parse(raw: pd.DataFrame, party_idx: int, votes_idx: int,
               has_seats_col: bool = False) -> dict | None:
    dem = rep = other = 0
    table_total = None
    has_dem = has_rep = False
    has_hold_marker = False

    for _, row in raw.iterrows():
        party_text = str(row.iloc[party_idx]).lower().strip()
        votes = _to_int(row.iloc[votes_idx])
        # 'X hold'/'X gain' rows mark a general-election results table —
        # they have no numeric votes, only a status string in every cell.
        if ("hold" in party_text or "gain" in party_text) and "household" not in party_text:
            has_hold_marker = True
            continue
        if votes is None or party_text in {"", "nan"}:
            continue
        if "total" in party_text:
            table_total = votes
            continue
        if "democrat" in party_text:
            dem += votes
            has_dem = True
        elif "republican" in party_text:
            rep += votes
            has_rep = True
        else:
            other += votes

    # Accept tables that look like state-summary or district general election:
    #   - State summary: D+R rows AND a Seats column (e.g., FL party-totals).
    #   - District general (contested): D+R rows AND a hold/gain marker row.
    #   - District general (uncontested): one of D/R AND a hold/gain marker.
    # Rejects open primaries (e.g., AK pick-one) which can have D+R but no
    # hold marker and no Seats column.
    is_summary = has_dem and has_rep and has_seats_col
    is_contested_general = has_dem and has_rep and has_hold_marker
    is_uncontested_general = (has_dem or has_rep) and has_hold_marker
    if not (is_summary or is_contested_general or is_uncontested_general):
        return None

    computed_total = dem + rep + other
    if table_total is not None:
        if abs(table_total - computed_total) > TOTAL_SANITY_TOLERANCE_VOTES:
            return None
        total = table_total
    else:
        total = computed_total

    if total <= 0:
        return None

    return {
        "dem": dem,
        "rep": rep,
        "other": other,
        "total": total,
        "_table_id": id(raw),
    }


def compute_pct(counts: dict) -> tuple[float, float, float]:
    t = counts["total"]
    if t <= 0:
        return (0.0, 0.0, 0.0)
    return (
        100.0 * counts["dem"] / t,
        100.0 * counts["rep"] / t,
        100.0 * counts["other"] / t,
    )


def compare_state(usps: str, computed: dict, wiki: dict) -> dict:
    c_d, c_r, c_o = compute_pct(computed)
    w_d, w_r, w_o = compute_pct(wiki)
    diffs = (c_d - w_d, c_r - w_r, c_o - w_o)
    tols = (TOL_MAJOR_PP, TOL_MAJOR_PP, TOL_OTHER_PP)
    passes = tuple(abs(d) <= t for d, t in zip(diffs, tols))
    return {
        "usps": usps,
        "calc": (c_d, c_r, c_o),
        "wiki": (w_d, w_r, w_o),
        "diff": diffs,
        "pass": passes,
        "verdict": "PASS" if all(passes) else "FAIL",
        "computed_total": computed["total"],
        "wiki_total": wiki["total"],
    }


def fmt_metric(calc: float, wiki: float, diff: float) -> str:
    return f"{calc:5.2f}/{wiki:5.2f}/{diff:+5.2f}"


def print_results(results: list[dict], errors: list[tuple[str, str]],
                  seed: int = SEED) -> None:
    print(
        f"2024 U.S. House aggregation validation - sample of {SAMPLE_SIZE} states"
    )
    print(
        f"Seed: {seed}  Tolerances: D/R +-{TOL_MAJOR_PP}pp, "
        f"Other +-{TOL_OTHER_PP}pp"
    )
    print(f"Source: {STATE_CSV.relative_to(ROOT.parent)}  vs  en.wikipedia.org")
    print()
    header = (
        "State |   D% calc/wiki/diff   |   R% calc/wiki/diff   "
        "|  Other% calc/wiki/diff  | Verdict"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        d_str = fmt_metric(r["calc"][0], r["wiki"][0], r["diff"][0])
        r_str = fmt_metric(r["calc"][1], r["wiki"][1], r["diff"][1])
        o_str = fmt_metric(r["calc"][2], r["wiki"][2], r["diff"][2])
        print(
            f"{r['usps']:<5} | {d_str:<21} | {r_str:<21} | "
            f"{o_str:<22} | {r['verdict']}"
        )
    for usps, reason in errors:
        print(f"{usps:<5} | (error)               | (error)               "
              f"| (error)                | FAIL ({reason})")

    print()
    n_pass = sum(1 for r in results if r["verdict"] == "PASS")
    n_total = len(results) + len(errors)
    print(f"Summary: {n_pass}/{n_total} pass.")
    fails = [r for r in results if r["verdict"] == "FAIL"]
    for r in fails:
        bad = []
        labels = ("D", "R", "Other")
        tols = (TOL_MAJOR_PP, TOL_MAJOR_PP, TOL_OTHER_PP)
        for lbl, diff, tol, ok in zip(labels, r["diff"], tols, r["pass"]):
            if not ok:
                bad.append(f"{lbl} diff {diff:+.2f}pp > {tol}pp")
        print(f"  FAIL {r['usps']}: {'; '.join(bad)}")
    for usps, reason in errors:
        print(f"  FAIL {usps}: {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=SEED,
                        help=f"random seed for state sample (default {SEED})")
    args = parser.parse_args()

    if not STATE_CSV.exists():
        sys.stderr.write(
            f"ERROR: missing {STATE_CSV}. Run aggregate_house_2024.py first.\n"
        )
        return 1

    computed = load_computed_totals()
    sample = sample_states(sorted(computed.keys()), SAMPLE_SIZE, args.seed)

    results: list[dict] = []
    errors: list[tuple[str, str]] = []

    for i, usps in enumerate(sample):
        name = USPS_TO_NAME[usps]
        if i > 0:
            time.sleep(REQUEST_SLEEP_S)
        try:
            html = fetch_wiki_html(name)
        except urllib.error.HTTPError as e:
            errors.append((usps, f"HTTP {e.code}"))
            continue
        except urllib.error.URLError as e:
            errors.append((usps, f"fetch error: {e.reason}"))
            continue

        wiki = parse_state_totals(html)
        if wiki is None:
            errors.append((usps, "wiki parse failed"))
            continue

        results.append(compare_state(usps, computed[usps], wiki))

    print_results(results, errors, seed=args.seed)
    all_pass = all(r["verdict"] == "PASS" for r in results) and not errors
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
