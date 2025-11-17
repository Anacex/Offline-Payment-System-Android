import pytest
import requests
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ============================================================================
# UNIT TESTS - Run locally against your code
# ============================================================================

@pytest.mark.unit
def test_health_check():
    """Test the health endpoint returns 200 OK"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ============================================================================
# INTEGRATION TESTS - Run against production Render server
# Uncomment and configure as needed
# ============================================================================

@pytest.mark.integration
def test_production_health_check():
    """Test health endpoint on production Render server"""
    base_url = "https://offline-payment-system-android.onrender.com"
    response = requests.get(f"{base_url}/health", timeout=10)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# @pytest.mark.integration
# def test_production_user_endpoints():
#     """Test user endpoints on production server"""
#     base_url = "https://offline-payment-system-android.onrender.com"
#     
#     # Example: Test GET /users/
#     response = requests.get(f"{base_url}/users/", timeout=10)
#     assert response.status_code in [200, 401]  # Might require auth
#     
#
# @pytest.mark.integration
# def test_production_wallet_endpoints():
#     """Test wallet endpoints on production server"""
#     base_url = "https://offline-payment-system-android.onrender.com"
#     
#     # Example: Test GET /wallet/
#     response = requests.get(f"{base_url}/wallet/", timeout=10)
#     assert response.status_code in [200, 401]  # Might require auth


# ============================================================================
# SMOKE TESTS - Quick validation tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.unit
def test_api_responds():
    """Quick smoke test - API server is responding"""
    response = client.get("/health")
    assert response.status_code == 200
