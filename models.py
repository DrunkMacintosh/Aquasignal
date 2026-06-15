"""AquaSignal modelling layer (v2 -- accuracy improvement plan).

Model 1 -- Spatial Downscaler
    Ablation of two feature sets (raw lat/lon vs transferable covariates)
    under leave-one-region-out spatial CV, then a Random Forest vs
    HistGradientBoosting comparison where the boosted model is tuned with
    NESTED spatial CV (hyperparameters chosen inside each outer fold, so
    reported metrics are never contaminated by tuning). Winner saved to
    downscaler.pkl.

Model 2 -- Temporal Forecaster
    Seed-ensemble of 2-layer LSTMs with calendar (month sin/cos) channels,
    ReduceLROnPlateau, gap-aware window building (windows spanning the
    GRACE instrument gap are skipped, never imputed), and a 3-way spatial
    cell split: train / val (steers early stopping) / test (untouched,
    headline metrics). Saved to forecaster.pt (weights_only-loadable).

Loss for Model 2: MSE + monotonicity penalty
    P = sum_i ReLU(y_hat_i - y_hat_{i+1})^2 applied only to samples whose
    observed 6-month risk slope >= TREND_TAU pts/month (aquifer inertia:
    drawdown built over months does not rebound in one).

Data loading and label engineering live in features.py; static covariates
are produced by static_features.py (run it once before this file).
"""

from __future__ import annotations

import logging
import random
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
import torch
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch import nn
from torch.utils.data import DataLoader, Dataset

from features import (
    CV_FOLDS,
    FEATURES_BASE,
    FEATURES_COVARIATE,
    TARGET,
    build_model_frame,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parent
DOWNSCALER_PATH = PROJECT_ROOT / "downscaler.pkl"
FORECASTER_PATH = PROJECT_ROOT / "forecaster.pt"
CHECKPOINT_PATH = PROJECT_ROOT / "forecaster_checkpoint.pt"
REPORT_PATH = PROJECT_ROOT / "training_report.png"

SEED = 42

# Reference metrics from the 24-month baseline run (2026-06-10) for the
# before/after comparison log. RF values are spatial-CV means; the LSTM value
# is the mean per-horizon validation MAE in risk points.
BASELINE_24M = {"rf_rmse": 8.95, "rf_mae": 7.96, "rf_r2": 0.692, "lstm_mae": 3.46}

# Prefer the gradient-boosting downscaler unless the RF beats it by more than
# this many RMSE points. On the full dataset the RF serialises ~150x larger
# (~670 MB vs a few MB) -- the difference between deploying on a free-tier host
# and OOMing on it -- so a sub-0.5-point, noise-level RMSE edge is not worth it.
DOWNSCALER_RF_RMSE_MARGIN = 0.5

HGB_GRID = [
    {"learning_rate": lr, "max_leaf_nodes": leaves, "l2_regularization": l2}
    for lr, leaves, l2 in product((0.05, 0.1), (31, 63), (0.0, 1.0))
]

LSTM_FEATURES = [TARGET, "precipitation", "evapotranspiration", "temperature",
                 "month_sin", "month_cos"]
N_PHYSICAL_CHANNELS = 4          # jitter only physical channels, not calendar
HISTORY_MONTHS, FORECAST_MONTHS = 12, 6
HIDDEN_SIZE, NUM_LAYERS, DROPOUT = 128, 2, 0.2
LEARNING_RATE, MAX_EPOCHS, PATIENCE = 1e-3, 80, 8
BATCH_SIZE, WEIGHT_DECAY, GRAD_CLIP = 1024, 1e-5, 1.0
MONO_LAMBDA, TREND_TAU = 0.1, 1.0
VAL_CELL_FRACTION, TEST_CELL_FRACTION = 0.15, 0.15
JITTER_SIGMA, SCALE_JITTER = 0.05, 0.10
# 3 members: with ~11x more data than the 24-month baseline, member variance
# is already low; members 4-5 buy <0.1 MAE for +40 min CPU.
ENSEMBLE_SEEDS = (42, 43, 44)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=sys.stdout,
)
LOG = logging.getLogger("aquasignal.models")


