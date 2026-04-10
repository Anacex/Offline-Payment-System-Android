"""
Reset database - Drop all tables and recreate them.
WARNING: This will delete all data!
"""

from app.core.db import engine, Base
from app.models import User, Wallet, OfflineTransaction, WalletTransfer, Transaction
from app.models_refresh_token import RefreshToken

print("WARNING: This will delete all existing data!")
print("Dropping all tables...")

# Drop all tables
Base.metadata.drop_all(bind=engine)
print("All tables dropped")

print("\nCreating fresh tables...")
# Create all tables
Base.metadata.create_all(bind=engine)

print("\nSUCCESS: Database reset complete!")
print("\nTables created:")
print("  - users")
print("  - wallets")
print("  - wallet_transfers")
print("  - offline_transactions")
print("  - transactions")
print("  - refresh_tokens")
