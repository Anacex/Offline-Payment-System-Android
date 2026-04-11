"""Unit tests for authentication endpoints."""
import uuid

import pytest
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
def test_verify_email_success(client: TestClient):
    """Signup issues a real OTP challenge; verify-email must accept that code."""
    email = f"verify_{uuid.uuid4().hex[:8]}@example.com"
    signup_payload = {
        "name": "Verify User",
        "email": email,
        "password": "Str0ngP@ssw0rd!",
        "phone": "1234567890",
        "role": "payer",
    }
    signup_resp = client.post("/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201
    otp = signup_resp.json().get("otp_demo")
    assert otp, "DEBUG must be true in tests so otp_demo is returned from signup"

    response = client.post("/auth/verify-email", json={"email": email, "otp": otp})
    assert response.status_code == 200
    assert response.json().get("msg") == "Email verified"


@pytest.mark.unit
def test_verify_email_nonexistent_user(client: TestClient):
    """No OTP challenge exists for unknown email -> invalid code (400)."""
    payload = {
        "email": "nonexistent@example.com",
        "otp": "anyotp"
    }
    response = client.post("/auth/verify-email", json=payload)
    assert response.status_code == 400
    assert "invalid" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_login_success(client: TestClient, test_user):
    """Verified users get tokens immediately; unverified users get OTP challenge."""
    payload = {
        "email": test_user["email"],
        "password": test_user["password"],
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    if body.get("requires_otp") is False:
        assert "access_token" in body
        assert body.get("token_type") == "bearer"
    else:
        assert "nonce_demo" in body
        assert body.get("otp_demo")


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
    """Unverified users can start login: step 1 returns OTP challenge (not 401)."""
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
    assert response.status_code == 200
    body = response.json()
    assert body.get("requires_otp") is True
    assert body.get("nonce_demo")
    assert body.get("otp_demo")


@pytest.mark.unit
def test_login_confirm_success(client: TestClient, db_session):
    """Login step 2: OTP + nonce from step 1 issue tokens."""
    from app.models import User
    from app.core import security

    user = User(
        name="Confirm User",
        email="confirm_login@example.com",
        phone="1234567890",
        password_hash=security.get_password_hash("TestPassword123!"),
        is_email_verified=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    step1 = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": "TestPassword123!",
            "device_fingerprint": "device123",
        },
    )
    assert step1.status_code == 200
    b1 = step1.json()
    assert b1.get("requires_otp") is True
    otp = b1["otp_demo"]
    nonce = b1["nonce_demo"]
    assert otp and nonce

    response = client.post(
        "/auth/login/confirm",
        json={
            "email": user.email,
            "otp": otp,
            "nonce": nonce,
            "device_fingerprint": "device123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "refresh_token" in body


@pytest.mark.unit
def test_login_confirm_nonexistent_user(client: TestClient):
    """Bad nonce / OTP yields 400 before user lookup."""
    payload = {
        "email": "nonexistent@example.com",
        "otp": "anyotp",
        "nonce": "nonce123",
        "device_fingerprint": "device123"
    }
    response = client.post("/auth/login/confirm", json=payload)
    assert response.status_code == 400
    assert "invalid" in response.json().get("detail", "").lower()


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
def test_forgot_password_request_existing_user(client: TestClient, test_user):
    """Registered email returns nonce for reset flow (otp_demo when DEBUG)."""
    email = test_user["email"]
    response = client.post("/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    body = response.json()
    assert "msg" in body
    assert body.get("nonce_demo")
    if body.get("otp_demo"):
        assert len(body["otp_demo"]) == 6


@pytest.mark.unit
def test_forgot_password_request_unknown_email(client: TestClient):
    """Unknown email: generic message, no nonce (no enumeration)."""
    response = client.post(
        "/auth/forgot-password",
        json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "msg" in body
    assert body.get("nonce_demo") is None


@pytest.mark.unit
def test_forgot_password_confirm_success(client: TestClient, test_user):
    """After request, confirm with OTP updates password."""
    email = test_user["email"]
    req = client.post("/auth/forgot-password", json={"email": email})
    assert req.status_code == 200
    nonce = req.json()["nonce_demo"]
    otp = req.json().get("otp_demo")
    assert nonce and otp, "DEBUG must be true for otp_demo in tests"

    new_pw = "N3wStr0ng!Pass"
    confirm = client.post(
        "/auth/forgot-password/confirm",
        json={
            "email": email,
            "otp": otp,
            "nonce": nonce,
            "new_password": new_pw,
            "confirm_password": new_pw,
        },
    )
    assert confirm.status_code == 200
    assert "password" in confirm.json().get("msg", "").lower() or "sign in" in confirm.json().get("msg", "").lower()

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": new_pw,
            "device_fingerprint": "device123",
        },
    )
    assert login.status_code == 200


@pytest.mark.unit
def test_forgot_password_confirm_password_mismatch(client: TestClient, test_user):
    req = client.post("/auth/forgot-password", json={"email": test_user["email"]})
    nonce = req.json()["nonce_demo"]
    otp = req.json().get("otp_demo")
    response = client.post(
        "/auth/forgot-password/confirm",
        json={
            "email": test_user["email"],
            "otp": otp,
            "nonce": nonce,
            "new_password": "Str0ngN3w!Pass",
            "confirm_password": "Different!Pass1",
        },
    )
    assert response.status_code == 422
    assert "match" in response.json().get("detail", "").lower()


@pytest.mark.unit
def test_forgot_password_confirm_weak_password(client: TestClient, test_user):
    req = client.post("/auth/forgot-password", json={"email": test_user["email"]})
    nonce = req.json()["nonce_demo"]
    otp = req.json().get("otp_demo")
    response = client.post(
        "/auth/forgot-password/confirm",
        json={
            "email": test_user["email"],
            "otp": otp,
            "nonce": nonce,
            "new_password": "weak",
            "confirm_password": "weak",
        },
    )
    assert response.status_code == 422


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
