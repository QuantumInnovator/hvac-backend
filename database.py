import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# On Railway, set the DATABASE_URL environment variable to your Postgres
# connection string (copy it from your Postgres service's "Variables" tab).
# If DATABASE_URL isn't set (e.g. running locally on your own machine),
# it falls back to the local SQLite file so local development still works.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hvac_leads.db")

# Railway's Postgres URL sometimes starts with "postgres://" (old-style),
# but SQLAlchemy needs "postgresql://" — this fixes it automatically if needed.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# connect_args is only needed for SQLite — Postgres doesn't need it.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()