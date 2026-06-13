"""AquaSignal backend API entrypoint.

Run locally:
    uvicorn app:app --reload --port 8000

Public endpoints: /auth/login, /health, /docs. Everything else requires a
JWT bearer token; POST /alerts/trigger requires the internal cron token.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from core.config import get_settings
from core.database import SessionFactory, engine
from core.ratelimit import limiter
from core.security import get_current_user
from models.schemas import HealthResponse
from routers import alerts, auth, export, forecast, history, risk, satellite

LOG = logging.getLogger("aquasignal.api")

_OPENAPI_DESCRIPTION = """
Groundwater risk forecasting API for water-authority staff and field officers.

* **Risk map** -- current well-failure risk (0-100) for every 0.25-degree grid
  cell as GeoJSON, with risk bands and 3-month trends.
* **Forecast** -- 6-month LSTM-ensemble outlooks per cell or aggregated
  (area-weighted) per district.
* **Alerts** -- FCM push subscriptions with per-district thresholds, history,
  and acknowledgement.
* **Export** -- CSV time series and PDF district reports.

Authenticate via `POST /auth/login`, then send `Authorization: Bearer <token>`.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Settings are validated here (fail fast on missing secrets); the DB check
    # is advisory only -- /health keeps reporting status if the DB comes up later.
    get_settings()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        LOG.info("Database reachable")
    except Exception:  # noqa: BLE001 -- startup should not hard-fail on a DB blip
        LOG.exception("Database not reachable at startup; /health will report it")
    yield
    await engine.dispose()


app = FastAPI(
    title="AquaSignal API",
    version="1.0.0",
    description=_OPENAPI_DESCRIPTION,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Public router (login is its own rate-limited gate).
app.include_router(auth.router)
# JWT-protected routers. alerts wires its guards per-endpoint because
# /alerts/trigger authenticates with the internal token instead of a JWT.
app.include_router(risk.router, dependencies=[Depends(get_current_user)])
app.include_router(forecast.router, dependencies=[Depends(get_current_user)])
app.include_router(history.router, dependencies=[Depends(get_current_user)])
app.include_router(satellite.router, dependencies=[Depends(get_current_user)])
app.include_router(export.router, dependencies=[Depends(get_current_user)])
app.include_router(alerts.router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Service health",
    description=(
        "Liveness/readiness probe: database connectivity, presence of both ML "
        "artifacts on disk, and the timestamp of the last completed scoring "
        "run. Public (no auth) so load balancers can poll it."
    ),
)
async def health() -> HealthResponse:
    db_connected = False
    last_pipeline_run = None
    try:
        async with SessionFactory() as session:
            result = await session.execute(
                text(
                    "SELECT MAX(model_run_at) FROM risk_scores "
                    "WHERE score_type = 'observed'"
                )
            )
            last_pipeline_run = result.scalar()
            db_connected = True
    except Exception:  # noqa: BLE001 -- health must answer even when the DB is down
        LOG.exception("Health check: database unreachable")

    models_loaded = (
        settings.downscaler_path.exists() and settings.forecaster_path.exists()
    )
    return HealthResponse(
        status="ok" if (db_connected and models_loaded) else "degraded",
        db_connected=db_connected,
        models_loaded=models_loaded,
        last_pipeline_run=last_pipeline_run,
    )
