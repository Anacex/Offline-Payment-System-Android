# Offline Payment System - API Documentation

## Overview

The Offline Payment System API enables secure offline money transfers using asymmetric cryptography. This document describes all available endpoints, request/response formats, and usage examples.

**Base URL**: `http://localhost:8000` (development)  
**API Version**: 1.0.0  
**Authentication**: Bearer JWT tokens

---

## Table of Contents

1. [Authentication](#authentication)
2. [Wallet Management](#wallet-management)
3. [Offline Transactions](#offline-transactions)
4. [User Management](#user-management)
5. [Error Handling](#error-handling)

---

## Authentication

### 1. Sign Up

Create a new user account.

**Endpoint**: `POST /auth/signup`

**Request Body**:
```json
{
  "name": "Ahmed Khan",
  "email": "ahmed@example.com",
  "password": "SecurePass@123",
  "phone": "+923001234567"
}
```

**Password Requirements**:
- Minimum 10 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character

**Response** (201):
```json
{
  "msg": "User created. Check your email for verification code (demo prints).",
  "otp_demo": "abc123xyz"
}
```

---

### 2. Verify Email

Verify user email with OTP.

**Endpoint**: `POST /auth/verify-email`

**Request Body**:
```json
{
  "email": "ahmed@example.com",
  "otp": "abc123xyz"
}
```

**Response** (200):
```json
{
  "msg": "Email verified"
}
```

---

### 3. Login (Step 1)

Initiate login and receive MFA OTP.

**Endpoint**: `POST /auth/login`

**Request Body**:
```json
{
  "email": "ahmed@example.com",
  "password": "SecurePass@123",
  "device_fingerprint": "android-device-12345"
}
```

**Response** (200):
```json
{
  "nonce_demo": "temp-nonce-abc123",
  "otp_demo": "6a3f2b"
}
```

---

### 4. Login (Step 2 - Confirm MFA)

Complete login with MFA OTP.

**Endpoint**: `POST /auth/login/confirm`

**Request Body**:
```json
{
  "email": "ahmed@example.com",
  "otp": "6a3f2b",
  "nonce": "temp-nonce-abc123",
  "device_fingerprint": "android-device-12345"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Usage**: Include access token in subsequent requests:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

### 5. Refresh Token

Get new access token using refresh token.

**Endpoint**: `POST /auth/token/refresh`

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "device_fingerprint": "android-device-12345"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### 6. Logout

Revoke refresh token.

**Endpoint**: `POST /auth/logout`

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200):
```json
{
  "msg": "Logged out"
}
```

---

## Wallet Management

All wallet endpoints require authentication.

### 1. Create Wallet

Create a new current or offline wallet.

**Endpoint**: `POST /api/v1/wallets/`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Request Body**:
```json
{
  "wallet_type": "offline",
  "currency": "PKR"
}
```

**Wallet Types**:
- `current`: Online wallet (standard banking)
- `offline`: Offline wallet with cryptographic keys

**Response** (201):
```json
{
  "id": 1,
  "user_id": 1,
  "wallet_type": "offline",
  "balance": "0.00",
  "currency": "PKR",
  "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

---

### 2. List Wallets

Get all wallets for authenticated user.

**Endpoint**: `GET /api/v1/wallets/`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
[
  {
    "id": 1,
    "user_id": 1,
    "wallet_type": "current",
    "balance": "50000.00",
    "currency": "PKR",
    "public_key": null,
    "is_active": true,
    "created_at": "2024-01-15T10:00:00",
    "updated_at": "2024-01-15T10:00:00"
  },
  {
    "id": 2,
    "user_id": 1,
    "wallet_type": "offline",
    "balance": "5000.00",
    "currency": "PKR",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
]
```

---

### 3. Get Wallet Details

Get specific wallet information.

**Endpoint**: `GET /api/v1/wallets/{wallet_id}`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
{
  "id": 2,
  "user_id": 1,
  "wallet_type": "offline",
  "balance": "5000.00",
  "currency": "PKR",
  "public_key": "-----BEGIN PUBLIC KEY-----\n...",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

---

### 4. Transfer Between Wallets (Preload Offline Wallet)

Transfer money from current wallet to offline wallet.

**Endpoint**: `POST /api/v1/wallets/transfer`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Request Body**:
```json
{
  "from_wallet_id": 1,
  "to_wallet_id": 2,
  "amount": "1000.00",
  "currency": "PKR"
}
```

**Response** (201):
```json
{
  "id": 1,
  "user_id": 1,
  "from_wallet_id": 1,
  "to_wallet_id": 2,
  "amount": "1000.00",
  "currency": "PKR",
  "status": "completed",
  "reference": "WT-A1B2C3D4E5F6G7H8",
  "timestamp": "2024-01-15T11:00:00"
}
```

---

### 5. Get Transfer History

Get wallet transfer history.

**Endpoint**: `GET /api/v1/wallets/transfers/history?limit=50`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `limit` (optional): Number of records (default: 50)

**Response** (200):
```json
[
  {
    "id": 1,
    "user_id": 1,
    "from_wallet_id": 1,
    "to_wallet_id": 2,
    "amount": "1000.00",
    "currency": "PKR",
    "status": "completed",
    "reference": "WT-A1B2C3D4E5F6G7H8",
    "timestamp": "2024-01-15T11:00:00"
  }
]
```

---

### 6. Generate QR Code

Generate QR code for receiving offline payments.

**Endpoint**: `POST /api/v1/wallets/qr-code`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Request Body**:
```json
{
  "wallet_id": 2
}
```

**Response** (200):
```json
{
  "qr_data": {
    "version": "1.0",
    "type": "offline_payment_receiver",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "user_id": 1,
    "wallet_id": 2,
    "timestamp": "2024-01-15T11:30:00",
    "nonce": "a1b2c3d4e5f6g7h8"
  },
  "qr_image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Usage**: Display `qr_image_base64` as image in mobile app.

---

### 7. Get Wallet Private Key

Retrieve private key for offline wallet (sensitive operation).

**Endpoint**: `GET /api/v1/wallets/{wallet_id}/private-key`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
{
  "wallet_id": 2,
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC...",
  "warning": "Store this securely on your device. Never share it."
}
```

**⚠️ Security Warning**: This endpoint should require additional authentication in production (e.g., PIN, biometric).

---

## Offline Transactions

### 1. Create Offline Transaction (Local)

Prepare offline transaction data for signing.

**Endpoint**: `POST /api/v1/offline-transactions/create-local`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Request Body**:
```json
{
  "sender_wallet_id": 2,
  "receiver_qr_data": {
    "version": "1.0",
    "type": "offline_payment_receiver",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "user_id": 5,
    "wallet_id": 10,
    "timestamp": "2024-01-15T12:00:00",
    "nonce": "xyz789"
  },
  "amount": "500.00",
  "currency": "PKR",
  "device_fingerprint": "android-device-12345",
  "created_at_device": "2024-01-15T12:05:00"
}
```

**Response** (201):
```json
{
  "transaction_data": {
    "sender_wallet_id": 2,
    "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "receiver_user_id": 5,
    "receiver_wallet_id": 10,
    "amount": "500.00",
    "currency": "PKR",
    "nonce": "abc123def456...",
    "timestamp": "2024-01-15T12:05:00"
  },
  "message": "Sign this transaction data with your private key",
  "nonce": "abc123def456..."
}
```

**Next Step**: Sign `transaction_data` with sender's private key on mobile device.

---

### 2. Sign and Store Offline Transaction

Store signed transaction locally (simulates mobile local storage).

**Endpoint**: `POST /api/v1/offline-transactions/sign-and-store`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Request Body**:
```json
{
  "transaction_data": {
    "sender_wallet_id": 2,
    "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "receiver_user_id": 5,
    "receiver_wallet_id": 10,
    "amount": "500.00",
    "currency": "PKR",
    "nonce": "abc123def456...",
    "timestamp": "2024-01-15T12:05:00"
  },
  "signature": "base64_encoded_signature_here..."
}
```

**Response** (201):
```json
{
  "message": "Transaction signed and stored locally",
  "receipt": {
    "version": "1.0",
    "type": "offline_payment_receipt",
    "sender_wallet_id": 2,
    "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "amount": "500.00",
    "currency": "PKR",
    "nonce": "abc123def456...",
    "signature": "base64_encoded_signature_here...",
    "timestamp": "2024-01-15T12:05:00",
    "receipt_hash": "sha256_hash_here..."
  },
  "local_balance": 4500.00,
  "warning": "Keep this receipt as proof. Sync when online to complete transaction."
}
```

**Important**: Sender gives receipt to receiver as proof of payment.

---

### 3. Sync Offline Transactions

Sync offline transactions from mobile to server (when online).

**Endpoint**: `POST /api/v1/offline-transactions/sync`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Request Body**:
```json
{
  "transactions": [
    {
      "transaction_data": {
        "sender_wallet_id": 2,
        "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
        "amount": "500.00",
        "currency": "PKR",
        "nonce": "abc123def456...",
        "timestamp": "2024-01-15T12:05:00"
      },
      "signature": "base64_encoded_signature...",
      "receipt": {
        "version": "1.0",
        "type": "offline_payment_receipt",
        "sender_wallet_id": 2,
        "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
        "amount": "500.00",
        "currency": "PKR",
        "nonce": "abc123def456...",
        "signature": "base64_encoded_signature...",
        "timestamp": "2024-01-15T12:05:00",
        "receipt_hash": "sha256_hash..."
      },
      "device_fingerprint": "android-device-12345"
    }
  ]
}
```

**Response** (200):
```json
{
  "message": "Synced 1 transactions",
  "synced": [
    {
      "nonce": "abc123def456...",
      "amount": "500.00",
      "status": "synced"
    }
  ],
  "failed": [],
  "total_synced": 1,
  "total_failed": 0
}
```

---

### 4. Verify Receipt

Verify transaction receipt (receiver can do this offline).

**Endpoint**: `POST /api/v1/offline-transactions/verify-receipt`

**Request Body** (no authentication required):
```json
{
  "receipt_data": {
    "version": "1.0",
    "type": "offline_payment_receipt",
    "sender_wallet_id": 2,
    "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "amount": "500.00",
    "currency": "PKR",
    "nonce": "abc123def456...",
    "signature": "base64_encoded_signature...",
    "timestamp": "2024-01-15T12:05:00",
    "receipt_hash": "sha256_hash..."
  },
  "signature": "base64_encoded_signature...",
  "sender_public_key": "-----BEGIN PUBLIC KEY-----\n..."
}
```

**Response** (200):
```json
{
  "valid": true,
  "signature_valid": true,
  "hash_valid": true,
  "transaction_data": {
    "sender_wallet_id": 2,
    "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "amount": "500.00",
    "currency": "PKR",
    "nonce": "abc123def456...",
    "timestamp": "2024-01-15T12:05:00"
  },
  "message": "Receipt is valid"
}
```

---

### 5. List Offline Transactions

Get offline transaction history.

**Endpoint**: `GET /api/v1/offline-transactions/?status_filter=synced&limit=50`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `status_filter` (optional): Filter by status (pending, synced, confirmed, failed)
- `limit` (optional): Number of records (default: 50)

**Response** (200):
```json
[
  {
    "id": 1,
    "sender_wallet_id": 2,
    "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "amount": "500.00",
    "currency": "PKR",
    "transaction_signature": "base64_encoded_signature...",
    "nonce": "abc123def456...",
    "receipt_hash": "sha256_hash...",
    "receipt_data": "{...}",
    "status": "synced",
    "created_at_device": "2024-01-15T12:05:00",
    "synced_at": "2024-01-15T14:00:00",
    "confirmed_at": null,
    "created_at": "2024-01-15T14:00:00"
  }
]
```

---

### 6. Confirm Offline Transaction

Confirm transaction and transfer to receiver's current account.

**Endpoint**: `POST /api/v1/offline-transactions/{transaction_id}/confirm`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
{
  "message": "Transaction confirmed and settled",
  "transaction_id": 1,
  "amount": 500.00,
  "receiver_balance": 10500.00,
  "status": "confirmed"
}
```

---

## User Management

### 1. List Users

Get all users (admin/testing only).

**Endpoint**: `GET /api/v1/users/`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
[
  {
    "id": 1,
    "name": "Ahmed Khan",
    "email": "ahmed@example.com",
    "phone": "+923001234567",
    "created_at": "2024-01-15T10:00:00",
    "updated_at": "2024-01-15T10:00:00"
  }
]
```

---

## Error Handling

### Standard Error Response

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate resource (e.g., duplicate nonce) |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server error |

### Common Error Examples

**Invalid Credentials**:
```json
{
  "detail": "Invalid credentials"
}
```

**Insufficient Balance**:
```json
{
  "detail": "Insufficient balance in offline wallet"
}
```

**Duplicate Transaction**:
```json
{
  "detail": "Duplicate transaction (replay attack detected)"
}
```

**Invalid Signature**:
```json
{
  "detail": "Invalid transaction signature"
}
```

---

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- **Authentication endpoints**: 5 requests per minute per IP
- **Wallet operations**: 30 requests per minute per user
- **Transaction sync**: 10 requests per minute per user

**Rate Limit Headers**:
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1642252800
```

---

## Testing with cURL

### Example: Complete Offline Transaction Flow

```bash
# 1. Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Ahmed","email":"ahmed@test.com","password":"SecurePass@123","phone":"+923001234567"}'

# 2. Verify email
curl -X POST http://localhost:8000/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"email":"ahmed@test.com","otp":"abc123"}'

# 3. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ahmed@test.com","password":"SecurePass@123","device_fingerprint":"test-device"}'

# 4. Confirm login with OTP
curl -X POST http://localhost:8000/auth/login/confirm \
  -H "Content-Type: application/json" \
  -d '{"email":"ahmed@test.com","otp":"6a3f2b","nonce":"temp-nonce","device_fingerprint":"test-device"}'

# 5. Create offline wallet
curl -X POST http://localhost:8000/api/v1/wallets/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_type":"offline","currency":"PKR"}'

# 6. Generate QR code
curl -X POST http://localhost:8000/api/v1/wallets/qr-code \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_id":2}'
```

---

## WebSocket Support (Future)

Real-time transaction notifications will be added in future versions:

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/transactions');

// Listen for transaction updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Transaction update:', data);
};
```

---

## SDK & Client Libraries (Planned)

Official SDKs will be provided for:
- Android (Kotlin)
- iOS (Swift)
- JavaScript/TypeScript
- Python

---

## Support & Contact

For API support and questions:
- **Email**: support@offlinepay.pk
- **Documentation**: https://docs.offlinepay.pk
- **GitHub**: https://github.com/offlinepay/api

---

**API Version**: 1.0.0  
**Last Updated**: 2024  
**License**: Proprietary
