"""Backfill grid_cells soil permeability from the static feature store.

Reads ``data/processed/static_features.parquet`` (produced by
static_features.py) and copies its ``permeability_index`` / ``soil_ksat_mm_hr``
columns onto grid_cells, matching on cell code ("<lat>_<lon>"). Cells absent
from the parquet, or with no soil value, are left NULL. Idempotent -- columns
are reset first, then rewritten -- so re-run after regenerating static features
or syncing new grid cells:

    python scripts/load_permeability.py
"""

import asyncio
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.config import get_settings  # noqa: E402
from core.database import SessionFactory, engine  # noqa: E402

_SOIL_COLUMNS = ["permeability_index", "soil_ksat_mm_hr"]

_RESET_SQL = text(
    "UPDATE grid_cells SET permeability_index = NULL, soil_ksat_mm_hr = NULL"
)

_UPDATE_SQL = text("""
    UPDATE grid_cells
    SET permeability_index = :permeability_index,
        soil_ksat_mm_hr = :soil_ksat_mm_hr
    WHERE cell_code = :cell_code
""")

_STATS_SQL = text("""
    SELECT COUNT(*) AS total, COUNT(permeability_index) AS with_soil
    FROM grid_cells
""")


def _load_records() -> list[dict]:
    """Read the static parquet into UPDATE param dicts (NaN -> None)."""
    path = get_settings().processed_data_dir / "static_features.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing -- run 'python static_features.py' first"
        )
    df = pd.read_parquet(path)
    missing = [c for c in _SOIL_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(
            f"static_features.parquet lacks {missing}; re-run static_features.py "
            "to add the soil permeability columns"
        )
    return [
        {
            "cell_code": row.cell_id,
            "permeability_index": (
                None if pd.isna(row.permeability_index) else float(row.permeability_index)
            ),
            "soil_ksat_mm_hr": (
                None if pd.isna(row.soil_ksat_mm_hr) else float(row.soil_ksat_mm_hr)
            ),
        }
        for row in df.itertuples(index=False)
    ]


async def main() -> None:
    records = _load_records()
    async with SessionFactory() as session:
        await session.execute(_RESET_SQL)
        # asyncpg executemany returns rowcount -1, so the stats query below is
        # the source of truth for how many cells actually took a value.
        await session.execute(_UPDATE_SQL, records)
        await session.commit()
        stats = (await session.execute(_STATS_SQL)).one()
    await engine.dispose()
    print(
        f"Loaded soil data from {len(records)} parquet row(s); "
        f"{stats.with_soil}/{stats.total} cells now carry a permeability value "
        f"({stats.total - stats.with_soil} without soil data)."
    )


asyncio.run(main())
