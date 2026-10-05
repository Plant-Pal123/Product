"""SQLAlchemy models mirroring the ERD in design.md §4."""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)

    plots: Mapped[list["Plot"]] = relationship(back_populates="user")
    preferences: Mapped["Preferences"] = relationship(back_populates="user", uselist=False)


class Preferences(Base):
    """User-defined constraints (P) - budget, timeframe, excluded crops (FR-6.x)."""

    __tablename__ = "preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    timeframe_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excluded_crops: Mapped[str | None] = mapped_column(String, nullable=True)  # comma-separated

    user: Mapped["User"] = relationship(back_populates="preferences")


class Plot(Base):
    """A user-defined area of land that analysis runs against."""

    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String)
    boundary: Mapped[dict] = mapped_column(JSON)  # GeoJSON; swap for PostGIS geometry later

    user: Mapped["User"] = relationship(back_populates="plots")
    soil_readings: Mapped[list["SoilReading"]] = relationship(back_populates="plot")
    weather_readings: Mapped[list["WeatherReading"]] = relationship(back_populates="plot")
    satellite_readings: Mapped[list["SatelliteReading"]] = relationship(back_populates="plot")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="plot")
    soil_observations: Mapped[list["SoilObservation"]] = relationship(back_populates="plot")


class SoilReading(Base):
    __tablename__ = "soil_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"))
    date: Mapped[date] = mapped_column(Date)
    ph: Mapped[float] = mapped_column(Float)
    n: Mapped[float] = mapped_column(Float)
    p: Mapped[float] = mapped_column(Float)
    k: Mapped[float] = mapped_column(Float)
    moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String)  # e.g. "soilgrids" or "manual"

    plot: Mapped["Plot"] = relationship(back_populates="soil_readings")


class SoilObservation(Base):
    """A single numeric (or categorical-fallback) soil property value ingested
    from an external, source-attributed provider - see
    app/services/soil_enrichment and plantpal_soil_data_scraper_spec.md.

    Distinct from SoilReading: SoilReading is a flat n/p/k/ph snapshot the
    classifier/regressor consume directly; SoilObservation is the richer,
    provenance-tagged model the spec asks for (one row per property per
    source per depth), meant for display/audit rather than direct ML input.
    """

    __tablename__ = "soil_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"))

    property_code: Mapped[str] = mapped_column(String)  # e.g. "ph", "organic_carbon"
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    depth_top_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_bottom_cm: Mapped[float | None] = mapped_column(Float, nullable=True)

    observation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    provenance_type: Mapped[str] = mapped_column(String)  # measured | modelled | mapped | derived
    source_name: Mapped[str] = mapped_column(String)
    source_dataset: Mapped[str] = mapped_column(String)
    source_record_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str] = mapped_column(String)
    source_version_or_vintage: Mapped[str | None] = mapped_column(String, nullable=True)

    spatial_resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry_method: Mapped[str] = mapped_column(String)  # field_polygon | centroid | raster_pixel | source_feature
    quality_flag: Mapped[str] = mapped_column(String)  # valid | estimated | stale | missing | review
    uncertainty: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_properties_json: Mapped[dict] = mapped_column(JSON)

    plot: Mapped["Plot"] = relationship(back_populates="soil_observations")


class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"))
    date: Mapped[date] = mapped_column(Date)
    # Nullable: a source can report some of these for a given day and not
    # others (rare, but real) - app/services/feature_builder.py already
    # imputes missing fields with regional defaults rather than assuming 0.
    temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)

    plot: Mapped["Plot"] = relationship(back_populates="weather_readings")


class SatelliteReading(Base):
    __tablename__ = "satellite_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"))
    date: Mapped[date] = mapped_column(Date)
    ndvi_mean: Mapped[float] = mapped_column(Float)

    plot: Mapped["Plot"] = relationship(back_populates="satellite_readings")


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    days_to_harvest: Mapped[int] = mapped_column(Integer)
    cost_per_ha: Mapped[float] = mapped_column(Float)
    price_per_kg: Mapped[float] = mapped_column(Float)

    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="crop")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    confidence: Mapped[float] = mapped_column(Float)
    soil_targets: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String)  # traceability, see design.md §5.3
    created: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    plot: Mapped["Plot"] = relationship(back_populates="recommendations")
    crop: Mapped["Crop"] = relationship(back_populates="recommendations")
    future_plan: Mapped["FuturePlan"] = relationship(back_populates="recommendation", uselist=False)


class FuturePlan(Base):
    __tablename__ = "future_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"))
    content: Mapped[dict] = mapped_column(JSON)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="future_plan")
