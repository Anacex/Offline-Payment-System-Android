# Offline Payment System - Backend API

A secure banking backend that enables **offline money transfers** using asymmetric cryptography, digital signatures, and QR codes. Designed for integration with Pakistani banking apps like Meezan Bank.

## 🎯 Core Concept

Enable users to transfer money **without internet connectivity** through:
- **Dual Wallet System**: Current (online) + Offline wallets
- **Asymmetric Cryptography**: RSA 2048-bit encryption
- **Digital Signatures**: Transaction verification
- **QR Code Payments**: Scan receiver's QR to pay offline
- **Receipt System**: Cryptographic proof of payment
- **Ledger Sync**: Local ledger syncs to global when online

## 🏗️ Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  Mobile App     │◄────────┤  Backend API     │
│  (Android)      │  HTTPS  │  (FastAPI)       │
│                 │         │                  │
│ • Local Ledger  │         │ • Global Ledger  │
│ • Private Keys  │         │ • PostgreSQL DB  │
│ • QR Scanner    │         │ • JWT Auth       │
└─────────────────┘         └──────────────────┘
      │                              │
      │ Offline Transaction          │ Online Sync
      ▼                              ▼
┌─────────────────┐         ┌──────────────────┐
│  Receiver       │         │  Blockchain      │
│  (Nearby)       │         │  (Future)        │
└─────────────────┘         └──────────────────┘
```

## ✨ Features

### Security
- ✅ RSA 2048-bit asymmetric encryption
- ✅ Digital signatures (RSA-PSS + SHA-256)
- ✅ Replay attack prevention (nonce-based)
- ✅ Multi-factor authentication (MFA)
- ✅ JWT access + refresh tokens
- ✅ Device fingerprinting
- ✅ Strong password policy
- ✅ Receipt verification

### Wallet Management
- ✅ Create current & offline wallets
- ✅ Transfer between wallets (preload)
- ✅ Balance tracking
- ✅ Multi-currency support (PKR, USD, AED, SAR)
- ✅ Transaction history

### Offline Transactions
- ✅ QR code generation
- ✅ Offline transaction signing
- ✅ Receipt generation
- ✅ Local ledger updates
- ✅ Sync when online
- ✅ Transaction confirmation

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL 14+
- pip (Python package manager)

## 🚀 Quick Start

### 1. Clone & Setup

```bash
cd backend-auth-pack
pip install -r requirements.txt
```

### 2. Configure Database

Create PostgreSQL database:
```sql
CREATE DATABASE offlinepay;
```

Set environment variables (or edit `app/core/config.py`):
```bash
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/offlinepay"
export SECRET_KEY="your-super-secret-key-change-in-production"
export ALGORITHM="HS256"
export ACCESS_TOKEN_EXPIRE_MINUTES="15"
```

### 3. Initialize Database

```bash
python -m app.db_init
```

### 4. Run Server

```bash
uvicorn app.main:app --reload --port 8000
```

Server runs at: `http://localhost:8000`

### 5. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🐳 Docker & Cloud Deployment

### Local development with Docker Compose

Ship a consistent stack without installing Python or PostgreSQL locally:

```bash
docker compose up --build
```

This starts:
- API at http://localhost:8000 (environment from `.env` if present)
- PostgreSQL (user `postgres`, password `postgres`, database `offlinepay`) exposed on localhost:5432

To run just the API container against a different database:

```bash
docker build -t offline-pay-backend .
docker run --env-file .env -p 8000:8000 offline-pay-backend
```

### Deploying to Render (Docker service)

Render can either run a managed Python service (installs requirements each deploy) or a Docker service (builds the same container you run locally). We ship a Docker-first workflow so every environment uses the same image.

1. Push the repository (with `Dockerfile` and `render.yaml`) to GitHub.
2. In Render → **New → Web Service**, pick your repo. Render reads `render.yaml`, builds the Docker image, and runs `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Set environment variables in Render (Dashboard → Environment):
   - `DATABASE_URL` – Supabase Postgres connection string (SQLAlchemy format: `postgresql+psycopg2://user:pass@host:5432/db`)
   - `SECRET_KEY` – strong random string (`openssl rand -hex 32`)
   - `DEBUG` – `false`
   - `REQUIRE_SSL` – `true`
   - `CORS_ORIGINS` – comma-separated list of allowed front-end origins
   - Optional: `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_MINUTE`
4. Deploy (Render auto-deploys on pushes to the tracked branch).

### Supabase database setup

1. In Supabase, create a project and copy the connection string (Project Settings → Database).
2. (Optional) Rotate the password; update the connection string.
3. Either:
   - Let the API auto-create tables on startup (default via FastAPI startup hook), or
   - Run locally with the Supabase URL and execute `python -m app.db_init` once.
4. On Render, set `DATABASE_URL` to the Supabase connection string and keep `REQUIRE_SSL=true` so connections enforce TLS.

### Render Docker vs. docker-compose (what’s the difference?)

