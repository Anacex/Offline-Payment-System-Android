"""Unit tests for user management endpoints."""
import pytest
from fastapi.testclient import TestClient


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
def test_list_users_requires_auth(client: TestClient):
    """Test that listing users requires authentication."""
    response = client.get("/api/v1/users/")
    # HTTPBearer used in deps returns 403 when auth is missing; accept 403
    assert response.status_code == 403


@pytest.mark.unit
def test_list_users_requires_admin(client: TestClient, test_user):
    """Test that listing users requires admin privileges."""
    headers = get_auth_headers(client, test_user)
    
    response = client.get("/api/v1/users/", headers=headers)
    assert response.status_code == 403
    assert "admin" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_create_user_requires_admin(client: TestClient, test_user):
    """Test that creating users requires admin privileges."""
    headers = get_auth_headers(client, test_user)
    
    payload = {
        "name": "New User",
        "email": "newuser@example.com",
        "phone": "0987654321",
        "password": "SecurePass123!"
    }
    response = client.post("/api/v1/users/", json=payload, headers=headers)
    assert response.status_code == 403
    assert "admin" in response.json().get("detail", "").lower()
