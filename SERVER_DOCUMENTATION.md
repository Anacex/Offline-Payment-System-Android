# Server Documentation - Offline Payment System

## Overview

The Offline Payment System backend is built using **FastAPI** (Python) and **PostgreSQL**. It provides secure RESTful APIs for user authentication, wallet management, and offline transaction processing.

**Base URL (Production)**: `https://offline-payment-system-android-f8hr.onrender.com`  
**Base URL (Development)**: `http://localhost:8000`  
**API Version**: 1.0.0

---

## Table of Contents

1. [API Endpoints](#api-endpoints)
2. [Database Schema](#database-schema)
3. [Database Migrations](#database-migrations)
4. [Third-Party Services](#third-party-services)
5. [Security Features](#security-features)
6. [Configuration](#configuration)

---

## API Endpoints

### Authentication Endpoints

#### 1. Sign Up
- **Endpoint**: `POST /auth/signup`
- **Description**: Create a new user account with email verification
- **Request Body**:
  ```json
  {
    "name": "Ahmed Khan",
    "email": "ahmed@example.com",
    "password": "SecurePass@123",
    "phone": "+923001234567"
  }
  ```
- **Response**: Returns OTP for email verification
- **Email Service**: Sends verification OTP via SendGrid/SMTP

#### 2. Verify Email
- **Endpoint**: `POST /auth/verify-email`
- **Description**: Verify user email with OTP
- **Request Body**:
  ```json
  {
    "email": "ahmed@example.com",
    "otp": "123456"
  }
  ```

#### 3. Login (Step 1)
- **Endpoint**: `POST /auth/login`
- **Description**: Initiate login and receive MFA OTP
- **Request Body**:
  ```json
  {
    "email": "ahmed@example.com",
    "password": "SecurePass@123",
    "device_fingerprint": "android-device-12345"
  }
  ```
- **Response**: Returns `nonce_demo` and `otp_demo`

#### 4. Login (Step 2 - Confirm MFA)
- **Endpoint**: `POST /auth/login/confirm`
- **Description**: Complete login with MFA OTP
- **Request Body**:
  ```json
  {
    "email": "ahmed@example.com",
    "otp": "123456",
    "nonce": "temp-nonce-abc123",
    "device_fingerprint": "android-device-12345"
  }
  ```
- **Response**: Returns `access_token` and `refresh_token`

#### 5. Refresh Token
- **Endpoint**: `POST /auth/token/refresh`
- **Description**: Get new access token using refresh token
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "device_fingerprint": "android-device-12345"
  }
  ```

#### 6. Get Current User Info
- **Endpoint**: `GET /auth/me`
- **Description**: Get current authenticated user's information
- **Headers**: `Authorization: Bearer {access_token}`
- **Response**: Returns user ID, email, name, phone, email verification status, and wallet balance

#### 7. Logout
- **Endpoint**: `POST /auth/logout`
- **Description**: Revoke refresh token
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

---

### Wallet Management Endpoints

#### 1. Initiate Wallet Creation
- **Endpoint**: `POST /api/v1/wallets/create-request`
- **Description**: Request wallet creation (sends OTP email)
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "wallet_type": "offline",
    "currency": "PKR",
    "bank_account_number": "1234567890"
  }
  ```
- **Response**: Returns OTP for wallet creation verification
- **Email Service**: Sends OTP via SendGrid/SMTP

#### 2. Verify and Create Wallet
- **Endpoint**: `POST /api/v1/wallets/create-verify`
- **Description**: Verify OTP and create wallet with bank account
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "wallet_type": "offline",
    "currency": "PKR",
    "bank_account_number": "1234567890",
    "otp": "123456"
  }
  ```
- **Response**: Returns created wallet with RSA key pair

#### 3. Create Wallet (Deprecated)
- **Endpoint**: `POST /api/v1/wallets/`
- **Description**: Legacy endpoint (deprecated, use create-request/create-verify)
- **Status**: Deprecated

#### 4. List Wallets
- **Endpoint**: `GET /api/v1/wallets/`
- **Description**: Get all wallets for authenticated user
- **Headers**: `Authorization: Bearer {access_token}`
- **Response**: Returns list of user's wallets

#### 5. Get Wallet Details
- **Endpoint**: `GET /api/v1/wallets/{wallet_id}`
- **Description**: Get specific wallet information
- **Headers**: `Authorization: Bearer {access_token}`

#### 6. Transfer Between Wallets
- **Endpoint**: `POST /api/v1/wallets/transfer`
- **Description**: Transfer money between wallets (preload offline wallet)
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "from_wallet_id": 1,
    "to_wallet_id": 2,
    "amount": "1000.00",
    "currency": "PKR"
  }
  ```

#### 7. Get Transfer History
- **Endpoint**: `GET /api/v1/wallets/transfers/history?limit=50`
- **Description**: Get wallet transfer history
- **Headers**: `Authorization: Bearer {access_token}`
- **Query Parameters**: `limit` (optional, default: 50)

#### 8. Generate QR Code
- **Endpoint**: `POST /api/v1/wallets/qr-code`
- **Description**: Generate QR code for receiving offline payments
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "wallet_id": 2
  }
  ```
- **Response**: Returns QR data and Base64-encoded QR image

#### 9. Get Wallet Private Key
- **Endpoint**: `GET /api/v1/wallets/{wallet_id}/private-key`
- **Description**: Retrieve private key for offline wallet (sensitive operation)
- **Headers**: `Authorization: Bearer {access_token}`
- **Security Warning**: Should require additional authentication in production

#### 10. Request Wallet Top-Up
- **Endpoint**: `POST /api/v1/wallets/topup`
- **Description**: Request wallet top-up (sends OTP email)
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "wallet_id": 2,
    "amount": "500.00",
    "password": "SecurePass@123",
    "bank_account_number": "1234567890"
  }
  ```
- **Email Service**: Sends OTP via SendGrid/SMTP

#### 11. Verify Top-Up
- **Endpoint**: `POST /api/v1/wallets/topup/verify`
- **Description**: Verify top-up OTP and update wallet balance
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "wallet_id": 2,
    "otp": "123456",
    "amount": "500.00",
    "bank_account_number": "1234567890"
  }
  ```

---

### Offline Transaction Endpoints

#### 1. Create Offline Transaction (Local)
- **Endpoint**: `POST /api/v1/offline-transactions/create-local`
- **Description**: Prepare offline transaction data for signing
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "sender_wallet_id": 2,
    "receiver_qr_data": {
      "payeeId": "34",
      "payeeName": "Ahmed Khan",
      "deviceId": "android-device-12345",
      "nonce": "xyz789",
      "maxTransactionLimit": 500.0
    },
    "amount": "500.00",
    "currency": "PKR",
    "device_fingerprint": "android-device-12345",
    "created_at_device": "2024-01-15T12:05:00"
  }
  ```

#### 2. Sign and Store Offline Transaction
- **Endpoint**: `POST /api/v1/offline-transactions/sign-and-store`
- **Description**: Store signed transaction locally
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**:
  ```json
  {
    "transaction_data": {
      "sender_wallet_id": 2,
      "receiver_public_key": "-----BEGIN PUBLIC KEY-----\n...",
      "amount": "500.00",
      "currency": "PKR",
      "nonce": "abc123def456...",
      "timestamp": "2024-01-15T12:05:00"
    },
    "signature": "base64_encoded_signature_here..."
  }
  ```

#### 3. Sync Offline Transactions
- **Endpoint**: `POST /api/v1/offline-transactions/sync`
- **Description**: Sync offline transactions from mobile to server
- **Headers**: `Authorization: Bearer {access_token}`
- **Request Body**: Array of transaction objects with signatures and receipts

#### 4. Verify Transaction Receipt
- **Endpoint**: `POST /api/v1/offline-transactions/verify-receipt`
- **Description**: Verify transaction receipt (public endpoint)
- **Request Body**: Receipt data and signature

#### 5. List Offline Transactions
- **Endpoint**: `GET /api/v1/offline-transactions/`
- **Description**: List offline transactions for authenticated user
- **Headers**: `Authorization: Bearer {access_token}`
- **Query Parameters**: `status_filter` (optional), `limit` (optional, default: 50)

#### 6. Confirm Offline Transaction
- **Endpoint**: `POST /api/v1/offline-transactions/{transaction_id}/confirm`
- **Description**: Confirm and finalize offline transaction
- **Headers**: `Authorization: Bearer {access_token}`

---

### User Management Endpoints

#### 1. List Users
- **Endpoint**: `GET /api/v1/users/`
- **Description**: List all users (admin only)
- **Headers**: `Authorization: Bearer {access_token}`
- **Access**: Admin only

#### 2. Create User
- **Endpoint**: `POST /api/v1/users/`
- **Description**: Create new user (admin only)
- **Headers**: `Authorization: Bearer {access_token}`
- **Access**: Admin only

---

### Transaction Endpoints

#### 1. List Transactions
- **Endpoint**: `GET /api/v1/transactions/`
- **Description**: List all transactions
- **Headers**: `Authorization: Bearer {access_token}`

#### 2. Create Transaction
- **Endpoint**: `POST /api/v1/transactions/`
- **Description**: Create new transaction
- **Headers**: `Authorization: Bearer {access_token}`

---

### Health Check

#### 1. Health Check
- **Endpoint**: `GET /health`
- **Description**: Server health check
- **Response**: `{"status": "ok"}`

---

## Database Schema

### Tables Overview

The system uses **PostgreSQL** with the following tables:

1. **users** - User accounts and authentication
2. **wallets** - Wallet information and cryptographic keys
3. **wallet_transfers** - Transfer history between wallets
4. **offline_transactions** - Offline transaction records
5. **transactions** - General transaction records
6. **refresh_tokens** - JWT refresh token storage

---

### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    email VARCHAR(256) UNIQUE NOT NULL,
    phone VARCHAR(32),
    password_hash VARCHAR(256) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_email_verified BOOLEAN DEFAULT FALSE NOT NULL,
    mfa_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    offline_balance INTEGER DEFAULT 0 NOT NULL,  -- DEPRECATED: Use Wallet model
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_users_email ON users(email);
```

**Fields**:
- `id`: Primary key (auto-increment)
- `name`: User's full name
- `email`: Unique email address (indexed)
- `phone`: Phone number (optional)
- `password_hash`: bcrypt hashed password
- `is_active`: Account active status
- `is_email_verified`: Email verification status
- `mfa_enabled`: Multi-factor authentication enabled
- `offline_balance`: DEPRECATED - Use Wallet model instead
- `created_at`: Account creation timestamp
- `updated_at`: Last update timestamp

---

### Wallets Table

```sql
CREATE TABLE wallets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_type VARCHAR(20) NOT NULL,  -- 'current' or 'offline'
    balance NUMERIC(12, 2) DEFAULT 0 NOT NULL,
    currency VARCHAR(3) DEFAULT 'PKR' NOT NULL,
    public_key TEXT,  -- RSA public key (PEM format)
    private_key_encrypted TEXT,  -- Encrypted RSA private key
    bank_account_number VARCHAR(64) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_wallets_user_id ON wallets(user_id);
```

**Fields**:
- `id`: Primary key (auto-increment)
- `user_id`: Foreign key to users table
- `wallet_type`: Type of wallet ('current' or 'offline')
- `balance`: Wallet balance (NUMERIC with 2 decimal places)
- `currency`: Currency code (default: 'PKR')
- `public_key`: RSA 2048-bit public key (PEM format)
- `private_key_encrypted`: Encrypted RSA private key
- `bank_account_number`: User's bank account number
- `is_active`: Wallet active status
- `created_at`: Wallet creation timestamp
- `updated_at`: Last update timestamp

**Constraints**:
- Each user can have multiple wallets but typically one of each type
- Offline wallets have cryptographic keys
- Bank account number is required

---

### Wallet Transfers Table

```sql
CREATE TABLE wallet_transfers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    from_wallet_id INTEGER NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
    to_wallet_id INTEGER NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'PKR' NOT NULL,
    status VARCHAR(20) DEFAULT 'completed' NOT NULL,  -- 'completed', 'failed', 'pending'
    reference VARCHAR(64) UNIQUE NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_wallet_transfers_user_id ON wallet_transfers(user_id);
CREATE INDEX idx_wallet_transfers_reference ON wallet_transfers(reference);
```

**Fields**:
- `id`: Primary key
- `user_id`: User who initiated transfer
- `from_wallet_id`: Source wallet ID
- `to_wallet_id`: Destination wallet ID
- `amount`: Transfer amount
- `currency`: Currency code
- `status`: Transfer status
- `reference`: Unique transfer reference
- `timestamp`: Transfer timestamp

---

### Offline Transactions Table

```sql
CREATE TABLE offline_transactions (
    id SERIAL PRIMARY KEY,
    sender_wallet_id INTEGER NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
    receiver_public_key TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'PKR' NOT NULL,
    transaction_signature TEXT NOT NULL,
    nonce VARCHAR(64) UNIQUE NOT NULL,
    receipt_hash VARCHAR(128) NOT NULL,
    receipt_data TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,  -- 'pending', 'synced', 'confirmed', 'failed'
    created_at_device TIMESTAMP NOT NULL,
    synced_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    device_fingerprint VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_offline_transactions_sender_wallet_id ON offline_transactions(sender_wallet_id);
CREATE INDEX idx_offline_transactions_nonce ON offline_transactions(nonce);
```

**Fields**:
- `id`: Primary key
- `sender_wallet_id`: Sender's wallet ID
- `receiver_public_key`: Receiver's public key from QR code
- `amount`: Transaction amount
- `currency`: Currency code
- `transaction_signature`: Digital signature of transaction
- `nonce`: Unique nonce (prevents replay attacks)
- `receipt_hash`: SHA-256 hash of receipt
- `receipt_data`: JSON receipt data
- `status`: Transaction status
- `created_at_device`: Timestamp when created on device
- `synced_at`: Timestamp when synced to server
- `confirmed_at`: Timestamp when confirmed
- `device_fingerprint`: Device identifier
- `created_at`: Server record creation timestamp
- `updated_at`: Last update timestamp

---

### Transactions Table

```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'PKR' NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    reference VARCHAR(64) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_transactions_sender_id ON transactions(sender_id);
CREATE INDEX idx_transactions_receiver_id ON transactions(receiver_id);
CREATE INDEX idx_transactions_reference ON transactions(reference);
CREATE INDEX ix_transactions_sender_receiver_time ON transactions(sender_id, receiver_id, timestamp);
```

**Fields**:
- `id`: Primary key
- `sender_id`: Sender's user ID
- `receiver_id`: Receiver's user ID
- `amount`: Transaction amount
- `currency`: Currency code
- `status`: Transaction status
- `reference`: Unique transaction reference
- `timestamp`: Transaction timestamp

---

### Refresh Tokens Table

```sql
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    device_fingerprint VARCHAR(128) NOT NULL,
    revoked BOOLEAN DEFAULT FALSE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token);
```

**Fields**:
- `id`: Primary key
- `user_id`: User ID (foreign key)
- `token`: JWT refresh token
- `device_fingerprint`: Device identifier
- `revoked`: Token revocation status
- `expires_at`: Token expiration timestamp
- `created_at`: Token creation timestamp

---

## Database Migrations

### Current Migration Status

The system currently uses **SQLAlchemy's automatic table creation** via `Base.metadata.create_all()`. This is handled in `app/db_init.py` and runs automatically on server startup.

### Migration Files Location

- **Directory**: `migrations/` (currently empty)
- **Future**: Will use Alembic for version-controlled migrations

### Current Migration Approach

**Automatic Table Creation**:
- Tables are created automatically on server startup
- Defined in `app/db_init.py`
- Uses SQLAlchemy `Base.metadata.create_all()`
- Checks if tables exist before creating (`checkfirst=True`)

**Tables Created Automatically**:
1. `users`
2. `wallets`
3. `wallet_transfers`
4. `offline_transactions`
5. `transactions`
6. `refresh_tokens`

### Manual Database Initialization

To manually initialize the database:

```bash
python -m app.db_init
```

This will:
- Create all tables if they don't exist
- Print success message with list of created tables
- Not drop existing data

### Future Migration Strategy (FYP-2)

For production, the system should use **Alembic** for:
- Version-controlled migrations
- Rollback capabilities
- Schema versioning
- Migration history tracking

---

## Third-Party Services

### 1. SendGrid Email Service

**Purpose**: Send transactional emails (OTP, verification codes, wallet creation confirmations)

**Configuration**:
- **Environment Variable**: `SENDGRID_API_KEY`
- **Provider Selection**: `EMAIL_PROVIDER=sendgrid`
- **API Endpoint**: `https://api.sendgrid.com/v3/mail/send`

**Implementation**:
- Located in: `app/core/email.py`
- Function: `_send_via_sendgrid()`
- Async HTTP client using `httpx`
- Supports HTML email templates

**Email Types Sent**:
1. **Signup OTP**: Email verification code during registration
2. **Login OTP**: Multi-factor authentication code
3. **Wallet Creation OTP**: Wallet creation verification code
4. **Wallet Top-Up OTP**: Top-up verification code

**Email Template Features**:
- HTML email templates with styling
- Plain text fallback
- OTP codes prominently displayed
- Professional branding

**Free Tier Limits**:
- 100 emails/day free tier
- Sufficient for development and testing

**Fallback Options**:
- **Resend API**: Alternative email provider (100 emails/day free)
- **SMTP**: Direct SMTP (Gmail, etc.)
- **Console**: Development fallback (prints to console)

**Configuration Example**:
```env
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com
```

---

### 2. SMTP Email Service (Alternative)

**Purpose**: Alternative email sending method using direct SMTP

**Configuration**:
- **Environment Variables**:
  - `EMAIL_PROVIDER=smtp`
  - `SMTP_HOST=smtp.gmail.com` (or other SMTP server)
  - `SMTP_PORT=587`
  - `SMTP_USER=your-email@gmail.com`
  - `SMTP_PASSWORD=your-app-password`
  - `EMAIL_FROM=noreply@yourdomain.com`

**Implementation**:
- Located in: `app/core/email.py`
- Function: `_send_via_smtp()`
- Uses Python's `smtplib`
- Async implementation with timeout (15 seconds)
- Supports STARTTLS

**Gmail Setup**:
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use app password in `SMTP_PASSWORD`

---

### 3. Resend API (Alternative)

**Purpose**: Alternative email provider with simple API

**Configuration**:
- **Environment Variables**:
  - `EMAIL_PROVIDER=resend`
  - `RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
  - `EMAIL_FROM=noreply@yourdomain.com`

**Free Tier**: 100 emails/day

---

### 4. PostgreSQL Database

**Purpose**: Primary database for all application data

**Configuration**:
- **Environment Variable**: `DATABASE_URL`
- **Format**: `postgresql+psycopg2://user:password@host:port/database`
- **SSL**: Configurable via `REQUIRE_SSL` setting

**Production Setup**:
- Currently using managed PostgreSQL (Supabase/Render)
- SSL enabled by default
- Connection pooling via SQLAlchemy

**Local Development**:
- Can use local PostgreSQL or SQLite
- SQLite: `sqlite:///./local_dev.db`

---

## Security Features

### Authentication & Authorization

1. **JWT Tokens**:
   - Access tokens (15 minutes expiration)
   - Refresh tokens (30 days expiration)
   - HS256 algorithm
   - Device fingerprint binding

2. **Password Security**:
   - bcrypt hashing (cost factor 12)
   - Strong password requirements:
     - Minimum 10 characters
     - At least 1 uppercase letter
     - At least 1 lowercase letter
     - At least 1 digit
     - At least 1 special character

3. **Multi-Factor Authentication (MFA)**:
   - Email-based OTP
   - 6-digit OTP codes
   - 10-minute expiration
   - Required for login

4. **Device Fingerprinting**:
   - Unique device ID per device
   - Bound to refresh tokens
   - Prevents token theft

### API Security

1. **Rate Limiting**:
   - 30 requests per minute per IP
   - Configurable via `RATE_LIMIT_ENABLED`
   - Uses `slowapi` library

2. **CORS Configuration**:
   - Configurable allowed origins
   - Credentials support
   - Method restrictions

3. **Security Headers**:
   - Content Security Policy
   - X-Frame-Options
   - X-Content-Type-Options
   - X-XSS-Protection
   - Strict-Transport-Security

4. **Request Logging**:
   - All API requests logged
   - Security event logging
   - Transaction logging

### Cryptographic Features

1. **RSA Key Generation**:
   - 2048-bit RSA key pairs
   - Generated per offline wallet
   - Public key stored in database
   - Private key encrypted before storage

2. **Digital Signatures**:
   - RSA-PSS + SHA-256
   - Transaction payload signing
   - Receipt signing

3. **Nonce Generation**:
   - Unique nonce per transaction
   - Prevents replay attacks
   - Stored in database

---

## Configuration

### Environment Variables

**Required Variables**:
```env
# Database
DATABASE_URL=postgresql+psycopg2://user:password@host:port/database

# Security
SECRET_KEY=your-secret-key-here-min-32-chars
ALGORITHM=HS256

# Email Service
EMAIL_PROVIDER=sendgrid  # Options: sendgrid, resend, smtp, console
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# OR for SMTP:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@yourdomain.com

# Application
DEBUG=true  # Set false in production
APP_NAME=Offline Payment System

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30

# Database SSL
REQUIRE_SSL=true  # true for managed DBs, false for local
```

### Configuration File

**Location**: `app/core/config.py`

**Settings Class**: `Settings` (using Pydantic Settings)

**Features**:
- Environment variable loading
- Type validation
- Default values
- Helper properties (e.g., `cors_origin_list`)

---

## Deployment

### Production Deployment

**Platform**: Render.com

**Configuration**:
- PostgreSQL database (managed)
- FastAPI application
- Environment variables configured in Render dashboard
- Automatic SSL/TLS via Render

**Health Check**: `GET /health`

**Monitoring**:
- Application logs
- Security logs
- Transaction logs

---

## API Rate Limits

- **Default**: 30 requests per minute per IP
- **Configurable**: Via `RATE_LIMIT_PER_MINUTE`
- **Headers**: Rate limit info in response headers

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

- `200`: Success
- `201`: Created
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (authentication required)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `422`: Unprocessable Entity (validation errors)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error

---

## Logging

### Log Files

- **Application Logs**: `logs/app.log`
- **Security Logs**: `logs/security.log`
- **Transaction Logs**: `logs/transactions.log`

### Log Levels

- **INFO**: General application events
- **WARNING**: Non-critical issues
- **ERROR**: Error conditions
- **DEBUG**: Detailed debugging (only in debug mode)

---

## Testing

### Test Database

- Uses temporary SQLite database for unit tests
- Isolated test environment
- Automatic cleanup after tests

### Test Coverage

- Unit tests for all API endpoints
- Integration tests for transaction flows
- Security tests for authentication

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**API Version**: 1.0.0

