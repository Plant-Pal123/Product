"""One-off setup script: creates (or reuses) a real backend Plot row for each
of the 4 demo paddocks in frontend/js/app.js, so the "Live backend" tab
(frontend/js/live.js) can query real farmland locations instead of the single
urban seed plot from sql/seed.sql.

Mirrors the get-or-create pattern in ingest_soil_data.py's
get_or_create_workbook_plot, but keyed by paddock id/name under the existing
demo user (id=1, demo@example.com from seed.sql) rather than a dedicated
workbook user - this is that user's own farm dashboard.

Run once:
    python scripts/ensure_paddock_plots.py

Prints the resulting {paddock_id: plot_id} mapping - copy those ids into the
`plotId` field of each paddock in frontend/js/app.js.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Plot, User
from app.db.session import SessionLocal

DEMO_USER_EMAIL = "demo@example.com"

# Must match frontend/js/app.js's `paddocks` array (id, region, location).
PADDOCKS = [
    ("riverflat-a", "Kōwhai Downs, Nelson", -41.35, 173.05),
    ("riverflat-b", "Ohaupo, Waikato", -37.9319, 175.2536),
    ("terrace-north", "Lincoln, Canterbury", -43.6333, 172.4833),
    ("clay-flat", "Mosgiel, Otago", -45.8795, 170.3419),
]


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_USER_EMAIL).one_or_none()
        if user is None:
            raise SystemExit(
                f"No user {DEMO_USER_EMAIL!r} found - run `psql mango -f sql/seed.sql` first."
            )

        mapping: dict[str, int] = {}
        for paddock_id, region, lat, lon in PADDOCKS:
            plot = db.query(Plot).filter(Plot.user_id == user.id, Plot.name == region).one_or_none()
            if plot is None:
                plot = Plot(user_id=user.id, name=region, boundary={"type": "Point", "coordinates": [lon, lat]})
                db.add(plot)
                db.commit()
                db.refresh(plot)
                print(f"created plot {plot.id} for {paddock_id!r} ({region})")
            else:
                print(f"reusing plot {plot.id} for {paddock_id!r} ({region})")
            mapping[paddock_id] = plot.id

        print()
        print("paddockId -> plotId mapping (copy into frontend/js/app.js):")
        for paddock_id, plot_id in mapping.items():
            print(f"  {paddock_id}: {plot_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
