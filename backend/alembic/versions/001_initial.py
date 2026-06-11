"""Initial schema: users, districts, grid_cells, risk_scores,
alert_subscriptions, alert_events.

Geometry columns are declared with spatial_index=False and the GIST indexes
are created explicitly below, so index DDL lives in the migration (reviewable,
reversible) instead of happening as a GeoAlchemy2 side effect.

District geometries are seeded out-of-band (e.g. GADM level-2 boundaries via
ogr2ogr/shp2pgsql into the `districts` table); grid cells are synced from
data/processed/grid_cells.geojson by monthly_cron.py.

Revision ID: 001
Revises:
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

SRID = 4326


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "role", sa.String(50), nullable=False, server_default="field_officer"
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "districts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "geom",
            Geometry(geometry_type="MULTIPOLYGON", srid=SRID, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", name="uq_districts_name"),
    )
    op.create_index("ix_districts_geom", "districts", ["geom"], postgresql_using="gist")

    op.create_table(
        "grid_cells",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cell_code", sa.String(32), nullable=False),
        sa.Column("centroid_lat", sa.Float, nullable=False),
        sa.Column("centroid_lon", sa.Float, nullable=False),
        sa.Column("priority_region", sa.String(50), nullable=True),
        sa.Column(
            "geom",
            Geometry(geometry_type="POLYGON", srid=SRID, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("cell_code", name="uq_grid_cells_cell_code"),
    )
    op.create_index(
        "ix_grid_cells_geom", "grid_cells", ["geom"], postgresql_using="gist"
    )

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "cell_id",
            sa.Integer,
            sa.ForeignKey("grid_cells.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.Date, nullable=False),
        sa.Column(
            "score_type",
            sa.Enum("observed", "forecast", name="score_type"),
            nullable=False,
        ),
        sa.Column("risk", sa.Float, nullable=False),
        sa.Column("ci_low", sa.Float, nullable=True),
        sa.Column("ci_high", sa.Float, nullable=True),
        sa.Column(
            "model_run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "cell_id", "month", "score_type", name="uq_risk_scores_cell_month_type"
        ),
        sa.CheckConstraint(
            "risk >= 0 AND risk <= 100", name="ck_risk_scores_risk_range"
        ),
    )
    op.create_index(
        "ix_risk_scores_type_month", "risk_scores", ["score_type", "month"]
    )

    op.create_table(
        "alert_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_token", sa.String(512), nullable=False),
        sa.Column(
            "district_name",
            sa.String(120),
            sa.ForeignKey("districts.name", onupdate="CASCADE"),
            nullable=False,
        ),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "device_token", "district_name", name="uq_alert_subs_token_district"
        ),
        sa.CheckConstraint(
            "threshold >= 0 AND threshold <= 100",
            name="ck_alert_subs_threshold_range",
        ),
    )
    op.create_index(
        "ix_alert_subscriptions_device_token", "alert_subscriptions", ["device_token"]
    )
    op.create_index(
        "ix_alert_subscriptions_district_name",
        "alert_subscriptions",
        ["district_name"],
    )

    op.create_table(
        "alert_events",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "subscription_id",
            sa.Integer,
            sa.ForeignKey("alert_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("district_name", sa.String(120), nullable=False),
        sa.Column("month", sa.Date, nullable=False),
        sa.Column("risk_value", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("fcm_message_id", sa.String(256), nullable=True),
        sa.Column(
            "acknowledged", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "subscription_id", "month", name="uq_alert_events_sub_month"
        ),
    )
    op.create_index(
        "ix_alert_events_district_sent", "alert_events", ["district_name", "sent_at"]
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_subscriptions")
    op.drop_table("risk_scores")
    op.drop_table("grid_cells")
    op.drop_table("districts")
    op.drop_table("users")
    sa.Enum(name="score_type").drop(op.get_bind(), checkfirst=True)
    # PostGIS extension is intentionally left installed (shared resource).
