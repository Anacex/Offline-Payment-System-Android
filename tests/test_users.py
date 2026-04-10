"""Unit tests for user management endpoints."""
import pytest
from fastapi.testclient import TestClient

from tests.auth_helpers import get_auth_headers


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
