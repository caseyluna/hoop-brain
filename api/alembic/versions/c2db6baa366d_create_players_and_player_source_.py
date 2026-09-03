"""create players and player_source_mapping tables

Revision ID: c2db6baa366d
Revises: dbbcd80f9627
Create Date: 2026-08-30 22:52:09.816741

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c2db6baa366d"
down_revision: Union[str, None] = "dbbcd80f9627"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `league` already exists (created by 2af3099f35b5) - reuse it, don't recreate.
# `match_method` is new here. Both managed explicitly (create_type=False on the
# column) so upgrade/downgrade are symmetric, same reasoning as 2af3099f35b5:
# without this, downgrade's drop_column would leave match_method orphaned, and
# a later re-upgrade would fail trying to recreate a type that still exists.
league_enum = postgresql.ENUM("NBA", "WNBA", name="league", create_type=False)
match_method_enum = postgresql.ENUM(
    "tier1_passthrough",
    "tier2_deterministic",
    "tier3_fuzzy",
    "tier4_manual",
    name="match_method",
)


def upgrade() -> None:
    match_method_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league", league_enum, nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("birthdate", sa.Date(), nullable=True),
        sa.Column("position", sa.String(), nullable=True),
        sa.Column("height", sa.String(), nullable=True),
        sa.Column("current_team_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["current_team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_players_id"), "players", ["id"], unique=False)
    op.create_table(
        "player_source_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("internal_player_id", sa.Integer(), nullable=False),
        sa.Column("league", league_enum, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column(
            "match_method",
            postgresql.ENUM(
                "tier1_passthrough",
                "tier2_deterministic",
                "tier3_fuzzy",
                "tier4_manual",
                name="match_method",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["internal_player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "league",
            "source",
            "source_id",
            name="uq_player_source_mapping_league_source_source_id",
        ),
    )
    op.create_index(
        op.f("ix_player_source_mapping_id"),
        "player_source_mapping",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_player_source_mapping_id"), table_name="player_source_mapping"
    )
    op.drop_table("player_source_mapping")
    op.drop_index(op.f("ix_players_id"), table_name="players")
    op.drop_table("players")
    match_method_enum.drop(op.get_bind(), checkfirst=True)
