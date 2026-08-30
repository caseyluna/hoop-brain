from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.db.base import Base
from app.models.enums import League, MatchMethod


class PlayerSourceMapping(Base):
    """
    The only table allowed to hold raw source player IDs, per ADR 001
    (docs/adr/001-player-identity.md). `Player` itself carries no vendor
    columns -- every source's raw ID lives here instead, joined to the
    internal surrogate `Player.id` it resolves to.
    """

    __tablename__ = "player_source_mapping"

    id = Column(Integer, primary_key=True, index=True)
    internal_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    league = Column(Enum(League, name="league"), nullable=False)
    source = Column(String, nullable=False)
    source_id = Column(String, nullable=False)
    match_method = Column(
        Enum(
            MatchMethod,
            name="match_method",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    confidence = Column(Float, nullable=False)
    matched_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "league",
            "source",
            "source_id",
            name="uq_player_source_mapping_league_source_source_id",
        ),
    )
