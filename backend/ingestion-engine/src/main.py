from modules.nba_api import NBAApi


def main():
    bucket = "hoop-brain-raw-data"
    nba_client = NBAApi(bucket=bucket)
    nba_client.ingest_teams()


if __name__ == "__main__":
    main()
