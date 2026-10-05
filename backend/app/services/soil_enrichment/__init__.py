"""Soil property enrichment pipeline.

Ingests genuinely numeric, source-attributed soil properties from the LRIS
Portal (Manaaki Whenua - Landcare Research) for a plot's centroid, normalises
them, and stores them as `SoilObservation` rows with full provenance. See
`plantpal_soil_data_scraper_spec.md` at the repo root for the brief this
implements, and backend/README.md#soil-property-enrichment for setup,
licensing and limitations.
"""
