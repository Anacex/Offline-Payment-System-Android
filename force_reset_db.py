"""
Force reset database — drop all ORM-registered tables and recreate.
"""

from app.core.db import engine, Base
from app.models import (
    User,
    Wallet,
    OfflineTransaction,
    OfflineReceiverSync,
    WalletTransfer,
    DeviceLedgerHead,
    OtpChallenge,
)
from app.models_refresh_token import RefreshToken

print("Dropping all registered tables...")
Base.metadata.drop_all(bind=engine)
print("Recreating...")
Base.metadata.create_all(bind=engine)
print("SUCCESS: Database recreated.")

from sqlalchemy import inspect

inspector = inspect(engine)
print("\nTables:")
for table in sorted(inspector.get_table_names()):
    print(f"  - {table}")
