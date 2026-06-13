"""Risk map endpoint: current scores for every grid cell as GeoJSON."""

import json

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.queries import all_districts_current_risk, latest_observed_month
from core.ratelimit import RISK_MAP_RATE_LIMIT, limiter
from core.scoring import TREND_WINDOW_MONTHS, risk_level, trend_label
from models.schemas import (
    CellRiskProperties,
    DistrictRiskFeature,
    DistrictRiskMapResponse,
    DistrictRiskProperties,
    MultiPolygonGeometry,
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
           -- geom_land = the square clipped to the coastline (precomputed by
           -- scripts/clip_cells_to_land.py); raw square as fallback.
           ST_AsGeoJSON(COALESCE(c.geom_land, c.geom)) AS geometry_json,
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
    WHERE (:land_only = FALSE OR c.geom_land IS NOT NULL)
      AND (:use_bbox = FALSE
           OR ST_Intersects(
                  c.geom, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
              ))
    ORDER BY c.cell_code
""")

# Once scripts/clip_cells_to_land.py has run, the grid view shows only cells
# overlapping Vietnamese territory (clipped to the coast/border). Before the
# backfill, every cell falls back to its raw square so the map never blanks.
_HAS_CLIPPED_CELLS_SQL = text(
    "SELECT EXISTS (SELECT 1 FROM grid_cells WHERE geom_land IS NOT NULL)"
)


# District outlines for the choropleth. Geometry is simplified at serve time
# only -- the stored full-resolution polygons keep driving the area-weighted
# aggregations. ~0.005 deg (~500 m) is invisible at province scale but cuts
# the payload substantially.
_DISTRICT_GEOMETRY_SQL = text("""
    SELECT d.name AS name,
           -- ST_Multi: simplification collapses single-part multipolygons to
           -- POLYGON, which would break the MultiPolygon response contract.
           ST_AsGeoJSON(ST_Multi(ST_SimplifyPreserveTopology(d.geom, :tolerance))) AS geometry_json,
           (SELECT COUNT(*) FROM grid_cells c
             WHERE ST_Intersects(c.geom, d.geom)) AS cell_count
    FROM districts d
    ORDER BY d.name
""")

_GEOMETRY_TOLERANCE_DEG = 0.005


def _cell_geometry(geometry_json: str) -> MultiPolygonGeometry | PolygonGeometry:
    """Coast-clipped cells are MultiPolygon; unclipped fallbacks are Polygon."""
    geometry = json.loads(geometry_json)
    if geometry["type"] == "MultiPolygon":
        return MultiPolygonGeometry(**geometry)
    return PolygonGeometry(**geometry)


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
    "/risk-map/districts",
    response_model=DistrictRiskMapResponse,
    summary="Current risk per district (GeoJSON, area-weighted)",
    description=(
        "Returns a GeoJSON FeatureCollection of district boundaries with the "
        "current month's area-weighted well-failure risk (0-100), a banded "
        "`risk_level`, and a 3-month `trend` -- the same aggregation used by "
        "forecasts and PDF reports. Districts without scored cells are "
        "omitted. Geometry is simplified for transfer; aggregation uses the "
        "full-resolution boundaries."
    ),
)
@limiter.limit(RISK_MAP_RATE_LIMIT)
async def get_district_risk_map(
    request: Request,  # required by slowapi to key the client IP
    db: AsyncSession = Depends(get_db),
) -> DistrictRiskMapResponse:
    current_month = await latest_observed_month(db)
    if current_month is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No risk scores available yet -- run the monthly pipeline first.",
        )

    current = await all_districts_current_risk(db, current_month)
    prior = await all_districts_current_risk(
        db, current_month - relativedelta(months=TREND_WINDOW_MONTHS)
    )
    rows = (
        await db.execute(
            _DISTRICT_GEOMETRY_SQL, {"tolerance": _GEOMETRY_TOLERANCE_DEG}
        )
    ).all()

    # Every district is returned — ones without scored cells (e.g. island
    # provinces whose cells are ocean-masked) come back has_data=false so the
    # map can paint them as "no data" instead of leaving holes.
    features = [
        DistrictRiskFeature(
            geometry=MultiPolygonGeometry(**json.loads(row.geometry_json)),
            properties=DistrictRiskProperties(
                district_name=row.name,
                has_data=row.name in current,
                current_risk=(
                    round(current[row.name], 2) if row.name in current else None
                ),
                risk_level=(
                    risk_level(current[row.name]) if row.name in current else None
                ),
                trend=(
                    trend_label(current[row.name], prior.get(row.name))
                    if row.name in current
                    else None
                ),
                cells_in_district=row.cell_count,
            ),
        )
        for row in rows
    ]
    return DistrictRiskMapResponse(
        month=current_month.strftime("%Y-%m"), features=features
    )


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

    land_only = bool((await db.execute(_HAS_CLIPPED_CELLS_SQL)).scalar())
    params: dict[str, object] = {
        "current_month": current_month,
        "prior_month": current_month - relativedelta(months=TREND_WINDOW_MONTHS),
        "land_only": land_only,
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
            geometry=_cell_geometry(row.geometry_json),
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
