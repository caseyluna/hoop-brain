from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Alembic's --autogenerate diffs Base.metadata against the live db. A model
# not imported here is invisible to that diff, so autogenerate reads it as
# "should not exist" and will script a DROP for its table. Import every
# model module below, even if nothing in this file appears to use it.
from app.models.team import Team  # noqa: E402, F401
