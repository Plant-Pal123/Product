# Backend

FastAPI backend for the Crop Recommendation & Soil Health Dashboard (see `../design.md`, `../requirements.md`).

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
createdb mango
psql mango -f sql/schema.sql
psql mango -f sql/seed.sql          # optional: demo user, plot, readings, crops
python scripts/train_classifier.py  # trains models/crop_dt_v1.joblib
python scripts/train_regressor.py   # trains models/soil_reg_v1.joblib
```

## Run

The frontend's `API_BASE` (`frontend/js/api.js`) points at port **8001** (8000
is taken by the frontend's own static file server - see the root README), so
run the backend on that port:

```bash
uvicorn app.main:app --reload --port 8001
```

Or, once the one-time setup above is done, use `../start.ps1` (Windows) from
the repo root to start Postgres (if it's a stopped Docker container), the
backend and the frontend together in one step.

## Test

```bash
pytest
```

## Soil property enrichment

`app/services/soil_enrichment` ingests genuinely numeric, source-attributed
soil properties (pH, organic carbon, CEC, available water capacity,
potential rooting depth, phosphate retention) from the **LRIS Portal**
(Manaaki Whenua – Landcare Research's national land-resource data
repository, https://lris.scinfo.org.nz/) and stores them in `soil_observations`
alongside the existing `soil_readings` table. It does not touch `soil_readings` or
the ML pipeline - it is additive.

> **⚠️ S-map use is PENDING A LICENCE DECISION, so it is off by default.**
> `SMAP_ENABLED=true` in `backend/.env` (and `SMAP_ENABLED = true` in
> `frontend/js/config.js` for the "Get S-map data" button) adds three S-map
> layers - Soil Drainage (125063), Soil Texture (125064) and Soil Depth
> (125062) - to the soil refresh, as `smap_drainage`,
> `smap_texture` and `smap_depth_class`. S-map is licensed **CC BY-NC-ND 4.0**:
> - **NC (non-commercial):** someone must decide whether PlantPal counts as
>   commercial use. If it does, a commercial licence from Manaaki Whenua –
>   Landcare Research is needed before S-map can be used.
> - **ND (no derivatives):** S-map values are stored and shown exactly as
>   published (e.g. "Poorly drained", "Silty", "Deep") and are never
>   converted to numbers by the backend. The frontend shows a rough cm figure
>   per depth class only when FSL has no rooting depth, labelled "estimate";
>   it is never stored.
> - The credit line "Soil data: S-map © Manaaki Whenua – Landcare Research
>   (CC BY-NC-ND)" is returned in `attribution` whenever an S-map value exists.
>
> **Do not set `SMAP_ENABLED=true` in a deployment until the licence decision
> is made.** While it's false the backend neither fetches nor returns S-map
> values (even ones stored earlier) and the frontend hides the button; FSL
> data works as before.

### Source, why it was chosen, and its limits

- **Adapter used:** the **Fundamental Soil Layers (FSL)**, a national-coverage
  1:50,000 polygon dataset (`app/services/soil_enrichment/specs.py` lists the
  six layers, their exact fields, units and depths - verified against each
  layer's public metadata at `https://lris.scinfo.org.nz/services/api/v1.x/layers/<id>/`
  on 2026-09-27).
- **It is out of date.** Landcare Research's own metadata says FSL soil
  property data "have not been updated since the late 1990s" and recommends
  **S-map Online** (`https://smap.landcareresearch.co.nz/`) as the current
  source where it has coverage (44% of NZ, 60% of farmable land as of
  Aug 2026). FSL was used here because it has full national coverage and a
  workable licence (see below); it is a fallback, not a lab result, and the
  API response is stored with `provenance = "mapped"` so the UI can label it
  accordingly.
- **S-map's own per-property layers were deliberately NOT wired up.** e.g.
  "S-map Predicted pH August 2020" (layer 120518) is licensed
  **CC BY-NC-ND 4.0** - No-Derivatives forbids the kind of
  normalisation/re-expression this pipeline does to every value, and
  No-Commercial needs someone to decide whether PlantPal counts as commercial
  use before it can be used at all. That's a call for the team, not this
  script - see the completion report.
