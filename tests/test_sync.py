"""Unit tests for sync endpoints."""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from decimal import Decimal
import json
from app.core.crypto import CryptoManager


def get_auth_headers(client: TestClient, test_user, device_fingerprint=None):
    """Helper to get valid auth headers by logging in."""
    import secrets
    # Use unique device fingerprint for each call to avoid refresh token conflicts
    if device_fingerprint is None:
        device_fingerprint = f"device_{secrets.token_hex(8)}"
    
    payload = {
        "email": test_user["email"],
        "password": test_user["password"],
        "device_fingerprint": device_fingerprint
    }
    login_resp = client.post("/auth/login", json=payload)
    login_body = login_resp.json()
    
    # Use nonce_demo if available, otherwise use a default nonce
    nonce = login_body.get("nonce_demo") or "nonce123"
    
    confirm_payload = {
        "email": test_user["email"],
        "otp": "anyotp",
        "nonce": nonce,
        "device_fingerprint": device_fingerprint
    }
    confirm_resp = client.post("/auth/login/confirm", json=confirm_payload)
    
    # Check if login was successful
    if confirm_resp.status_code != 200:
        raise Exception(f"Login failed: {confirm_resp.status_code} - {confirm_resp.json()}")
    
    token = confirm_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_transaction_data(sender_wallet_id, receiver_public_key, amount, nonce=None):
    """Helper to create valid transaction data for testing."""
    if nonce is None:
        nonce = CryptoManager.generate_nonce()
    
    transaction_data = {
        "sender_wallet_id": sender_wallet_id,
        "receiver_public_key": receiver_public_key,
        "amount": str(amount),
        "currency": "PKR",
        "nonce": nonce,
        "timestamp": datetime.utcnow().isoformat()
    }
    return transaction_data


def create_sync_transaction_request(transaction_data, signature, receipt=None):
    """Helper to create sync transaction request."""
    if receipt is None:
        receipt = CryptoManager.create_transaction_receipt(
            sender_wallet_id=transaction_data["sender_wallet_id"],
            receiver_public_key=transaction_data["receiver_public_key"],
            amount=float(transaction_data["amount"]),
            currency=transaction_data["currency"],
            nonce=transaction_data["nonce"],
            signature=signature,
            timestamp=transaction_data["timestamp"]
        )
    
    return {
        "transaction_data": transaction_data,
        "signature": signature,
        "receipt": receipt,
        "device_fingerprint": "test_device_123"
    }


@pytest.mark.unit
def test_sync_endpoint_requires_auth(client: TestClient):
    """Test that sync endpoint requires authentication."""
    payload = {"transactions": []}
    response = client.post("/api/v1/offline-transactions/sync", json=payload)
    assert response.status_code == 401


@pytest.mark.unit
def test_sync_empty_transactions(client: TestClient, test_user):
    """Test syncing with empty transaction list."""
    headers = get_auth_headers(client, test_user)
    
    payload = {"transactions": []}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 0
    assert len(body["results"]) == 0
    assert "message" in body


