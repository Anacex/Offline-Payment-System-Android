
import sys
import sys
import os
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Create a temporary file-based SQLite DB for pytest runs.
# This avoids SQLite :memory: thread issues when TestClient runs app code
# in worker threads. We set DATABASE_URL before importing the app so
# the app's engine (if created at import) picks it up.
tmpdir = tempfile.mkdtemp(prefix="pytest_sqlite_")
test_db_path = os.path.join(tmpdir, "test_db.sqlite")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["REQUIRE_SSL"] = "False"
os.environ["SECRET_KEY"] = "test-secret-only"
os.environ["DEBUG"] = "True"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import app and DB base AFTER setting DATABASE_URL
from app.main import app
from app.core import db as db_module

# Import Base (declarative base) from the project. Adjust if located elsewhere.
try:
    from app.core.db import Base
except Exception:
    # fallback location
    from app.models.base import Base

# Create a SQLAlchemy engine for tests with check_same_thread disabled
test_engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create all tables on the test engine
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="session")
def db_engine():
    """Provide the test engine for session-scoped use and cleanup."""
    yield test_engine


@pytest.fixture(scope="function")
def db_session(db_engine) -> Session:
    """Provide a fresh session for each test using a transaction that is
    rolled back at the end of the test to keep the DB clean between tests.
    """
    # Use a connection + transaction to isolate tests and rollback changes
    connection = db_engine.connect()
    transaction = connection.begin()
    SessionForTest = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionForTest()
    try:
        yield session
    finally:
        session.close()
        # rollback any changes made during the test
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """Provide TestClient with overridden DB dependency that yields
    sessions from the temporary test DB.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    # Override the app's get_db dependency
    app.dependency_overrides[db_module.get_db] = override_get_db

    with TestClient(app) as tc:
        yield tc

    # Clear overrides after each test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session: Session):
    """Create and return a test user."""
    from app.models import User
    from app.core import security

    user = User(
        name="Test User",
        email="test@example.com",
        phone="1234567890",
        password_hash=security.get_password_hash("TestPassword123!"),
        is_email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return {"user": user, "email": user.email, "password": "TestPassword123!"}


@pytest.fixture(scope="function")
def test_user_with_wallets(db_session: Session, test_user):
    """Create user with current and offline wallets."""
    from app.models import Wallet
    from app.core.crypto import CryptoManager

    user = test_user["user"]
    current_wallet = Wallet(
        user_id=user.id, wallet_type="current", currency="PKR", balance=10000.00, is_active=True
    )
    db_session.add(current_wallet)

    public_key, private_key = CryptoManager.generate_key_pair()
    # Give offline wallet some initial balance to allow create-local tests
    offline_wallet = Wallet(
        user_id=user.id,
        wallet_type="offline",
        currency="PKR",
        balance=1000.00,
        public_key=public_key,
        private_key_encrypted=private_key,
        is_active=True,
    )
    db_session.add(offline_wallet)
    db_session.commit()
    db_session.refresh(current_wallet)
    db_session.refresh(offline_wallet)

    return {**test_user, "current_wallet": current_wallet, "offline_wallet": offline_wallet}


def pytest_sessionfinish(session, exitstatus):
    """Cleanup temporary DB files after the entire pytest session."""
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass