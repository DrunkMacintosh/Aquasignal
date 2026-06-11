"""AquaSignal monthly batch job: refresh data, re-score, store, alert.

Steps
-----
1. Re-run the ingestion pipeline (``pipeline.run_pipeline``) -- idempotent,
   only missing months are fetched.
2. Sync grid cells from ``data/processed/grid_cells.geojson`` into PostGIS
   (INSERT ... ON CONFLICT DO NOTHING; the grid is static).
3. Re-score every cell: the downscaler produces the current month's observed
   risk; the LSTM ensemble produces a 6-month forecast whose confidence
   interval is the 10th/90th percentile of the ensemble-member spread.
4. Upsert all scores into ``risk_scores`` (idempotent on
   (cell_id, month, score_type) -- safe to re-run after a crash).
5. POST /alerts/trigger so breached subscriptions receive FCM pushes.

Runs at the repo root in the pilot venv (needs torch/sklearn/joblib), plus
``asyncpg`` and ``httpx`` (see requirements.txt). It talks to the database
directly via asyncpg instead of importing the backend package: the backend's
``models/`` package would shadow the root ``models.py`` ML module on
``sys.path``, so the two codebases stay import-isolated on purpose.

Environment
-----------
AQUASIGNAL_DSN                 postgresql://user:pass@host:5432/aquasignal
                               (AQUASIGNAL_DATABASE_URL with +asyncpg also accepted)
AQUASIGNAL_API_URL             backend base URL (default http://localhost:8000)
AQUASIGNAL_INTERNAL_API_TOKEN  shared secret for POST /alerts/trigger
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx
import joblib
import numpy as np
import pandas as pd
import torch

from features import build_model_frame
from models import DOWNSCALER_PATH, FORECASTER_PATH, LSTMForecaster, inhibit_sleep
from pipeline import run_pipeline

LOG = logging.getLogger("aquasignal.cron")

GRID_GEOJSON = (
    Path(__file__).resolve().parent / "data" / "processed" / "grid_cells.geojson"
)
CI_LOW_PERCENTILE = 10
CI_HIGH_PERCENTILE = 90

GRID_UPSERT_SQL = """
    INSERT INTO grid_cells (cell_code, centroid_lat, centroid_lon,
                            priority_region, geom)
    VALUES ($1, $2, $3, $4, ST_SetSRID(ST_GeomFromGeoJSON($5), 4326))
    ON CONFLICT (cell_code) DO NOTHING
"""

SCORE_UPSERT_SQL = """
    INSERT INTO risk_scores (cell_id, month, score_type, risk,
                             ci_low, ci_high, model_run_at)
    VALUES ($1, $2, $3::score_type, $4, $5, $6, $7)
    ON CONFLICT (cell_id, month, score_type) DO UPDATE
       SET risk = EXCLUDED.risk,
           ci_low = EXCLUDED.ci_low,
           ci_high = EXCLUDED.ci_high,
           model_run_at = EXCLUDED.model_run_at
