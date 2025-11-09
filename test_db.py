from app.core.db import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('Database connection OK')
except Exception as e:
    print(f'Database error: {e}')
