from modules.nba_api import NBAApi
from modules.wnba import WNBAApi


def main():
    bucket = "hoop-brain-raw-data"
    nba_client = NBAApi(bucket=bucket)
    nba_client.ingest_teams()
    nba_client.ingest_players()
    wnba_client = WNBAApi(bucket=bucket)
    wnba_client.ingest_teams()


if __name__ == "__main__":
    main()