- **Licence for the layers that are wired up:** the custom "Landcare Data Use
  License" (https://lris.scinfo.org.nz/license/landcare-data-use-licence-v1/).
  Permits use, incorporation into other datasets, and derivative works;
  forbids redistributing the raw data to third parties for a fee or
  otherwise, and requires this exact attribution string wherever the data is
  shown or used (already wired into the API's `attribution` field and
  `app/services/soil_enrichment/normalize.ATTRIBUTION_TEXT`):

  > Data reproduced with the permission of Landcare Research New Zealand Limited

### Setup

1. Register a free account at https://lris.scinfo.org.nz/ and generate a web
   service API key (account menu → API keys).
2. Set `LRIS_API_KEY=<your key>` in `backend/.env`.
3. Apply the `soil_observations` table (added to `sql/schema.sql`; there's no
   Alembic in this project yet, so run the new `CREATE TABLE`/`CREATE INDEX`
   statements against your existing database, or re-run the whole file
   against a fresh one).

### Running it

```bash
# Always dry-run a small batch first and diff the logged response shape
# against app/services/soil_enrichment/lris_client.py's docstring - this
# integration has not been checked against a live LRIS response yet.
python scripts/ingest_soil_data.py --dry-run --limit 3

# Then a real small batch, then the rest:
python scripts/ingest_soil_data.py --field-id 1
python scripts/ingest_soil_data.py --all
```

Or per-plot, from the API (used by the frontend's "Live backend" panel, which
follows whichever paddock is selected - see
`scripts/ensure_paddock_plots.py` below):

```
GET  /api/v1/plots/{id}/soil-properties          # stored values only, no network call
POST /api/v1/plots/{id}/soil-properties/refresh  # queries LRIS and upserts (?force=true to bypass the freshness cache)
```

`scripts/ensure_paddock_plots.py` creates (or reuses) one real `Plot` row per
demo paddock in `frontend/js/app.js`'s `paddocks` array, at that paddock's
real farmland coordinates, so the "Live backend" tab has real farmland
locations to query instead of the one urban plot from `sql/seed.sql`. Run it
once, then set the printed plot ids as the `plotId` field on each paddock in
`app.js`.

### Coordinates

The workbook's field centroids are **NZTM2000 / EPSG:2193** (confirmed by its
own "Legend & Assumptions" sheet); Plot boundaries drawn in the app are
GeoJSON, which is WGS84 by spec. `app/services/soil_enrichment/crs.py` makes
both conversions explicit via `pyproj` rather than guessing from coordinate
magnitude. `scripts/ingest_soil_data.py` creates one `Plot` row per workbook
`Field ID` (owned by a dedicated `workbook@plantpal.local` user, named
`"Workbook field {id}"`) so `soil_observations` has something to key off,
without modifying the workbook or the existing 168-row dataset.

### Refresh policy, caching and error handling

- `refresh_soil_observations` skips re-querying a property if a stored value
  is younger than `SOIL_OBSERVATION_TTL_HOURS` (default 30 days - these map
  layers are republished at most a few times a year); pass `force=True` /
  `?force=true` to bypass it.
- Requests retry on timeout/5xx/429 with exponential backoff
  (`LRIS_MAX_RETRIES`, default 3); a 401/403 fails fast as a configuration
  error rather than retrying.
- A source error or "no feature at this point" for one property never blocks
  the others or crashes the endpoint - it's recorded/reported with a status
  of `"error"` (nothing written) or `quality_flag = "missing"` (written, with
  `value_numeric = None`), never a fabricated zero or a class-to-number
  guess.
- Requests within one refresh call (6 properties per plot) are paced
  `LRIS_REQUEST_PACING_SECONDS` apart (default 0.3s) - LRIS doesn't publish
  an explicit rate limit for this API, but there's no reason to hammer it.

### Two real bugs found once a key was actually available (2026-09-27)

Verified against a real key against two points: central Wellington (an
urban/"town" polygon) and a real farmland point (Turakirae soil series,
Wairarapa). Both surfaced bugs the mocked tests couldn't catch:

