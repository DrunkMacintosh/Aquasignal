"""AquaSignal feature and label engineering.

Shared by ``models.py`` (training) and prediction utilities. Loads the
monthly Parquet partitions produced by ``pipeline.py``, engineers the
``well_failure_risk`` target, and assembles the two candidate feature sets
for the spatial downscaler ablation:

* ``FEATURES_BASE``       -- original set including raw lat/lon (location-
  memorising; kept as the ablation baseline).
* ``FEATURES_COVARIATE``  -- transferable set: physical covariates that
  explain *why* a region is stressed (elevation, slope, distance to coast,
  water balance, climatology-relative GRACE) instead of *where* it is.

GRACE/GRACE-FO instrument gap: months between the GRACE decommissioning
(mid-2017) and GRACE-FO science operations (mid-2018) have no anomaly data
beyond the pipeline's 2-month forward-fill. Rows with NaN grace_anomaly are
dropped from the label frame (logged), never imputed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
STATIC_FEATURES_PATH = PROCESSED_DIR / "static_features.parquet"

# (min_lat, max_lat, min_lon, max_lon) -- match pipeline.py PRIORITY_REGIONS.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "mekong_delta": (9.0, 11.0, 104.5, 106.8),
    "red_river_delta": (20.0, 21.5, 105.5, 107.0),
    "central_highlands": (12.0, 15.0, 107.5, 108.5),
}
CV_FOLDS = ["mekong_delta", "red_river_delta", "central_highlands"]

DRY_SEASON_MONTHS = {11, 12, 1, 2, 3, 4}
CLIMATE_STRESS_THRESHOLD_MM = -50.0
SUBSIDENCE_MM_THRESHOLD = 5.0       # used only if true mm/month data arrives
SUBSIDENCE_PROXY_QUANTILE = 0.10    # most-negative decile of VV anomaly
MEKONG_BONUS, RED_RIVER_BONUS, DRY_SEASON_BONUS = 15.0, 10.0, 8.0
SUBSIDENCE_PENALTY, CLIMATE_STRESS_PENALTY = 10.0, 15.0

TARGET = "well_failure_risk"

GEE_VARIABLES = ["sar_subsidence", "precipitation", "evapotranspiration", "temperature"]

FEATURES_BASE = [
    "grace_anomaly", "sar_subsidence", "precipitation",
    "evapotranspiration", "temperature", "lat", "lon",
    "month_sin", "month_cos",
]
FEATURES_COVARIATE = [
    "grace_anomaly", "sar_subsidence", "precipitation",
    "evapotranspiration", "temperature", "month_sin", "month_cos",
    "water_balance", "precip_3m", "grace_rel", "grace_trend",
    "elevation_m", "slope_deg", "dist_coast_km", "permeability_index",
]

LOG = logging.getLogger("aquasignal.features")


def load_dataset(processed_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    """Load all monthly Parquet partitions into one long dataframe.

    Drops ocean cells (NaN in the land-masked GEE variables) and attaches
    ``cell_id`` (matching grid_cells.geojson), ``region`` and ``month``.
    Rows with NaN grace are kept here -- the derived features need the full
    time axis -- and dropped later in :func:`engineer_labels`.
    """
    files = sorted(processed_dir.glob("aquasignal_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No partitions found in {processed_dir}; run pipeline.py first")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    n_raw = len(df)
    df = df.dropna(subset=GEE_VARIABLES).copy()
    df["cell_id"] = df["lat"].map("{:.3f}".format) + "_" + df["lon"].map("{:.3f}".format)
    df["region"] = [assign_region(la, lo) for la, lo in zip(df["lat"], df["lon"])]
    df["month"] = pd.to_datetime(df["time"]).dt.month
    df = df.sort_values(["cell_id", "time"]).reset_index(drop=True)
    LOG.info(
        "Loaded %d land rows (%d ocean/no-SAR rows dropped) from %d months, %d cells",
        len(df), n_raw - len(df), len(files), df["cell_id"].nunique(),
    )
    return df


def assign_region(lat: float, lon: float) -> str:
    """Classify a cell centroid into one of Vietnam's hydrological zones."""
    for name, (la0, la1, lo0, lo1) in REGIONS.items():
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return name
    return "other"


def subsidence_penalty_mask(df: pd.DataFrame) -> pd.Series:
    """Boolean mask of cell-months receiving the +10 subsidence penalty.

    With true displacement data (mm/month, positive median) the spec rule
    ``> 5 mm/month`` applies directly. With the current VV-backscatter proxy
    (dB), the penalty goes to the most negative decile of per-cell
    backscatter anomaly -- the best GRD-era stand-in for deformation.
    """
    sar = df["sar_subsidence"]
    if sar.median() > 0:
        LOG.info("Subsidence column looks like mm/month; applying > %.1f mm rule",
                 SUBSIDENCE_MM_THRESHOLD)
        return sar > SUBSIDENCE_MM_THRESHOLD
    anomaly = sar - sar.groupby(df["cell_id"]).transform("mean")
    threshold = anomaly.quantile(SUBSIDENCE_PROXY_QUANTILE)
    LOG.info("Subsidence proxy mode (VV dB): anomaly decile threshold %.3f dB", threshold)
    return anomaly < threshold


