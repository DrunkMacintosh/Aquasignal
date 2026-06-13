"""Backfill grid_cells.geom_land: each cell polygon clipped to land.

Land = ST_Union of all district boundaries. Cells with no land overlap keep
geom_land = NULL (the risk map then falls back to the raw square, which only
happens for fully offshore cells). Idempotent — re-run after re-seeding
districts or syncing new grid cells:

    python scripts/clip_cells_to_land.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionFactory, engine  # noqa: E402

# ST_CollectionExtract(..., 3) keeps only polygonal pieces (an intersection
# along a shared border can emit stray points/lines); ST_Multi normalises the
# result to MULTIPOLYGON to match the column type.
_CLIP_SQL = text("""
    WITH land AS (SELECT ST_Union(geom) AS geom FROM districts),
    clipped AS (
        SELECT c.id,
               ST_Multi(ST_CollectionExtract(ST_Intersection(c.geom, land.geom), 3)) AS geom_land
        FROM grid_cells c
        CROSS JOIN land
        WHERE ST_Intersects(c.geom, land.geom)
    )
    UPDATE grid_cells g
    SET geom_land = clipped.geom_land
    FROM clipped
    WHERE g.id = clipped.id AND NOT ST_IsEmpty(clipped.geom_land)
""")

_STATS_SQL = text("""
    SELECT COUNT(*) AS total,
           COUNT(geom_land) AS clipped
    FROM grid_cells
""")


async def main() -> None:
    async with SessionFactory() as session:
        await session.execute(text("UPDATE grid_cells SET geom_land = NULL"))
        result = await session.execute(_CLIP_SQL)
        await session.commit()
        stats = (await session.execute(_STATS_SQL)).one()
        print(
            f"Clipped {result.rowcount} cell(s); "
            f"{stats.clipped}/{stats.total} now carry a land geometry "
            f"({stats.total - stats.clipped} fully offshore)."
        )
    await engine.dispose()


asyncio.run(main())
