"""Fetch static per-cell covariates for the AquaSignal downscaler.

Produces ``data/processed/static_features.parquet`` with one row per grid
cell: elevation_m and slope_deg sampled from SRTM via Google Earth Engine,
plus dist_coast_km computed locally from the dataset's own ocean mask.

These replace raw lat/lon in the transferable feature set: a model that
learns "low, flat, coastal cells are stressed" can generalise to a region
it has never seen; one that learns coordinates cannot.

SRTM (USGS/SRTMGL1_003) is a single ee.Image, so ee.Terrain.slope works
directly -- no composite default-projection pitfalls.

Run: python static_features.py   (requires GEE_PROJECT / EE credentials)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

from pipeline import (
    VIETNAM_BBOX,
    build_grid_points,
    build_target_grid,
    features_to_grid_arrays,
    init_earth_engine,
    sample_image_at_grid,
)

PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "static_features.parquet"
EARTH_RADIUS_KM = 6371.0

# Soil permeability. Sand fraction comes from OpenLandMap (official GEE catalog,
# always accessible); saturated hydraulic conductivity is estimated with the
# Cosby et al. (1984) univariate sand pedotransfer used in Noah/CLM land models:
#     Ksat[mm/s] = 0.0070556 * 10^(-0.884 + 0.0153 * sand%)
# then converted to mm/hour. permeability_index is that Ksat log-normalised to
# [0, 1] against physically plausible bounds, so it is a transferable covariate
# regardless of absolute calibration. (If a direct Ksat layer such as
# HiHydroSoil is confirmed accessible, swap SAND_ASSET sampling for it -- the
# normalisation below still applies.)
OPENLANDMAP_SAND_ASSET = "OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02"
OPENLANDMAP_SAND_BAND = "b0"  # surface (0 cm), percent sand by weight
COSBY_KSAT_INTERCEPT = -0.884
COSBY_KSAT_SAND_COEF = 0.0153
COSBY_KSAT_SCALE_MM_S = 0.0070556
SECONDS_PER_HOUR = 3600.0
PERMEABILITY_KSAT_MIN_MM_HR = 0.1     # ~heavy clay floor
PERMEABILITY_KSAT_MAX_MM_HR = 1000.0  # ~gravel/sand ceiling

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=sys.stdout,
)
LOG = logging.getLogger("aquasignal.static")


def fetch_terrain(grid) -> pd.DataFrame:
    """Sample SRTM elevation and slope at every grid centroid via GEE."""
    init_earth_engine()
    srtm = ee.Image("USGS/SRTMGL1_003")
    image = srtm.select("elevation").addBands(ee.Terrain.slope(srtm).rename("slope"))
    points = build_grid_points(grid)
    features = sample_image_at_grid(image, points, ["elevation", "slope"])
    arrays = features_to_grid_arrays(features, ["elevation", "slope"], grid)

    lats = np.repeat(grid.lats, len(grid.lons))
    lons = np.tile(grid.lons, len(grid.lats))
    return pd.DataFrame(
        {
            "cell_id": [f"{la:.3f}_{lo:.3f}" for la, lo in zip(lats, lons)],
            "lat": lats,
            "lon": lons,
            "elevation_m": arrays["elevation"].ravel(),
            "slope_deg": arrays["slope"].ravel(),
        }
    )


def cosby_ksat_mm_hr(sand_pct: np.ndarray) -> np.ndarray:
    """Cosby (1984) univariate sand -> saturated hydraulic conductivity (mm/hr).

    NaN sand (masked / ocean cells) propagates to NaN Ksat.
    """
    ksat_mm_s = COSBY_KSAT_SCALE_MM_S * 10.0 ** (
        COSBY_KSAT_INTERCEPT + COSBY_KSAT_SAND_COEF * sand_pct
    )
    return ksat_mm_s * SECONDS_PER_HOUR


def permeability_index_from_ksat(ksat_mm_hr: np.ndarray) -> np.ndarray:
    """Log-normalise Ksat to a [0, 1] permeability index, clamped at the bounds.

    NaN Ksat stays NaN so downstream consumers treat the cell as 'no soil data'.
    """
    lo = np.log10(PERMEABILITY_KSAT_MIN_MM_HR)
    hi = np.log10(PERMEABILITY_KSAT_MAX_MM_HR)
    with np.errstate(divide="ignore", invalid="ignore"):
        index = (np.log10(ksat_mm_hr) - lo) / (hi - lo)
    return np.clip(index, 0.0, 1.0)


def fetch_soil(grid) -> pd.DataFrame:
    """Sample OpenLandMap sand at every grid centroid and derive permeability."""
    init_earth_engine()
    sand = ee.Image(OPENLANDMAP_SAND_ASSET).select(OPENLANDMAP_SAND_BAND).rename("sand")
    points = build_grid_points(grid)
    features = sample_image_at_grid(sand, points, ["sand"])
    sand_pct = features_to_grid_arrays(features, ["sand"], grid)["sand"].ravel()

    ksat = cosby_ksat_mm_hr(sand_pct)
    lats = np.repeat(grid.lats, len(grid.lons))
    lons = np.tile(grid.lons, len(grid.lats))
    return pd.DataFrame(
        {
            "cell_id": [f"{la:.3f}_{lo:.3f}" for la, lo in zip(lats, lons)],
            "soil_ksat_mm_hr": ksat,
            "permeability_index": permeability_index_from_ksat(ksat),
        }
    )


def haversine_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Great-circle distance in km between two coordinate arrays (broadcasting)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def compute_dist_coast(static: pd.DataFrame) -> pd.Series:
    """Distance from each cell to the nearest ocean cell of the dataset grid.

    The ocean mask comes from the dataset itself: cells with NaN ERA5-Land
    values in any monthly partition are sea. Approximation note: only coast
    inside the bounding box is seen, which covers Vietnam's entire coastline.
    """
    sample = sorted(PROCESSED_DIR.glob("aquasignal_*.parquet"))[0]
    month = pd.read_parquet(sample)
    ocean = month[month["precipitation"].isna()][["lat", "lon"]]
    if ocean.empty:
        LOG.warning("No ocean cells in %s; dist_coast_km set to NaN", sample.name)
        return pd.Series(np.nan, index=static.index)
    dists = haversine_km(
        static["lat"].to_numpy()[:, None], static["lon"].to_numpy()[:, None],
        ocean["lat"].to_numpy()[None, :], ocean["lon"].to_numpy()[None, :],
    )
    LOG.info("Distance-to-coast computed against %d ocean cells", len(ocean))
    return pd.Series(dists.min(axis=1), index=static.index)


def _log_summary(static: pd.DataFrame) -> None:
    """Log the persisted covariate ranges (one place for both build paths)."""
    LOG.info(
        "Wrote %s (%d cells; elevation %.0f..%.0f m, slope max %.1f deg, "
        "coast dist max %.0f km, Ksat %.1f..%.1f mm/hr, permeability %.2f..%.2f)",
        OUTPUT_PATH.name, len(static),
        np.nanmin(static["elevation_m"]), np.nanmax(static["elevation_m"]),
        np.nanmax(static["slope_deg"]), np.nanmax(static["dist_coast_km"]),
        np.nanmin(static["soil_ksat_mm_hr"]), np.nanmax(static["soil_ksat_mm_hr"]),
        np.nanmin(static["permeability_index"]), np.nanmax(static["permeability_index"]),
    )


def main() -> None:
    """Build and persist the static covariate table (idempotent).

    Adds the soil permeability columns in place to a terrain-only parquet from
    an earlier run, so the upgrade does not require a full re-fetch of SRTM.
    """
    grid = build_target_grid(VIETNAM_BBOX)

    if OUTPUT_PATH.exists():
        existing = pd.read_parquet(OUTPUT_PATH)
        if "permeability_index" in existing.columns:
            LOG.info("Static features already complete, skipping: %s", OUTPUT_PATH.name)
            return
        LOG.info("Augmenting existing static features with soil permeability")
        merged = existing.merge(fetch_soil(grid), on="cell_id", how="left")
        merged.to_parquet(OUTPUT_PATH, engine="pyarrow", index=False)
        _log_summary(merged)
        return

    static = fetch_terrain(grid)
    static["dist_coast_km"] = compute_dist_coast(static)
    static = static.merge(fetch_soil(grid), on="cell_id", how="left")
    static.to_parquet(OUTPUT_PATH, engine="pyarrow", index=False)
    _log_summary(static)


if __name__ == "__main__":
    main()
