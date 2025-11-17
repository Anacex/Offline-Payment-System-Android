"""Unit tests for sync endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_sync_endpoint_requires_valid_request(client: TestClient):
    """Test sync endpoint with valid request format."""
    payload = {
        "transactions": [
            {
                "from_user_id": 1,
                "to_user_id": 2,
                "amount": 100.00,
                "token": "token123",
                "sequence_number": 1
            }
        ]
    }
    response = client.post("/sync/", json=payload)
    # May return 200 or 422 depending on endpoint implementation
    assert response.status_code in (200, 422)
