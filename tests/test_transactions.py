"""Unit tests for transaction endpoints."""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
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
def test_list_transactions_requires_auth(client: TestClient):
    """Test that listing transactions requires authentication."""
    response = client.get("/api/v1/transactions/")
    assert response.status_code == 401


@pytest.mark.unit
def test_list_transactions_empty(client: TestClient, test_user):
    """Test listing transactions returns empty list for new user."""
    headers = get_auth_headers(client, test_user)
    
    response = client.get("/api/v1/transactions/", headers=headers)
    assert response.status_code == 200
    transactions = response.json()
    assert isinstance(transactions, list)


@pytest.mark.unit
def test_create_transaction_requires_auth(client: TestClient):
    """Test that creating transactions requires authentication."""
    tx_payload = {
        "sender_id": 1,
        "receiver_id": 2,
        "amount": 100.00,
        "currency": "PKR",
        "reference": "ref123"
    }
    response = client.post("/api/v1/transactions/", json=tx_payload)
    assert response.status_code == 401


@pytest.mark.unit
def test_create_transaction_invalid_users(client: TestClient, test_user):
    """Test transaction creation fails with invalid sender/receiver."""
    headers = get_auth_headers(client, test_user)
    
    tx_payload = {
        "sender_id": 99999,  # Non-existent user
        "receiver_id": 88888,  # Non-existent user
        "amount": 100.00,
        "currency": "PKR",
        "reference": "ref123"
    }
    response = client.post("/api/v1/transactions/", json=tx_payload, headers=headers)
    assert response.status_code == 400
    assert "invalid" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_create_transaction_duplicate_reference(client: TestClient, test_user, test_user_with_wallets, db_session):
    """Test transaction creation fails with duplicate reference."""
    from app.models import Transaction
    
    headers = get_auth_headers(client, test_user_with_wallets)
    
    # Create first transaction
    tx_payload = {
        "sender_id": test_user_with_wallets["user"].id,
        "receiver_id": test_user["user"].id,
        "amount": 100.00,
        "currency": "PKR",
        "reference": "unique-ref-123"
    }
    client.post("/api/v1/transactions/", json=tx_payload, headers=headers)
    
    # Attempt to create with same reference
    response = client.post("/api/v1/transactions/", json=tx_payload, headers=headers)
    assert response.status_code == 409
    assert "duplicate" in response.json().get("detail", "").lower()
