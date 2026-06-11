"""SQLAlchemy ORM models for the AquaSignal PostGIS schema.

Design notes
------------
* ``grid_cells`` stores each 0.25-degree cell as a Polygon (SRID 4326) with a
  GIST index, plus precomputed centroid floats -- the grid is static, so the
  centroid is never recomputed at query time. ``cell_code`` is the pipeline's
  natural key (``"<lat>_<lon>"``, e.g. ``"10.125_105.625"``); the integer PK
  keeps the time-series FK compact.
* ``risk_scores`` is a type-discriminated time series: one row per
  ``(cell, month, score_type)``. ``observed`` rows are append-mostly;
  ``forecast`` rows carry confidence intervals and are overwritten by each
  monthly model run via upsert on the composite unique key.
* District membership is resolved spatially (``ST_Intersects``) against
  ``districts.geom`` -- there is deliberately no ``district_id`` column on
  grid_cells, so boundary changes never require a backfill.
* ``alert_events.district_name`` is denormalized so alert history survives
  unsubscription (``subscription_id`` is SET NULL on delete).
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SRID_WGS84 = 4326
GRID_RESOLUTION_DEG = 0.25


class Base(DeclarativeBase):
    pass


class ScoreType(str, enum.Enum):
    OBSERVED = "observed"
    FORECAST = "forecast"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(50), default="field_officer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=SRID_WGS84)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GridCell(Base):
    __tablename__ = "grid_cells"
    __table_args__ = (UniqueConstraint("cell_code", name="uq_grid_cells_cell_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cell_code: Mapped[str] = mapped_column(String(32))
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    priority_region: Mapped[str | None] = mapped_column(String(50))
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=SRID_WGS84)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    scores: Mapped[list[RiskScore]] = relationship(back_populates="cell")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        UniqueConstraint(
            "cell_id", "month", "score_type", name="uq_risk_scores_cell_month_type"
        ),
        CheckConstraint("risk >= 0 AND risk <= 100", name="ck_risk_scores_risk_range"),
        Index("ix_risk_scores_type_month", "score_type", "month"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cell_id: Mapped[int] = mapped_column(
        ForeignKey("grid_cells.id", ondelete="CASCADE")
    )
    month: Mapped[date] = mapped_column(Date)  # first day of the month
    score_type: Mapped[ScoreType] = mapped_column(
        Enum(
            ScoreType,
            name="score_type",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    risk: Mapped[float] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)  # forecast rows only
    ci_high: Mapped[float | None] = mapped_column(Float)
    model_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cell: Mapped[GridCell] = relationship(back_populates="scores")


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "device_token", "district_name", name="uq_alert_subs_token_district"
        ),
        CheckConstraint(
            "threshold >= 0 AND threshold <= 100", name="ck_alert_subs_threshold_range"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_token: Mapped[str] = mapped_column(String(512), index=True)
    district_name: Mapped[str] = mapped_column(
        ForeignKey("districts.name", onupdate="CASCADE"), index=True
    )
    threshold: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        # one alert per subscription per scored month -> idempotent cron trigger
        UniqueConstraint("subscription_id", "month", name="uq_alert_events_sub_month"),
        Index("ix_alert_events_district_sent", "district_name", "sent_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("alert_subscriptions.id", ondelete="SET NULL")
    )
    district_name: Mapped[str] = mapped_column(String(120))
    month: Mapped[date] = mapped_column(Date)
    risk_value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fcm_message_id: Mapped[str | None] = mapped_column(String(256))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
