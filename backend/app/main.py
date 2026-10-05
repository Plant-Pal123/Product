from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, plans, plots, preferences, recommendations
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

# Dev-only: the frontend is static files served from its own origin (e.g. a
# local static server on a different port), so the browser needs CORS to allow
# it to call this API. Tighten this to the real frontend origin before deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(plots.router, prefix=settings.api_v1_prefix)
app.include_router(preferences.router, prefix=settings.api_v1_prefix)
app.include_router(recommendations.router, prefix=settings.api_v1_prefix)
app.include_router(plans.router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the presentation UI from the same origin as the API. This keeps the
# public Cloudflare URL stable and avoids mobile browsers having to call a
# second, cross-origin quick tunnel. Only the frontend directory is exposed;
# backend files such as .env remain private.
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"


@app.get("/", include_in_schema=False)
def frontend_root():
    return RedirectResponse(url="/frontend/")


app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")
