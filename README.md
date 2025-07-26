Ok this works when you run docker compose up --build
but you have to exec into the sync-engine and run uv run python main.py
to sync over the teams data from BQ to postgres because its not persistent
then you will see it in the web app

when you create a new table in the db you also have to run alembic in the api service

TODOs:

- Clean up API and front end code - make it clearer where to add stuff
- Automate testing in docker-compose (e.g. populate the db with the sync-engine)
- Automate adding new tables and alembic migrations
- Finish constructing the Dagger code
  - We should be able to run all the CI checks in GHA
  - We should also be able to run modular parts of each service
  - Leverage Taskfiles to simplify running dagger commands
  - Eventually all testing and job execution will happen with Dagger
- Add tests and comments everywhere
- Build out ingestion pipeline to gather all the data
  - Add a load function to load to BQ
  - All raw data should land in it's own raw\_{vendor} dataset
- Build out transformation pipeline to prepare data
  - A staging model should be built on top of every raw table (deduping happens here)
  - All intermediate tables should have the prefix int\_
  - A dataset called `marts` will contain all cleaned and transformed data (prefer wide)
  - Views will be created off of marts to be synced over to Postgres to reduce the need for joins in the app db
- Add a db service that houses the postgres Dockerfile
