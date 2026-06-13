"""Add grid_cells.geom_land: the cell polygon clipped to land.

The 0.25-degree cells are sensor-grid squares that overhang coastlines; for
display the API serves the cell clipped to the union of district boundaries
(the de-facto land mask). Clipping is precomputed because district geometry
is static — run scripts/clip_cells_to_land.py after this migration (and again
whenever districts are re-seeded). NULL means "not clipped yet" or "no land
overlap"; the API falls back to the raw square.

Revision ID: 002
Revises: 001
"""

import geoalchemy2  # noqa: F401 -- registers the Geometry type with alembic
import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "grid_cells",
        sa.Column(
            "geom_land",
            Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("grid_cells", "geom_land")
