"""Domain rules for turning numeric risk scores into labels."""

RISK_MIN = 0.0
RISK_MAX = 100.0

# risk_level thresholds (spec: 25 / 50 / 75)
LEVEL_MEDIUM = 25.0
LEVEL_HIGH = 50.0
LEVEL_CRITICAL = 75.0

# trend: change over TREND_WINDOW_MONTHS needed to leave "stable"
TREND_WINDOW_MONTHS = 3
TREND_DELTA_POINTS = 5.0

FORECAST_HORIZON_MONTHS = 6
EXPORT_HISTORY_MONTHS = 24
ALERT_HISTORY_LIMIT = 30


def risk_level(score: float) -> str:
    if score >= LEVEL_CRITICAL:
        return "critical"
    if score >= LEVEL_HIGH:
        return "high"
    if score >= LEVEL_MEDIUM:
        return "medium"
    return "low"


def trend_label(current: float, three_months_ago: float | None) -> str:
    """Classify the 3-month trajectory; missing history reads as stable."""
    if three_months_ago is None:
        return "stable"
    delta = current - three_months_ago
    if delta >= TREND_DELTA_POINTS:
        return "worsening"
    if delta <= -TREND_DELTA_POINTS:
        return "improving"
    return "stable"