def engineer_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Build ``well_failure_risk`` (0-100, higher = worse) and drop gap rows.

    Rows with NaN grace_anomaly (GRACE/GRACE-FO instrument gap beyond the
    pipeline's bounded forward-fill) are excluded rather than imputed --
    fabricated anomalies would contaminate the label.
    """
    n_before = len(df)
    out = df.dropna(subset=["grace_anomaly"]).copy()
    if n_before - len(out):
        gap_months = sorted(
            pd.to_datetime(df.loc[df["grace_anomaly"].isna(), "time"]).dt.strftime("%Y-%m").unique()
        )
        LOG.info("GRACE gap: dropped %d rows across %d months (%s .. %s)",
                 n_before - len(out), len(gap_months), gap_months[0], gap_months[-1])

    g_min, g_max = out["grace_anomaly"].min(), out["grace_anomaly"].max()
    out["risk_base"] = 100.0 * (g_max - out["grace_anomaly"]) / (g_max - g_min)

    sub_mask = subsidence_penalty_mask(out)
    climate_mask = (out["precipitation"] - out["evapotranspiration"]) < CLIMATE_STRESS_THRESHOLD_MM
    dry_mask = out["month"].isin(DRY_SEASON_MONTHS)
    mekong_mask = out["region"] == "mekong_delta"
    red_river_mask = out["region"] == "red_river_delta"

    out[TARGET] = (
        out["risk_base"]
        + SUBSIDENCE_PENALTY * sub_mask
        + CLIMATE_STRESS_PENALTY * climate_mask
        + DRY_SEASON_BONUS * dry_mask
        + MEKONG_BONUS * mekong_mask
        + RED_RIVER_BONUS * red_river_mask
    ).clip(0.0, 100.0)

    LOG.info(
        "Label engineered: grace range [%.1f, %.1f] cm | firing rates: subsidence %.1f%%, "
        "climate stress %.1f%%, dry season %.1f%%, mekong %.1f%%, red river %.1f%%",
        g_min, g_max, 100 * sub_mask.mean(), 100 * climate_mask.mean(),
        100 * dry_mask.mean(), 100 * mekong_mask.mean(), 100 * red_river_mask.mean(),
    )
    LOG.info("Risk score: mean %.1f, p5 %.1f, p95 %.1f",
             out[TARGET].mean(), out[TARGET].quantile(0.05), out[TARGET].quantile(0.95))
    return out


def add_cyclic_month(df: pd.DataFrame) -> pd.DataFrame:
    """Add sin/cos month-of-year encodings (Dec and Jan are 1 month apart,
    not 11 -- a raw integer month would teach the model otherwise)."""
    out = df.copy()
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12.0)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12.0)
    return out


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add temporally derived features, computed BEFORE gap rows are dropped
    so rolling windows see the true time axis.

    * water_balance : precipitation - potential evaporation (mm/month)
    * precip_3m     : per-cell 3-month rolling mean precipitation
    * grace_rel     : grace anomaly relative to the cell's own climatology
    * grace_trend   : per-cell 3-month grace slope, (g_t - g_{t-2}) / 2;
                      NaN at series starts / across the GRACE gap -> 0
                      (neutral "no trend", never a fabricated trend)
    """
    out = df.sort_values(["cell_id", "time"]).copy()
    out["water_balance"] = out["precipitation"] - out["evapotranspiration"]
    grouped = out.groupby("cell_id", sort=False)
    out["precip_3m"] = grouped["precipitation"].transform(
        lambda s: s.rolling(3, min_periods=1).mean()
    )
    out["grace_rel"] = out["grace_anomaly"] - grouped["grace_anomaly"].transform("mean")
    out["grace_trend"] = (grouped["grace_anomaly"].diff(2) / 2.0).fillna(0.0)
    return out


def load_static_features(path: Path = STATIC_FEATURES_PATH) -> pd.DataFrame:
    """Load static per-cell covariates written by static_features.py."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing -- run 'python static_features.py' first"
        )
    return pd.read_parquet(path)


def build_model_frame(processed_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    """Full assembly: load, derive, label, encode, merge static covariates.

    Returns one dataframe containing the target plus every column required
    by both FEATURES_BASE and FEATURES_COVARIATE.
    """
    df = load_dataset(processed_dir)
    df = add_derived_features(df)
    df = engineer_labels(df)
    df = add_cyclic_month(df)
    static = load_static_features()
    static_cols = ["elevation_m", "slope_deg", "dist_coast_km", "permeability_index"]
    df = df.merge(static[["cell_id", *static_cols]], on="cell_id", how="left")
    # Fill each covariate's gaps with its own land median: a cell can be missing
    # soil but not terrain (different source masks), so guard each column rather
    # than gating on elevation alone.
    for col in static_cols:
        n_missing = int(df[col].isna().sum())
        if n_missing:
            LOG.warning("%d rows missing %s; filling with land median", n_missing, col)
            df[col] = df[col].fillna(df[col].median())
    return df.reset_index(drop=True)
