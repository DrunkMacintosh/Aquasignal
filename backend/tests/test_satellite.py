"""Pure helpers in core/satellite.py (no parquet store / DB needed)."""

import math

from core.satellite import SATELLITE_VARIABLES, _clean, weighted_series


def test_clean_maps_nan_and_inf_to_none():
    assert _clean(float("nan")) is None
    assert _clean(float("inf")) is None
    assert _clean(28.6) == 28.6
    assert _clean(0.0) == 0.0


def test_clean_handles_numpy_scalars():
    import numpy as np

    assert _clean(np.float64("nan")) is None
    assert _clean(np.float64(4.25)) == 4.25


def test_weighted_series_with_no_store_returns_all_null_months():
    # No parquet files exist for these labels -> every variable is null,
    # but the month skeleton is still returned (math.nan never leaks).
    rows = weighted_series([(10.125, 105.625, 1.0)], ["1999-01", "1999-02"])
    assert [row["month"] for row in rows] == ["1999-01", "1999-02"]
    for row in rows:
        for variable in SATELLITE_VARIABLES:
            assert row[variable] is None
            assert not isinstance(row[variable], float) or math.isfinite(row[variable])
