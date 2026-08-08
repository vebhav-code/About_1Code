from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL

# pool_pre_ping=True tests connections before using them to prevent using dead/stale sockets.
# pool_recycle=280 recycles connections every 280s (safely below typical hosted Postgres 300s
# idle timeouts, eliminating random slow first-query symptoms after period of inactivity).
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
    pool_size=10,
    max_overflow=10,
)

SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine

)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()