@pytest.mark.unit
def test_sync_missing_required_fields(client: TestClient, test_user_with_wallets):
    """Test sync fails when required fields are missing."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Missing receiver_public_key
    transaction_data = {
        "sender_wallet_id": offline_wallet.id,
        "amount": "50.00",
        "currency": "PKR",
        "nonce": CryptoManager.generate_nonce()
    }
    
    payload = {
        "transactions": [{
            "transaction_data": transaction_data,
            "signature": "fake_signature"
        }]
    }
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert len(body["results"]) == 1
    assert body["results"][0]["result"] == "failed"
    assert "Missing required fields" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_missing_signature(client: TestClient, test_user_with_wallets):
    """Test sync fails when signature is missing."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00
    )
    
    payload = {
        "transactions": [{
            "transaction_data": transaction_data
            # Missing signature
        }]
    }
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Signature field is missing" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_invalid_sender_wallet(client: TestClient, test_user_with_wallets):
    """Test sync fails when sender wallet doesn't exist or doesn't belong to user."""
    headers = get_auth_headers(client, test_user_with_wallets)
    
    transaction_data = create_test_transaction_data(
        99999,  # Non-existent wallet ID
        "receiver_public_key_123",
        50.00
    )
    
    signature = "fake_signature"
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Sender wallet not found" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_invalid_amount_zero(client: TestClient, test_user_with_wallets):
    """Test sync fails when amount is zero or negative."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Test with zero amount
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        0.00
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Amount must be greater than 0" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_duplicate_nonce(client: TestClient, test_user_with_wallets, db_session):
    """Test sync fails when nonce already exists (replay attack prevention)."""
    from app.models.wallet import OfflineTransaction
    
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Create a transaction with a specific nonce
    nonce = CryptoManager.generate_nonce()
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
        nonce=nonce
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    
    # First, create an existing transaction with this nonce
    existing_tx = OfflineTransaction(
        sender_wallet_id=offline_wallet.id,
        receiver_public_key="receiver_public_key_123",
        amount=Decimal("50.00"),
        currency="PKR",
        transaction_signature=signature,
        nonce=nonce,
        receipt_hash="hash123",
        receipt_data="{}",
        status="synced",
        created_at_device=datetime.utcnow()
    )
    db_session.add(existing_tx)
    db_session.commit()
    
    # Try to sync the same transaction again
    sync_req = create_sync_transaction_request(transaction_data, signature)
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Duplicate transaction" in body["results"][0]["error_reason"] or "nonce already exists" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_success_single_transaction(client: TestClient, test_user_with_wallets, db_session):
    """Test successful sync of a single transaction with balance updates."""
    from app.models.wallet import Wallet
    
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Create receiver wallet
    receiver_public_key, receiver_private_key = CryptoManager.generate_key_pair()
    receiver_wallet = Wallet(
        user_id=test_user_with_wallets["user"].id,
        wallet_type="offline",
        currency="PKR",
        balance=100.00,
        public_key=receiver_public_key,
        private_key_encrypted=receiver_private_key,
        bank_account_number="receiver_account_123",
        is_active=True,
    )
    db_session.add(receiver_wallet)
    db_session.commit()
    db_session.refresh(receiver_wallet)
    
    # Get initial balances
    db_session.refresh(offline_wallet)
    initial_sender_balance = Decimal(str(offline_wallet.balance))
    initial_receiver_balance = Decimal(str(receiver_wallet.balance))
    transfer_amount = Decimal("50.00")
    
    # Create transaction
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        float(transfer_amount)
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 1
    assert body["total_failed"] == 0
    assert len(body["results"]) == 1
    assert body["results"][0]["result"] == "synced"
    assert body["results"][0]["transaction_id"] is not None
    assert body["results"][0]["error_reason"] is None
    
    # Verify balances were updated
    db_session.refresh(offline_wallet)
    db_session.refresh(receiver_wallet)
    
    expected_sender_balance = initial_sender_balance - transfer_amount
    expected_receiver_balance = initial_receiver_balance + transfer_amount
    
    assert Decimal(str(offline_wallet.balance)) == expected_sender_balance
    assert Decimal(str(receiver_wallet.balance)) == expected_receiver_balance


@pytest.mark.unit
def test_sync_multiple_transactions_mixed_results(client: TestClient, test_user_with_wallets, db_session):
    """Test syncing multiple transactions where some succeed and some fail."""
    from app.models.wallet import Wallet
    
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Create receiver wallet
    receiver_public_key, receiver_private_key = CryptoManager.generate_key_pair()
    receiver_wallet = Wallet(
        user_id=test_user_with_wallets["user"].id,
        wallet_type="offline",
        currency="PKR",
        balance=100.00,
        public_key=receiver_public_key,
        private_key_encrypted=receiver_private_key,
        bank_account_number="receiver_account_123",
        is_active=True,
    )
    db_session.add(receiver_wallet)
    db_session.commit()
    db_session.refresh(receiver_wallet)
    
    transactions = []
    
    # Valid transaction 1
    tx1_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        25.00
    )
    tx1_signature = CryptoManager.sign_transaction(tx1_data, offline_wallet.private_key_encrypted)
    transactions.append(create_sync_transaction_request(tx1_data, tx1_signature))
    
    # Invalid transaction - missing amount
    tx2_data = {
        "sender_wallet_id": offline_wallet.id,
        "receiver_public_key": receiver_public_key,
        "currency": "PKR",
        "nonce": CryptoManager.generate_nonce(),
        "timestamp": datetime.utcnow().isoformat()
    }
    transactions.append({
        "transaction_data": tx2_data,
        "signature": "fake_signature"
    })
    
    # Valid transaction 2
    tx3_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        30.00
    )
    tx3_signature = CryptoManager.sign_transaction(tx3_data, offline_wallet.private_key_encrypted)
    transactions.append(create_sync_transaction_request(tx3_data, tx3_signature))
    
    # Invalid transaction - zero amount
    tx4_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        0.00
    )
    tx4_signature = CryptoManager.sign_transaction(tx4_data, offline_wallet.private_key_encrypted)
    transactions.append(create_sync_transaction_request(tx4_data, tx4_signature))
    
    payload = {"transactions": transactions}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 2
    assert body["total_failed"] == 2
    assert len(body["results"]) == 4
    
    # Check results
    synced_results = [r for r in body["results"] if r["result"] == "synced"]
    failed_results = [r for r in body["results"] if r["result"] == "failed"]
    
    assert len(synced_results) == 2
    assert len(failed_results) == 2
    
    # Verify all synced transactions have transaction_id
    for result in synced_results:
        assert result["transaction_id"] is not None
        assert result["error_reason"] is None
    
    # Verify all failed transactions have error_reason
    for result in failed_results:
        assert result["error_reason"] is not None


@pytest.mark.unit
def test_sync_receiver_wallet_not_found(client: TestClient, test_user_with_wallets):
    """Test sync succeeds even if receiver wallet doesn't exist (will be created later)."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Use a public key that doesn't match any wallet
    receiver_public_key, _ = CryptoManager.generate_key_pair()
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        50.00
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    # Transaction should still sync successfully even if receiver wallet not found
    # (receiver balance won't be updated, but transaction is recorded)
    assert body["total_synced"] == 1
    assert body["results"][0]["result"] == "synced"


