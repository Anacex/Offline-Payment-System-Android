# app/core/db.py
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings  # ✅ Import your Settings


def _db_host_is_local(url: str) -> bool:
    """localhost / loopback should not force sslmode=require (typical local Postgres has no SSL)."""
    try:
        normalized = url.replace("postgresql+psycopg2://", "postgresql://", 1)
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    except Exception:
        return False


# Use the database URL loaded from .env via pydantic settings
# Managed Postgres (Supabase, etc.): set REQUIRE_SSL=true; local Postgres skips require when host is loopback.
connect_args = {}
if (
    settings.DATABASE_URL.startswith("postgresql")
    and "sslmode=" not in settings.DATABASE_URL
    and settings.REQUIRE_SSL
    and not _db_host_is_local(settings.DATABASE_URL)
):
    connect_args["sslmode"] = "require"

engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    pool_pre_ping=True,        # prevents stale connection errors
    pool_recycle=1800,         # recycle every 30 min (recommended for Render + Supabase)
    connect_args=connect_args if connect_args else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
