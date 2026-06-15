"""Add grid_cells soil permeability covariates.

Two static per-cell soil columns sampled from soil data by static_features.py:

* ``permeability_index`` -- saturated hydraulic conductivity normalised to
  [0, 1]; used both as a downscaler covariate and for the overview readout.
* ``soil_ksat_mm_hr`` -- the raw conductivity (mm/hour), kept for display.

Both are nullable: NULL means "no soil data for this cell" (fully offshore, or
before scripts/load_permeability.py has run). Run that backfill after this
migration (and again whenever the static features are regenerated).

Revision ID: 003
Revises: 002
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "grid_cells", sa.Column("permeability_index", sa.Float(), nullable=True)
    )
    op.add_column(
        "grid_cells", sa.Column("soil_ksat_mm_hr", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("grid_cells", "soil_ksat_mm_hr")
    op.drop_column("grid_cells", "permeability_index")
