# app/db_init.py
from app.core.db import engine, Base
# import models so they are registered on the Base metadata
from app.models import User, Wallet, OfflineTransaction, WalletTransfer, Transaction
from app.models_refresh_token import RefreshToken

def init():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("SUCCESS: All tables created successfully!")
    print("")
    print("Tables created:")
    print("  - users")
    print("  - wallets")
    print("  - wallet_transfers")
    print("  - offline_transactions")
    print("  - transactions")
    print("  - refresh_tokens")
    print("")
    print("Database is ready for use!")

if __name__ == "__main__":
    init()
