"""Unit tests for authentication endpoints."""
import pytest
import uuid
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_signup_success(client: TestClient):
    """Test successful user signup with valid data."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "Test User",
        "email": email,
        "password": "Str0ngP@ssw0rd!",
        "phone": "1234567890",
        "role": "payer"
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert "otp_demo" in body or "msg" in body
    assert "User created" in body.get("msg", "")


@pytest.mark.unit
def test_signup_duplicate_email(client: TestClient, test_user):
    """Test signup fails with duplicate email."""
    email = test_user["email"]
    payload = {
        "name": "Another User",
        "email": email,
        "password": "NewPassword123!",
        "phone": "0987654321"
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_signup_weak_password(client: TestClient):
    """Test signup fails with weak password (no special char, lowercase, uppercase, digit)."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "Test User",
        "email": email,
        "password": "weak",  # Too short and missing requirements
        "phone": "1234567890"
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422
    assert "complexity" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_signup_missing_required_fields(client: TestClient):
    """Test signup fails when required fields are missing."""
    payload = {
        "name": "Test User",
        "email": "test@example.com"
        # Missing password
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.unit
def test_verify_email_success(client: TestClient, test_user):
    """Test email verification succeeds for a valid user."""
    email = test_user["email"]
    payload = {
        "email": email,
        "otp": "anything"  # Demo accepts any OTP
    }
    response = client.post("/auth/verify-email", json=payload)
    assert response.status_code == 200
    assert response.json().get("msg") == "Email verified"


@pytest.mark.unit
def test_verify_email_nonexistent_user(client: TestClient):
    """Test email verification fails for non-existent user."""
    payload = {
        "email": "nonexistent@example.com",
        "otp": "anyotp"
    }
    response = client.post("/auth/verify-email", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_login_success(client: TestClient, test_user):
    """Test login step 1: credential check and MFA OTP generation."""
    payload = {
        "email": test_user["email"],
        "password": test_user["password"],
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "nonce_demo" in body or "otp_demo" in body


@pytest.mark.unit
def test_login_wrong_password(client: TestClient, test_user):
    """Test login fails with wrong password."""
    payload = {
        "email": test_user["email"],
        "password": "WrongPassword123!",
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert "invalid" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_login_unverified_email(client: TestClient, db_session):
    """Test login fails when email is not verified."""
    from app.models import User
    from app.core import security
    
    # Create unverified user
    user = User(
        name="Unverified User",
        email="unverified@example.com",
        phone="1234567890",
        password_hash=security.get_password_hash("TestPassword123!"),
        is_email_verified=False,  # Not verified
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    payload = {
        "email": user.email,
        "password": "TestPassword123!",
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert "not verified" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_login_confirm_success(client: TestClient, test_user):
    """Test login step 2: OTP verification and token issuance."""
    payload = {
        "email": test_user["email"],
        "otp": "anyotp",  # Demo accepts any OTP
        "nonce": "nonce123",
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login/confirm", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "refresh_token" in body


@pytest.mark.unit
def test_login_confirm_nonexistent_user(client: TestClient):
    """Test login confirm fails for non-existent user."""
    payload = {
        "email": "nonexistent@example.com",
        "otp": "anyotp",
        "nonce": "nonce123",
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login/confirm", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_token_refresh_success(client: TestClient, test_user, db_session):
    """Test refresh token endpoint returns new access token."""
    from app.models_refresh_token import RefreshToken
    from app.core import security
    
    user = test_user["user"]
    refresh_token, expires_at = security.create_refresh_token(
        subject=str(user.id),
        device_fingerprint="device123"
    )
    
    # Store refresh token in DB
    rt = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        device_fingerprint="device123",
        expires_at=expires_at
    )
    db_session.add(rt)
    db_session.commit()
    
    payload = {
        "refresh_token": refresh_token,
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/token/refresh", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.unit
def test_logout_success(client: TestClient, test_user, db_session):
    """Test logout revokes the refresh token."""
    from app.models_refresh_token import RefreshToken
    from app.core import security
    
    user = test_user["user"]
    refresh_token, expires_at = security.create_refresh_token(
        subject=str(user.id),
        device_fingerprint="device123"
    )
    
    # Store refresh token in DB
    rt = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        device_fingerprint="device123",
        expires_at=expires_at
    )
    db_session.add(rt)
    db_session.commit()
    
    # For single-body string param, send the raw string as the JSON body
    response = client.post("/auth/logout", json=refresh_token)
    # Debug: print validation errors if any
    try:
        print('logout response body:', response.json())
    except Exception:
        print('logout response text:', response.text)
    assert response.status_code == 200
    assert "logged out" in response.json().get("msg", "").lower()
