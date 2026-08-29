# ADR 001: Player Identity & League Conventions

**Status:** Accepted
**Date:** 2026-08-29
**Ticket:** CAL-146

## Context

Every source Hoop Brain pulls from identifies players differently: `nba_api` uses its own numeric `PERSON_ID`, a WNBA source will use a different vendor scheme, and contract data is scraped from sites with no ID at all — just a name. If source IDs leak into internal tables (a foreign key straight to `nba_api`'s `PERSON_ID`, say), adding a second source later means re-keying every downstream table that referenced it. This decision has to be made before the `Player` entity exists, not after.

This ADR is a repo artifact for a decision already made in the backend PRD (§5–6) — it doesn't introduce anything new, it makes the decision durable and independently discoverable.

## Decision

### 1. Internal surrogate `player_id`

Every internal table keys on an internal surrogate `player_id` — never a source's raw ID. **Surrogate key type: integer identity** (Postgres `IDENTITY`/`SERIAL`, i.e. `Integer` primary key in SQLAlchemy), matching the existing `Team.id` convention. Chosen over UUIDs because:

- Every `Player` row is minted server-side by the Tier-1 resolver during ingestion — there's no client-side ID generation use case that would favor UUIDs.
- Integer PKs keep join and index performance simple across the high-fan-out derived tables this schema implies (`player_season_*`, `player_traits`, `player_surplus_value`, `lineup_possessions`, …).
- Consistency with `Team.id` avoids a mixed-key-type schema for no benefit.

### 2. `PlayerSourceMapping` — the only table holding raw source IDs

```
PlayerSourceMapping
  id               Integer, PK
  internal_player_id  Integer, FK -> Player.id, not null
  league           Enum(League), not null
  source           String, not null        -- e.g. "nba_api", "spotrac", "wehoop"
  source_id        String, not null        -- raw vendor ID or matched name, as the source provides it
  match_method     Enum(MatchMethod), not null   -- tier1_passthrough | tier2_deterministic | tier3_fuzzy | tier4_manual
  confidence       Float, not null         -- 1.0 for Tier 1; explicit score for Tiers 2-4
  matched_at       DateTime, not null

  unique(league, source, source_id)
```

No table other than `PlayerSourceMapping` ever stores a raw source ID. `Player` itself carries no vendor columns.

### 3. `PlayerMatchCandidate` — the review queue

```
PlayerMatchCandidate
  id                 Integer, PK
  league             Enum(League), not null
  source             String, not null
  source_id          String, not null
  candidate_player_id  Integer, FK -> Player.id, nullable   -- null if no plausible match at all
  candidate_name     String, not null                       -- raw name as scraped, for human review
  score              Float, not null
  status             Enum(pending, confirmed, rejected), not null, default pending
  created_at         DateTime, not null
  resolved_at        DateTime, nullable
```

Confirming a candidate here writes the corresponding `PlayerSourceMapping` row; it never happens automatically.

### 4. Matching tiers (most to least reliable)

| Tier | Method | Confidence | Auto-resolves? |
|---|---|---|---|
| 1 | Authoritative passthrough — source is the system of record for the league (`nba_api` for NBA) | 1.0, fixed | Yes |
| 2 | Deterministic — normalized full name + birthdate + league | computed, typically high | Yes, if unambiguous |
| 3 | Fuzzy — name similarity + current team + position (used when birthdate is unavailable, e.g. scraped contract sites) | computed | Yes, only if ≥ threshold |
| 4 | Below threshold (start at **0.90**, tune with experience) | — | **No — `PlayerMatchCandidate`, human confirms** |

NBA and WNBA players are **never** cross-matched, even on identical names — `league` is part of every mapping's identity, not a filter applied after the fact.

Resolution runs as part of each source's ingestion pipeline and must be idempotent: re-running ingestion against the same source data creates zero duplicate `Player` rows or `PlayerSourceMapping` rows (upsert on the `(league, source, source_id)` unique key).

### 5. League conventions

- `league` is a non-nullable enum (`NBA`, `WNBA`) on every entity that needs it — never inferred, never defaulted silently.
- `league` is part of every relevant unique key (`PlayerSourceMapping`, and any future per-league entity), not bolted on as a plain filter column.
- No aggregate, comparison, leaderboard, or percentile computation ever mixes leagues. Enforced at the schema level, not by application-code convention.

## Consequences

- Adding a second NBA source, or the WNBA adapter, only ever adds rows to `PlayerSourceMapping` — no schema change, no re-keying.
- The review queue (Tier 4) is a deliberate manual step: a small human cost on ambiguous identity beats silent misattribution downstream (a surplus-value number attached to the wrong player is worse than no number). This does not conflict with the "no manual trait tagging" rule elsewhere in the project — confirming identity is fixing data, not authoring an opinion.
- `Player.id` being a plain integer means it is **not** globally unique outside this database and must never be exposed as if it were a vendor ID; API consumers should treat it as opaque.

## References

- Backend PRD §5 (Domain Model) and §6 (Entity Resolution) — this ADR is a durable record of that decision, not a new one.
- `CLAUDE.md` — Entity resolution section.
