from sqlalchemy import Boolean, Column, Date, Enum, ForeignKey, Integer, String

from app.db.base import Base
from app.models.enums import League


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    league = Column(Enum(League, name="league"), nullable=False)
    full_name = Column(String, nullable=False)
    # Nullable: entity resolution can mint a Player before every enrichment
    # source (e.g. CAL-255's birthdate/current-team backfill) has run.
    birthdate = Column(Date, nullable=True)
    position = Column(String, nullable=True)
    height = Column(String, nullable=True)
    # deferrable/initially deferred: CAL-150's Tier-1 resolver runs inside the
    # same transaction as the teams sync's delete+reinsert (see bq_to_postgres.py) --
    # without this, Postgres checks the FK per-statement and rejects the
    # momentary gap while teams rows are being replaced, even though both
    # tables end the transaction consistent.
    current_team_id = Column(
        Integer,
        ForeignKey("teams.id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, server_default="true")
