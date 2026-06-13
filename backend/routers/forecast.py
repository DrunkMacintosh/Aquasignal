"""Forecast endpoints: per-cell and district-aggregated 6-month outlooks.

Forecasts are *precomputed* by monthly_cron.py (LSTM ensemble) and stored in
risk_scores with score_type='forecast'; the API only reads them. Serving
model inference per-request would couple API latency to torch and make
responses non-reproducible between deploys.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.queries import (
    district_cell_count,
    district_exists,
    district_forecast,
    latest_observed_month,
)
from core.ratelimit import READ_RATE_LIMIT, limiter
from core.scoring import FORECAST_HORIZON_MONTHS
from models.db import GridCell, RiskScore, ScoreType
from models.schemas import (
    CellForecastResponse,
    DistrictForecastResponse,
    ForecastPoint,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get(
    "/district/{district_name}",
    response_model=DistrictForecastResponse,
    summary="6-month district forecast (area-weighted)",
    description=(
        "Aggregates cell-level forecasts for the named district. Cells are "
        "selected with ST_Intersects against the district polygon and each "
        "cell's contribution is weighted by its overlap area, so boundary "
        "cells count proportionally."
    ),
)
@limiter.limit(READ_RATE_LIMIT)
async def get_district_forecast(
    request: Request,  # required by slowapi to key the client IP
    district_name: str = Path(description="District name as stored in `districts`."),
    db: AsyncSession = Depends(get_db),
) -> DistrictForecastResponse:
    if not await district_exists(db, district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {district_name}"
        )
    current_month = await latest_observed_month(db)
    if current_month is None:
        return DistrictForecastResponse(
            district_name=district_name, cells_in_district=0, forecast=[]
        )
    rows = await district_forecast(
        db, district_name, after_month=current_month, limit=FORECAST_HORIZON_MONTHS
    )
    cells = await district_cell_count(db, district_name)
    return DistrictForecastResponse(
        district_name=district_name,
        cells_in_district=cells,
        forecast=[
            ForecastPoint(
                month=row.month.strftime("%Y-%m"),
                predicted_risk=round(row.predicted_risk, 2),
                confidence_interval_low=round(row.ci_low, 2),
                confidence_interval_high=round(row.ci_high, 2),
            )
            for row in rows
        ],
    )


@router.get(
    "/{cell_id}",
    response_model=CellForecastResponse,
    summary="6-month forecast for one grid cell",
    description=(
        "Returns the stored LSTM-ensemble forecast for the given cell code "
        "(e.g. `10.125_105.625`): predicted risk plus the 10th/90th-percentile "
        "ensemble spread as a confidence interval, for the 6 months after the "
        "latest observed month."
    ),
)
@limiter.limit(READ_RATE_LIMIT)
async def get_cell_forecast(
    request: Request,  # required by slowapi to key the client IP
    cell_id: str = Path(description="Cell code '<lat>_<lon>', e.g. '10.125_105.625'."),
    db: AsyncSession = Depends(get_db),
) -> CellForecastResponse:
    cell = (
        await db.execute(select(GridCell).where(GridCell.cell_code == cell_id))
    ).scalar_one_or_none()
    if cell is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown grid cell: {cell_id}"
        )

    current_month = await latest_observed_month(db)
    if current_month is None:
        return CellForecastResponse(cell_id=cell_id, generated_at=None, forecast=[])

    result = await db.execute(
        select(RiskScore)
        .where(
            RiskScore.cell_id == cell.id,
            RiskScore.score_type == ScoreType.FORECAST,
            RiskScore.month > current_month,
        )
        .order_by(RiskScore.month)
        .limit(FORECAST_HORIZON_MONTHS)
    )
    scores = result.scalars().all()
    return CellForecastResponse(
        cell_id=cell_id,
        generated_at=scores[0].model_run_at if scores else None,
        forecast=[
            ForecastPoint(
                month=s.month.strftime("%Y-%m"),
                predicted_risk=round(s.risk, 2),
                confidence_interval_low=round(s.ci_low or s.risk, 2),
                confidence_interval_high=round(s.ci_high or s.risk, 2),
            )
            for s in scores
        ],
    )
