"""Risk map endpoint: current scores for every grid cell as GeoJSON."""

import json

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.queries import latest_observed_month
from core.ratelimit import RISK_MAP_RATE_LIMIT, limiter
from core.scoring import TREND_WINDOW_MONTHS, risk_level, trend_label
from models.schemas import (
    CellRiskProperties,
    PolygonGeometry,
    RiskFeature,
    RiskMapResponse,
)

router = APIRouter(tags=["risk-map"])

# Single round-trip: current score, score 3 months back (for trend), and the
# cell polygon. The bbox filter is applied by PostGIS against the GIST index
# (ST_Intersects with ST_MakeEnvelope) -- never in Python.
_RISK_MAP_SQL = text("""
    SELECT c.cell_code AS cell_code,
           c.centroid_lat AS centroid_lat,
           c.centroid_lon AS centroid_lon,
           ST_AsGeoJSON(c.geom) AS geometry_json,
           cur.risk AS current_risk,
           prior.risk AS prior_risk
    FROM grid_cells c
    JOIN risk_scores cur
      ON cur.cell_id = c.id
     AND cur.score_type = 'observed'
     AND cur.month = :current_month
    LEFT JOIN risk_scores prior
      ON prior.cell_id = c.id
     AND prior.score_type = 'observed'
     AND prior.month = :prior_month
    WHERE :use_bbox = FALSE
       OR ST_Intersects(
              c.geom, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
          )
    ORDER BY c.cell_code
""")


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    """Validate 'minLon,minLat,maxLon,maxLat'; reject inverted or out-of-range."""
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox must be 'minLon,minLat,maxLon,maxLat'",
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bbox values must be numbers"
        ) from exc
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox out of range or min >= max",
        )
    return min_lon, min_lat, max_lon, max_lat


@router.get(
    "/risk-map",
    response_model=RiskMapResponse,
    summary="Current risk for all grid cells (GeoJSON)",
    description=(
        "Returns a GeoJSON FeatureCollection of every 0.25-degree grid cell with "
        "the current month's well-failure risk (0-100), a banded `risk_level` "
        "(thresholds 25/50/75), and a 3-month `trend`. Optional `bbox` filters "
        "cells spatially via PostGIS. Rate-limited to 60 requests/minute per IP."
    ),
)
@limiter.limit(RISK_MAP_RATE_LIMIT)
async def get_risk_map(
    request: Request,  # required by slowapi to key the client IP
    bbox: str | None = Query(
        default=None,
        description="Spatial filter 'minLon,minLat,maxLon,maxLat' (EPSG:4326).",
        examples=["104.5,8.5,107.0,11.0"],
    ),
    db: AsyncSession = Depends(get_db),
) -> RiskMapResponse:
    current_month = await latest_observed_month(db)
    if current_month is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No risk scores available yet -- run the monthly pipeline first.",
        )

    params: dict[str, object] = {
        "current_month": current_month,
        "prior_month": current_month - relativedelta(months=TREND_WINDOW_MONTHS),
        "use_bbox": False,
        "min_lon": 0.0,
        "min_lat": 0.0,
        "max_lon": 0.0,
        "max_lat": 0.0,
    }
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = _parse_bbox(bbox)
        params.update(
            use_bbox=True,
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )

    rows = (await db.execute(_RISK_MAP_SQL, params)).all()

    features = [
        RiskFeature(
            geometry=PolygonGeometry(**json.loads(row.geometry_json)),
            properties=CellRiskProperties(
                cell_id=row.cell_code,
                centroid_lat=row.centroid_lat,
                centroid_lon=row.centroid_lon,
                current_risk=round(row.current_risk, 2),
                risk_level=risk_level(row.current_risk),
                trend=trend_label(row.current_risk, row.prior_risk),
            ),
        )
        for row in rows
    ]
    return RiskMapResponse(month=current_month.strftime("%Y-%m"), features=features)
