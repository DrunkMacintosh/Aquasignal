"""Domain rules in core/scoring.py — the band/trend semantics every layer
(map colours, alerts, exports) relies on."""

from core.scoring import risk_level, trend_label


def test_risk_level_band_boundaries():
    assert risk_level(0) == "low"
    assert risk_level(24.99) == "low"
    assert risk_level(25) == "medium"
    assert risk_level(49.99) == "medium"
    assert risk_level(50) == "high"
    assert risk_level(74.99) == "high"
    assert risk_level(75) == "critical"
    assert risk_level(100) == "critical"


def test_trend_label_five_point_rule():
    assert trend_label(50, 44) == "worsening"  # +6
    assert trend_label(50, 45) == "worsening"  # exactly +5
    assert trend_label(50, 46) == "stable"     # +4
    assert trend_label(40, 45) == "improving"  # exactly -5
    assert trend_label(44, 45) == "stable"     # -1


def test_trend_label_missing_history_reads_stable():
    assert trend_label(90, None) == "stable"
