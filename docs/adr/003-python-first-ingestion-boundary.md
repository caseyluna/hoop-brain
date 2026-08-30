# ADR 003: Python-first ingestion, hoopR/wehoop as gap-filler only

**Status:** Accepted
**Date:** 2026-08-30
**Supersedes:** [ADR 002](002-hoopr-wehoop-ingestion-entrypoint.md)
**Ticket:** correction made directly in conversation, no separate spike — the underlying research (function names, the R-invocation mechanism) was already done for ADR 002 and didn't need redoing, only re-applying under a different default.

## Context

ADR 002 set hoopR/wehoop as the *default* entry point for every new (not-yet-built) ingestion source, reasoning that it's one package with confirmed functions across nearly every domain and already handles its own rate-limiting. That default was wrong: it's true hoopR/wehoop can reach most of these domains, but for most of them **a working Python-native path already exists too** — `nba_api` (already in the repo, already proven via CAL-145), `sportsdataverse-py` (confirmed real Python port for WNBA stats-API calls), or a source whose API is simple enough to hit with a plain `requests.get()` (ESPN's site API, Bart Torvik's direct JSON, ESPN's draft endpoint). Reaching for an R subprocess through CAL-252's invocation utility for those is unnecessary indirection — a second runtime, a slower feedback loop (R package installs, `docker run` round-trips through the R container) for something a native Python call already does directly.

hoopR/wehoop's real, durable value is narrower than ADR 002 treated it: **things Python genuinely doesn't have a clean path to** — pre-built possession-level stint matrices (`nba_possession_lineups()`, which would otherwise mean writing a possession parser from raw play-by-play by hand) being the clearest case, plus scraping targets with no official API either way (Spotrac, HoopsHype, Basketball-Reference) where hoopR's maintained wrapper is at least as good as a bespoke Python scraper and already proven working.

## Decision

**Default to the Python-native path. Use hoopR/wehoop (via CAL-252) only where no reasonable Python path exists.**

| Domain | League | Default path | Why |
|---|---|---|---|
| Teams | Both | Already shipped (nba_api-direct / `requests`-direct) | Unaffected — CAL-145/249 |
| Players (roster/bio index) | NBA | `nba_api` — static `players.get_players()` for the roster, a bulk bio endpoint (e.g. league-wide bio stats) for birthdate; verify the exact bio endpoint/columns, don't assume | Already in the repo |
| Players (roster/bio index) | WNBA | `sportsdataverse-py`'s `wnba_stats_*`, or direct `requests` to stats.wnba.com mirroring CAL-249's shape | Confirmed real Python package; CAL-249 already proved the direct-request path works |
| Games, box scores | Both | `nba_api` (NBA, confirmed classes); `sportsdataverse-py`/direct `requests` (WNBA) | Both already Python-native, no gap |
| On/off splits | NBA | `nba_api`'s `TeamPlayerOnOffSummary`/`Details` | Confirmed to exist in nba_api directly — no need for hoopR's wrapper over the same endpoint |
| On/off splits | WNBA | Direct `requests` to stats.wnba.com's equivalent endpoint (mirrors NBA's shape per CAL-249's established pattern) — verify it exists before assuming | Same logic as NBA; not independently confirmed this pass |
| **Possession-level lineups / stints** | **Both** | **hoopR/wehoop** — `nba_possession_lineups()` (NBA, confirmed); WNBA equivalent unconfirmed, check before assuming | **Genuine gap** — nba_api only gives raw pbp, not pre-parsed stints; this is real leverage, not just convenience |
| Play-by-play (raw) | Both | `nba_api` (`PlayByPlay`/`V2`/`V3`, NBA); `sportsdataverse-py`/direct `requests` (WNBA) | Both Python-native |
| Injuries, transactions | Both | Direct `requests` to ESPN's site API (`site.api.espn.com/...`) | Plain unauthenticated JSON GET — as easy as it gets, no client library needed either way |
| Draft history | NBA | `nba_api`'s `DraftHistory` endpoint — verify exact class name, not independently confirmed this pass | Standard nba_api endpoint |
| Draft history | WNBA | Direct `requests` to ESPN's site API draft endpoint | Same plain-JSON case as injuries/transactions |
| Contracts — Spotrac, HoopsHype | NBA | hoopR (`spotrac_team_cap()`, `hoopshype_salaries()`) *or* a bespoke Python scraper — either is fine | No official API/Python client either way; hoopR's wrapper is already proven via CAL-252, but isn't mandatory over a bespoke scraper |
| Basketball-Reference | NBA | hoopR (`bref_*()`) *or* a bespoke Python scraper | Same reasoning as Spotrac/HoopsHype |
| College — CollegeBasketballData | College | **Python** — the official `cbbd` client | Real official Python client exists; no reason to route through hoopR's `cbbd_*()` wrapper for the same API |
| College — Bart Torvik | College | **Python** — direct `requests` (confirmed real JSON endpoints) | Plain JSON, no client needed |
| College — KenPom | College | hoopR (`kp_*()`) | No known Python/API path — only relevant if CAL-236 picks KenPom over CBD/Torvik |
| Cross-source player-ID crosswalks | NBA | hoopR (`nba_player_crosswalk()`) | No Python equivalent known; nice-to-have, not core |

**CAL-252's R-invocation utility is not being removed or devalued** — it's still the right mechanism for the shrunk set of genuine gaps above, and stays proven/working exactly as built.

## Consequences

- Tickets already redirected to hoopR/wehoop under ADR 002 (CAL-147, 156, 159, 160, 163 [on-off/pbp portions], 236, 237, 243, 253, 254) need their source mapping corrected back to a Python-native path per the table above, keeping hoopR/wehoop only for CAL-163/254's possession-lineup portion specifically, and CAL-178/241/242 (unaffected — those were already the hoopR-appropriate case and stay that way).
- **CAL-159 was already implemented and has an open PR (#26) using `wehoop::wnba_playerindex()`.** This ADR doesn't retroactively invalidate working, verified code by itself — whether to redo it via a Python-native WNBA path is a real cost/benefit call (rework a working PR vs. carry one inconsistent source), made explicitly, not automatically.
- Every ticket touched by this correction should state its Python-native function/endpoint with the same rigor ADR 002 required for hoopR functions — confirmed via research, not assumed from a naming-convention guess.

## References

- ADR 002 (superseded, but its function-name research and the CAL-252 mechanism remain accurate)
- CAL-252 (R-invocation utility — unaffected, still the mechanism for the domains that need it)
