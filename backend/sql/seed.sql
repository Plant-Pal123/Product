-- Seed data for local dev / manual testing of the pipeline end-to-end.
-- Run after sql/schema.sql:
--   psql mango -f sql/seed.sql
--
-- Crop names match the labels in the standard "Crop Recommendation Dataset"
-- (N, P, K, temperature, humidity, pH, rainfall -> crop) so that whichever crop
-- the trained classifier predicts, app/services/preference_filter.py can look
-- it up by name via `{c.name: c for c in db.query(Crop).all()}`.
-- cost_per_ha / price_per_kg / days_to_harvest are illustrative placeholders,
-- not sourced figures - refine once real crop economics are decided.

-- Demo user (email: demo@example.com, password: demo1234)
INSERT INTO users (email, password_hash)
VALUES ('demo@example.com', '$2b$12$8bY.4mCG9KaAoG45fhq1lOM3VSuYdd2fo49x63ZLNvwtrnlXGU/1q')
RETURNING id;

INSERT INTO preferences (user_id, budget, timeframe_days, excluded_crops)
VALUES (1, 5000, 180, '');

-- Demo plot (a small square boundary near Wellington, NZ)
INSERT INTO plots (user_id, name, boundary)
VALUES (
    1,
    'Home paddock',
    '{"type":"Polygon","coordinates":[[[174.77,-41.29],[174.78,-41.29],[174.78,-41.28],[174.77,-41.28],[174.77,-41.29]]]}'
);

-- One reading per source for the demo plot (id = 1)
INSERT INTO soil_readings (plot_id, date, ph, n, p, k, moisture, source)
VALUES (1, CURRENT_DATE, 6.5, 90, 42, 43, 20.5, 'manual');

INSERT INTO weather_readings (plot_id, date, temp, rainfall, humidity)
VALUES (1, CURRENT_DATE, 20.9, 202.9, 82.0);

INSERT INTO satellite_readings (plot_id, date, ndvi_mean)
VALUES (1, CURRENT_DATE, 0.62);

-- Crops (the 22 labels from the standard crop-recommendation dataset)
INSERT INTO crops (name, days_to_harvest, cost_per_ha, price_per_kg) VALUES
    ('rice',        120, 1200, 0.40),
    ('maize',        90,  800, 0.25),
    ('chickpea',     100,  700, 0.90),
    ('kidneybeans',  100,  750, 1.10),
    ('pigeonpeas',   150,  700, 0.85),
    ('mothbeans',     75,  600, 0.80),
    ('mungbean',      65,  650, 1.00),
    ('blackgram',     90,  650, 0.95),
    ('lentil',       100,  650, 1.20),
    ('pomegranate',  180, 3000, 1.50),
    ('banana',       300, 2500, 0.35),
    ('mango',        365, 2800, 0.60),
    ('grapes',       150, 4000, 1.80),
    ('watermelon',    90, 1500, 0.30),
    ('muskmelon',     90, 1400, 0.35),
    ('apple',        365, 3500, 1.00),
    ('orange',       270, 2600, 0.55),
    ('papaya',       270, 1800, 0.40),
    ('coconut',      365, 2200, 0.50),
    ('cotton',       180, 1600, 1.60),
    ('jute',         120,  900, 0.45),
    ('coffee',       270, 3200, 2.50)
ON CONFLICT (name) DO NOTHING;
