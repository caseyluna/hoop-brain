# ADR 002: hoopR/wehoop as the primary ingestion entry point

**Status:** Accepted
**Date:** 2026-08-30
**Ticket:** CAL-251 (decision), CAL-252 (shared plumbing)

## Context

Hoop Brain's ingestion backlog spans a wide set of domains — core NBA/WNBA stats (teams, players, games, box scores), on/off splits, play-by-play/lineups/possessions, injuries and transactions, contract salaries (Spotrac/HoopsHype/RealGM), and college basketball production. The original plan was one bespoke Python scraper/client per source (`docs/hoop-brain-data-source-catalog.md`, and tickets CAL-156/159/160/163/178/179/237/242/243).

Two R packages in the sportsdataverse ecosystem — **hoopR** (NBA + men's college) and **wehoop** (WNBA + women's college) — already wrap nearly all of this: direct NBA/WNBA Stats API access (`nba_*`/`wnba_*` functions, including on/off splits and possession-level lineup data), ESPN data (`espn_*` functions, including injuries), and maintained scrapers for Spotrac, HoopsHype, RealGM, NBADraft, KenPom, Bart Torvik, and Basketball-Reference. They also handle their own request pacing internally, so the project doesn't reimplement rate-limiting per source.

Confirmed real (via research, not assumed from package names):

- `hoopR::nba_teamplayeronoffsummary()` / `nba_teamplayeronoffdetails()` — direct on/off pulls, wrapping the same stats.nba.com endpoints nba_api exposes as `TeamPlayerOnOffSummary`/`Details`.
- `hoopR::nba_possession_lineups()` — pre-built possession-level stint matrices.
- `hoopR::espn_nba_injuries()` / `espn_nba_team_injuries()`, plus `rotowire_injuries()` and `bref_injuries()` as alternates.
- `wehoop::wnba_teamplayeronoffsummary()` confirmed to exist, mirroring hoopR's naming.
- `hoopR::nba_player_crosswalk()` / `load_nba_player_crosswalk()` — links ESPN, NBA Stats, and Fox player identities. **Does not** solve the contract-scraper name-matching problem (Spotrac/HoopsHype/RealGM rows are still name-only) — CAL-181's Tier-3 fuzzy matcher is still required for those regardless of which client fetched the raw rows.
- Neither package has a Python-native equivalent for the domains above (`sportsdataverse-py` only ports the stats-API + ESPN wrapper portions, not the scraper/college surface) — this is genuinely R-only today.

## Decision

**Adopt hoopR/wehoop as the default ingestion entry point for new (not-yet-built) sources**, specifically:

- **Core stats going forward** (games, box scores, on/off, play-by-play, possessions/lineups, shot charts, tracking, hustle) — both leagues.
- **Injuries/transactions** (CAL-243) — via `espn_nba_injuries`/`espn_wnba_injuries`-family functions, superseding the direct-ESPN-endpoint plan written into CAL-243 (kept there as a documented fallback, not deleted).
- **Contract salary sources** (CAL-178/179/242, Spotrac/RealGM/HoopsHype) and **Basketball-Reference** (CAL-241) — via hoopR's maintained scraper wrappers, superseding bespoke Python scrapers.
- **College basketball** (CAL-236/237) — hoopR's CBD/Torvik/KenPom wrappers are strong candidates for CAL-236's own decision, alongside the standalone CBD API + `cbbd` Python client already added there.

**Not retroactively rewritten:** CAL-145 (NBA teams) and CAL-249 (WNBA teams) are already merged and working via nba_api-direct / `requests`-direct. There's no functional gain in reworking already-shipped, trivial entity pulls — only churn. If either needs a rewrite for unrelated reasons later, route it through the mechanism below for consistency, but that's not this decision's mandate.

**Implementation shape:** a small, separate `Rscript`-in-container utility (`pipelines/ingestion-engine/r/`, CAL-252) — never merged into the Python ingestion-engine image, and R never becomes the pipeline's control flow. Task orchestrates it as a sibling step to the existing Python containers (same pattern root `Taskfile.yml` already uses to compose `ingest-daily`), writing CSV output to a shared host-mounted volume that a small Python module (`modules/hoopr_bridge.py`) then picks up and carries through the *same* GCS→BQ Parquet path every other source already uses. No Docker-in-Docker — Python never spawns the R container itself, Task does, as two ordinary sequential steps.

## Consequences

- Two client approaches now coexist by design: nba_api/direct-`requests` for the two already-shipped team entities, hoopR/wehoop for everything built from here forward. This is a deliberate, bounded exception, not drift — documented here so it doesn't need re-explaining per ticket.
- The pipeline gains a second language/toolchain (R) for the first time. Contained to one image (`pipelines/ingestion-engine/r/`), not spread across services.
- CAL-181's Tier-3 fuzzy matcher remains necessary — hoopR's crosswalk covers ESPN/NBA-Stats/Fox IDs, not the name-only contract-scraper matching problem.
- Every affected ticket (CAL-156/159/160/163/164/165/178/179/241/242/243/237) implements against a hoopR/wehoop function per this ADR instead of a bespoke scraper/client — see each ticket for its specific function mapping.

## References

- CAL-251 (this decision), CAL-252 (the shared R-invocation utility)
- `docs/hoop-brain-data-source-catalog.md` §1-5
- `docs/adr/001-player-identity.md` (entity resolution — the crosswalk finding above relates to but doesn't replace this)
