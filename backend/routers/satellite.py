"""Raw satellite observations: the model's *inputs*, not its risk output.

Served straight from the pipeline's monthly parquet store (see
core/satellite.py). District values use the same overlap-area weights as the
risk aggregation, so the numbers shown beside a district's risk score come
from exactly the same cells. pandas work runs in a worker thread.
"""

from functools import partial

import anyio
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.queries import district_centroid_weights, district_exists
from core.satellite import available_months, cell_series, weighted_series
from models.db import GridCell
from models.schemas import (
    CellSatelliteResponse,
    DistrictSatelliteResponse,
    SatelliteMonth,
)

router = APIRouter(prefix="/satellite", tags=["satellite"])

DEFAULT_MONTHS = 24
MAX_MONTHS = 200  # store currently holds ~136 months

_MONTHS_QUERY = Query(
    default=DEFAULT_MONTHS,
    ge=1,
    le=MAX_MONTHS,
    description="How many most-recent months to return.",
)


def _recent_months(count: int) -> list[str]:
    return available_months()[-count:]


@router.get(
    "/district/{district_name}",
    response_model=DistrictSatelliteResponse,
    summary="Raw satellite observations, area-weighted per district",
    description=(
        "Monthly GRACE water-storage anomaly, Sentinel-1 radar backscatter "
        "(subsidence proxy), precipitation, potential evapotranspiration, and "
        "2 m air temperature for the named district — the raw inputs behind "
        "the risk score, aggregated with the same overlap-area weights. "
        "Values can be null where a sensor has a gap."
    ),
)
async def get_district_satellite(
    district_name: str = Path(description="District name as stored in `districts`."),
    months: int = _MONTHS_QUERY,
    db: AsyncSession = Depends(get_db),
) -> DistrictSatelliteResponse:
    if not await district_exists(db, district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {district_name}"
        )
    weights = await district_centroid_weights(db, district_name)
    rows = await anyio.to_thread.run_sync(
        partial(weighted_series, weights, _recent_months(months))
    )
    return DistrictSatelliteResponse(
        district_name=district_name,
        observations=[SatelliteMonth(**row) for row in rows],
    )


@router.get(
    "/{cell_id}",
    response_model=CellSatelliteResponse,
    summary="Raw satellite observations for one grid cell",
    description=(
        "Monthly satellite observations for the given cell code. Values can "
        "be null where a sensor has a gap (e.g. the GRACE/GRACE-FO bridge)."
    ),
)
async def get_cell_satellite(
    cell_id: str = Path(description="Cell code '<lat>_<lon>', e.g. '10.125_105.625'."),
    months: int = _MONTHS_QUERY,
    db: AsyncSession = Depends(get_db),
) -> CellSatelliteResponse:
    cell = (
        await db.execute(select(GridCell).where(GridCell.cell_code == cell_id))
    ).scalar_one_or_none()
    if cell is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown grid cell: {cell_id}"
        )
    rows = await anyio.to_thread.run_sync(
        partial(cell_series, cell.centroid_lat, cell.centroid_lon, _recent_months(months))
    )
    return CellSatelliteResponse(
        cell_id=cell_id,
        observations=[SatelliteMonth(**row) for row in rows],
    )