- **Render Docker service**: Production deployment. Render builds and runs your `Dockerfile` in the cloud. Ideal for a unified runtime across environments.
- **docker-compose (local)**: Developer convenience to run API + Postgres locally. It spins up multiple containers on your workstation; Render doesn’t use this file directly.

## 📚 Documentation

- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference
- **[Threat Model](THREAT_MODEL.md)** - Security analysis & threat mitigation
- **[Swagger UI](http://localhost:8000/docs)** - Interactive API testing

## 🔐 Authentication Flow

```
1. Sign Up → Email Verification
2. Login → MFA (Email OTP)
3. Receive Access Token + Refresh Token
4. Use Bearer Token for API calls
5. Refresh when token expires
```

**Example**:
```bash
# Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Ahmed","email":"ahmed@test.com","password":"SecurePass@123","phone":"+923001234567"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ahmed@test.com","password":"SecurePass@123","device_fingerprint":"device-123"}'
```

## 💰 Wallet & Transaction Flow

### 1. Create Wallets

```bash
# Create current wallet
curl -X POST http://localhost:8000/api/v1/wallets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_type":"current","currency":"PKR"}'

# Create offline wallet (generates RSA keys)
curl -X POST http://localhost:8000/api/v1/wallets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_type":"offline","currency":"PKR"}'
```

### 2. Preload Offline Wallet

```bash
curl -X POST http://localhost:8000/api/v1/wallets/transfer \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_wallet_id":1,"to_wallet_id":2,"amount":"5000.00","currency":"PKR"}'
```

### 3. Generate QR Code (Receiver)

```bash
curl -X POST http://localhost:8000/api/v1/wallets/qr-code \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_id":2}'
```

### 4. Create Offline Transaction (Sender)

```bash
# Step 1: Prepare transaction
curl -X POST http://localhost:8000/api/v1/offline-transactions/create-local \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_wallet_id":2,
    "receiver_qr_data":{...},
    "amount":"500.00",
    "currency":"PKR",
    "device_fingerprint":"device-123",
    "created_at_device":"2024-01-15T12:00:00"
  }'

# Step 2: Sign with private key (on mobile device)
# Step 3: Store signed transaction
curl -X POST http://localhost:8000/api/v1/offline-transactions/sign-and-store \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"transaction_data":{...},"signature":"..."}'
```

### 5. Sync When Online

```bash
curl -X POST http://localhost:8000/api/v1/offline-transactions/sync \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"transactions":[...]}'
```

## 🗂️ Project Structure

```
backend-auth-pack/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py                 # Authentication endpoints
│   │       ├── wallet.py               # Wallet management
│   │       ├── offline_transaction.py  # Offline transactions
│   │       ├── transaction.py          # Online transactions
│   │       └── user.py                 # User management
│   ├── core/
│   │   ├── auth.py                     # Auth utilities
│   │   ├── config.py                   # Configuration
│   │   ├── crypto.py                   # Cryptography (RSA, signatures)
│   │   ├── db.py                       # Database connection
│   │   ├── deps.py                     # Dependencies
│   │   └── security.py                 # Security utilities
│   ├── models/
│   │   ├── user.py                     # User model
│   │   ├── wallet.py                   # Wallet models
│   │   ├── transaction.py              # Transaction model
│   │   └── base.py                     # Base model
│   ├── schemas/
│   │   ├── auth.py                     # Auth schemas
│   │   ├── wallet.py                   # Wallet schemas
│   │   ├── transaction.py              # Transaction schemas
│   │   └── user.py                     # User schemas
│   ├── db_init.py                      # Database initialization
│   └── main.py                         # FastAPI application
├── API_DOCUMENTATION.md                # Complete API docs
├── THREAT_MODEL.md                     # Security analysis
├── requirements.txt                    # Python dependencies
└── README.md                           # This file
```

## 🔧 API Endpoints

### Public Endpoints
- `POST /auth/signup` - Create account
- `POST /auth/verify-email` - Verify email
- `POST /auth/login` - Login (step 1)
- `POST /auth/login/confirm` - Confirm MFA (step 2)
- `POST /auth/token/refresh` - Refresh access token
- `POST /auth/logout` - Logout
- `POST /api/v1/offline-transactions/verify-receipt` - Verify receipt

### Protected Endpoints (Require Bearer Token)

**Wallets**:
- `POST /api/v1/wallets/` - Create wallet
- `GET /api/v1/wallets/` - List wallets
- `GET /api/v1/wallets/{id}` - Get wallet
- `POST /api/v1/wallets/transfer` - Transfer between wallets
- `GET /api/v1/wallets/transfers/history` - Transfer history
- `POST /api/v1/wallets/qr-code` - Generate QR code
- `GET /api/v1/wallets/{id}/private-key` - Get private key

**Offline Transactions**:
- `POST /api/v1/offline-transactions/create-local` - Create transaction
- `POST /api/v1/offline-transactions/sign-and-store` - Sign & store
- `POST /api/v1/offline-transactions/sync` - Sync to server
- `GET /api/v1/offline-transactions/` - List transactions
- `POST /api/v1/offline-transactions/{id}/confirm` - Confirm transaction

**Users**:
- `GET /api/v1/users/` - List users

**Transactions**:
- `GET /api/v1/transactions/` - List transactions
- `POST /api/v1/transactions/` - Create transaction

## 🔒 Security Features

### Cryptography
- **RSA 2048-bit**: Asymmetric encryption for offline transactions
- **RSA-PSS + SHA-256**: Digital signatures
- **bcrypt**: Password hashing (cost factor 12)
- **JWT HS256**: Token signing
- **SHA-256**: Receipt hashing

### Attack Prevention
- **Replay Attacks**: Unique nonce per transaction
- **Double Spending**: Local + server-side balance checks
- **MITM**: TLS encryption, certificate pinning (mobile)
- **Brute Force**: Rate limiting, account lockout
- **SQL Injection**: SQLAlchemy ORM
- **XSS/CSRF**: Input validation, CORS configuration

### Authentication
- Strong password policy (10+ chars, complexity)
- Multi-factor authentication (email OTP)
- Device fingerprinting
- Token expiration & rotation
- Secure session management

## 🧪 Testing

### Manual Testing

Use Swagger UI at `http://localhost:8000/docs` for interactive testing.

### Example Test Flow

```bash
# 1. Create user
# 2. Verify email
# 3. Login
# 4. Create wallets
# 5. Preload offline wallet
# 6. Generate QR code
# 7. Create offline transaction
# 8. Sync transaction
# 9. Confirm transaction
```

## 📦 Dependencies

### Core
- **FastAPI** 0.114.0 - Web framework
- **uvicorn** 0.37.0 - ASGI server
- **SQLAlchemy** 2.0.34 - ORM
- **psycopg2-binary** 2.9.9 - PostgreSQL adapter
- **pydantic** 2.9.2 - Data validation

### Security
- **cryptography** 41.0.7 - RSA encryption
- **python-jose** 3.3.0 - JWT tokens
- **passlib** 1.7.4 - Password hashing
- **slowapi** 0.1.9 - Rate limiting

### Utilities
- **qrcode** 7.4.2 - QR code generation
- **redis** 5.0.1 - Caching (optional)
- **pydantic-settings** 2.1.0 - Settings management

## 🚀 Deployment

### Production Checklist

- [ ] Change `SECRET_KEY` to strong random value
- [ ] Set `DATABASE_URL` to production database
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS origins (restrict from `*`)
- [ ] Set up Redis for caching
- [ ] Enable rate limiting
- [ ] Configure email service (SMTP)
- [ ] Set up monitoring & logging
- [ ] Database backups
- [ ] Load balancing
- [ ] Firewall rules

### Environment Variables

```bash
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
SECRET_KEY=your-256-bit-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
CORS_ORIGINS=https://yourapp.com
REDIS_URL=redis://localhost:6379
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Docker Deployment (Optional)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🤝 Integration with Banking Apps

This backend can be integrated with existing Pakistani banking apps:

1. **API Integration**: Banking app calls our API endpoints
2. **SSO**: Single sign-on with bank credentials
3. **Wallet Sync**: Link offline wallet to bank account
4. **Settlement**: Offline transactions settle to bank account
5. **Compliance**: Follow SBP regulations

## 📱 Mobile App Development

The Android app should implement:

- **Local Ledger**: SQLite database
- **Key Storage**: Android Keystore
- **QR Scanner**: Camera + ZXing library
- **Cryptography**: Sign transactions locally
- **Sync Service**: Background sync when online
- **Biometric Auth**: Fingerprint/Face unlock
- **Offline Mode**: Full functionality without internet

## 🛡️ Compliance

- **State Bank of Pakistan (SBP)** guidelines
- **Electronic Transactions Ordinance 2002**
- **PECA 2016** (Prevention of Electronic Crimes Act)
- **GDPR** (for international users)
- **PCI DSS** (payment security)

## 📊 Database Schema

### Tables
- `users` - User accounts
- `wallets` - Current & offline wallets
- `wallet_transfers` - Transfers between wallets
- `offline_transactions` - Offline transaction records
- `transactions` - Online transactions
- `refresh_tokens` - JWT refresh tokens

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U postgres -d offlinepay
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Port Already in Use
```bash
# Use different port
uvicorn app.main:app --reload --port 8001
```

## 📈 Future Enhancements

- [ ] Blockchain integration for immutable ledger
- [ ] Multi-signature transactions
- [ ] Biometric authentication API
- [ ] WebSocket for real-time updates
- [ ] Machine learning fraud detection
- [ ] Cross-border payments
- [ ] Smart contracts
- [ ] Decentralized identity (DID)
- [ ] Post-quantum cryptography

## 📞 Support

For questions or issues:
- **Documentation**: See API_DOCUMENTATION.md
- **Security**: See THREAT_MODEL.md
- **Issues**: Create GitHub issue

## 📄 License

Proprietary - Offline Payment System

## 👥 Contributors

- Development Team - Offline Payment System

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Status**: Production Ready (after security audit)
