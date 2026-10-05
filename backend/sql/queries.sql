-- Reference queries for the Crop Recommendation & Soil Health Dashboard.
-- These mirror the ORM calls in app/services/ingestion.py, app/api/routes/*.py
-- and app/services/preference_filter.py - kept here as the raw-SQL equivalent
-- for debugging, ad-hoc inspection, or a future non-ORM/reporting path.

-- === Ingestion: latest reading per source for a plot (ingestion.py) ===

-- Latest soil reading for a plot
SELECT *
FROM soil_readings
WHERE plot_id = :plot_id
ORDER BY date DESC
LIMIT 1;

-- Latest weather reading for a plot
SELECT *
FROM weather_readings
WHERE plot_id = :plot_id
ORDER BY date DESC
LIMIT 1;

-- Latest satellite reading for a plot
SELECT *
FROM satellite_readings
WHERE plot_id = :plot_id
ORDER BY date DESC
LIMIT 1;

-- === Plots (plots.py) ===

-- Create a plot
INSERT INTO plots (user_id, name, boundary)
VALUES (:user_id, :name, :boundary)
RETURNING id, user_id, name, boundary;

-- All plots for a user (FR-7.2)
SELECT id, name, boundary
FROM plots
WHERE user_id = :user_id;

-- === Soil enrichment (app/services/soil_enrichment/pipeline.py, plots.py) ===

-- All soil properties currently stored for a plot (GET /plots/{id}/soil-properties)
SELECT property_code, value_numeric, value_text, unit, depth_top_cm, depth_bottom_cm,
       provenance_type, source_name, source_dataset, source_url, source_version_or_vintage,
       retrieved_at, spatial_resolution_m, quality_flag, uncertainty
FROM soil_observations
WHERE plot_id = :plot_id
ORDER BY property_code;

-- Existing row for a given property/source/depth (idempotency check before insert)
SELECT id, retrieved_at
FROM soil_observations
WHERE plot_id = :plot_id
  AND property_code = :property_code
  AND source_name = :source_name
  AND source_dataset = :source_dataset
  AND depth_top_cm IS NOT DISTINCT FROM :depth_top_cm
  AND depth_bottom_cm IS NOT DISTINCT FROM :depth_bottom_cm;

-- === Preferences (preferences.py) ===

-- Read preferences for a user
SELECT budget, timeframe_days, excluded_crops
FROM preferences
WHERE user_id = :user_id;

-- Upsert preferences
INSERT INTO preferences (user_id, budget, timeframe_days, excluded_crops)
VALUES (:user_id, :budget, :timeframe_days, :excluded_crops)
ON CONFLICT (user_id)
DO UPDATE SET
    budget = EXCLUDED.budget,
    timeframe_days = EXCLUDED.timeframe_days,
    excluded_crops = EXCLUDED.excluded_crops;

-- === Recommendations (recommendations.py, preference_filter.py) ===

-- All crops, used to apply budget/timeframe filters (preference_filter.py)
SELECT id, name, days_to_harvest, cost_per_ha, price_per_kg
FROM crops;

-- Crops that satisfy a preference's budget and timeframe (equivalent filter,
-- excluded_crops handled in application code since it's a comma-separated column)
SELECT id, name, days_to_harvest, cost_per_ha, price_per_kg
FROM crops
WHERE (:budget IS NULL OR cost_per_ha <= :budget)
  AND (:timeframe_days IS NULL OR days_to_harvest <= :timeframe_days);

-- Persist a recommendation
INSERT INTO recommendations (plot_id, crop_id, confidence, soil_targets, model_version)
VALUES (:plot_id, :crop_id, :confidence, :soil_targets, :model_version)
RETURNING id, created;

-- Fetch a recommendation with its crop (used to build the future plan)
SELECT r.id, r.plot_id, r.crop_id, r.confidence, r.soil_targets, r.model_version, r.created,
       c.name AS crop_name, c.days_to_harvest, c.cost_per_ha, c.price_per_kg
FROM recommendations r
JOIN crops c ON c.id = r.crop_id
WHERE r.id = :recommendation_id;

-- === Plans (plans.py) ===

-- Persist a future plan for a recommendation
INSERT INTO future_plans (recommendation_id, content, pdf_path)
VALUES (:recommendation_id, :content, :pdf_path)
RETURNING id;

-- Fetch a plan by id
SELECT id, recommendation_id, content, pdf_path
FROM future_plans
WHERE id = :plan_id;

-- Set the PDF path once rendered
UPDATE future_plans
SET pdf_path = :pdf_path
WHERE id = :plan_id;

-- === Auth (auth.py) ===

-- Look up a user by email (register/login)
SELECT id, email, password_hash
FROM users
WHERE email = :email;

-- Create a user
INSERT INTO users (email, password_hash)
VALUES (:email, :password_hash)
RETURNING id, email;

-- === Health monitoring (FR-4.5 - soil/NDVI trend over time, not yet exposed via API) ===

-- Soil values over time for a plot
SELECT date, ph, n, p, k, moisture
FROM soil_readings
WHERE plot_id = :plot_id
ORDER BY date ASC;

-- NDVI trend for a plot
SELECT date, ndvi_mean
FROM satellite_readings
WHERE plot_id = :plot_id
ORDER BY date ASC;
