#!/bin/sh
set -e
cd /app

python <<'PY'
import time
from sqlalchemy import create_engine, text
from app.core.config import settings

last = None
for _ in range(60):
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except Exception as e:
        last = e
        time.sleep(1)
else:
    raise SystemExit(f"Database not reachable after 60s: {last}")
PY

python -m app.db_init

if [ -f migrations/001_update_schema_constraints.sql ]; then
  conn="${DATABASE_URL#postgresql+psycopg2://}"
  conn="${conn#postgresql://}"
  psql "postgresql://${conn}" -v ON_ERROR_STOP=1 -f migrations/001_update_schema_constraints.sql
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
