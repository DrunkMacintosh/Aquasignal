"""Observed risk history as JSON: per cell and area-weighted per district.

Replaces the dashboard's workaround of parsing the CSV export for its
sparklines. Returns the full observed record (bounded by HISTORY_WINDOW_MONTHS)
up to the latest scored month; the dashboard widens its axis to span whatever
comes back.
"""

from datetime import date

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db import GridCell
from core.queries import (
    cell_history,
    district_exists,
    district_history,
    latest_observed_month,
)
from core.ratelimit import READ_RATE_LIMIT, limiter
from core.scoring import HISTORY_WINDOW_MONTHS, risk_level
from models.schemas import CellHistoryResponse, DistrictHistoryResponse, HistoryPoint

router = APIRouter(prefix="/history", tags=["history"])


async def _history_cutoff(db: AsyncSession) -> date | None:
    latest = await latest_observed_month(db)
    if latest is None:
        return None
    return latest - relativedelta(months=HISTORY_WINDOW_MONTHS - 1)


def _points(rows) -> list[HistoryPoint]:
    return [
        HistoryPoint(
            month=row.month.strftime("%Y-%m"),
            risk=round(row.risk, 2),
            risk_level=risk_level(row.risk),
        )
        for row in rows
    ]


@router.get(
    "/district/{district_name}",
    response_model=DistrictHistoryResponse,
    summary="Observed district risk history (area-weighted)",
    description=(
        "Monthly area-weighted mean risk for the named district across its full "
        f"observed record (up to {HISTORY_WINDOW_MONTHS} months), ascending."
    ),
)
@limiter.limit(READ_RATE_LIMIT)
async def get_district_history(
    request: Request,  # required by slowapi to key the client IP
    district_name: str = Path(description="District name as stored in `districts`."),
    db: AsyncSession = Depends(get_db),
) -> DistrictHistoryResponse:
    if not await district_exists(db, district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {district_name}"
        )
    cutoff = await _history_cutoff(db)
    rows = [] if cutoff is None else await district_history(db, district_name, cutoff)
    return DistrictHistoryResponse(district_name=district_name, history=_points(rows))


@router.get(
    "/{cell_id}",
    response_model=CellHistoryResponse,
    summary="Observed risk history for one grid cell",
    description=(
        "Monthly observed risk for the given cell code across its full observed "
        f"record (up to {HISTORY_WINDOW_MONTHS} months), ascending."
    ),
)
@limiter.limit(READ_RATE_LIMIT)
async def get_cell_history(
    request: Request,  # required by slowapi to key the client IP
    cell_id: str = Path(description="Cell code '<lat>_<lon>', e.g. '10.125_105.625'."),
    db: AsyncSession = Depends(get_db),
) -> CellHistoryResponse:
    cutoff = await _history_cutoff(db)
    rows = [] if cutoff is None else await cell_history(db, cell_id, cutoff)
    if not rows:
        # Distinguish "unknown cell" from "known cell, no scores yet".
        exists = (
            await db.execute(select(GridCell.id).where(GridCell.cell_code == cell_id))
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"Unknown grid cell: {cell_id}"
            )
    return CellHistoryResponse(cell_id=cell_id, history=_points(rows))
