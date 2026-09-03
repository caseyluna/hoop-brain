import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Tuple

import polars as pl
from google.cloud import bigquery
from sqlalchemy import Engine, text

from src.jobs.base import BaseJob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

# Tier-1 authoritative passthrough per league (docs/adr/001-player-identity.md):
# each league's own stats-API source maps 1:1 at confidence 1.0, no fuzzy logic.
# Matches the vendor labels CAL-145/147/159/249 already established.
SOURCE_BY_LEAGUE = {"NBA": "nba_api", "WNBA": "wehoop"}


@dataclass
class PlayerResolverJob(BaseJob):
    """
    Tier-1 entity resolution (CAL-150): reads the raw-source-keyed marts.players
    view and either mints a new internal Player + PlayerSourceMapping row (first
    time seeing that (league, source, source_id)), or updates an existing
    Player's mutable fields (current_team_id, is_active) by internal id.

    Deliberately not a BQToPostgresJob: that job truncates-and-replaces, which
    would re-mint a new internal id for every player on every run - exactly
    what this ticket exists to prevent. Internal ids must be stable across runs.
    """

    bq_view: str
    bq_client: bigquery.Client
    pg_engine: Engine
    dry_run: bool = False
    source_by_league: Dict[str, str] = field(default_factory=lambda: SOURCE_BY_LEAGUE)

    def run(self) -> None:
        self.log(f"Resolving players from BQ view `{self.bq_view}`")
        df = self._read_from_bq()
        if self.dry_run:
            self.log(f"[DRY RUN] Would resolve {len(df)} rows from {self.bq_view}")
            return
        inserted, updated = self._resolve(df)
        self.log(
            f"Resolved {len(df)} rows from {self.bq_view}: "
            f"{inserted} new players minted, {updated} existing players updated"
        )

    def _read_from_bq(self) -> pl.DataFrame:
        query = f"SELECT * FROM `{self.bq_view}`"
        self.log(f"Executing BQ query: {query}")
        result = self.bq_client.query(query).to_dataframe()
        self.log(f"Retrieved {len(result)} rows from BQ view `{self.bq_view}`")
        return pl.from_pandas(result)

    def _resolve(self, df: pl.DataFrame) -> Tuple[int, int]:
        rows = df.to_dicts()
        for row in rows:
            row["source"] = self.source_by_league[row["league"]]
            row["source_id"] = str(row["id"])

        with self.pg_engine.begin() as conn:
            existing = self._load_existing_mappings(conn)
            valid_team_ids = self._load_valid_team_ids(conn)

            dropped_team_ids = 0
            for row in rows:
                if row["team_id"] is not None and row["team_id"] not in valid_team_ids:
                    # Source data references a team_id (G-League, international,
                    # or a stale/placeholder value) that isn't in our `teams`
                    # table at all -- current_team_id is nullable precisely for
                    # this (a player can legitimately have no resolvable current
                    # team), so null it out rather than fail the whole batch on
                    # a foreign-key violation for one bad row.
                    row["team_id"] = None
                    dropped_team_ids += 1
            if dropped_team_ids:
                self.log(
                    f"{dropped_team_ids} rows had a team_id not present in `teams` "
                    "- nulled out current_team_id for those rows rather than fail"
                )

            inserted = 0
            updated = 0
            now = datetime.now(timezone.utc)
            for row in rows:
                key = (row["league"], row["source"], row["source_id"])
                internal_id = existing.get(key)
                if internal_id is None:
                    self._insert_player(conn, row, now)
                    inserted += 1
                else:
                    self._update_player(conn, internal_id, row)
                    updated += 1

            return inserted, updated

    def _load_valid_team_ids(self, conn) -> set:
        rows = conn.execute(text("SELECT id FROM teams")).fetchall()
        return {r.id for r in rows}

    def _load_existing_mappings(self, conn) -> Dict[Tuple[str, str, str], int]:
        rows = conn.execute(
            text(
                "SELECT league, source, source_id, internal_player_id "
                "FROM player_source_mapping WHERE source = ANY(:sources)"
            ),
            {"sources": list(self.source_by_league.values())},
        ).fetchall()
        return {(r.league, r.source, r.source_id): r.internal_player_id for r in rows}

    def _insert_player(self, conn, row: dict, matched_at: datetime) -> None:
        new_id = conn.execute(
            text(
                "INSERT INTO players (league, full_name, current_team_id, is_active) "
                "VALUES (:league, :full_name, :team_id, :is_active) RETURNING id"
            ),
            row,
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO player_source_mapping "
                "(internal_player_id, league, source, source_id, match_method, confidence, matched_at) "
                "VALUES (:internal_player_id, :league, :source, :source_id, "
                "'tier1_passthrough', 1.0, :matched_at)"
            ),
            {**row, "internal_player_id": new_id, "matched_at": matched_at},
        )

    def _update_player(self, conn, internal_id: int, row: dict) -> None:
        conn.execute(
            text(
                "UPDATE players SET current_team_id = :team_id, is_active = :is_active "
                "WHERE id = :internal_id"
            ),
            {**row, "internal_id": internal_id},
        )
