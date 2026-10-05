"""CLI entry point for the soil property enrichment pipeline
(app/services/soil_enrichment). Run from backend/ with the venv active:

    python scripts/ingest_soil_data.py --dry-run --limit 3
    python scripts/ingest_soil_data.py --field-id 1
    python scripts/ingest_soil_data.py --all

Reads field centroids from ../data/plant_pal_soil_crop_suitability.xlsx (NZTM,
confirmed by that workbook's own "Legend & Assumptions" sheet - see
plantpal_soil_data_scraper_spec.md). This script never modifies the workbook;
it only creates/reuses one Plot row per workbook Field ID (name
"Workbook field {id}", owned by a dedicated "workbook@plantpal.local" user) so
soil_observations has something to key off, then runs the same
refresh_soil_observations() the API's POST /plots/{id}/soil-properties/refresh
uses.

ALWAYS run with --dry-run first against a small --limit to confirm the LRIS
response shape matches app/services/soil_enrichment/lris_client.py's
assumptions before a bulk run (see that module's docstring) - the spec
requires verifying the query pattern before any bulk request, and this
integration has not yet been checked against a live response.
"""

import argparse
import logging
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.db.models import Plot, User
from app.db.session import SessionLocal
from app.services.soil_enrichment.crs import nztm_to_lonlat
from app.services.soil_enrichment.pipeline import refresh_soil_observations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest_soil_data")

WORKBOOK_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "plant_pal_soil_crop_suitability.xlsx"
WORKBOOK_USER_EMAIL = "workbook@plantpal.local"


def read_workbook_fields() -> list[tuple[int, float, float]]:
    """Returns (field_id, centroid_x_nztm, centroid_y_nztm) for every row."""
    wb = openpyxl.load_workbook(WORKBOOK_PATH, read_only=True, data_only=True)
    ws = wb["Field Suitability"]
    rows = ws.iter_rows(min_row=2, values_only=True)
    return [(int(r[0]), float(r[1]), float(r[2])) for r in rows if r[0] is not None]


def get_or_create_workbook_plot(db, field_id: int, lon: float, lat: float) -> Plot:
    user = db.query(User).filter(User.email == WORKBOOK_USER_EMAIL).one_or_none()
    if user is None:
        user = User(email=WORKBOOK_USER_EMAIL, password_hash="!disabled")
        db.add(user)
        db.commit()
        db.refresh(user)

    name = f"Workbook field {field_id}"
    plot = db.query(Plot).filter(Plot.user_id == user.id, Plot.name == name).one_or_none()
    if plot is None:
        plot = Plot(user_id=user.id, name=name, boundary={"type": "Point", "coordinates": [lon, lat]})
        db.add(plot)
        db.commit()
        db.refresh(plot)
    return plot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--field-id", type=int, help="Ingest a single workbook Field ID")
    parser.add_argument("--all", action="store_true", help="Ingest every workbook row")
    parser.add_argument("--limit", type=int, default=None, help="Cap how many rows --all processes")
    parser.add_argument("--dry-run", action="store_true", help="Query and log, but do not write to the database")
    parser.add_argument("--force", action="store_true", help="Re-query even if a fresh cached value exists")
    args = parser.parse_args()

    if not args.field_id and not args.all:
        parser.error("pass --field-id N or --all")

    settings = get_settings()
    if not settings.lris_api_key and not args.dry_run:
        parser.error(
            "LRIS_API_KEY is not set in backend/.env - see backend/README.md#soil-property-enrichment "
            "for how to get a free key, or pass --dry-run to see what would happen without one"
        )

    fields = read_workbook_fields()
    if args.field_id is not None:
        fields = [f for f in fields if f[0] == args.field_id]
        if not fields:
            parser.error(f"Field ID {args.field_id} not found in {WORKBOOK_PATH.name}")
    elif args.limit:
        fields = fields[: args.limit]

    db = SessionLocal()
    try:
        for field_id, x, y in fields:
            location = nztm_to_lonlat(x, y)
            plot = get_or_create_workbook_plot(db, field_id, location.lon, location.lat)
            summary = refresh_soil_observations(db, plot, settings=settings, force=args.force, dry_run=args.dry_run)
            for result in summary.results:
                logger.info(
                    "field=%s plot_id=%s property=%s -> %s%s",
                    field_id, plot.id, result.property_code, result.status,
                    f" ({result.detail})" if result.detail else "",
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