1. **A non-soil polygon (town, water, etc.) zero-fills every numeric field
   instead of leaving them null** - `PH_MID=0.0` came back with
   `PH_CLASS`/`PH_VAR`/`PH_EST` all null. The original code would have
   stored that 0.0 as a real, "valid" pH. Fixed: `_EST` present (any value)
   is now the actual "this is a real soil record" signal, checked *before*
   looking at the numeric fields at all - see `normalize.py`'s docstring.
2. **`_EST` is not the Y/N flag the layer's plain-English description
   implies** - a real record returned `PH_EST: "u"`, not `"Y"`/`"N"`. It
   documents a graded "origin of estimate" scale (measured → general
   inference) whose exact code table isn't published anywhere reachable.
   Rather than guess which codes mean "measured", every real FSL value is
   now conservatively labelled `quality = "estimated"` (true of the whole
   scale), with the raw code kept in `uncertainty`.

The demo plot (id 1, central Wellington) is itself the "town" case above -
it has no real FSL farmland data at its exact coordinates, so
`/plots/1/soil-properties` correctly shows every property as `missing`.
That's the pipeline working as intended, not a bug: a plot drawn somewhere
with actual farmland (like the Turakirae point above) returns real data.

### Limitations / not done

- The Vector Query API's response shape (`lris_client._extract_features`)
  matched Koordinates' documented platform format on the first real request -
  no changes needed there.
- S-map (the current, higher-resolution source) is only integrated for its
  categorical drainage/texture/depth layers, and only on the smap-integration
  branch pending the licence decision above. Its per-property numeric layers
  (pH etc.) are still not integrated.
- No scheduled job wires up `refresh_soil_observations` yet; run
  `scripts/ingest_soil_data.py` manually or hook it into whatever scheduler
  design.md §3 eventually settles on for weather/satellite refresh.

## Satellite (NDVI) enrichment

