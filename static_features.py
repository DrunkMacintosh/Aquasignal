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


def main() -> None:
    """Build and persist the static covariate table (idempotent)."""
    if OUTPUT_PATH.exists():
        LOG.info("Static features already exist, skipping: %s", OUTPUT_PATH.name)
        return
    grid = build_target_grid(VIETNAM_BBOX)
    static = fetch_terrain(grid)
    static["dist_coast_km"] = compute_dist_coast(static)
    static.to_parquet(OUTPUT_PATH, engine="pyarrow", index=False)
    LOG.info(
        "Wrote %s (%d cells; elevation %.0f..%.0f m, slope max %.1f deg, "
        "coast dist max %.0f km)",
        OUTPUT_PATH.name, len(static),
        np.nanmin(static["elevation_m"]), np.nanmax(static["elevation_m"]),
        np.nanmax(static["slope_deg"]), np.nanmax(static["dist_coast_km"]),
    )


if __name__ == "__main__":
    main()
