"""
Force reset database - Drop all tables manually and recreate.
"""

from app.core.db import engine
from sqlalchemy import text

print("Force dropping all tables...")

with engine.connect() as conn:
    # Drop tables in correct order (respecting foreign keys)
    conn.execute(text("DROP TABLE IF EXISTS wallet_transfers CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS offline_transactions CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS wallets CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS transactions CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS refresh_tokens CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
    conn.commit()
    print("All tables dropped successfully!")

print("\nRecreating tables with correct schema...")

from app.core.db import Base
from app.models import User, Wallet, OfflineTransaction, WalletTransfer, Transaction
from app.models_refresh_token import RefreshToken

Base.metadata.create_all(bind=engine)

print("\nSUCCESS: Database recreated with correct schema!")

# Verify
from sqlalchemy import inspect
inspector = inspect(engine)

print("\nVerifying 'users' table columns:")
columns = inspector.get_columns('users')
for col in columns:
    print(f"  - {col['name']}: {col['type']}")

print("\nAll tables:")
for table in inspector.get_table_names():
    print(f"  - {table}")
