-- Schema for the Crop Recommendation & Soil Health Dashboard.
-- Mirrors the ERD in design.md §4 and the SQLAlchemy models in app/db/models.py.
-- Run against a fresh database, e.g.:
--   createdb mango
--   psql mango -f sql/schema.sql

-- CREATE DATABASE mango;  -- uncomment if the database doesn't exist yet

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL
);

CREATE TABLE preferences (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    budget          DOUBLE PRECISION,
    timeframe_days  INTEGER,
    excluded_crops  VARCHAR  -- comma-separated crop names
);

CREATE TABLE plots (
    id       SERIAL PRIMARY KEY,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name     VARCHAR NOT NULL,
    boundary JSONB NOT NULL  -- GeoJSON geometry; swap for PostGIS `geometry` type later
);

CREATE INDEX idx_plots_user_id ON plots(user_id);

CREATE TABLE soil_readings (
    id       SERIAL PRIMARY KEY,
    plot_id  INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    date     DATE NOT NULL,
    ph       DOUBLE PRECISION NOT NULL,
    n        DOUBLE PRECISION NOT NULL,
    p        DOUBLE PRECISION NOT NULL,
    k        DOUBLE PRECISION NOT NULL,
    moisture DOUBLE PRECISION,
    source   VARCHAR NOT NULL  -- e.g. 'soilgrids' or 'manual'
);

CREATE INDEX idx_soil_readings_plot_date ON soil_readings(plot_id, date DESC);

-- Source-attributed numeric soil properties ingested from external providers
-- (see app/services/soil_enrichment). One row per property/source/depth per
-- plot; re-ingestion updates the matching row instead of duplicating it.
CREATE TABLE soil_observations (
    id                       SERIAL PRIMARY KEY,
    plot_id                  INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,

    property_code            VARCHAR NOT NULL,  -- e.g. 'ph', 'organic_carbon', 'cec'
    value_numeric             DOUBLE PRECISION,
    value_text                VARCHAR,
    unit                       VARCHAR,
    depth_top_cm               DOUBLE PRECISION,
    depth_bottom_cm            DOUBLE PRECISION,

    observation_date          DATE,
    retrieved_at              TIMESTAMP NOT NULL DEFAULT now(),

    provenance_type            VARCHAR NOT NULL,  -- measured | modelled | mapped | derived
    source_name                VARCHAR NOT NULL,
    source_dataset              VARCHAR NOT NULL,
    source_record_id            VARCHAR,
    source_url                 VARCHAR NOT NULL,
    source_version_or_vintage   VARCHAR,

    spatial_resolution_m        DOUBLE PRECISION,
    geometry_method             VARCHAR NOT NULL,  -- field_polygon | centroid | raster_pixel | source_feature
    quality_flag                VARCHAR NOT NULL,  -- valid | estimated | stale | missing | review
    uncertainty                 VARCHAR,
    raw_properties_json         JSONB NOT NULL
);

CREATE INDEX idx_soil_observations_plot_id ON soil_observations(plot_id);

-- Idempotency: re-running ingestion for the same plot/property/source/depth
-- updates the existing row (see app/services/soil_enrichment/pipeline.py)
-- rather than creating duplicates. Depth columns are part of the key because
-- a source can report the same property at multiple depth intervals.
CREATE UNIQUE INDEX uq_soil_observations_identity ON soil_observations(
    plot_id, property_code, source_name, source_dataset,
    COALESCE(depth_top_cm, -1), COALESCE(depth_bottom_cm, -1)
);

CREATE TABLE weather_readings (
    id       SERIAL PRIMARY KEY,
    plot_id  INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    date     DATE NOT NULL,
    -- Nullable: see app/db/models.py's WeatherReading - a source can report
    -- some of these for a day and not others; feature_builder.py imputes.
    temp     DOUBLE PRECISION,
    rainfall DOUBLE PRECISION,
    humidity DOUBLE PRECISION
);

CREATE INDEX idx_weather_readings_plot_date ON weather_readings(plot_id, date DESC);

-- Idempotency for app/services/weather_enrichment/pipeline.py: re-running
-- ingestion for the same plot/date updates the existing row instead of
-- creating a duplicate.
CREATE UNIQUE INDEX uq_weather_readings_plot_date ON weather_readings(plot_id, date);

CREATE TABLE satellite_readings (
    id        SERIAL PRIMARY KEY,
    plot_id   INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    date      DATE NOT NULL,
    ndvi_mean DOUBLE PRECISION NOT NULL
);

CREATE INDEX idx_satellite_readings_plot_date ON satellite_readings(plot_id, date DESC);

-- Idempotency for app/services/satellite_enrichment/pipeline.py: re-running
-- ingestion for the same plot/date updates the existing row instead of
-- creating a duplicate NDVI reading for that 10-day interval.
CREATE UNIQUE INDEX uq_satellite_readings_plot_date ON satellite_readings(plot_id, date);

CREATE TABLE crops (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR NOT NULL UNIQUE,
    days_to_harvest INTEGER NOT NULL,
    cost_per_ha    DOUBLE PRECISION NOT NULL,
    price_per_kg   DOUBLE PRECISION NOT NULL
);

CREATE TABLE recommendations (
    id            SERIAL PRIMARY KEY,
    plot_id       INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    crop_id       INTEGER REFERENCES crops(id),
    confidence    DOUBLE PRECISION NOT NULL,
    soil_targets  JSONB NOT NULL,
    model_version VARCHAR NOT NULL,  -- traceability, see design.md §5.3
    created       TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_recommendations_plot_id ON recommendations(plot_id);

CREATE TABLE future_plans (
    id                SERIAL PRIMARY KEY,
    recommendation_id INTEGER NOT NULL UNIQUE REFERENCES recommendations(id) ON DELETE CASCADE,
    content           JSONB NOT NULL,
    pdf_path          VARCHAR
);