@pytest.mark.unit
def test_sync_invalid_amount_format(client: TestClient, test_user_with_wallets):
    """Test sync fails with invalid amount format."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00
    )
    transaction_data["amount"] = "not_a_number"  # Invalid format
    
    signature = "fake_signature"
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Invalid amount format" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_response_structure(client: TestClient, test_user_with_wallets, db_session):
    """Test that sync response has correct structure."""
    from app.models.wallet import Wallet
    
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    receiver_public_key, receiver_private_key = CryptoManager.generate_key_pair()
    receiver_wallet = Wallet(
        user_id=test_user_with_wallets["user"].id,
        wallet_type="offline",
        currency="PKR",
        balance=100.00,
        public_key=receiver_public_key,
        private_key_encrypted=receiver_private_key,
        is_active=True,
    )
    db_session.add(receiver_wallet)
    db_session.commit()
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        50.00
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    
    # Verify response structure
    assert "message" in body
    assert "results" in body
    assert "total_synced" in body
    assert "total_failed" in body
    
    # Verify result structure
    if len(body["results"]) > 0:
        result = body["results"][0]
        assert "transaction_id" in result or result.get("transaction_id") is None
        assert "reference" in result
        assert "result" in result
        assert result["result"] in ["synced", "failed"]
        if result["result"] == "failed":
            assert "error_reason" in result
