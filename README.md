# congress-representation-viz

Interactive choropleth: how proportionally each state's U.S. House delegation reflects its electorate's partisan lean.

Default view colors states by **representation deviation** = (Democratic share of House delegation) − (Democratic share of 2024 presidential two-party vote). Hover/click reveals citizen breakdown, House delegation breakdown, and deviation.

Static site, vanilla JS + D3 v7 + TopoJSON. No build step. Hosted on GitHub Pages.

## Run locally

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

## Rebuild data

```sh
# refresh raw inputs (optional)
curl -sSL -o data/raw/2024-pres-county.csv \
  https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/master/2024_US_County_Level_Presidential_Results.csv
curl -sSL -o data/raw/legislators-current.json \
  https://unitedstates.github.io/congress-legislators/legislators-current.json

# rebuild data/data.json
python3 data/build_data.py
```

Stdlib only, no `pip install` needed.

## Data sources

- **2024 presidential results (county-level, aggregated to state):** [tonmcg/US_County_Level_Election_Results_08-24](https://github.com/tonmcg/US_County_Level_Election_Results_08-24)
- **House composition (119th Congress):** [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)
- **State boundary TopoJSON:** [topojson/us-atlas](https://github.com/topojson/us-atlas) (loaded from CDN)

## Caveats

- Presidential vote share proxies partisan lean; it is not party identification.
- Single- and two-seat states (AK, DE, ND, SD, VT, WY, ID, HI, ME, MT, NH, RI, WV) can only land on coarse delegation shares (0%, 50%, 100%), so their deviations look extreme by construction.
- Vacancies and independents are excluded from the House two-party share.
- DC and U.S. territories have no voting House representation and are omitted.

## Out of scope (v1)

- State legislative chambers (planned)
- Historical Congresses
- Gerrymandering decomposition (efficiency gap, etc.)

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
