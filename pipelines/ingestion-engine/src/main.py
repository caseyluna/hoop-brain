from pathlib import Path

from core.logging_utils import get_logger, log
from modules.nba_api import NBAApi
from modules.wnba import WNBAApi

logger = get_logger(__name__)

# Written by `task ingestion:r-wnba-players` (wehoop::wnba_playerindex via the shared
# R-invocation utility, CAL-252) before this module runs. `wnba_playerindex()` returns a
# named list, so run.R writes one CSV per element -- PlayerIndex is the only element.
WNBA_PLAYERS_CSV = Path("r/output/wnba_players__PlayerIndex.csv")


def main():
    bucket = "hoop-brain-raw-data"
    nba_client = NBAApi(bucket=bucket)
    nba_client.ingest_teams()
    wnba_client = WNBAApi(bucket=bucket)
    wnba_client.ingest_teams()

    # The R pull (task ingestion:r-wnba-players) isn't wired into the composed
    # ingest-daily/scheduled-ingest pipeline yet (CAL-159 lands raw ingestion only;
    # composing the R step into the scheduled run is a fast-follow) -- so a bare
    # `run-main` won't have this CSV. Skip with a clear warning rather than failing
    # the whole ingest run.
    if WNBA_PLAYERS_CSV.exists():
        wnba_client.ingest_players(csv_path=WNBA_PLAYERS_CSV)
    else:
        log(
            logger,
            "WARNING",
            f"Skipping WNBA players ingest - {WNBA_PLAYERS_CSV} not found. "
            "Run `task ingestion:r-wnba-players` first to pull it via wehoop.",
            name="main",
        )


if __name__ == "__main__":
    main()
