# congress-representation-viz

Interactive choropleth: how proportionally each state's U.S. House delegation reflects its electorate's partisan lean.

Three view modes (toggle above the map):

- **Party bias** — signed `house_dem_share − house_vote_dem_2p`. Blue = delegation more Democratic than voters, red = more Republican.
- **Absolute fit** — `1 − |house_dem_share − house_vote_dem_2p|`. Two-party-only. Green = close to proportional, red = far off. Domain `[0.7, 1.0]`, clamped.
- **[Gallagher index](https://en.wikipedia.org/wiki/Gallagher_index)** — `sqrt(½·Σ(seat_share − vote_share)²)` over Dem / Rep / Other-or-Independent shares. 0 = perfect proportionality; higher = worse. Penalises larger gaps more heavily than absolute fit and accounts for third-party voters. Green-to-red reversed (green at 0).

A **seats slider** fades states with delegations below a threshold (a one-seat state cannot be proportional by construction). A **scatterplot** below the map shows each state as a dot (delegation size × deviation), recolored and rescaled when you switch modes — small-seat extremity becomes visually obvious. A **national strip** at the bottom compares the nationwide U.S. House vote split to the nationwide House seat split.

Static site, vanilla JS + D3 v7 + TopoJSON. No build step. Hosted on GitHub Pages.

## Run locally

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

## Rebuild data

The U.S. House precinct CSV is too large to commit. Download it manually,
then aggregate to a small state-level CSV that lives in the repo.

```sh
# 1. Download the MEDSL precinct file manually from Harvard Dataverse
#    (doi:10.7910/DVN/USBYR4), save it as:
#    data/raw/2024-house-precinct.csv
#    (gitignored; do not commit)

# 2. Refresh House composition
curl -sSL -o data/raw/legislators-current.json \
  https://unitedstates.github.io/congress-legislators/legislators-current.json

# 3. Aggregate precinct → state-level CSV (run once after each precinct refresh)
python3 data/aggregate_house_2024.py
# writes data/raw/2024-house-state.csv (commit this)

# 4. Rebuild data/data.json
python3 data/build_data.py
```

Stdlib only, no `pip install` needed.

## Data sources

- **2024 U.S. House results (precinct-level, aggregated to state):** [MEDSL Precinct Returns 2024 — Harvard Dataverse, doi:10.7910/DVN/USBYR4](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/USBYR4)
- **House composition (119th Congress):** [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)
- **State boundary TopoJSON:** [topojson/us-atlas](https://github.com/topojson/us-atlas) (loaded from CDN)

## Metrics

For each state with `h_two = house_dem + house_rep`:

- `house_dem_share    = house_dem / h_two`
- `house_vote_dem_2p  = house_vote_dem / (house_vote_dem + house_vote_rep)` (2-party House vote share derived from the 3-way fractions stored in `data.json`)
- `deviation          = house_dem_share − house_vote_dem_2p` (party-bias mode, persisted in `data.json`)
- `abs_fit            = 1 − |house_dem_share − house_vote_dem_2p|`
- `gallagher_index    = sqrt( ½ · Σ_p (seat_share_p − vote_share_p)² )` over `p ∈ {dem, rep, other/ind}`, where seat shares are computed over `house_total` (including independents) and vote shares are computed over total ballots cast.

Absolute fit returns 1 when the delegation perfectly mirrors the electorate and approaches 0 as the gap widens; its map color scale clamps to `[0.7, 1.0]` since real states cluster at the high end. Gallagher index inverts the convention: 0 = perfect, higher = worse, color scale clamped to `[0, 0.3]` and reversed (green at 0).

## Caveats

- Uncontested districts (where one major party has no candidate on the ballot) skew the state's two-party House vote: voters who would back the missing party either don't vote in that race or vote for the unopposed candidate, so the winner's share looks larger than partisan lean alone would predict.
- Single- and two-seat states can only land on coarse delegation shares (0%, 50%, 100%), so their deviations look extreme by construction. The seats slider and the scatterplot make this structural noise visible — fade out small delegations or look at the spread along the x-axis.
- Vacant seats are not counted toward delegation size.
- The Gallagher metric pairs the voter "other" share (third-party / independent House candidates) with the House "independent" share among seated members. These categories don't perfectly correspond, but the bucket is small enough that the approximation rarely changes the picture.
- DC and U.S. territories have no voting House representation and are omitted.

<!-- ## Out of scope (v1)

- State legislative chambers (planned)
- Historical Congresses
- Gerrymandering decomposition (efficiency gap, etc.) -->

## Tests

End-to-end render tests use [Playwright](https://playwright.dev/) against a local `python3 -m http.server`. CI runs them on every push (`.github/workflows/test.yml`).

```sh
npm install
npx playwright install chromium
npm test
```

## Deploy (GitHub Pages)

1. Create empty GitHub repo, push `main`.
2. Repo Settings → Pages → Source: `main` branch, root folder.
3. `.nojekyll` is included so paths starting with `_` aren't filtered.

## License

MIT (TBD).
