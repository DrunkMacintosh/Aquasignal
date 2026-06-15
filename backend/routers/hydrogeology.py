"""Per-district hydrogeology: soil permeability and a derived recharge readout.

Permeability is a *static* per-cell covariate -- saturated hydraulic
conductivity sampled from soil data and normalised to a 0-1 index
(static_features.py), backfilled onto grid_cells. It is area-weighted to the
district with the same overlap weights the risk score uses, so the soil context
shown beside a district's risk comes from exactly the same cells.

Recharge potential is derived at serve time by combining that permeability with
the district's latest water balance (precipitation - evapotranspiration), read
from the same parquet store as the satellite observations. The recharge figure
is a RELATIVE indicator, not a calibrated mm/month rate (see core/recharge.py).
pandas work runs in a worker thread.
"""

from functools import partial

import anyio
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.queries import (
    district_centroid_weights,
    district_exists,
    district_permeability,
)
from core.ratelimit import READ_RATE_LIMIT, limiter
from core.recharge import permeability_class, recharge_index, recharge_label
from core.satellite import available_months, weighted_series
from models.schemas import DistrictPermeabilityResponse

router = APIRouter(prefix="/hydrogeology", tags=["hydrogeology"])


def _latest_water_balance(
    weights: list[tuple[float, float, float]],
) -> tuple[str | None, float | None, float | None]:
    """(latest month, area-weighted precip, area-weighted ET) from the parquet
    store. Runs in a worker thread -- pandas IO must not block the event loop."""
    months = available_months()
    if not months:
        return None, None, None
    latest = months[-1]
    row = weighted_series(weights, [latest])[0]
    return latest, row["precipitation"], row["evapotranspiration"]


@router.get(
    "/district/{district_name}",
    response_model=DistrictPermeabilityResponse,
    summary="Soil permeability and recharge potential per district",
    description=(
        "Area-weighted soil permeability (saturated hydraulic conductivity, "
        "normalised 0-1) for the named district, plus a derived recharge "
        "indicator: permeability x the latest month's net infiltration "
        "(precipitation - evapotranspiration). Recharge is a RELATIVE ranking "
        "indicator, not a calibrated mm/month rate. `has_data` is false for "
        "units with no soil-bearing cells (e.g. all-ocean island provinces)."
    ),
)
@limiter.limit(READ_RATE_LIMIT)
async def get_district_permeability(
    request: Request,  # required by slowapi to key the client IP
    district_name: str = Path(description="District name as stored in `districts`."),
    db: AsyncSession = Depends(get_db),
) -> DistrictPermeabilityResponse:
    if not await district_exists(db, district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {district_name}"
        )

    perm_index, ksat = await district_permeability(db, district_name)
    if perm_index is None:
        return DistrictPermeabilityResponse(district_name=district_name, has_data=False)

    weights = await district_centroid_weights(db, district_name)
    month, precip, et = await anyio.to_thread.run_sync(
        partial(_latest_water_balance, weights)
    )

    net_infiltration_mm = recharge_value = recharge_lbl = None
    if precip is not None and et is not None:
        net_infiltration_mm = max(precip - et, 0.0)
        recharge_value = recharge_index(perm_index, precip, et)
        recharge_lbl = recharge_label(recharge_value)
    else:
        month = None  # no water balance -> no month to attribute recharge to

    return DistrictPermeabilityResponse(
        district_name=district_name,
        has_data=True,
        permeability_index=round(perm_index, 4),
        soil_ksat_mm_hr=round(ksat, 2),
        permeability_class=permeability_class(perm_index),
        month=month,
        net_infiltration_mm=(
            round(net_infiltration_mm, 1) if net_infiltration_mm is not None else None
        ),
        recharge_value=(
            round(recharge_value, 1) if recharge_value is not None else None
        ),
        recharge_label=recharge_lbl,
    )
