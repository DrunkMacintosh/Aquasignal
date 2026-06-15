"""Domain rules in core/recharge.py — the permeability/recharge semantics the
hydrogeology endpoint and the overview panel rely on."""

from core.recharge import (
    net_infiltration,
    permeability_class,
    recharge_index,
    recharge_label,
)


def test_permeability_class_band_boundaries():
    assert permeability_class(0.0) == "very low"
    assert permeability_class(0.19) == "very low"
    assert permeability_class(0.2) == "low"
    assert permeability_class(0.39) == "low"
    assert permeability_class(0.4) == "moderate"
    assert permeability_class(0.6) == "high"
    assert permeability_class(0.8) == "very high"
    assert permeability_class(1.0) == "very high"


def test_net_infiltration_floors_at_zero_when_et_exceeds_precip():
    # Deficit month: evapotranspiration outstrips rain, nothing left to recharge.
    assert net_infiltration(20.0, 50.0) == 0.0
    assert net_infiltration(120.0, 40.0) == 80.0


def test_recharge_index_scales_infiltration_by_permeability():
    # Free-draining ground passes all available water...
    assert recharge_index(1.0, 100.0, 20.0) == 80.0
    # ...half-permeable passes half...
    assert recharge_index(0.5, 100.0, 20.0) == 40.0
    # ...and a deficit month recharges nothing regardless of permeability.
    assert recharge_index(0.9, 30.0, 50.0) == 0.0


def test_recharge_label_band_boundaries():
    assert recharge_label(0.0) == "minimal"
    assert recharge_label(9.99) == "minimal"
    assert recharge_label(10.0) == "low"
    assert recharge_label(39.99) == "low"
    assert recharge_label(40.0) == "moderate"
    assert recharge_label(99.99) == "moderate"
    assert recharge_label(100.0) == "high"
