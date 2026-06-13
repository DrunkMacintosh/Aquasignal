"""Shared PostGIS queries used by multiple routers.

District membership is resolved spatially: a cell belongs to a district when
``ST_Intersects(cell.geom, district.geom)`` -- never by a Python-side filter.
Aggregates are weighted by the *overlap* area,
``ST_Area(ST_Intersection(...)::geography)`` (geography cast => square
metres), so a cell straddling a district boundary contributes proportionally
to how much of it lies inside.

All statements are parameterized ``text()`` constructs: the analytic SQL here
(CTE-style subqueries, spatial functions, weighted aggregates) is clearer as
SQL than as ORM expression trees, and bound parameters keep it injection-safe.
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

# Cells overlapping the named district, with their overlap area as weight.
_DISTRICT_WEIGHTS_SQL = """
    SELECT c.id AS cell_id,
           c.cell_code AS cell_code,
           ST_Area(ST_Intersection(c.geom, d.geom)::geography) AS weight
    FROM grid_cells c
    JOIN districts d
      ON d.name = :district
     AND ST_Intersects(c.geom, d.geom)
"""

_DISTRICT_EXISTS = text("SELECT 1 FROM districts WHERE name = :district")

_LATEST_OBSERVED_MONTH = text(
    "SELECT MAX(month) FROM risk_scores WHERE score_type = 'observed'"
)

_DISTRICT_CELL_COUNT = text(f"SELECT COUNT(*) FROM ({_DISTRICT_WEIGHTS_SQL}) w")

_DISTRICT_CURRENT_RISK = text(f"""
    SELECT SUM(rs.risk * w.weight) / NULLIF(SUM(w.weight), 0) AS risk
    FROM ({_DISTRICT_WEIGHTS_SQL}) w
    JOIN risk_scores rs ON rs.cell_id = w.cell_id
    WHERE rs.score_type = 'observed' AND rs.month = :month
""")

# NOTE: weighted means of ci_low/ci_high approximate the aggregate interval;
# exact district-level CIs would need the cells' error covariance. COALESCE
# falls back to the point estimate for rows missing a CI -- one NULL term
# would otherwise null the entire SUM for that month.
_DISTRICT_FORECAST = text(f"""
    SELECT rs.month AS month,
           SUM(rs.risk * w.weight) / NULLIF(SUM(w.weight), 0) AS predicted_risk,
           SUM(COALESCE(rs.ci_low, rs.risk) * w.weight)
             / NULLIF(SUM(w.weight), 0) AS ci_low,
           SUM(COALESCE(rs.ci_high, rs.risk) * w.weight)
             / NULLIF(SUM(w.weight), 0) AS ci_high
    FROM ({_DISTRICT_WEIGHTS_SQL}) w
    JOIN risk_scores rs ON rs.cell_id = w.cell_id
    WHERE rs.score_type = 'forecast' AND rs.month > :after_month
    GROUP BY rs.month
    ORDER BY rs.month
    LIMIT :limit
""")

_ALL_DISTRICTS_CURRENT_RISK = text("""
    SELECT d.name AS district_name,
           SUM(rs.risk * ST_Area(ST_Intersection(c.geom, d.geom)::geography))
             / NULLIF(SUM(ST_Area(ST_Intersection(c.geom, d.geom)::geography)), 0)
             AS risk
    FROM districts d
    JOIN grid_cells c ON ST_Intersects(c.geom, d.geom)
    JOIN risk_scores rs
      ON rs.cell_id = c.id
     AND rs.score_type = 'observed'
     AND rs.month = :month
    GROUP BY d.name
""")

_CELL_HISTORY = text("""
    SELECT rs.month AS month, rs.risk AS risk
    FROM risk_scores rs
    JOIN grid_cells c ON c.id = rs.cell_id
    WHERE c.cell_code = :cell_code
      AND rs.score_type = 'observed'
      AND rs.month >= :cutoff
    ORDER BY rs.month
