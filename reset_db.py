"""
Reset database - Drop all tables and recreate them.
WARNING: This will delete all data!
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

print("WARNING: This will delete all existing data!")
print("Dropping all tables...")

Base.metadata.drop_all(bind=engine)
print("All tables dropped")

print("\nCreating fresh tables...")
Base.metadata.create_all(bind=engine)

print("\nSUCCESS: Database reset complete!")
print("\nTables created:")
print("  - users")
print("  - wallets")
print("  - wallet_transfers")
print("  - offline_transactions")
print("  - offline_receiver_syncs")
print("  - device_ledger_heads")
print("  - refresh_tokens")
print("  - otp_challenges")
