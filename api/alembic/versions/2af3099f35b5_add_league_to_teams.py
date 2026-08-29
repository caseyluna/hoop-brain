"""add league to teams

Revision ID: 2af3099f35b5
Revises: afb820e4592a
Create Date: 2026-08-29 12:31:40.205317

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2af3099f35b5"
down_revision: Union[str, None] = "afb820e4592a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Managed explicitly (not via create_type=True on the column) so upgrade/downgrade
# are symmetric: without this, `drop_column` on downgrade leaves the Postgres
# ENUM type orphaned, and a later re-upgrade would fail trying to recreate it.
league_enum = postgresql.ENUM("NBA", "WNBA", name="league")


def upgrade() -> None:
    league_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "teams",
        sa.Column(
            "league",
            sa.Enum("NBA", "WNBA", name="league", create_type=False),
            server_default="NBA",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("teams", "league")
    league_enum.drop(op.get_bind(), checkfirst=True)
