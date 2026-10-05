"""Weather enrichment pipeline.

Ingests real daily weather (mean temperature, precipitation, mean relative
humidity) from Open-Meteo's free forecast API for a plot's centroid, and
stores it in the existing `weather_readings` table - the same table
app/services/feature_builder.py reads temperature/humidity/rainfall from for
the crop classifier and soil regressor's feature vector.

Same source as the frontend's Climate tab (frontend/js/weather.js), queried
independently from the backend so /plots/{id}/recommend doesn't depend on
the browser having made a request first.
"""
