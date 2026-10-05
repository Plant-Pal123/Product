# PlantPal Soil Data Enrichment Scraper — Coding Agent Brief

## Objective

Build a reliable, source-attributed data ingestion tool that enriches PlantPal's existing soil suitability dataset with **measurable numeric soil properties** and exposes them in a format the website can display and compare.

This must be a compliant data collector, not a brittle website scraper. Prefer documented public APIs, official geospatial services, downloadable open datasets, or permitted WFS/REST endpoints. Respect each provider's terms, licensing, attribution, and rate limits. Do not bypass authentication, CAPTCHAs, access controls, or robots policies. Do not scrape a website if its terms prohibit it; report the limitation and propose an official data-access route instead.

## Existing project context

The current workbook is `plant_pal_soil_crop_suitability.xlsx`. It contains roughly 168 rows with:

- `Field ID`
- `Centroid X`, `Centroid Y` in NZTM coordinates (confirm EPSG with the source metadata; likely NZTM2000 / EPSG:2193)
- `Soil Order`
- `Reserve K Class` and `Reserve K Label`
- `N Leach Risk`
- Crop suitability classes for corn, potato, cabbage, and wheat

These are mainly categorical baseline attributes. They are not laboratory measurements. Existing scripts include `PlantPal-2.py` for weather API data and `SatData.py` for Sentinel-2 vegetation indices. Do not overwrite or silently reinterpret those files.

## Important scope distinction

The goal is to find and ingest numeric soil information that is genuinely available at the requested location. Do **not** fabricate numeric measurements by mapping labels such as `Low` or `Very High` to arbitrary numbers. A categorical source field can be retained as categorical, but must not be represented as an observed soil test result.

For every value, identify whether it is:

- `measured`: laboratory or in-field sensor observation;
- `modelled`: model estimate or prediction;
- `mapped`: spatial soil-map attribute / class or map-derived value;
- `derived`: calculated from other recorded values.

Show users this provenance clearly. Spatial coverage values are estimates for a point or area and are not substitutes for a paddock soil test.

## First task: inspect before coding

1. Inspect the repository structure, existing application framework, data files, database, and deployment setup.
2. Read the workbook and existing Python scripts. Preserve existing behavior unless a change is necessary and documented.
3. Identify the workbook's actual coordinate reference system from source metadata or project documentation. Do not assume it from coordinate magnitudes alone.
4. Identify the website's current data contract and UI components that display field/soil suitability.
5. Write a short implementation plan and list any access keys or decisions required. Continue with public, no-secret data sources wherever possible.

## Data source discovery

Prioritize authoritative New Zealand sources and official open-data services. Investigate sources such as national soil databases/maps, regional council open data, government geospatial portals, and documented soil-property APIs or download services. Verify each candidate's:

- Actual numerical variables and units;
- Spatial coverage and resolution;
- Whether values are measured, modelled, or mapped;
- Update frequency / vintage;
- Licence, attribution requirement, terms, and API limits;
- Documented query method and coordinate system.

Potential numerical variables to support **when genuinely provided by a source**:

- Soil pH, including test method and depth;
- Soil organic carbon / organic matter, with units and depth;
- Total or available nitrogen, with method and depth;
- Olsen P or other phosphorus measure, retaining its exact method;
- Exchangeable potassium or reserve potassium, retaining exact source definition;
- Cation exchange capacity (CEC) and base saturation;
- Electrical conductivity (EC);
- Texture fractions: sand, silt, clay (%);
- Bulk density (g/cm³ or kg/m³);
- Available water capacity / plant-available water, with depth and units;
- Drainage, stoniness, rooting depth, and other properties if numerically available.

Do not claim a value exists until an actual supported source is confirmed. If only categorical classes are available for an area, preserve them as classes and display that no numeric measurement is available.

## Ingestion behavior

Implement a reusable ingestion pipeline that:

1. Accepts a field polygon or location. Use a field polygon when available; otherwise use the existing centroid and clearly indicate point-based lookup.
2. Converts coordinates explicitly to the provider's required CRS using a maintained geospatial library such as `pyproj` / GeoPandas, if already compatible with the project.
3. Queries only documented public endpoints or approved downloads.
4. Handles timeouts, rate limiting, retries with exponential backoff, HTTP errors, invalid responses, missing data, and provider downtime.
5. Caches responses and avoids unnecessary repeated requests. Make refresh intervals configurable per source.
6. Supports a dry-run mode and a small test query before bulk ingestion.
7. Keeps source-specific adapters separate from common normalization and storage code.
8. Never silently substitutes zero for missing, null, censored, or unavailable values.
9. Logs source, query time, feature/field identifier, success/failure, and a safe error message. Do not log secrets or personal data.
10. Can be run manually and scheduled through the project's existing job mechanism. Do not introduce a paid service or new infrastructure without explaining it first.

## Suggested normalized data model

Use the project's existing database and conventions if present. Otherwise define a migration and storage schema equivalent to:

