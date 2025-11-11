# app/core/db.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings  # ✅ Import your Settings

# Use the database URL loaded from .env via pydantic settings
# Ensure SSL is required for managed Postgres providers like Supabase
connect_args = {}
if settings.DATABASE_URL.startswith("postgresql") and "sslmode=" not in settings.DATABASE_URL and settings.REQUIRE_SSL:
    connect_args["sslmode"] = "require"

engine = create_engine(
    settings.DATABASE_URL,
    future=True,
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
