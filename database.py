import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# On Railway, set the DATABASE_URL environment variable to your Postgres
# connection string (copy it from your Postgres service's "Variables" tab).
# If DATABASE_URL isn't set (e.g. running locally on your own machine),
# it falls back to the local SQLite file so local development still works.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hvac_leads.db")

# Railway's Postgres URL starts with "postgres://" or "postgresql://" —
# we rewrite it to use the psycopg3 driver ("postgresql+psycopg://"),
# which is more reliable in Railway's build environment than psycopg2.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

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