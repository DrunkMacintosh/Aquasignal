"""One-time backfill: score `observed` risk for the last N months and upsert
into ``risk_scores``.

The monthly cron (``monthly_cron.score_observed``) only ever scores the single
latest month (``periods.max()``), so the dashboard's history charts had just one
data point to plot. This script reuses the very same downscaler and feature
frame, but loops over a window of months instead of only the latest one, so the
history endpoints return a real multi-year series.

It is **observed-only** (never touches forecast rows) and **idempotent**
(``ON CONFLICT (cell_id, month, score_type) DO UPDATE``), so it is safe to
re-run. Nothing is deleted.

Environment
-----------
AQUASIGNAL_DSN   postgresql://user:pass@host:5432/db
                 (AQUASIGNAL_DATABASE_URL with +asyncpg also accepted)

Usage
-----
    AQUASIGNAL_DSN=postgresql://... python backfill_history.py --months 25
    AQUASIGNAL_DSN=postgresql://... python backfill_history.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

import asyncpg
import joblib
import numpy as np
import pandas as pd

from features import build_model_frame
from models import DOWNSCALER_PATH, inhibit_sleep
from monthly_cron import SCORE_UPSERT_SQL, database_dsn

LOG = logging.getLogger("aquasignal.backfill")


def target_months(frame: pd.DataFrame, count: int) -> list[pd.Period]:
    """The `count` most recent monthly periods present in `frame`, ascending."""
    periods = pd.PeriodIndex(pd.to_datetime(frame["time"]), freq="M")
    latest = periods.max()
    return [latest - i for i in range(count - 1, -1, -1)]


def score_observed_window(frame: pd.DataFrame, months: list[pd.Period]) -> pd.DataFrame:
    """Downscaler observed-risk prediction for every cell across `months`.

    Mirrors ``monthly_cron.score_observed`` row-for-row (same bundle, same
    feature columns, same 0-100 clip) but for each month in the window rather
    than only the latest.
    """
    # joblib/pickle is required for the sklearn estimator; downscaler.pkl is a
    # locally produced training artifact, never loaded from an untrusted source
    # (same policy as monthly_cron / models.predict_downscaler).
    bundle = joblib.load(DOWNSCALER_PATH)
    features = bundle["features"]
    periods = pd.PeriodIndex(pd.to_datetime(frame["time"]), freq="M")

    frames: list[pd.DataFrame] = []
    for period in months:
        rows = frame[periods == period].dropna(subset=features)
        if rows.empty:
            LOG.warning("No scoreable rows for %s -- skipped", period)
            continue
        risk = np.clip(bundle["model"].predict(rows[features]), 0.0, 100.0)
        frames.append(
            pd.DataFrame(
                {
                    "cell_id": rows["cell_id"].to_numpy(),
                    "month": period.to_timestamp().date(),
                    "risk": risk,
                }
            )
        )
        LOG.info("Scored %d cells for %s", len(rows), period)

    if not frames:
        raise RuntimeError("No month in the window produced any scores")
    return pd.concat(frames, ignore_index=True)


async def upsert_observed(dsn: str, observed: pd.DataFrame, dry_run: bool) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        cell_ids = {
            record["cell_code"]: record["id"]
            for record in await conn.fetch("SELECT id, cell_code FROM grid_cells")
        }
        run_at = datetime.now(timezone.utc)
        rows, skipped = [], 0
        for record in observed.itertuples(index=False):
            db_id = cell_ids.get(record.cell_id)
            if db_id is None:
                skipped += 1
                continue
            # (cell_id, month, score_type, risk, ci_low, ci_high, model_run_at)
            rows.append((db_id, record.month, "observed", float(record.risk), None, None, run_at))

        months = sorted({row[1] for row in rows})
        LOG.info(
            "Prepared %d observed rows over %d months (%s .. %s); %d skipped (cell not in grid_cells)",
            len(rows), len(months), months[0], months[-1], skipped,
        )
        if dry_run:
            LOG.info("DRY RUN -- nothing written")
            return
        async with conn.transaction():
            await conn.executemany(SCORE_UPSERT_SQL, rows)
        LOG.info("Upserted %d observed rows across %d months", len(rows), len(months))
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--months", type=int, default=25,
        help="Months of history to backfill, ending at the latest available month "
             "(default 25: fills the dashboard's 2-year window inclusive of both ends).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Score and report, but do not write.")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    dsn = database_dsn()
    inhibit_sleep(True)  # scoring + IO must not be killed by laptop sleep
    try:
        LOG.info("Building model frame from data/processed ...")
        frame = build_model_frame()
        months = target_months(frame, args.months)
        LOG.info("Backfilling %d months: %s .. %s", len(months), months[0], months[-1])
        observed = score_observed_window(frame, months)
        asyncio.run(upsert_observed(dsn, observed, args.dry_run))
        LOG.info("Backfill complete")
        return 0
    finally:
        inhibit_sleep(False)


if __name__ == "__main__":
    sys.exit(main())
