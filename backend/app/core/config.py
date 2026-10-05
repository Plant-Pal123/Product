from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, overridable via environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_name: str = "Crop Recommendation & Soil Health Dashboard API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/mango"

    secret_key: str = "change-me-in-.env"
    access_token_expire_minutes: int = 60 * 24

    # External data sources - final choices are an open decision (see design.md §13).
    soil_data_api_base: str | None = None
    weather_data_api_base: str | None = None
    satellite_data_api_base: str | None = None

    # LRIS Portal (Manaaki Whenua - Landcare Research) soil property enrichment.
    # Free account + web service key from https://lris.scinfo.org.nz/ - see
    # backend/README.md#soil-property-enrichment for registration steps and licensing.
    lris_api_key: str | None = None
    lris_api_base: str = "https://lris.scinfo.org.nz/services/query/v1/vector.json"
    lris_request_timeout_seconds: float = 10.0
    lris_max_retries: int = 3
    # Courtesy pacing between sequential requests within one refresh call (6
    # properties per plot) - LRIS doesn't publish an explicit rate limit for
    # this API, but there's no reason to hammer it either.
    lris_request_pacing_seconds: float = 0.3
    # How long a stored soil observation is considered fresh before refresh_soil_data
    # will re-query the source for it (FSL/S-map layers are republished a few times
    # a year at most, so this defaults high).
    soil_observation_ttl_hours: int = 24 * 30

    # Copernicus Data Space Ecosystem (Sentinel Hub-compatible) satellite/NDVI
    # enrichment. Free account + OAuth client at https://dataspace.copernicus.eu/ -
    # see backend/README.md#satellite-ndvi-enrichment for registration steps and
    # licensing (Sentinel-2 data is free/open under the Copernicus data policy;
    # attribution is required).
    cdse_client_id: str | None = None
    cdse_client_secret: str | None = None
    cdse_token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    cdse_statistics_url: str = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
    cdse_request_timeout_seconds: float = 30.0
    cdse_max_retries: int = 3
    # How far back to (re)compute 10-day NDVI aggregates from, and the minimum
    # age before a stored SatelliteReading is re-queried.
    ndvi_lookback_days: int = 60
    ndvi_aggregation_days: int = 10
    ndvi_max_cloud_coverage_pct: int = 60
    satellite_reading_ttl_hours: int = 24 * 5  # Sentinel-2 revisits every ~5 days

    # Open-Meteo (free, no key) weather enrichment - same provider as
    # frontend/js/weather.js, queried independently from the backend so
    # /plots/{id}/recommend doesn't depend on the browser having called it.
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_request_timeout_seconds: float = 10.0
    open_meteo_max_retries: int = 3

    # DeepSeek (OpenAI-compatible chat completions API) - turns a generated
    # future plan's JSON into a plain-language summary for the PDF (FR-5.10).
    # Free/low-cost API key from https://platform.deepseek.com/ - see
    # backend/README.md#ai-plan-summary for setup. Leave blank to skip the AI
    # summary section (the PDF still renders with the heuristic data only).
    deepseek_api_key: str | None = None
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_request_timeout_seconds: float = 30.0
    deepseek_max_retries: int = 3

    # Directory where versioned joblib model artifacts live (design.md §5.3).
    # Relative to the process cwd, which is `backend/` per README.md's run instructions.
    model_artifact_dir: str = "models"
    crop_classifier_version: str = "crop_dt_v1"
    soil_regressor_version: str = "soil_reg_v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
