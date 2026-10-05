# TheLastMango: PlantPal Crop Advisor

A decision-support dashboard for agricultural consultants. For a given field it ranks crops,
estimates yield ranges, costs and margins, explains *why* each crop ranks where it does, and
adapts when the consultant pushes back ("too expensive", "too risky", "no equipment" …).

## Run

No build step. ES modules need to be served over HTTP.

**Full stack (frontend + real backend), Windows:** after doing the one-time
setup in `backend/README.md` once, run `.\start.ps1` from the repository root.
It starts the `mango-postgres` Docker container if it's stopped, then opens
the backend (port 8001) and frontend (port 8000) each in their own window and
opens the dashboard in your browser.

**Frontend only** (demo data, no backend/`Live backend` tab):

From the repository root:

```sh
python3 -m http.server 8000
# open http://localhost:8000 (redirects to /frontend/)
```

Or serve the frontend directly:

```sh
python3 -m http.server 8000 --directory frontend
```

## What's on screen

| Area | Contents |
|---|---|
| Field panel | Satellite-style zone map (NDVI / yield zones / slope), terrain stats, soil texture, nutrient bullets vs target ranges, field history |
| Suggested crops | Ranked cards (or table view) with score, yield range, cost, margin, loss risk, soil score; ★ prefer and **Not suitable ▾** feedback |
| Ruled-out crops | Every hard constraint that blocks a crop, with one-click "what would it take" relaxations |
| Margin outlook | P10–P90 margin range per crop |
| Crop detail | Why (narrative + weighted suitability factors) · Expected yield (range, break-even, yield drivers) · Financials (waterfall, price×yield sensitivity, cost table) · Management plan (template + field-specific actions) · Soil impact · Rotation outlook |
| Conditions | Rainfall vs normal + forecast, temperature, soil moisture with stress thresholds |
| Preferences & constraints | Budget, fertiliser budget, target return, risk, labour, machinery, contractors, irrigation, planting window, sustainability, horizon, crop preferences |
| Adjustment log | Every change, how it moved the top recommendation, with undo |

## How recommendations work (`js/engine.js`)

For each crop × management strategy (standard, low-input, irrigated if available):

1. **Suitability** from weighted factors: water supply vs demand (seasonal rain with outlook + soil
   water store + irrigation), growing degree-days and frost, pH (with liming), texture & drainage,
   rotation effects (disease carry-over, legume N credit, break-crop benefit), slope, P & K status.
2. **Yield** = regional potential × factor multipliers × field productivity × strategy, blended
   with the field's own history when available; P10/P90 from crop CV × field weather sensitivity.
3. **Costs** from the crop budget, soil-test-based fertiliser rates, contractor rates for missing
   machinery, labour and irrigation; then revenue, margin, break-even yield/price, and loss
   probability (yield + price variance).
4. **Hard constraints** (budget, labour, machinery, window, risk, horizon, exclusions, strict
   sustainability, water) mark a strategy infeasible; each crop shows its best feasible strategy.
5. **Score** = suitability, profit, risk and sustainability, weighted by risk tolerance,
   sustainability objective and time horizon, plus a farmer-preference bonus.

Consultant feedback (`applyFeedback`) turns an objection into a constraint. For example,
"too expensive" caps the budget just below that option's cost. The dashboard then re-ranks and
shows the trade-offs against the next-best option. That can be the same crop under a cheaper
strategy.

## Plugging in real data

All figures in `js/data/` are **demonstration data**. Replace with adapters that produce the same
shapes:

- `fields.js` → soil lab results / soil grids, DEM slope, Sentinel-2 NDVI zones, weather
  normals, current-season observations and the seasonal outlook.
- `crops.js` → regional agronomic parameters, crop budgets and forward prices.

## Files

```
index.html                   root redirect
frontend/index.html          dashboard layout
frontend/css/styles.css      theme tokens, responsive layout, print styles
frontend/js/app.js           dashboard data, rendering and interactions
frontend/js/engine.js        legacy scoring engine reference
frontend/js/plan.js          legacy season-plan generator reference
frontend/js/charts.js        legacy SVG chart helpers
frontend/js/data/*.js        legacy crop and field data
```
