# Documentation index

Quick map of the main docs in this repo. For a full learning path, see **[START_HERE.md](START_HERE.md)**.

| Topic | Document |
|--------|----------|
| Overview & setup | [README.md](README.md) |
| API reference | [API_DOCUMENTATION.md](API_DOCUMENTATION.md) |
| Server / DB overview | [SERVER_DOCUMENTATION.md](SERVER_DOCUMENTATION.md) |
| Tests | [TESTING.md](TESTING.md) |
| Mobile ↔ API | [MOBILE_APP_GUIDE.md](MOBILE_APP_GUIDE.md) |
| Offline QR / BLE flow | [OFFLINE_TRANSACTION_WORKFLOW.md](OFFLINE_TRANSACTION_WORKFLOW.md) |
| Supabase SQL scripts | [migrations/README_MIGRATION.md](migrations/README_MIGRATION.md) |
| Android app | [Android-App/README.md](Android-App/README.md) |
| Threat model | [THREAT_MODEL.md](THREAT_MODEL.md) |
| CI / secrets | [CI_AND_SECRETS.md](CI_AND_SECRETS.md) |
| Production deploy | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) |

## API note (2026)

Legacy **`GET/POST /api/v1/transactions/`** and root **`POST /sync`** are removed. Use **wallets**, **wallet_transfers**, and **`/api/v1/offline-transactions/*`** (including **`/sync`**, **`/unified-history`**). The **`public.transactions`** table is dropped by [`migrations/supabase_offline_sync_link_timestamps.sql`](migrations/supabase_offline_sync_link_timestamps.sql).