```text
soil_observations
- id
- field_id
- property_code                 # e.g. ph, organic_carbon, bulk_density
- value_numeric                 # nullable numeric value
- value_text                    # nullable class/text where source is categorical
- unit                          # e.g. pH, %, mg/kg, g/cm3
- depth_top_cm                  # nullable
- depth_bottom_cm               # nullable
- observation_date              # date of measurement, if supplied
- retrieved_at                  # UTC timestamp when PlantPal retrieved it
- provenance_type               # measured | modelled | mapped | derived
- source_name
- source_dataset
- source_record_id              # nullable
- source_url                    # dataset/product landing page or record link
- source_version_or_vintage     # nullable
- spatial_resolution_m          # nullable
- geometry_method               # field_polygon | centroid | raster_pixel | source_feature
- quality_flag                  # valid | estimated | stale | missing | review
- uncertainty                   # nullable; include units/method in metadata
- raw_properties_json           # retained source attributes for audit/debugging
```

Add uniqueness/idempotency rules so repeated ingestion updates an existing source observation rather than creating endless duplicates. Preserve historical observations when the source provides dates or when values change; do not erase history without explicit migration logic.

## Units and validation

- Preserve the provider's original value, units, method, and depth.
- Normalize units only when the conversion is unambiguous. Store the original source value and unit as well as any normalized value.
- Do not compare values produced by different laboratory methods as if they were interchangeable.
- Add validation for plausible formats and bounds, but flag suspicious values for review rather than silently clipping them.
- Distinguish absent data from zero and from “below detection limit.”
- For spatial raster data, document the extraction method (point sample, pixel value, or polygon mean/median) and pixel resolution.
- For polygon summaries, include count of valid pixels, coverage percentage, and an aggregation statistic such as median. Do not average categories as though they were continuous measurements.

## Website/API integration

Follow the existing app architecture. Add or extend an endpoint/service to return soil properties for a field in a structured response, for example:

```json
{
  "field_id": "field-123",
  "soil_properties": [
    {
      "property": "organic_carbon",
      "value": 3.2,
      "unit": "%",
      "depth_cm": {"top": 0, "bottom": 10},
      "provenance": "mapped",
      "source": "Verified source name",
      "source_vintage": "YYYY or source version",
      "retrieved_at": "ISO-8601 timestamp",
      "spatial_resolution_m": 100,
      "quality": "estimated"
    }
  ]
}
```

The actual source name, date, resolution, variables, and units must come from verified source metadata; do not use the example values as real data.

Website requirements:

- Display actual numeric values with units and depth where available.
- Clearly label each value `Measured`, `Modelled`, `Mapped`, or `Derived`.
- Show source, sample/map date, spatial resolution, and last retrieval date.
- Indicate unavailable data honestly; never turn missing data into zero or an invented score.
- Keep the existing categorical suitability ratings, but explain that they are baseline/rule-derived ratings, not direct soil measurements.
- Add loading, stale-data, partial-coverage, and source-error states.
- Make mobile layouts usable and preserve the existing visual style.
- Do not make new agronomic recommendations from an added variable unless the rule is documented and scientifically justified.

## Security and operational requirements

- Put API credentials in environment variables or the project's existing secret manager; never commit keys.
- Validate and constrain user-supplied coordinates and field geometry.
- Avoid executing downloaded content. Validate content types and response sizes.
- Do not collect personal information not needed for the feature.
- Add request timeouts, rate limiting, and safe error handling.
- Include provider attribution and comply with data licences in the UI/documentation.

## Tests and acceptance criteria

Add automated tests for:

1. Coordinate transformation and known-coordinate handling.
2. Each source adapter using saved/mock responses; tests must not depend on live services.
3. Correct parsing of numeric values, units, depths, dates, nulls, and categorical values.
4. Provenance tagging and source attribution.
5. Missing, stale, malformed, and out-of-range data handling.
6. Idempotent repeated ingestion and preservation of history.
7. API response shape and website display states.
8. Rate-limit and provider-error behavior.

Feature acceptance criteria:

- The tool can retrieve at least one confirmed numeric soil property from a documented source for a valid supported location, or it explains clearly why no numerical source is available there.
- No category has been converted into an invented measurement.
- Each stored property includes value/unit (or a clear missing state), provenance, source, relevant date/vintage, and retrieval timestamp.
- Existing workbook fields and suitability behavior remain intact.
- The UI distinguishes measurement from map/model estimates.
- Tests pass and a README explains setup, configuration, source/licence attribution, refresh behavior, and limitations.

## Deliverables

1. Working ingestion code integrated into the existing project.
2. Database migration/schema changes, if needed.
3. API/UI changes to show numerical soil properties with provenance.
4. Tests with fixtures or mocked source responses.
5. README documenting sources, licences, units, coordinate assumptions, setup, scheduling, refresh policy, and limitations.
6. A concise completion report stating which sources were verified, what variables are truly numeric, geographic coverage, what remains unavailable, and any required credentials.

## Implementation discipline

- Make the smallest coherent changes consistent with the existing stack.
- Do not rewrite the application or replace the workbook without a demonstrated need.
- Do not make live bulk requests until the source, licence, query pattern, and small test request are verified.
- If a source is unavailable, blocked, or unsuitable, do not fake a successful result. Report the limitation and suggest the next viable official source or a manual soil-lab upload workflow.