`app/services/satellite_enrichment` ingests real Sentinel-2-derived NDVI
(Normalised Difference Vegetation Index) for a plot's boundary from the
**Copernicus Data Space Ecosystem** (the EU/ESA's free Sentinel Hub-compatible
satellite data platform, https://dataspace.copernicus.eu/) and stores it in
the existing `satellite_readings` table (no schema change - just the
`plot_id, date, ndvi_mean` table `app/services/ingestion.py` already reads
from for `/plots/{id}/data`).

### Source, why it was chosen, and its limits

- **Adapter used:** the Statistical API's `sentinel-2-l2a` collection
  (10 m resolution, ~5-day revisit), confirmed live on 2026-09-27 -
  `curl -X POST https://sh.dataspace.copernicus.eu/api/v1/statistics` returns
  a clean 401 (not a 404/connection error), and the collection id was
  confirmed via the API's own public, unauthenticated STAC catalog at
  `https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/collections`.
- NDVI is computed server-side from bands B04 (red) and B08 (near-infrared)
  via the evalscript in `app/services/satellite_enrichment/evalscript.py`,
  which also masks out cloud/cloud-shadow/snow pixels using the Sentinel-2
  L2A Scene Classification Layer - an interval with no cloud-free pixels
  comes back as `no_data`, never a fabricated 0.
- Every other real, no-key-required satellite/NDVI source was checked and
  ruled out: NASA/USGS options all require an Earthdata login; the
  Copernicus Global Land Service's 300 m NDVI product also needs a portal
  account; only fully-keyless options found were browser-only visual tools
  (PixelGust, Pera Portal), not programmatic APIs.
- **Licence:** the STAC catalog lists `"license": "proprietary"` for this
  collection, which is Sentinel Hub's field for data it hosts, not a
  paywall - actual terms are the Copernicus Sentinel Data legal notice
  (free/open, any use, with attribution), citation
  `"Modified Copernicus Sentinel data [Year]/Sentinel Hub"`. The API's
  `/plots/{id}/satellite-history` response includes an `attribution` field
  with the exact text to show in the UI.

### Setup

1. Register a free account at https://dataspace.copernicus.eu/ and create an
   OAuth client (Dashboard → User Settings → OAuth clients).
2. Set `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` in `backend/.env`.
3. Apply the `uq_satellite_readings_plot_date` unique index (added to
   `sql/schema.sql`; no Alembic yet, so run it against your existing database
   or re-run the whole file against a fresh one).

### Running it

```
GET  /api/v1/plots/{id}/satellite-history      # stored NDVI readings only, no network call
POST /api/v1/plots/{id}/satellite/refresh      # queries CDSE and upserts (?force=true to bypass the freshness cache)
```

The Live backend tab follows whichever paddock is selected in the sidebar -
each of the 4 demo paddocks has its own real backend `Plot` row (see
`scripts/ensure_paddock_plots.py`, under soil enrichment above), so this
endpoint returns real, distinct NDVI history per paddock rather than one
fixed plot.

### Refresh policy, caching and error handling

- `refresh_satellite_readings` skips re-querying if the plot's latest stored
  reading is younger than `SATELLITE_READING_TTL_HOURS` (default 5 days,
  matching Sentinel-2's revisit time); pass `force=True` / `?force=true` to
  bypass it.
- Requests retry on timeout/5xx/429 with exponential backoff
  (`CDSE_MAX_RETRIES`, default 3); a 401/403 fails fast as a configuration
  error. The OAuth access token is cached in memory and reused until shortly
  before expiry - the identity server explicitly rate-limits token requests.
- A source error, or an interval with no cloud-free pixels, never crashes
  the endpoint or blocks other intervals - it's reported with a status of
  `"error"` or `"no_data"` (nothing written), never a fabricated NDVI value.

### Limitations / not done

- Verified against a real OAuth client and a real request on 2026-09-27 -
  one thing the docs don't make clear: resolution must be
  `aggregation.resolution: [10, 10]`, not top-level `resx`/`resy` keys (the
  latter are silently ignored, and the API falls back to a single pixel
  spanning the whole AOI, which trips its max-pixel-size guard on anything
  but a tiny bbox - see `client.py`'s module docstring).
- A bare `Point` boundary (e.g. the workbook-derived plots soil's
  `scripts/ingest_soil_data.py` creates) is buffered into a ~200 m square
  before querying, since the Statistics API needs an area, not a point -
  documented in `pipeline._plot_geometry_wgs84`.
- No scheduled job wires this up yet; call the refresh endpoint manually or
  hook it into whatever scheduler design.md §3 eventually settles on.

## Weather enrichment

`app/services/weather_enrichment` ingests real daily weather (mean
temperature, precipitation, mean relative humidity) from **Open-Meteo**
(free, no key or signup - same provider `frontend/js/weather.js` already
uses client-side for the Climate tab) and stores it in the existing
`weather_readings` table - the same table
`app/services/feature_builder.py` reads temperature/humidity/rainfall from
to build the crop classifier and soil regressor's feature vector.

This one queries the backend independently of the frontend's own Open-Meteo
call, so `/plots/{id}/recommend` doesn't depend on the browser having made a
request first.

### Setup

None needed - no API key, no signup. Apply the `uq_weather_readings_plot_date`
unique index and the now-nullable `temp`/`rainfall`/`humidity` columns (both
added to `sql/schema.sql`; no Alembic yet, so run them against your existing
database or re-run the whole file against a fresh one).

### Running it

```
GET  /api/v1/plots/{id}/weather-history      # stored readings only, no network call
POST /api/v1/plots/{id}/weather/refresh      # queries Open-Meteo and upserts (?force=true to bypass the freshness cache)
```

Also follows the selected paddock (see `scripts/ensure_paddock_plots.py`,
under soil enrichment above) - each paddock's plot gets real, distinct
weather rather than one fixed plot.

### Refresh policy and error handling

- `refresh_weather_readings` skips re-querying if a row for **today's local
  date** already exists (unless `force=True`) - simpler than soil/satellite's
  TTL since this table is naturally one row per calendar day. Fetches
  yesterday + today (`past_days=1`) each time so a gap day gets backfilled.
- Requests retry on timeout/5xx/429 with exponential backoff
  (`OPEN_METEO_MAX_RETRIES`, default 3).
- A source error never crashes the endpoint - it's reported with a status of
  `"error"` (nothing written). A field Open-Meteo doesn't report for a given
  day is stored as `NULL`, never a fabricated 0 -
  `app/services/feature_builder.py` already imputes missing fields with
  regional defaults, so this fits that existing design rather than needing
  a new one.

### A real bug this surfaced (and fixed)

`app/services/ingestion.py`'s `get_latest_weather`/`get_latest_soil`/
`get_latest_satellite` used to pick whichever row had the **highest** date on
record, with no upper bound - so a future-dated row (a forecast-shaped
response, or just stray test data) could silently become "the latest
observation" fed into the recommendation. All three now filter to
`date <= today`. Found by installing this pipeline against the seeded demo
plot and noticing `/plots/1/recommend`'s feature vector was reading a
NDVI-adjacent stray weather row dated two weeks in the future instead of
today's real reading.

## AI plan summary

`app/services/plan_summary.py` calls **DeepSeek**'s OpenAI-compatible chat
completions API to add a plain-language section to the future plan PDF: a
short narrative summary, a couple of agronomic notes not already covered by
`plan_generator.py`'s heuristics, and a one-line comment on the finance
table. It never invents figures - the prompt hands the model the exact
numbers `generate_plan` already computed and asks it to describe them, not
recompute them.

### Setup

1. Create a free/low-cost account at https://platform.deepseek.com/ and
   generate an API key (API keys page).
2. Set `DEEPSEEK_API_KEY=<your key>` in `backend/.env`.

No key set → the PDF still renders, just without the "AI summary" section
(see the error handling below).

### Running it

The summary is generated lazily, the first time a plan's PDF is downloaded,
and cached on `FuturePlan.content["ai_summary"]` so it isn't re-requested on
repeat downloads of the same plan:

```
GET /api/v1/plans/{id}/pdf
GET /api/v1/plans/{id}/pdf?force_ai_summary=true   # re-request even if cached (see below)
```

### Error handling

A missing/rejected key or a failed request never blocks the PDF - it's
logged as a warning and `ai_summary` is stored as `null`, same as the
"error"/"missing" pattern used by the soil/satellite/weather pipelines
above. Because it's cached, a plan whose PDF was first downloaded while the
key was missing/invalid/out of credit stays without a summary on later plain
downloads too - even after fixing the key - since `ai_summary` is already
present (as `null`) on that plan. Pass `?force_ai_summary=true` to bypass the
cache and re-request it (e.g. after fixing `DEEPSEEK_API_KEY` or topping up
credit); drop it again once you've confirmed a summary comes back, since it
calls the paid API on every download.

Also remember: **`.env` changes require restarting `uvicorn`** -
`Settings` is `@lru_cache`d and read once at process start, so editing
`DEEPSEEK_API_KEY` (or any other setting) while the server is running has no
effect until it's restarted.

## Notes

- No migrations yet - `sql/schema.sql` is the source of truth for the DDL and must be kept in sync with `app/db/models.py` by hand; wire up Alembic once the DB is provisioned. `sql/queries.sql` has the raw-SQL equivalent of every query the app makes, for debugging/ad-hoc use.
- `/plots/{id}/recommend`, `/recommendations/{id}/plan` and `/plans/{id}/pdf` are fully wired end-to-end against `models/*.joblib` (trained by `scripts/train_classifier.py` / `train_regressor.py` - not checked into git, see `.gitignore`). Both scripts currently train on synthetic per-crop ranges in `app/ml/crop_catalog.py`, not a real dataset - swap in one once `requirements.md` §7 is decided.
- Real external data ingestion (`app/services/ingestion.py`'s `refresh_plot_data`) is superseded by dedicated per-source pipelines - see the Soil/Satellite/Weather enrichment sections above. `soil_readings` (n/p/k) is the one exception: no source has been found that reports real, current N/P/K for a point without a lab test, so it still only comes from `sql/seed.sql` or a manual insert (FR-1.5 already covers manual entry as the intended path).
- PDF export uses ReportLab, not WeasyPrint as design.md originally proposed - WeasyPrint needs native GTK/Pango/Cairo libraries not available on every dev machine (this one included).
