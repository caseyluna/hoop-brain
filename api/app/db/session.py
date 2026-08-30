import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

# Small pool + pre-ping: the app connects through Neon's pooler (PgBouncer),
# which already multiplexes connections server-side — a large local pool
# just adds a second layer of pooling for no benefit, and each serverless
# invocation gets its own process anyway. pool_pre_ping guards against
# connections gone stale while Neon's compute was scaled to zero; pool_recycle
# matches Neon's 5-minute default scale-to-zero suspend timeout.
engine = create_engine(
    DATABASE_URL,
    pool_size=1,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
