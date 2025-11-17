"""Unit tests for offline transaction endpoints."""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json


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
def test_create_offline_transaction_local_requires_auth(client: TestClient):
    """Test that offline transaction endpoint requires authentication."""
    payload = {
        "sender_wallet_id": 1,
        "receiver_qr_data": {"public_key": "test"},
        "amount": 100.00,
        "currency": "PKR",
        "created_at_device": datetime.utcnow().isoformat()
    }
    response = client.post("/api/v1/offline-transactions/create-local", json=payload)
    assert response.status_code == 401


@pytest.mark.unit
def test_create_offline_transaction_local_success(client: TestClient, test_user_with_wallets):
    """Test creating offline transaction locally."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    payload = {
        "sender_wallet_id": offline_wallet.id,
        "receiver_qr_data": {
            "public_key": "test_receiver_public_key_123",
            "user_id": 999,
            "wallet_id": 888
        },
        "amount": 50.00,
        "currency": "PKR",
        "created_at_device": datetime.utcnow().isoformat()
    }
    response = client.post("/api/v1/offline-transactions/create-local", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert "transaction_data" in body
    assert "nonce" in body
    assert body["transaction_data"]["amount"] == "50.00"


@pytest.mark.unit
def test_create_offline_transaction_insufficient_balance(client: TestClient, test_user_with_wallets):
    """Test offline transaction fails with insufficient balance."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    payload = {
        "sender_wallet_id": offline_wallet.id,
        "receiver_qr_data": {"public_key": "test_key"},
        "amount": 999999.00,  # Insufficient
        "currency": "PKR",
        "created_at_device": datetime.utcnow().isoformat()
    }
    response = client.post("/api/v1/offline-transactions/create-local", json=payload, headers=headers)
    assert response.status_code == 400
    assert "insufficient" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_create_offline_transaction_invalid_qr(client: TestClient, test_user_with_wallets):
    """Test offline transaction fails with invalid QR data (missing public key)."""
    headers = get_auth_headers(client, test_user_with_wallets)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    payload = {
        "sender_wallet_id": offline_wallet.id,
        "receiver_qr_data": {},  # Missing public_key
        "amount": 50.00,
        "currency": "PKR",
        "created_at_device": datetime.utcnow().isoformat()
    }
    response = client.post("/api/v1/offline-transactions/create-local", json=payload, headers=headers)
    assert response.status_code == 400
    assert "invalid qr" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_sync_offline_transactions_requires_auth(client: TestClient):
    """Test that sync endpoint requires authentication."""
    payload = {"transactions": []}
    response = client.post("/api/v1/offline-transactions/sync", json=payload)
    assert response.status_code == 401


@pytest.mark.unit
def test_sync_offline_transactions_empty(client: TestClient, test_user):
    """Test syncing with empty transaction list."""
    headers = get_auth_headers(client, test_user)
    
    payload = {"transactions": []}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 0


@pytest.mark.unit
def test_list_offline_transactions(client: TestClient, test_user):
    """Test listing offline transactions."""
    headers = get_auth_headers(client, test_user)
    
    response = client.get("/api/v1/offline-transactions/", headers=headers)
    assert response.status_code == 200
    transactions = response.json()
    assert isinstance(transactions, list)


@pytest.mark.unit
def test_verify_receipt(client: TestClient):
    """Test receipt verification endpoint."""
    payload = {
        "receipt_data": {
            "sender_wallet_id": 1,
            "receiver_public_key": "receiver_key",
            "amount": 100.00,
            "currency": "PKR",
            "nonce": "nonce123",
            "timestamp": datetime.utcnow().isoformat(),
            "receipt_hash": "hash123"
        },
        "signature": "sig123",
        "sender_public_key": "sender_key"
    }
    response = client.post("/api/v1/offline-transactions/verify-receipt", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "valid" in body
    assert "signature_valid" in body
    assert "hash_valid" in body