"""


def database_dsn() -> str:
    dsn = os.environ.get("AQUASIGNAL_DSN") or os.environ.get(
        "AQUASIGNAL_DATABASE_URL"
    )
    if not dsn:
        raise SystemExit(
            "Set AQUASIGNAL_DSN (postgresql://user:pass@host:5432/aquasignal)"
        )
    # asyncpg wants a plain postgresql:// scheme, not SQLAlchemy's dialect form
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


# --------------------------------------------------------------------------- #
# Scoring (loads each model bundle once -- the per-cell predict_* helpers in
# models.py reload bundles per call, which would be ~3000x redundant here)
# --------------------------------------------------------------------------- #


def score_observed(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Period]:
    """Downscaler prediction for every cell in the latest available month."""
    # joblib/pickle is required for sklearn estimators; downscaler.pkl is a
    # locally produced training artifact, never loaded from an untrusted
    # source (same policy as models.predict_downscaler). The torch bundle
    # below is loaded with weights_only=True, which cannot execute code.
    bundle = joblib.load(DOWNSCALER_PATH)
    periods = pd.PeriodIndex(pd.to_datetime(frame["time"]), freq="M")
    latest = periods.max()
    rows = frame[(periods == latest).values].dropna(subset=bundle["features"])
    if rows.empty:
        raise RuntimeError(f"No scoreable rows for latest month {latest}")
    risk = np.clip(bundle["model"].predict(rows[bundle["features"]]), 0.0, 100.0)
    observed = pd.DataFrame(
        {
            "cell_id": rows["cell_id"].to_numpy(),
            "month": latest.to_timestamp().date(),
            "risk": risk,
        }
    )
    LOG.info("Observed scores: %d cells for %s", len(observed), latest)
    return observed, latest


def score_forecast(frame: pd.DataFrame, latest: pd.Period) -> pd.DataFrame:
    """LSTM-ensemble 6-month forecast per cell.

    Mirrors models.build_sequences' gap policy: a cell is only forecast when
    it has a complete, contiguous 12-month history ending at the latest month
    (the model was never trained on imputed history, so we never feed it any).
    """
    bundle = torch.load(FORECASTER_PATH, weights_only=True)
    members = []
    for state in bundle["state_dicts"]:
        member = LSTMForecaster()
        member.load_state_dict(state)
        member.eval()
        members.append(member)
    norm_mean = bundle["norm_mean"].numpy()
    norm_std = bundle["norm_std"].numpy()
    history_n = int(bundle["history_months"])
    feature_cols = list(bundle["features"])

    periods = pd.PeriodIndex(pd.to_datetime(frame["time"]), freq="M")
    ordered = frame.assign(_period=periods).sort_values("_period")

    sequences: list[np.ndarray] = []
    cells: list[str] = []
    for cell_id, group in ordered.groupby("cell_id", sort=False):
        tail = group.tail(history_n)
        if len(tail) < history_n or tail["_period"].iloc[-1] != latest:
            continue
        if (tail["_period"].iloc[-1] - tail["_period"].iloc[0]).n != history_n - 1:
            continue  # gap inside the window
        x_raw = tail[feature_cols].to_numpy(np.float64)
        if np.isnan(x_raw).any():
            continue
        sequences.append((x_raw - norm_mean) / norm_std)
        cells.append(str(cell_id))
    if not sequences:
        raise RuntimeError("No cell has a complete 12-month history window")

    x = torch.tensor(np.stack(sequences), dtype=torch.float32)
    with torch.no_grad():
        member_preds = np.stack([m(x).numpy() for m in members])  # (M, cells, 6)
    member_preds = np.clip(member_preds * norm_std[0] + norm_mean[0], 0.0, 100.0)
    point = member_preds.mean(axis=0)
    ci_low = np.percentile(member_preds, CI_LOW_PERCENTILE, axis=0)
    ci_high = np.percentile(member_preds, CI_HIGH_PERCENTILE, axis=0)

    horizon = int(bundle["forecast_months"])
    months = [(latest + h).to_timestamp().date() for h in range(1, horizon + 1)]
    records = [
        (cell, months[h], float(point[i, h]), float(ci_low[i, h]),
         float(ci_high[i, h]))
        for i, cell in enumerate(cells)
        for h in range(horizon)
    ]
    forecast = pd.DataFrame(
        records, columns=["cell_id", "month", "risk", "ci_low", "ci_high"]
    )
    LOG.info(
        "Forecast scores: %d cells x %d months (%d skipped for gaps)",
        len(cells), horizon, frame["cell_id"].nunique() - len(cells),
    )
    return forecast


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


async def sync_grid_cells(conn: asyncpg.Connection) -> None:
    if not GRID_GEOJSON.exists():
        raise RuntimeError(f"Grid GeoJSON missing: {GRID_GEOJSON} -- run the pipeline")
    collection = json.loads(GRID_GEOJSON.read_text(encoding="utf-8"))
    rows = [
        (
            feature["properties"]["cell_id"],
            float(feature["properties"]["centroid_lat"]),
            float(feature["properties"]["centroid_lon"]),
            feature["properties"].get("priority_region"),
            json.dumps(feature["geometry"]),
        )
        for feature in collection["features"]
    ]
    await conn.executemany(GRID_UPSERT_SQL, rows)
    LOG.info("Grid cells synced (%d features)", len(rows))


async def write_scores(
    conn: asyncpg.Connection, observed: pd.DataFrame, forecast: pd.DataFrame
) -> None:
    cell_ids = {
        record["cell_code"]: record["id"]
        for record in await conn.fetch("SELECT id, cell_code FROM grid_cells")
    }
    run_at = datetime.now(timezone.utc)

    def to_rows(scores: pd.DataFrame, score_type: str, with_ci: bool) -> list[tuple]:
        rows, skipped = [], 0
        for record in scores.itertuples(index=False):
            db_id = cell_ids.get(record.cell_id)
            if db_id is None:
                skipped += 1
                continue
            rows.append(
                (
                    db_id,
                    record.month,
                    score_type,
                    float(record.risk),
                    float(record.ci_low) if with_ci else None,
                    float(record.ci_high) if with_ci else None,
                    run_at,
                )
            )
        if skipped:
            LOG.warning(
                "%d %s rows skipped (cell missing from grid_cells)",
                skipped, score_type,
            )
        return rows

    observed_rows = to_rows(observed, "observed", with_ci=False)
    forecast_rows = to_rows(forecast, "forecast", with_ci=True)
    async with conn.transaction():  # all-or-nothing: never half a month
        await conn.executemany(SCORE_UPSERT_SQL, observed_rows)
        await conn.executemany(SCORE_UPSERT_SQL, forecast_rows)
    LOG.info(
        "Upserted %d observed + %d forecast scores",
        len(observed_rows), len(forecast_rows),
    )


async def store_results(
    dsn: str, observed: pd.DataFrame, forecast: pd.DataFrame
) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await sync_grid_cells(conn)
        await write_scores(conn, observed, forecast)
    finally:
        await conn.close()


# --------------------------------------------------------------------------- #
# Alert trigger
# --------------------------------------------------------------------------- #


def trigger_alerts(api_url: str, token: str) -> None:
    response = httpx.post(
        f"{api_url.rstrip('/')}/alerts/trigger",
        headers={"X-Internal-Token": token},
        timeout=300.0,
    )
    response.raise_for_status()
    LOG.info("Alert trigger summary: %s", response.json())


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-pipeline", action="store_true",
        help="Re-score from existing parquet data without fetching new months.",
    )
    parser.add_argument(
        "--skip-trigger", action="store_true",
        help="Do not call POST /alerts/trigger after scoring.",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    dsn = database_dsn()
    api_url = os.environ.get("AQUASIGNAL_API_URL", "http://localhost:8000")
    token = os.environ.get("AQUASIGNAL_INTERNAL_API_TOKEN", "")
    if not args.skip_trigger and not token:
        raise SystemExit(
            "Set AQUASIGNAL_INTERNAL_API_TOKEN (or pass --skip-trigger)"
        )

    inhibit_sleep(True)  # long run on a laptop must not be killed by sleep
    try:
        if args.skip_pipeline:
            LOG.info("Step 1/4: pipeline refresh skipped (--skip-pipeline)")
        else:
            LOG.info("Step 1/4: refreshing ingestion pipeline")
            run_pipeline()

        LOG.info("Step 2/4: scoring all cells")
        frame = build_model_frame()
        observed, latest = score_observed(frame)
        forecast = score_forecast(frame, latest)

        LOG.info("Step 3/4: writing scores to PostGIS")
        asyncio.run(store_results(dsn, observed, forecast))

        if args.skip_trigger:
            LOG.info("Step 4/4: alert trigger skipped (--skip-trigger)")
        else:
            LOG.info("Step 4/4: triggering alerts")
            trigger_alerts(api_url, token)

        LOG.info("Monthly run complete for %s", latest)
        return 0
    finally:
        inhibit_sleep(False)


if __name__ == "__main__":
    sys.exit(main())
