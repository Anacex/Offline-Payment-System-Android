-- Receiver-side offline credit attestation (hash chain + RSA), no balance mutation.
-- Run in Supabase SQL Editor if upgrading an existing project (create_all does not ALTER).

CREATE TABLE IF NOT EXISTS offline_receiver_syncs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_wallet_id INTEGER NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'PKR',
    payment_nonce VARCHAR(64) NOT NULL,
    tx_id VARCHAR(64) NOT NULL,
    payer_id VARCHAR(64) NOT NULL,
    payee_id VARCHAR(64) NOT NULL,
    transaction_signature TEXT NOT NULL,
    receipt_hash VARCHAR(128) NOT NULL DEFAULT '',
    receipt_data TEXT NOT NULL DEFAULT '{}',
    device_fingerprint VARCHAR(128),
    created_at_device TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    CONSTRAINT uq_offline_recv_user_nonce UNIQUE (user_id, payment_nonce)
);

CREATE INDEX IF NOT EXISTS ix_offline_receiver_syncs_user_id ON offline_receiver_syncs (user_id);
CREATE INDEX IF NOT EXISTS ix_offline_receiver_syncs_nonce ON offline_receiver_syncs (payment_nonce);
CREATE INDEX IF NOT EXISTS ix_offline_receiver_syncs_tx_id ON offline_receiver_syncs (tx_id);
