"""Satellite (NDVI) enrichment pipeline.

Ingests real Sentinel-2-derived NDVI statistics from the Copernicus Data
Space Ecosystem's Sentinel Hub-compatible Statistical API for a plot's
boundary, and stores them as `SatelliteReading` rows (the same table
app/services/ingestion.py already reads from for the dashboard's "as of"
satellite data). See backend/README.md#satellite-ndvi-enrichment for setup,
licensing and limitations.
"""
