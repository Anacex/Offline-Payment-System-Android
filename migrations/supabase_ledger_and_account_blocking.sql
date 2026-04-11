-- Run in Supabase SQL Editor (or any PostgreSQL client) if tables/columns are missing.
-- The API also runs SQLAlchemy create_all on startup, which creates NEW tables but does not
-- ALTER existing tables. Safer for production: apply this once after upgrading the app.

-- Hash-chain tail per user + device (offline sync integrity)
CREATE TABLE IF NOT EXISTS device_ledger_heads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    last_entry_hash VARCHAR(64) NOT NULL,
    last_sequence INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    CONSTRAINT uq_device_ledger_user_device UNIQUE (user_id, device_fingerprint)
);

CREATE INDEX IF NOT EXISTS ix_device_ledger_heads_user_id ON device_ledger_heads (user_id);

-- Account suspension / fraud review (set manually to clear a false positive)
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_blocked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS fraud_review_pending BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_blocked_reason TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_blocked_at TIMESTAMP;

-- Unblock example (run as admin / service role):
-- UPDATE users SET account_blocked = false, fraud_review_pending = false,
--   account_blocked_reason = NULL, account_blocked_at = NULL WHERE id = <user_id>;

-- ---------------------------------------------------------------------------
-- Manual demo: breaking the server-side chain tail (optional)
-- Changing last_entry_hash or last_sequence here desynchronizes the SERVER from
-- an honest CLIENT; the next chained sync can fail with LEDGER_INTEGRITY_* and
-- set users.account_blocked. You still need a pending tx that syncs WITH chain
-- fields. See OFFLINE_TRANSACTION_WORKFLOW.md § "Manual testing: account suspension
-- and ledger tail". To reset after a test, restore correct values or delete the
-- row only if you intend to restart from genesis for that device fingerprint.
-- ---------------------------------------------------------------------------