def set_seeds(seed: int = SEED) -> None:
    """Seed python, numpy and torch for reproducible runs."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def inhibit_sleep(active: bool) -> None:
    """Ask Windows not to idle-sleep while training runs (no-op elsewhere).

    Training runs were killed twice by laptop sleep; ES_SYSTEM_REQUIRED keeps
    the system awake for the lifetime of this process. Lid-close actions can
    still override this -- checkpointing covers that case.
    """
    if sys.platform != "win32":
        return
    import ctypes
    es_continuous, es_system_required = 0x80000000, 0x00000001
    flags = es_continuous | (es_system_required if active else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


# --------------------------------------------------------------------------- #
# Model 1: spatial downscaler (ablation + nested-CV model comparison)          #
# --------------------------------------------------------------------------- #


def build_random_forest() -> RandomForestRegressor:
    """Baseline RF: identical config to the 24-month run for attributable
    before/after comparison."""
    return RandomForestRegressor(
        n_estimators=300, min_samples_leaf=5, max_features="sqrt",
        n_jobs=-1, random_state=SEED,
    )


def build_hist_gb(params: dict) -> HistGradientBoostingRegressor:
    """Gradient boosting with built-in early stopping on a random 10% slice
    (stopping signal only; model selection uses region-out inner CV)."""
    return HistGradientBoostingRegressor(
        max_iter=500, early_stopping=True, validation_fraction=0.1,
        random_state=SEED, **params,
    )


def spatial_cv(
    df: pd.DataFrame, feature_cols: list[str], make_model, label: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Leave-one-region-out CV: each named hydrological zone is fully held
    out once; training uses the other zones plus background cells. This is
    the honest generalisation test -- random splits leak autocorrelated
    neighbours and inflate metrics.

    Returns (per-fold metrics, pooled held-out predictions for plotting).
    """
    rows, pooled = [], []
    for fold in CV_FOLDS:
        test, train = df[df["region"] == fold], df[df["region"] != fold]
        model = make_model()
        model.fit(train[feature_cols], train[TARGET])
        pred = model.predict(test[feature_cols])
        rows.append({
            "fold": fold, "n_test": len(test),
            "rmse": float(np.sqrt(mean_squared_error(test[TARGET], pred))),
            "mae": float(mean_absolute_error(test[TARGET], pred)),
            "r2": float(r2_score(test[TARGET], pred)),
        })
        pooled.append(pd.DataFrame({"y_true": test[TARGET].values, "y_pred": pred}))
        LOG.info("[%s] fold %-18s RMSE=%6.2f MAE=%6.2f R2=%6.3f",
                 label, fold, rows[-1]["rmse"], rows[-1]["mae"], rows[-1]["r2"])
    metrics = pd.DataFrame(rows).set_index("fold")
    LOG.info("[%s] spatial CV mean: RMSE=%.2f MAE=%.2f R2=%.3f", label,
             metrics["rmse"].mean(), metrics["mae"].mean(), metrics["r2"].mean())
    return metrics, pd.concat(pooled, ignore_index=True)


def run_feature_ablation(df: pd.DataFrame) -> tuple[list[str], str, pd.DataFrame, pd.DataFrame]:
    """Phase 2 ablation: raw lat/lon vs transferable covariates, same RF,
    same spatial CV. Returns the winning feature set and its CV artifacts."""
    base_metrics, base_scatter = spatial_cv(df, FEATURES_BASE, build_random_forest, "RF/latlon")
    cov_metrics, cov_scatter = spatial_cv(df, FEATURES_COVARIATE, build_random_forest, "RF/covariates")
    if cov_metrics["rmse"].mean() <= base_metrics["rmse"].mean():
        LOG.info("Ablation winner: covariate features (RMSE %.2f vs %.2f)",
                 cov_metrics["rmse"].mean(), base_metrics["rmse"].mean())
        return FEATURES_COVARIATE, "covariates", cov_metrics, cov_scatter
    LOG.info("Ablation winner: lat/lon features (RMSE %.2f vs %.2f)",
             base_metrics["rmse"].mean(), cov_metrics["rmse"].mean())
    return FEATURES_BASE, "latlon", base_metrics, base_scatter


