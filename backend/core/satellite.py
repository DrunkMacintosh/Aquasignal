"""Read-only access to the pipeline's processed satellite parquet store.

The monthly parquets under ``data/processed`` (written by pipeline.py) are the
canonical record of the raw satellite observations; the database only holds
model *outputs* (risk_scores). The API therefore reads the parquets directly
instead of duplicating them into Postgres — one source of truth, and a new
pipeline month is served with no extra sync step.

All functions here are synchronous and pandas-bound: call them from routers
via ``anyio.to_thread.run_sync`` so parquet IO never blocks the event loop.
Frames are memoised per (path, mtime), so a re-written month invalidates
itself and the whole 136-month store tops out around ~10 MB of cache.
"""

import math
from functools import lru_cache

import pandas as pd

from core.config import get_settings

SATELLITE_VARIABLES = [
    "grace_anomaly",
    "sar_subsidence",
    "precipitation",
    "evapotranspiration",
    "temperature",
]

_COORD_TOLERANCE_DEG = 1e-6  # grid centroids are exact binary fractions; belt & braces
# Merge keys are rounded so a 1-ULP drift between Postgres float8 and parquet
# float64 can never silently null out a whole district's observations.
# 6 decimals ≈ 0.1 m — far below the 0.25° grid spacing, far above float noise.
_MERGE_DECIMALS = 6


@lru_cache(maxsize=200)
def _load_month(path_str: str, _mtime_ns: int) -> pd.DataFrame:
    return pd.read_parquet(path_str, columns=["lat", "lon", *SATELLITE_VARIABLES])


def _month_frame(month: str) -> pd.DataFrame | None:
    path = get_settings().processed_data_dir / f"aquasignal_{month}.parquet"
    if not path.exists():
        return None
    return _load_month(str(path), path.stat().st_mtime_ns)


def available_months() -> list[str]:
    """Month labels ('YYYY-MM') present in the store, ascending."""
    data_dir = get_settings().processed_data_dir
    return sorted(
        path.stem.removeprefix("aquasignal_")
        for path in data_dir.glob("aquasignal_????-??.parquet")
    )


def _clean(value: object) -> float | None:
    """NaN/inf -> None so Pydantic emits JSON null, not an invalid float."""
    number = float(value)  # type: ignore[arg-type]
    return number if math.isfinite(number) else None


def cell_series(lat: float, lon: float, months: list[str]) -> list[dict]:
    """Raw observations for one grid cell, one dict per requested month."""
    series: list[dict] = []
    for month in months:
        frame = _month_frame(month)
        record: dict = {"month": month}
        if frame is None:
            record.update({variable: None for variable in SATELLITE_VARIABLES})
        else:
            match = frame[
                (frame["lat"].sub(lat).abs() < _COORD_TOLERANCE_DEG)
                & (frame["lon"].sub(lon).abs() < _COORD_TOLERANCE_DEG)
            ]
            row = match.iloc[0] if not match.empty else None
            record.update(
                {
                    variable: (None if row is None else _clean(row[variable]))
                    for variable in SATELLITE_VARIABLES
                }
            )
        series.append(record)
    return series


def weighted_series(
    weights: list[tuple[float, float, float]], months: list[str]
) -> list[dict]:
    """Area-weighted district means, one dict per requested month.

    ``weights`` is [(centroid_lat, centroid_lon, weight), ...] — the same
    overlap-area weights the risk aggregation uses. Cells with a missing
    value for a variable drop out of that variable's mean (weights are
    renormalised over the cells that do report).
    """
    weight_frame = pd.DataFrame(weights, columns=["lat", "lon", "weight"])
    weight_frame[["lat", "lon"]] = weight_frame[["lat", "lon"]].round(_MERGE_DECIMALS)
    series: list[dict] = []
    for month in months:
        frame = _month_frame(month)
        record: dict = {"month": month}
        if frame is None or weight_frame.empty:
            record.update({variable: None for variable in SATELLITE_VARIABLES})
            series.append(record)
            continue
        # .assign copies — the lru_cached frame must never be mutated.
        merged = weight_frame.merge(
            frame.assign(
                lat=frame["lat"].round(_MERGE_DECIMALS),
                lon=frame["lon"].round(_MERGE_DECIMALS),
            ),
            on=["lat", "lon"],
            how="left",
        )
        for variable in SATELLITE_VARIABLES:
            valid = merged[variable].notna()
            total_weight = merged.loc[valid, "weight"].sum()
            if total_weight > 0:
                weighted = (merged.loc[valid, variable] * merged.loc[valid, "weight"]).sum()
                record[variable] = _clean(weighted / total_weight)
            else:
                record[variable] = None
        series.append(record)
    return series
