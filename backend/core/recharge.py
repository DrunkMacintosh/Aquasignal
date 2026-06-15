"""Domain rules for soil permeability and groundwater recharge potential.

Groundwater is recharged when rain that is not lost to evapotranspiration
infiltrates the ground -- and how readily it infiltrates is governed by soil
permeability. This module turns the two ingredients the API already has into a
single readout:

* ``permeability_index`` -- a unitless [0, 1] measure derived from saturated
  hydraulic conductivity (``static_features.py``), area-weighted per district.
* the district's latest water balance, ``precipitation - evapotranspiration``.

    recharge = permeability_index * max(precip - et, 0)

The recharge figure is a RELATIVE indicator (mm/month-equivalent), not a
calibrated recharge flux: the pilot has no recharge ground truth, so the value
ranks units against each other rather than reporting an absolute rate. This
mirrors the pipeline's ``sar_subsidence`` proxy convention -- honest about what
the number is and is not.

Labels are returned lowercase to match ``scoring.risk_level``; the UI styles
them.
"""

# permeability_index upper band edges -> qualitative class (ascending).
PERMEABILITY_CLASS_EDGES: tuple[tuple[float, str], ...] = (
    (0.2, "very low"),
    (0.4, "low"),
    (0.6, "moderate"),
    (0.8, "high"),
)
PERMEABILITY_CLASS_TOP = "very high"

# Recharge-indicator upper band edges (mm/month-equivalent) -> one-word label.
# Heuristic thresholds for a glanceable readout; the numeric value carries the
# detail. Net infiltration across the Vietnam pilot runs ~0-300 mm/month.
RECHARGE_LABEL_EDGES: tuple[tuple[float, str], ...] = (
    (10.0, "minimal"),
    (40.0, "low"),
    (100.0, "moderate"),
)
RECHARGE_LABEL_TOP = "high"


def permeability_class(index: float) -> str:
    """Band a [0, 1] permeability index into a qualitative class."""
    for edge, label in PERMEABILITY_CLASS_EDGES:
        if index < edge:
            return label
    return PERMEABILITY_CLASS_TOP


def net_infiltration(precip_mm: float, et_mm: float) -> float:
    """Water available to infiltrate this month (mm); never negative.

    When evapotranspiration exceeds precipitation the surface is in deficit and
    no water is left to recharge the aquifer, so the floor is zero rather than a
    negative 'reverse recharge'.
    """
    return max(precip_mm - et_mm, 0.0)


def recharge_index(permeability_index: float, precip_mm: float, et_mm: float) -> float:
    """Relative recharge potential = permeability_index * net infiltration.

    Callers pass non-None values; missing inputs are handled upstream (a unit
    with no permeability data, or a month with a sensor gap, has no recharge).
    """
    return permeability_index * net_infiltration(precip_mm, et_mm)


def recharge_label(value: float) -> str:
    """Band a recharge indicator value into a one-word label."""
    for edge, label in RECHARGE_LABEL_EDGES:
        if value < edge:
            return label
    return RECHARGE_LABEL_TOP