def nested_cv_hist_gb(
    df: pd.DataFrame, feature_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Phase 3: nested spatial CV for gradient boosting.

    For each outer fold (held-out region), hyperparameters are selected by
    inner region-out CV on the remaining two named regions; the outer test
    region never influences tuning. The returned metrics are therefore an
    unbiased estimate despite the hyperparameter search.
    """
    rows, pooled, chosen = [], [], []
    for fold in CV_FOLDS:
        outer_train = df[df["region"] != fold]
        inner_regions = [r for r in CV_FOLDS if r != fold]
        best_params, best_rmse = None, float("inf")
        for params in HGB_GRID:
            inner_rmses = []
            for inner in inner_regions:
                fit_df = outer_train[outer_train["region"] != inner]
                val_df = outer_train[outer_train["region"] == inner]
                model = build_hist_gb(params)
                model.fit(fit_df[feature_cols], fit_df[TARGET])
                pred = model.predict(val_df[feature_cols])
                inner_rmses.append(np.sqrt(mean_squared_error(val_df[TARGET], pred)))
            mean_rmse = float(np.mean(inner_rmses))
            if mean_rmse < best_rmse:
                best_rmse, best_params = mean_rmse, params
        model = build_hist_gb(best_params)
        model.fit(outer_train[feature_cols], outer_train[TARGET])
        test = df[df["region"] == fold]
        pred = model.predict(test[feature_cols])
        rows.append({
            "fold": fold, "n_test": len(test),
            "rmse": float(np.sqrt(mean_squared_error(test[TARGET], pred))),
            "mae": float(mean_absolute_error(test[TARGET], pred)),
            "r2": float(r2_score(test[TARGET], pred)),
        })
        pooled.append(pd.DataFrame({"y_true": test[TARGET].values, "y_pred": pred}))
        chosen.append(best_params)
        LOG.info("[HGB] fold %-18s best=%s RMSE=%6.2f MAE=%6.2f R2=%6.3f",
                 fold, best_params, rows[-1]["rmse"], rows[-1]["mae"], rows[-1]["r2"])
    metrics = pd.DataFrame(rows).set_index("fold")
    LOG.info("[HGB] nested spatial CV mean: RMSE=%.2f MAE=%.2f R2=%.3f",
             metrics["rmse"].mean(), metrics["mae"].mean(), metrics["r2"].mean())
    # Final-model params: the config chosen most often across outer folds.
    counts = pd.Series([str(c) for c in chosen]).value_counts()
    final_params = next(c for c in chosen if str(c) == counts.index[0])
    return metrics, pd.concat(pooled, ignore_index=True), final_params


def train_downscaler(
    df: pd.DataFrame, feature_cols: list[str], model_type: str, hgb_params: dict | None
) -> object:
    """Fit the winning downscaler on ALL cells and persist with joblib.
    Spatial-CV metrics remain the honest generalisation estimate."""
    model = build_hist_gb(hgb_params) if model_type == "hist_gb" else build_random_forest()
    model.fit(df[feature_cols], df[TARGET])
    joblib.dump(
        {"model": model, "features": feature_cols, "target": TARGET,
         "model_type": model_type},
        DOWNSCALER_PATH,
    )
    LOG.info("Saved %s downscaler to %s (%d features)",
             model_type, DOWNSCALER_PATH.name, len(feature_cols))
    return model


def predict_downscaler(grid_cell_id: str, history_months: list[str]) -> pd.Series:
    """Predict risk for one grid cell over the given months ('YYYY-MM')."""
    # joblib/pickle is required for sklearn estimators; downscaler.pkl is a
    # locally produced artifact, never loaded from an untrusted source.
    bundle = joblib.load(DOWNSCALER_PATH)
    df = build_model_frame()
    months = pd.to_datetime(history_months).to_period("M")
    rows = df[(df["cell_id"] == grid_cell_id)
              & (pd.to_datetime(df["time"]).dt.to_period("M").isin(months))]
    if rows.empty:
        raise KeyError(f"No data for cell {grid_cell_id} in months {history_months}")
    pred = bundle["model"].predict(rows[bundle["features"]])
    return pd.Series(pred, index=rows["time"].dt.strftime("%Y-%m").values, name="predicted_risk")


# --------------------------------------------------------------------------- #
# Model 2: LSTM ensemble forecaster                                            #
# --------------------------------------------------------------------------- #


@dataclass
class SequenceData:
    """Raw sliding windows for the forecaster, prior to normalisation."""

    x: np.ndarray          # (n, HISTORY_MONTHS, n_features)
    y: np.ndarray          # (n, FORECAST_MONTHS) raw risk
    slope: np.ndarray      # (n,) depletion slope over last 6 history months
    cell_ids: np.ndarray   # (n,) cell id per window


def build_sequences(df: pd.DataFrame, cells: np.ndarray) -> SequenceData:
    """Gap-aware 12-in / 6-out windows (stride 1) for the given cells.

    Each cell's series is reindexed onto the full monthly axis; any window
    containing a missing month (GRACE gap, sparse early Sentinel-1) is
    skipped entirely -- the model never trains on imputed history.
    """
    periods = pd.PeriodIndex(pd.to_datetime(df["time"]), freq="M")
    full_range = pd.period_range(periods.min(), periods.max(), freq="M")
    window = HISTORY_MONTHS + FORECAST_MONTHS
    t6 = np.arange(6, dtype=np.float64)
    t6 -= t6.mean()
    denom = float((t6 * t6).sum())

    xs, ys, slopes, ids = [], [], [], []
    sub = df[df["cell_id"].isin(cells)].assign(_period=periods[df["cell_id"].isin(cells).values])
    for cell_id, group in sub.groupby("cell_id", sort=False):
        mat = group.set_index("_period")[LSTM_FEATURES].reindex(full_range).to_numpy(np.float64)
        if len(mat) < window:
            continue
        sw = sliding_window_view(mat, (window, mat.shape[1]))[:, 0]
        valid = ~np.isnan(sw).any(axis=(1, 2))
        if not valid.any():
            continue
        w = sw[valid]
        hist, future = w[:, :HISTORY_MONTHS, :], w[:, HISTORY_MONTHS:, 0]
        tail = hist[:, -6:, 0]
        slope = ((tail - tail.mean(axis=1, keepdims=True)) * t6).sum(axis=1) / denom
        xs.append(hist)
        ys.append(future)
        slopes.append(slope)
        ids.append(np.full(len(w), cell_id, dtype=object))
    return SequenceData(
        x=np.concatenate(xs), y=np.concatenate(ys),
        slope=np.concatenate(slopes), cell_ids=np.concatenate(ids),
    )


class RiskSequenceDataset(Dataset):
    """Windows with train-time augmentation.

    * magnitude scaling u ~ U(1-SCALE_JITTER, 1+SCALE_JITTER) on the risk
      channel of input AND target (consistent -- preserves the mapping);
    * Gaussian jitter on the physical channels only -- calendar sin/cos
      channels stay exact (a noisy calendar is just wrong information).
    """

    def __init__(self, data: SequenceData, norm_mean: np.ndarray,
                 norm_std: np.ndarray, augment: bool) -> None:
        self.data = data
        self.mean, self.std = norm_mean, norm_std
        self.augment = augment
        self.rng = np.random.default_rng(SEED)

    def __len__(self) -> int:
        return len(self.data.y)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x_raw, y_raw = self.data.x[i].copy(), self.data.y[i].copy()
        if self.augment:
            scale = 1.0 + self.rng.uniform(-SCALE_JITTER, SCALE_JITTER)
            x_raw[:, 0] = np.clip(x_raw[:, 0] * scale, 0.0, 100.0)
            y_raw = np.clip(y_raw * scale, 0.0, 100.0)
        x = (x_raw - self.mean) / self.std
        y = (y_raw - self.mean[0]) / self.std[0]
        if self.augment:
            x[:, :N_PHYSICAL_CHANNELS] += self.rng.normal(
                0.0, JITTER_SIGMA, size=(x.shape[0], N_PHYSICAL_CHANNELS)
            )
        return (
            torch.tensor(x, dtype=torch.float32),
            torch.tensor(y, dtype=torch.float32),
            torch.tensor(float(self.data.slope[i] >= TREND_TAU), dtype=torch.float32),
        )


class LSTMForecaster(nn.Module):
    """2-layer LSTM (hidden 128, dropout 0.2) + FC head -> 6-month forecast."""

    def __init__(self, n_features: int = len(LSTM_FEATURES),
                 hidden_size: int = HIDDEN_SIZE, num_layers: int = NUM_LAYERS,
                 horizon: int = FORECAST_MONTHS, dropout: float = DROPOUT) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden_size,
                            num_layers=num_layers, dropout=dropout, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2), nn.ReLU(),
            nn.Dropout(dropout), nn.Linear(hidden_size // 2, horizon),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :])


def monotonicity_penalty(pred: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """One-sided penalty on forecast reversals of a strong depletion trend
    (see module docstring for the formula and rationale)."""
    drops = torch.relu(pred[:, :-1] - pred[:, 1:])
    return ((drops ** 2).sum(dim=1) * mask).sum() / mask.sum().clamp(min=1.0)


def train_one_member(
    seed: int, train_loader: DataLoader, val_loader: DataLoader
) -> tuple[dict, float, list[float], list[float]]:
    """Train one ensemble member with early stopping + LR-on-plateau.
    Returns (best state_dict, best val MSE, train curve, val curve)."""
    torch.manual_seed(seed)
    model = LSTMForecaster()
    optimiser = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE,
                                 weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimiser, factor=0.5, patience=4
    )
    mse = nn.MSELoss()
    best_val, best_state, patience_left = float("inf"), None, PATIENCE
    train_curve, val_curve = [], []

    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        for x, y, mask in train_loader:
            optimiser.zero_grad()
            pred = model(x)
            loss = mse(pred, y) + MONO_LAMBDA * monotonicity_penalty(pred, mask)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimiser.step()
            epoch_loss += loss.item() * len(y)
        train_curve.append(epoch_loss / len(train_loader.dataset))

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for x, y, _ in val_loader:        # plain MSE as the stopping signal
                val_loss += mse(model(x), y).item() * len(y)
        val_curve.append(val_loss / len(val_loader.dataset))
        scheduler.step(val_curve[-1])

        if val_curve[-1] < best_val - 1e-5:
            best_val, patience_left = val_curve[-1], PATIENCE
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_left -= 1
        if epoch % 5 == 0 or patience_left == 0:
            LOG.info("seed %d epoch %3d  train=%.4f  val=%.4f  lr=%.1e  (best %.4f)",
                     seed, epoch, train_curve[-1], val_curve[-1],
                     optimiser.param_groups[0]["lr"], best_val)
        if patience_left == 0:
            LOG.info("seed %d: early stopping at epoch %d", seed, epoch)
            break
    return best_state, best_val, train_curve, val_curve


def train_forecaster(
    df: pd.DataFrame,
) -> tuple[list[LSTMForecaster], dict, list[float], list[float]]:
    """Train the seed ensemble with a 3-way spatial cell split.

    Validation cells steer early stopping; TEST cells are never touched
    during training or stopping, making them the honest headline metric.
    """
    cells = np.sort(df["cell_id"].unique())
    rng = np.random.default_rng(SEED)
    shuffled = rng.permutation(cells)
    n_val = int(len(cells) * VAL_CELL_FRACTION)
    n_test = int(len(cells) * TEST_CELL_FRACTION)
    val_cells, test_cells = shuffled[:n_val], shuffled[n_val:n_val + n_test]
    train_cells = shuffled[n_val + n_test:]

    train_seq = build_sequences(df, train_cells)
    val_seq = build_sequences(df, val_cells)
    LOG.info("Sequences: %d train (%d cells), %d val (%d cells), %d test cells held out",
             len(train_seq.y), len(train_cells), len(val_seq.y), len(val_cells), n_test)

    flat = train_seq.x.reshape(-1, len(LSTM_FEATURES))
    norm_mean, norm_std = flat.mean(axis=0), flat.std(axis=0) + 1e-8
    train_loader = DataLoader(
        RiskSequenceDataset(train_seq, norm_mean, norm_std, augment=True),
        batch_size=BATCH_SIZE, shuffle=True,
    )
    val_loader = DataLoader(
        RiskSequenceDataset(val_seq, norm_mean, norm_std, augment=False),
        batch_size=BATCH_SIZE, shuffle=False,
    )

    # Resume support: members completed by an interrupted run are reused.
    # The checkpoint is invalidated if the training data changed shape.
    done_states: dict[str, dict] = {}
    if CHECKPOINT_PATH.exists():
        ckpt = torch.load(CHECKPOINT_PATH, weights_only=True)
        if ckpt.get("n_train") == len(train_seq.y):
            done_states = ckpt["seed_states"]
            LOG.info("Resuming from checkpoint: members %s already trained",
                     sorted(done_states))
        else:
            LOG.warning("Checkpoint ignored: training data changed (%s vs %d windows)",
                        ckpt.get("n_train"), len(train_seq.y))

    states, models, first_curves = [], [], None
    for seed in ENSEMBLE_SEEDS:
        if str(seed) in done_states:
            state = done_states[str(seed)]
            LOG.info("Ensemble member seed=%d restored from checkpoint", seed)
        else:
            state, best_val, tc, vc = train_one_member(seed, train_loader, val_loader)
            LOG.info("Ensemble member seed=%d best val MSE %.4f", seed, best_val)
            if first_curves is None:
                first_curves = (tc, vc)
            done_states[str(seed)] = state
            torch.save({"seed_states": done_states, "n_train": len(train_seq.y)},
                       CHECKPOINT_PATH)
        states.append(state)
        member = LSTMForecaster()
        member.load_state_dict(state)
        member.eval()
        models.append(member)
    if first_curves is None:   # every member came from the checkpoint
        first_curves = ([], [])

    # Tensors/primitives only, so the bundle loads with weights_only=True.
    bundle = {
        "state_dicts": states,
        "norm_mean": torch.tensor(norm_mean, dtype=torch.float64),
        "norm_std": torch.tensor(norm_std, dtype=torch.float64),
        "features": LSTM_FEATURES,
        "history_months": HISTORY_MONTHS,
        "forecast_months": FORECAST_MONTHS,
        "val_cells": val_cells.tolist(),
        "test_cells": test_cells.tolist(),
        "seeds": list(ENSEMBLE_SEEDS),
    }
    torch.save(bundle, FORECASTER_PATH)
    CHECKPOINT_PATH.unlink(missing_ok=True)
    LOG.info("Saved %d-member ensemble to %s", len(states), FORECASTER_PATH.name)
    return models, bundle, first_curves[0], first_curves[1]


def ensemble_predict(models: list[LSTMForecaster], x: torch.Tensor) -> np.ndarray:
    """Mean forecast across ensemble members (normalised space)."""
    with torch.no_grad():
        return np.mean([m(x).numpy() for m in models], axis=0)


def evaluate_forecaster(
    models: list[LSTMForecaster], bundle: dict, df: pd.DataFrame
) -> pd.DataFrame:
    """Headline metrics on the untouched TEST cells, denormalised to risk
    points, with per-horizon and per-region breakdowns."""
    test_seq = build_sequences(df, np.asarray(bundle["test_cells"]))
    mean, std = bundle["norm_mean"].numpy(), bundle["norm_std"].numpy()
    x = torch.tensor((test_seq.x - mean) / std, dtype=torch.float32)
    pred = np.clip(ensemble_predict(models, x) * std[0] + mean[0], 0.0, 100.0)

    horizon = pd.DataFrame([
        {
            "horizon_month": h + 1,
            "rmse": float(np.sqrt(mean_squared_error(test_seq.y[:, h], pred[:, h]))),
            "mae": float(mean_absolute_error(test_seq.y[:, h], pred[:, h])),
        }
        for h in range(FORECAST_MONTHS)
    ]).set_index("horizon_month")
    LOG.info("Forecaster TEST metrics (risk points):\n%s", horizon.round(2).to_string())

    region_map = df.drop_duplicates("cell_id").set_index("cell_id")["region"]
    window_regions = region_map.reindex(test_seq.cell_ids).to_numpy()
    abs_err = np.abs(pred - test_seq.y).mean(axis=1)
    by_region = (
        pd.DataFrame({"region": window_regions, "mae": abs_err})
        .groupby("region")["mae"].agg(["mean", "count"]).round(2)
    )
    LOG.info("Forecaster TEST MAE by region:\n%s", by_region.to_string())
    return horizon


def predict_forecaster(grid_cell_id: str, history_months: list[str] | None = None) -> pd.Series:
    """Forecast 6 months of risk for one grid cell (ensemble mean).

    Args:
        grid_cell_id: Cell id, e.g. '10.125_105.625'.
        history_months: Optional 12 month labels ('YYYY-MM'); defaults to
            the latest 12 contiguous months available for the cell.
    """
    # weights_only=True: bundle holds only tensors/primitives, so loading
    # cannot execute arbitrary pickled code.
    bundle = torch.load(FORECASTER_PATH, weights_only=True)
    df = build_model_frame()
    rows = df[df["cell_id"] == grid_cell_id].sort_values("time")
    if history_months is not None:
        wanted = pd.to_datetime(history_months).to_period("M")
        rows = rows[pd.to_datetime(rows["time"]).dt.to_period("M").isin(wanted)]
    rows = rows.tail(bundle["history_months"])
    if len(rows) < bundle["history_months"]:
        raise ValueError(
            f"Cell {grid_cell_id}: need {bundle['history_months']} months, got {len(rows)}"
        )
    models = []
    for state in bundle["state_dicts"]:
        member = LSTMForecaster()
        member.load_state_dict(state)
        member.eval()
        models.append(member)
    mean, std = bundle["norm_mean"].numpy(), bundle["norm_std"].numpy()
    x_raw = rows[bundle["features"]].to_numpy(dtype=np.float64)
    x = torch.tensor(((x_raw - mean) / std)[None], dtype=torch.float32)
    pred = np.clip(ensemble_predict(models, x)[0] * std[0] + mean[0], 0.0, 100.0)
    last = pd.Period(pd.to_datetime(rows["time"].iloc[-1]), freq="M")
    labels = [(last + h).strftime("%Y-%m") for h in range(1, bundle["forecast_months"] + 1)]
    return pd.Series(pred, index=labels, name=f"forecast_{grid_cell_id}")


# --------------------------------------------------------------------------- #
# Report                                                                       #
# --------------------------------------------------------------------------- #


def downscaler_importances(model: object, model_type: str, df: pd.DataFrame,
                           feature_cols: list[str]) -> pd.Series:
    """Feature importances: native for RF, permutation on a 5k-row sample
    for gradient boosting (which exposes no impurity importances)."""
    if model_type == "random_forest":
        return pd.Series(model.feature_importances_, index=feature_cols)
    sample = df.sample(min(5000, len(df)), random_state=SEED)
    result = permutation_importance(
        model, sample[feature_cols], sample[TARGET], n_repeats=5,
        random_state=SEED, n_jobs=-1,
    )
    return pd.Series(result.importances_mean, index=feature_cols)


def build_report(importances: pd.Series, scatter: pd.DataFrame, model_label: str,
                 train_curve: list[float], val_curve: list[float],
                 sample_cell: str, df: pd.DataFrame) -> None:
    """training_report.png: importances, held-out scatter, loss curves,
    sample ensemble forecast."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("AquaSignal training report v2 -- Vietnam pilot (2015-2026 data)", fontsize=14)

    imp = importances.sort_values()
    axes[0, 0].barh(imp.index, imp.values, color="#2a7fb8")
    axes[0, 0].set_title(f"Downscaler feature importances ({model_label})")

    sample = scatter.sample(min(4000, len(scatter)), random_state=SEED)
    axes[0, 1].scatter(sample["y_true"], sample["y_pred"], s=4, alpha=0.25, color="#b8552a")
    axes[0, 1].plot([0, 100], [0, 100], "k--", linewidth=1)
    axes[0, 1].set_title(f"Downscaler ({model_label}): predicted vs actual, held-out regions")
    axes[0, 1].set_xlabel("actual risk")
    axes[0, 1].set_ylabel("predicted risk")
    axes[0, 1].set_xlim(0, 100)
    axes[0, 1].set_ylim(0, 100)

    epochs = range(1, len(train_curve) + 1)
    axes[1, 0].plot(epochs, train_curve, label="train (MSE + mono penalty)")
    axes[1, 0].plot(epochs, val_curve, label="validation (MSE)")
    axes[1, 0].set_title("LSTM loss curves, ensemble member 1 (normalised)")
    axes[1, 0].set_xlabel("epoch")
    axes[1, 0].legend()

    history = df[df["cell_id"] == sample_cell].sort_values("time").tail(HISTORY_MONTHS)
    forecast = predict_forecaster(sample_cell)
    hist_labels = pd.to_datetime(history["time"]).dt.strftime("%Y-%m").tolist()
    axes[1, 1].plot(hist_labels, history[TARGET].values, marker="o", label="observed risk")
    axes[1, 1].plot(forecast.index.tolist(), forecast.values, marker="s",
                    linestyle="--", color="#b8552a", label="ensemble forecast")
    axes[1, 1].set_title(f"Sample forecast -- Mekong Delta cell {sample_cell}")
    axes[1, 1].set_ylabel(TARGET)
    axes[1, 1].tick_params(axis="x", rotation=60, labelsize=7)
    axes[1, 1].legend()

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(REPORT_PATH, dpi=150)
    plt.close(fig)
    LOG.info("Wrote %s", REPORT_PATH.name)


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #


def main() -> None:
    """Run the full improvement plan: ablation, model comparison, ensemble
    training, hardened evaluation, report, and baseline comparison."""
    set_seeds()
    inhibit_sleep(True)
    LOG.info("=== AquaSignal model training v2 start (sleep inhibited) ===")
    df = build_model_frame()

    LOG.info("--- Phase 2: feature ablation (spatial CV) ---")
    feature_cols, feature_label, rf_metrics, rf_scatter = run_feature_ablation(df)

    LOG.info("--- Phase 3: nested-CV gradient boosting vs RF ---")
    hgb_metrics, hgb_scatter, hgb_params = nested_cv_hist_gb(df, feature_cols)
    # Tie-break toward the small, deployable HGB model: pick the RF only if it
    # wins by more than DOWNSCALER_RF_RMSE_MARGIN, not by noise.
    if hgb_metrics["rmse"].mean() <= rf_metrics["rmse"].mean() + DOWNSCALER_RF_RMSE_MARGIN:
        model_type, win_metrics, win_scatter = "hist_gb", hgb_metrics, hgb_scatter
    else:
        model_type, win_metrics, win_scatter = "random_forest", rf_metrics, rf_scatter
        hgb_params = None
    LOG.info("Downscaler winner: %s on %s features (RMSE %.2f)",
             model_type, feature_label, win_metrics["rmse"].mean())
    final_model = train_downscaler(df, feature_cols, model_type, hgb_params)

    LOG.info("--- Phase 4: LSTM ensemble forecaster ---")
    models, bundle, train_curve, val_curve = train_forecaster(df)
    horizon = evaluate_forecaster(models, bundle, df)

    LOG.info("--- Phase 5: report + baseline comparison ---")
    mekong = df[df["region"] == "mekong_delta"]
    sample_cell = (mekong.groupby("cell_id")[TARGET].mean().idxmax()
                   if not mekong.empty else df["cell_id"].iloc[0])
    importances = downscaler_importances(final_model, model_type, df, feature_cols)
    build_report(importances, win_scatter, f"{model_type}/{feature_label}",
                 train_curve, val_curve, sample_cell, df)

    LOG.info(
        "Baseline (24 months) vs improved:\n"
        "  downscaler RMSE %.2f -> %.2f | MAE %.2f -> %.2f | R2 %.3f -> %.3f\n"
        "  forecaster mean MAE %.2f -> %.2f (note: baseline was val cells, "
        "improved is untouched test cells)",
        BASELINE_24M["rf_rmse"], win_metrics["rmse"].mean(),
        BASELINE_24M["rf_mae"], win_metrics["mae"].mean(),
        BASELINE_24M["rf_r2"], win_metrics["r2"].mean(),
        BASELINE_24M["lstm_mae"], horizon["mae"].mean(),
    )
    LOG.info("Winner spatial CV per region:\n%s", win_metrics.round(2).to_string())
    inhibit_sleep(False)
    LOG.info("=== Training v2 complete ===")


if __name__ == "__main__":
    main()
