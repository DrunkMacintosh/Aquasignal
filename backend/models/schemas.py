"""Pydantic v2 request/response models -- the public API contract.

Months are exchanged as ``"YYYY-MM"`` strings everywhere (matching the
pipeline's month labels) rather than full ISO dates, since all scores are
monthly aggregates and a day component would imply false precision.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

RiskLevel = Literal["low", "medium", "high", "critical"]
TrendLabel = Literal["improving", "stable", "worsening"]
MONTH_PATTERN = r"^\d{4}-\d{2}$"

# Emails are normalized to lowercase at the API boundary so "Officer@X" and
# "officer@x" can never become two distinct accounts, and login stays
# case-insensitive regardless of how the address was typed.
NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


class LoginRequest(BaseModel):
    email: NormalizedEmail = Field(
        description="Registered water-authority account email."
    )
    password: str = Field(
        min_length=1,
        max_length=72,
        description="Account password (bcrypt caps input at 72 bytes).",
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="Signed JWT bearer token.")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds (24 h).")


class RegisterRequest(BaseModel):
    email: NormalizedEmail = Field(
        description="Work email; becomes the login identifier."
    )
    password: str = Field(
        min_length=12,
        max_length=72,
        description=(
            "At least 12 characters (same policy as scripts/create_user.py); "
            "bcrypt caps input at 72 bytes."
        ),
    )
    full_name: str = Field(default="", max_length=255)

    @field_validator("password")
    @classmethod
    def _password_fits_bcrypt(cls, value: str) -> str:
        # max_length counts characters; multi-byte characters can still blow
        # bcrypt's 72-BYTE cap, which verify_password treats as a failed match.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes")
        return value


# --------------------------------------------------------------------------- #
# Risk map (GeoJSON)
# --------------------------------------------------------------------------- #


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]] = Field(
        description="GeoJSON polygon rings, [lon, lat] order (RFC 7946)."
    )


class MultiPolygonGeometry(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[list[float]]]] = Field(
        description="GeoJSON multipolygon rings, [lon, lat] order (RFC 7946)."
    )


class CellRiskProperties(BaseModel):
    cell_id: str = Field(
        description="Stable cell code '<lat>_<lon>', e.g. '10.125_105.625'."
    )
    centroid_lat: float = Field(ge=-90, le=90)
    centroid_lon: float = Field(ge=-180, le=180)
    current_risk: float = Field(
        ge=0, le=100, description="Well-failure risk for the current month (0-100)."
    )
    risk_level: RiskLevel = Field(
        description="Banded risk: <25 low, 25-50 medium, 50-75 high, >=75 critical."
    )
    trend: TrendLabel = Field(
        description=(
            "3-month trajectory: +-5 points vs. three months ago maps to "
            "worsening/improving; otherwise stable."
        )
    )


class RiskFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    # MultiPolygon once clipped to the coastline; plain Polygon as fallback
    # for unclipped cells.
    geometry: MultiPolygonGeometry | PolygonGeometry
    properties: CellRiskProperties


class RiskMapResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    month: str = Field(
        pattern=MONTH_PATTERN, description="Month the scores belong to."
    )
    features: list[RiskFeature]


class DistrictRiskProperties(BaseModel):
    district_name: str = Field(description="Name as stored in `districts`.")
    has_data: bool = Field(
        description="False when no intersecting cell has a current risk score."
    )
    current_risk: float | None = Field(
        default=None, ge=0, le=100,
        description="Area-weighted mean of intersecting cells for the current month.",
    )
    risk_level: RiskLevel | None = None
    trend: TrendLabel | None = None
    cells_in_district: int = Field(
        description="Grid cells spatially intersecting the district."
    )


class DistrictRiskFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: MultiPolygonGeometry
    properties: DistrictRiskProperties


class DistrictRiskMapResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    month: str = Field(
        pattern=MONTH_PATTERN, description="Month the scores belong to."
    )
    features: list[DistrictRiskFeature]


# --------------------------------------------------------------------------- #
# History (observed risk time series)
# --------------------------------------------------------------------------- #


class HistoryPoint(BaseModel):
    month: str = Field(pattern=MONTH_PATTERN)
    risk: float = Field(ge=0, le=100)
    risk_level: RiskLevel


class CellHistoryResponse(BaseModel):
    cell_id: str
    history: list[HistoryPoint] = Field(description="Ascending by month.")


class DistrictHistoryResponse(BaseModel):
    district_name: str
    aggregation: Literal["area_weighted_mean"] = "area_weighted_mean"
    history: list[HistoryPoint] = Field(description="Ascending by month.")


# --------------------------------------------------------------------------- #
# Satellite observations (raw model inputs, read from the parquet store)
# --------------------------------------------------------------------------- #


class SatelliteMonth(BaseModel):
    month: str = Field(pattern=MONTH_PATTERN)
    grace_anomaly: float | None = Field(
        default=None,
        description=(
            "GRACE-FO water-storage anomaly vs the long-term mean "
            "(cm liquid water equivalent)."
        ),
    )
    sar_subsidence: float | None = Field(
        default=None,
        description=(
            "Sentinel-1 VV radar backscatter (dB) — an indirect proxy for "
            "subsidence/surface wetness, NOT a measured displacement rate "
            "(true subsidence needs InSAR; see pipeline.py)."
        ),
    )
    precipitation: float | None = Field(
        default=None, description="Monthly precipitation (mm, ERA5-Land)."
    )
    evapotranspiration: float | None = Field(
        default=None,
        description="Monthly potential evapotranspiration (mm, ERA5-Land).",
    )
    temperature: float | None = Field(
        default=None, description="2 m air temperature (°C, ERA5-Land)."
    )


class CellSatelliteResponse(BaseModel):
    cell_id: str
    observations: list[SatelliteMonth] = Field(description="Ascending by month.")


class DistrictSatelliteResponse(BaseModel):
    district_name: str
    aggregation: Literal["area_weighted_mean"] = "area_weighted_mean"
    observations: list[SatelliteMonth] = Field(description="Ascending by month.")


# --------------------------------------------------------------------------- #
# Hydrogeology (soil permeability + derived recharge potential)
# --------------------------------------------------------------------------- #


class DistrictPermeabilityResponse(BaseModel):
    district_name: str
    aggregation: Literal["area_weighted_mean"] = "area_weighted_mean"
    has_data: bool = Field(
        description="False when no intersecting cell carries soil permeability data."
    )
    permeability_index: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Area-weighted soil permeability, 0 (impermeable) to 1 (free-draining).",
    )
    soil_ksat_mm_hr: float | None = Field(
        default=None,
        description="Area-weighted saturated hydraulic conductivity (mm/hour).",
    )
    permeability_class: str | None = Field(
        default=None,
        description="Banded label: very low / low / moderate / high / very high.",
    )
    month: str | None = Field(
        default=None,
        pattern=MONTH_PATTERN,
        description="Month whose water balance the recharge readout is computed for.",
    )
    net_infiltration_mm: float | None = Field(
        default=None,
        description="Water available to infiltrate that month: max(precip - evapotranspiration, 0), mm.",
    )
    recharge_value: float | None = Field(
        default=None,
        description=(
            "Relative recharge potential (mm/month-equivalent): "
            "permeability_index x net infiltration. A ranking indicator, not a "
            "calibrated recharge rate."
        ),
    )
    recharge_label: str | None = Field(
        default=None, description="Banded label: minimal / low / moderate / high."
    )


# --------------------------------------------------------------------------- #
# Forecast
# --------------------------------------------------------------------------- #


class ForecastPoint(BaseModel):
    month: str = Field(pattern=MONTH_PATTERN)
    predicted_risk: float = Field(ge=0, le=100)
    confidence_interval_low: float = Field(
        description="10th percentile of the LSTM ensemble spread."
    )
    confidence_interval_high: float = Field(
        description="90th percentile of the LSTM ensemble spread."
    )


class CellForecastResponse(BaseModel):
    cell_id: str
    generated_at: datetime | None = Field(
        description="When the forecasting model last ran for this cell."
    )
    forecast: list[ForecastPoint] = Field(
        description="Up to 6 months, ascending by month."
    )


class DistrictForecastResponse(BaseModel):
    district_name: str
    cells_in_district: int = Field(
        description="Grid cells spatially intersecting the district."
    )
    aggregation: Literal["area_weighted_mean"] = "area_weighted_mean"
    forecast: list[ForecastPoint]


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #


class SubscribeRequest(BaseModel):
    device_token: str = Field(
        min_length=8, max_length=512, description="FCM device registration token."
    )
    district_name: str = Field(min_length=1, max_length=120)
    threshold: float = Field(
        ge=0,
        le=100,
        description="Notify when the district's area-weighted risk reaches this value.",
    )


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_token: str
    district_name: str
    threshold: float
    is_active: bool
    created_at: datetime


class UnsubscribeResponse(BaseModel):
    device_token: str
    removed: int = Field(description="Number of district subscriptions deleted.")


class AlertEventResponse(BaseModel):
    id: int
    district_name: str
    month: str = Field(pattern=MONTH_PATTERN, description="Scored month that breached.")
    risk_value: float
    threshold: float
    sent_at: datetime
    delivered: bool = Field(description="Whether FCM accepted the notification.")
    acknowledged: bool
    acknowledged_at: datetime | None


class AcknowledgeResponse(BaseModel):
    id: int
    acknowledged: Literal[True] = True
    acknowledged_at: datetime


class TriggerSummary(BaseModel):
    month: str | None = Field(
        default=None, pattern=MONTH_PATTERN, description="Evaluated month (null when no scores exist)."
    )
    subscriptions_evaluated: int
    thresholds_breached: int
    notifications_sent: int
    send_failures: int
    deactivated_tokens: int = Field(
        description="Stale FCM tokens deactivated during this run."
    )


# --------------------------------------------------------------------------- #
# AI advisor (OpenRouter-backed water-planning report)
# --------------------------------------------------------------------------- #

# The planning goals a user can choose. Kept in sync with ADVISOR_NEEDS on the
# frontend (lib/advisor.js) and the guidance map in core/advisor.py.
AdvisorNeed = Literal[
    "water_sustainability", "agriculture", "urban_supply", "industrial"
]

# Caps keep prompt size (and free-tier cost) bounded.
MAX_ANSWER_CHARS = 1000
MAX_ANSWERS = 8


def _sanitize_district_name(value: str) -> str:
    # district_name lands verbatim in the prompt; collapse whitespace (removes
    # newline-based prompt injection) and reject an all-whitespace name.
    collapsed = " ".join(value.split())
    if not collapsed:
        raise ValueError("district_name must not be blank")
    return collapsed


class AdvisorSnapshot(BaseModel):
    """Compact district-data context the frontend assembles from its cache and
    sends with the request (Option A thin proxy). Reuses the existing read-model
    types so the advisor's view of the data cannot drift from the panel's."""

    current_risk: float | None = Field(default=None, ge=0, le=100)
    risk_level: RiskLevel | None = None
    trend: TrendLabel | None = None
    latest_month: str | None = Field(default=None, pattern=MONTH_PATTERN)
    history: list[HistoryPoint] = Field(
        default_factory=list, description="Recent observed risk, ascending by month."
    )
    forecast: list[ForecastPoint] = Field(
        default_factory=list, description="6-month outlook, ascending by month."
    )
    satellite: list[SatelliteMonth] = Field(
        default_factory=list, description="Recent raw observations, ascending by month."
    )
    permeability_index: float | None = Field(default=None, ge=0, le=1)
    # Pipeline-produced enum labels; length-capped since they are interpolated
    # verbatim into the prompt (a direct caller could otherwise send arbitrary
    # strings).
    permeability_class: str | None = Field(default=None, max_length=64)
    recharge_value: float | None = None
    recharge_label: str | None = Field(default=None, max_length=64)
    net_infiltration_mm: float | None = None


# --- Step 1: intake questions ---------------------------------------------- #


class AdvisorQuestion(BaseModel):
    id: str = Field(max_length=40, description="Stable snake_case field id.")
    question: str = Field(min_length=1, max_length=300)
    hint: str | None = Field(default=None, max_length=120, description="Example answer.")


class AdvisorQuestionsRequest(BaseModel):
    district_name: str = Field(min_length=1, max_length=120)
    need: AdvisorNeed
    snapshot: AdvisorSnapshot

    @field_validator("district_name")
    @classmethod
    def _clean_district(cls, value: str) -> str:
        return _sanitize_district_name(value)


class AdvisorQuestionsResponse(BaseModel):
    questions: list[AdvisorQuestion]
    model: str = Field(description="OpenRouter model id that produced the questions.")


# --- Step 2: structured report --------------------------------------------- #


class AdvisorAnswer(BaseModel):
    question: str = Field(min_length=1, max_length=300, description="Echoed question.")
    answer: str = Field(default="", max_length=MAX_ANSWER_CHARS)


class AdvisorReportRequest(BaseModel):
    district_name: str = Field(min_length=1, max_length=120)
    need: AdvisorNeed
    snapshot: AdvisorSnapshot
    answers: list[AdvisorAnswer] = Field(default_factory=list, max_length=MAX_ANSWERS)

    @field_validator("district_name")
    @classmethod
    def _clean_district(cls, value: str) -> str:
        return _sanitize_district_name(value)


class AdvisorActionPhase(BaseModel):
    timeframe: str = Field(default="", description="e.g. 'Immediate (0-1 month)'.")
    actions: list[str] = Field(default_factory=list)


class AdvisorReport(BaseModel):
    """The structured report. Every field is defaulted so a partial (or
    coerced) model response still validates and renders."""

    headline: str = ""
    outlook: str = Field(default="", description="Short outlook tag.")
    situation_assessment: str = ""
    your_context: str = ""
    key_findings: list[str] = Field(default_factory=list)
    action_plan: list[AdvisorActionPhase] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    monitoring: list[str] = Field(default_factory=list)


class AdvisorReportResponse(BaseModel):
    report: AdvisorReport
    model: str = Field(description="OpenRouter model id that produced the report.")


class AdvisorConfigResponse(BaseModel):
    enabled: bool = Field(
        description="True when an OpenRouter key is configured server-side."
    )
    model: str | None = Field(
        default=None, description="Active model id, or null when disabled."
    )


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db_connected: bool
    models_loaded: bool = Field(
        description="Both ML artifacts (downscaler.pkl, forecaster.pt) present on disk."
    )
    last_pipeline_run: datetime | None = Field(
        description="model_run_at of the newest observed score; null before first run."
    )
