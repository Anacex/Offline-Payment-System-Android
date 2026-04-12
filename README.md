# Offline Payment System — Central README

This is the canonical entry point for new contributors. It links to focused documentation for setup, testing, API reference, CI, and deployment.

## 📖 Full walk through of the project's documentation
**→ [START_HERE.md](START_HERE.md)** — Complete documentation roadmap with learning paths for different roles (Backend, Frontend, DevOps, etc.), organized by topic and purpose. Start here if you're new to the project.

## Quick links

- Overview & quick start: this README
- **[Full documentation guide: START_HERE.md](START_HERE.md)** ← Start here for complete roadmap
- API reference: API_DOCUMENTATION.md
- Testing guide (unit & CI): TESTING.md
- CI & secrets: CI_AND_SECRETS.md
- Production deployment: PRODUCTION_DEPLOYMENT.md
- Deploy checklist: DEPLOYMENT_CHECKLIST.md
- Project index & additional docs: DOCUMENTATION_INDEX.md
- Threat model & security: THREAT_MODEL.md
- Mobile integration guide: MOBILE_APP_GUIDE.md 
- **Offline transaction workflow: [OFFLINE_TRANSACTION_WORKFLOW.md](OFFLINE_TRANSACTION_WORKFLOW.md)** ← Complete transaction flow documentation
- **Android app (BLE vs QR data channels, wire format): [Android-App/README.md](Android-App/README.md)** ← Bluetooth ack handshake; transaction fields only on QR
- **QR payload analysis: [QR_PAYLOAD_ANALYSIS.md](QR_PAYLOAD_ANALYSIS.md)** ← QR code field analysis & recommendations

## Recommended first steps for a new developer
1. Read [START_HERE.md](START_HERE.md) (5 min) — comprehensive documentation roadmap.
2. Choose a learning path based on your role (Backend, Frontend, DevOps, etc.).
3. Set up local environment (see the "Local setup" section below).
4. Read `TESTING.md` and run the unit tests: `pytest -m unit -q`
5. Explore `API_DOCUMENTATION.md` and open Swagger UI at `http://localhost:8000/docs` while running the server.

Local setup (minimal)

1. Create and activate a Python virtualenv (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. (Optional) Create a local `.env` with the essentials:

```
DATABASE_URL=sqlite:///./local_dev.db
SECRET_KEY=dev-secret-key
DEBUG=true
```

3. Initialize the database (creates tables):

```powershell
python -m app.db_init
```

**Supabase / managed PostgreSQL:** On each API **startup**, `app/main.py` runs `Base.metadata.create_all()`, which **creates any missing tables** (for example `device_ledger_heads`, `offline_receiver_syncs`) but does **not** add new **columns** to tables that already exist (for example new `users.*` suspension fields). For an existing Supabase project, run these idempotent scripts once in the SQL Editor as needed: [`migrations/supabase_ledger_and_account_blocking.sql`](migrations/supabase_ledger_and_account_blocking.sql) (ledger heads + user suspension columns), and [`migrations/supabase_offline_receiver_syncs.sql`](migrations/supabase_offline_receiver_syncs.sql) (receiver-side audit table for `RECEIVED` sync rows). Fresh installs can rely on startup + `python -m app.db_init` for a full schema.

4. Run the server:

```powershell
uvicorn app.main:app --reload --port 8000
```

Where to go next (documentation map)

- API docs: `API_DOCUMENTATION.md` — endpoints, request/response shapes.
- Tests & test DB strategy: `TESTING.md` — run unit tests locally, explanation of the temp SQLite strategy we use for fast, safe unit tests.
- CI & Secrets: `CI_AND_SECRETS.md` — what secrets to set in GitHub and CI pipeline overview.
- Production deployment: `PRODUCTION_DEPLOYMENT.md` — detailed step-by-step production deployment guide (Nginx, systemd, SSL).
- Quick deployment checklist: `DEPLOYMENT_CHECKLIST.md` — short list to follow before pushing to production.
- Project index: `DOCUMENTATION_INDEX.md` — map of all documentation files.

Contributing

1. Run unit tests before opening a PR: `pytest -m unit -q`.
2. Keep changes small and focused.
3. Update `DOCUMENTATION_INDEX.md` if you add new docs.

Need help?

Open an issue describing the problem or ask in the team chat and point to the failing test/logs. If you want, I can also move old/archived docs into an `archive_docs/` folder instead of deleting them.

---

If this looks good I will delete the old archived docs to remove clutter (you asked for removal). If you'd prefer moving them to `archive_docs/` instead, tell me and I'll do that instead.
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
- `POST /api/v1/wallets/topup` - Request wallet top-up (sends OTP email)
- `POST /api/v1/wallets/topup/verify` - Verify top-up OTP and update balance

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

## ✨ Current product features (high level)

- **Offline payments** via QR (and optional BLE confirmation path on Android); local pending queue until online sync.
- **Hash-chained local ledger** on the device (AES-GCM for sensitive JSON at rest) with deterministic integrity payloads; **server verifies** the chain on `/api/v1/offline-transactions/sync` and stores per-device tail in **`device_ledger_heads`**.
- **Fraud / tamper response:** any failed chained-ledger check during sync sets **`users.account_blocked`**, **`fraud_review_pending`**, and a reason; the account cannot use protected APIs or obtain new tokens until an operator **clears the flags in the database** (see migration SQL for an example `UPDATE`).
- **Android:** dedicated **account under review** full-screen after login or when `/auth/me` returns suspension; user returns to sign-in after acknowledging.

## 🔒 Security Features

### Cryptography
- **RSA 2048-bit**: Asymmetric encryption for offline transactions
- **RSA-PSS + SHA-256**: Digital signatures
- **bcrypt**: Password hashing (cost factor 12)
- **JWT HS256**: Token signing
- **SHA-256**: Receipt hashing

### Attack Prevention
- **Replay Attacks**: Unique nonce per transaction
- **Local ledger tampering**: Hash chain + server verification; failed verification flags the account for manual review
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

**Account suspension (blocked user / “under review” screen):** See **[OFFLINE_TRANSACTION_WORKFLOW.md — Manual testing: account suspension and ledger tail](OFFLINE_TRANSACTION_WORKFLOW.md#manual-testing-account-suspension-and-ledger-tail)**. Short version: (1) set `users.account_blocked = true` in Supabase to test login/`/auth/me` and the Android review screen without syncing; or (2) corrupt `device_ledger_heads.last_entry_hash` / `last_sequence` and then run a **chained** pending sync to trigger a **`LEDGER_INTEGRITY_*`** failure and automatic suspension.

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
- **Offline Transactions**: See OFFLINE_TRANSACTION_WORKFLOW.md
- **QR Code Implementation**: See QR_PAYLOAD_ANALYSIS.md
- **Issues**: Create GitHub issue

## 📄 License

Proprietary - Offline Payment System

## 👥 Contributors

- Development Team - Offline Payment System

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Status**: Production Ready (after security audit)
