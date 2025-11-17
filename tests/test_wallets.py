"""Unit tests for wallet management endpoints."""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal


def get_auth_headers(client: TestClient, test_user):
    """Helper to get valid auth headers by logging in."""
    payload = {
        "email": test_user["email"],
        "password": test_user["password"],
        "device_fingerprint": "device123"
    }
    login_resp = client.post("/auth/login", json=payload)
    login_body = login_resp.json()
    
    confirm_payload = {
        "email": test_user["email"],
        "otp": "anyotp",
        "nonce": login_body.get("nonce_demo"),
        "device_fingerprint": "device123"
    }
    confirm_resp = client.post("/auth/login/confirm", json=confirm_payload)
    token = confirm_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.unit
def test_create_current_wallet(client: TestClient, test_user):
    """Test creating a current wallet."""
    headers = get_auth_headers(client, test_user)
    
    payload = {
        "wallet_type": "current",
        "currency": "PKR"
    }
    response = client.post("/api/v1/wallets/", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["wallet_type"] == "current"
    assert body["currency"] == "PKR"
    # API returns Decimal as string; compare using Decimal for accuracy
    assert Decimal(body["balance"]) == Decimal("0.00")
    assert body["is_active"] is True


@pytest.mark.unit
def test_create_offline_wallet(client: TestClient, test_user):
    """Test creating an offline wallet with auto-generated RSA keys."""
    headers = get_auth_headers(client, test_user)
    
    payload = {
        "wallet_type": "offline",
        "currency": "PKR"
    }
    response = client.post("/api/v1/wallets/", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["wallet_type"] == "offline"
    assert body["currency"] == "PKR"
    assert body["public_key"] is not None


@pytest.mark.unit
def test_create_duplicate_wallet_type(client: TestClient, test_user, db_session):
    """Test that user cannot create two current wallets."""
    from app.models import Wallet
    
    headers = get_auth_headers(client, test_user)
    
    # Create first current wallet
    payload = {"wallet_type": "current", "currency": "PKR"}
    resp1 = client.post("/api/v1/wallets/", json=payload, headers=headers)
    assert resp1.status_code == 201
    
    # Attempt to create second current wallet
    resp2 = client.post("/api/v1/wallets/", json=payload, headers=headers)
    assert resp2.status_code == 400
    assert "already has" in resp2.json().get("detail", "").lower()


@pytest.mark.unit
def test_list_wallets(client: TestClient, test_user_with_wallets):
    """Test listing user's wallets."""
    headers = get_auth_headers(client, test_user_with_wallets)
    
    response = client.get("/api/v1/wallets/", headers=headers)
    assert response.status_code == 200
    wallets = response.json()
    assert isinstance(wallets, list)
    assert len(wallets) >= 2  # current + offline
    assert any(w["wallet_type"] == "current" for w in wallets)
    assert any(w["wallet_type"] == "offline" for w in wallets)


@pytest.mark.unit
def test_list_wallets_requires_auth(client: TestClient):
    """Test that listing wallets requires authentication."""
    response = client.get("/api/v1/wallets/")
    # Missing Authorization should return 401 Unauthorized from the auth dependency
    assert response.status_code == 401


@pytest.mark.unit
def test_get_wallet_by_id(client: TestClient, test_user_with_wallets):
    """Test retrieving a specific wallet."""
    headers = get_auth_headers(client, test_user_with_wallets)
    wallet_id = test_user_with_wallets["current_wallet"].id
    
    response = client.get(f"/api/v1/wallets/{wallet_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == wallet_id
    assert body["wallet_type"] == "current"


@pytest.mark.unit
def test_get_wallet_not_found(client: TestClient, test_user_with_wallets):
    """Test that accessing non-existent wallet returns 404."""
    headers = get_auth_headers(client, test_user_with_wallets)
    
    response = client.get("/api/v1/wallets/99999", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_transfer_between_wallets_success(client: TestClient, test_user_with_wallets, db_session):
    """Test transferring money from current to offline wallet."""
    headers = get_auth_headers(client, test_user_with_wallets)
    from_wallet_id = test_user_with_wallets["current_wallet"].id
    to_wallet_id = test_user_with_wallets["offline_wallet"].id
    
    payload = {
        "from_wallet_id": from_wallet_id,
        "to_wallet_id": to_wallet_id,
        "amount": 500.00,
        "currency": "PKR"
    }
    response = client.post("/api/v1/wallets/transfer", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["from_wallet_id"] == from_wallet_id
    assert body["to_wallet_id"] == to_wallet_id
    # API serializes amounts as strings; compare numerically
    assert Decimal(str(body["amount"])) == Decimal("500.00")
    assert body["status"] == "completed"
    
    # Verify balances updated by re-querying fresh objects from the DB
    from app.models import Wallet as WalletModel
    current = db_session.get(WalletModel, from_wallet_id)
    offline = db_session.get(WalletModel, to_wallet_id)
    assert current.balance == Decimal("9500.00")
    # conftest seeds the offline wallet with 1000.00, after transferring 500 it should be 1500.00
    assert offline.balance == Decimal("1500.00")


@pytest.mark.unit
def test_transfer_insufficient_balance(client: TestClient, test_user_with_wallets):
    """Test transfer fails with insufficient balance."""
    headers = get_auth_headers(client, test_user_with_wallets)
    from_wallet_id = test_user_with_wallets["current_wallet"].id
    to_wallet_id = test_user_with_wallets["offline_wallet"].id
    
    payload = {
        "from_wallet_id": from_wallet_id,
        "to_wallet_id": to_wallet_id,
        "amount": 999999.00,  # Insufficient balance
        "currency": "PKR"
    }
    response = client.post("/api/v1/wallets/transfer", json=payload, headers=headers)
    assert response.status_code == 400
    assert "insufficient" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_transfer_wallet_not_found(client: TestClient, test_user_with_wallets):
    """Test transfer fails when wallet not found."""
    headers = get_auth_headers(client, test_user_with_wallets)
    
    payload = {
        "from_wallet_id": 99999,
        "to_wallet_id": test_user_with_wallets["offline_wallet"].id,
        "amount": 100.00,
        "currency": "PKR"
    }
    response = client.post("/api/v1/wallets/transfer", json=payload, headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_get_transfer_history(client: TestClient, test_user_with_wallets):
    """Test retrieving wallet transfer history."""
    headers = get_auth_headers(client, test_user_with_wallets)
    
    # Do a transfer first
    payload = {
        "from_wallet_id": test_user_with_wallets["current_wallet"].id,
        "to_wallet_id": test_user_with_wallets["offline_wallet"].id,
        "amount": 100.00,
        "currency": "PKR"
    }
    client.post("/api/v1/wallets/transfer", json=payload, headers=headers)
    
    # Get history
    response = client.get("/api/v1/wallets/transfers/history", headers=headers)
    assert response.status_code == 200
    transfers = response.json()
    assert isinstance(transfers, list)
    assert len(transfers) > 0


@pytest.mark.unit
def test_generate_qr_code(client: TestClient, test_user_with_wallets):
    """Test QR code generation for offline wallet."""
    headers = get_auth_headers(client, test_user_with_wallets)
    wallet_id = test_user_with_wallets["offline_wallet"].id
    
    payload = {"wallet_id": wallet_id}
    response = client.post("/api/v1/wallets/qr-code", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "qr_data" in body
    assert "qr_image_base64" in body
    assert body["qr_data"]["public_key"] is not None


@pytest.mark.unit
def test_get_private_key(client: TestClient, test_user_with_wallets):
    """Test retrieving private key for offline wallet."""
    headers = get_auth_headers(client, test_user_with_wallets)
    wallet_id = test_user_with_wallets["offline_wallet"].id
    
    response = client.get(f"/api/v1/wallets/{wallet_id}/private-key", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "private_key" in body
    assert "warning" in body