""")

_DISTRICT_HISTORY = text(f"""
    SELECT rs.month AS month,
           SUM(rs.risk * w.weight) / NULLIF(SUM(w.weight), 0) AS risk
    FROM ({_DISTRICT_WEIGHTS_SQL}) w
    JOIN risk_scores rs ON rs.cell_id = w.cell_id
    WHERE rs.score_type = 'observed' AND rs.month >= :cutoff
    GROUP BY rs.month
    ORDER BY rs.month
""")

# Overlap weights with centroids, for joining against the satellite parquets
# (which are keyed by cell centroid lat/lon).
_DISTRICT_CENTROID_WEIGHTS = text(f"""
    SELECT gc.centroid_lat AS centroid_lat,
           gc.centroid_lon AS centroid_lon,
           w.weight AS weight
    FROM ({_DISTRICT_WEIGHTS_SQL}) w
    JOIN grid_cells gc ON gc.id = w.cell_id
""")

_DISTRICT_TOP_CELLS = text(f"""
    SELECT w.cell_code AS cell_code,
           gc.centroid_lat AS centroid_lat,
           gc.centroid_lon AS centroid_lon,
           rs.risk AS risk
    FROM ({_DISTRICT_WEIGHTS_SQL}) w
    JOIN grid_cells gc ON gc.id = w.cell_id
    JOIN risk_scores rs
      ON rs.cell_id = w.cell_id
     AND rs.score_type = 'observed'
     AND rs.month = :month
    ORDER BY rs.risk DESC
    LIMIT :limit
""")


async def district_exists(db: AsyncSession, district: str) -> bool:
    result = await db.execute(_DISTRICT_EXISTS, {"district": district})
    return result.scalar() is not None


async def latest_observed_month(db: AsyncSession) -> date | None:
    """The 'current month' everywhere in the API: the newest scored month.

    Anchoring to the data (not the wall clock) keeps the API correct when the
    cron is late or data sources lag (GRACE publishes ~60 days behind).
    """
    return (await db.execute(_LATEST_OBSERVED_MONTH)).scalar()


async def district_cell_count(db: AsyncSession, district: str) -> int:
    result = await db.execute(_DISTRICT_CELL_COUNT, {"district": district})
    return int(result.scalar() or 0)


async def district_current_risk(
    db: AsyncSession, district: str, month: date
) -> float | None:
    result = await db.execute(
        _DISTRICT_CURRENT_RISK, {"district": district, "month": month}
    )
    value = result.scalar()
    return float(value) if value is not None else None


async def district_forecast(
    db: AsyncSession, district: str, after_month: date, limit: int
) -> list[Row[Any]]:
    result = await db.execute(
        _DISTRICT_FORECAST,
        {"district": district, "after_month": after_month, "limit": limit},
    )
    return list(result.all())


async def all_districts_current_risk(
    db: AsyncSession, month: date
) -> dict[str, float]:
    result = await db.execute(_ALL_DISTRICTS_CURRENT_RISK, {"month": month})
    return {row.district_name: float(row.risk) for row in result if row.risk is not None}


async def cell_history(
    db: AsyncSession, cell_code: str, cutoff: date
) -> list[Row[Any]]:
    result = await db.execute(_CELL_HISTORY, {"cell_code": cell_code, "cutoff": cutoff})
    return list(result.all())


async def district_history(
    db: AsyncSession, district: str, cutoff: date
) -> list[Row[Any]]:
    result = await db.execute(
        _DISTRICT_HISTORY, {"district": district, "cutoff": cutoff}
    )
    return list(result.all())


async def district_centroid_weights(
    db: AsyncSession, district: str
) -> list[tuple[float, float, float]]:
    result = await db.execute(_DISTRICT_CENTROID_WEIGHTS, {"district": district})
    return [
        (float(row.centroid_lat), float(row.centroid_lon), float(row.weight))
        for row in result
    ]


async def district_top_cells(
    db: AsyncSession, district: str, month: date, limit: int
) -> list[Row[Any]]:
    result = await db.execute(
        _DISTRICT_TOP_CELLS, {"district": district, "month": month, "limit": limit}
    )
    return list(result.all())
