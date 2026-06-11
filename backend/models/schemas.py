"""Pydantic v2 request/response models -- the public API contract.

Months are exchanged as ``"YYYY-MM"`` strings everywhere (matching the
pipeline's month labels) rather than full ISO dates, since all scores are
monthly aggregates and a day component would imply false precision.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RiskLevel = Literal["low", "medium", "high", "critical"]
TrendLabel = Literal["improving", "stable", "worsening"]
MONTH_PATTERN = r"^\d{4}-\d{2}$"


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Registered water-authority account email.")
    password: str = Field(
        min_length=1,
        max_length=72,
        description="Account password (bcrypt caps input at 72 bytes).",
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="Signed JWT bearer token.")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds (24 h).")


# --------------------------------------------------------------------------- #
# Risk map (GeoJSON)
# --------------------------------------------------------------------------- #


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]] = Field(
        description="GeoJSON polygon rings, [lon, lat] order (RFC 7946)."
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
    geometry: PolygonGeometry
    properties: CellRiskProperties


class RiskMapResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    month: str = Field(
        pattern=MONTH_PATTERN, description="Month the scores belong to."
    )
    features: list[RiskFeature]


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
