-- =============================================================================
-- One-shot Supabase / Postgres maintenance
--
-- 1) Link columns for sender/receiver sync correlation (matches API models).
-- 2) Backfill constraints & indexes the app expects (safe if already present).
-- 3) DROP deprecated legacy P2P table public.transactions (replaced by wallets,
--    wallet_transfers, offline_transactions, offline_receiver_syncs).
--
-- Uses public.* and timestamp without time zone to align with your current schema.
-- Re-run safe: IF NOT EXISTS / IF EXISTS / guarded DO blocks.
--
-- After running: redeploy the API (see README / SERVER_DOCUMENTATION for current routes).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1) Link timestamps (offline sync correlation)
-- ---------------------------------------------------------------------------
ALTER TABLE public.offline_transactions
    ADD COLUMN IF NOT EXISTS receiver_attestation_at timestamp without time zone NULL;

ALTER TABLE public.offline_receiver_syncs
    ADD COLUMN IF NOT EXISTS sender_settlement_recorded_at timestamp without time zone NULL;

COMMENT ON COLUMN public.offline_transactions.receiver_attestation_at IS
    'When a matching receiver RECEIVED sync was accepted (same payment nonce).';

COMMENT ON COLUMN public.offline_receiver_syncs.sender_settlement_recorded_at IS
    'When sender SENT settlement was accepted for this nonce (after receiver attested).';

-- ---------------------------------------------------------------------------
-- 2) offline_receiver_syncs: UNIQUE (user_id, payment_nonce) — idempotent sync
--    Skipped automatically if duplicate (user_id, payment_nonce) rows exist;
--    fix duplicates manually then re-run this section if needed.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_offline_recv_user_nonce'
    ) THEN
        NULL;
    ELSIF EXISTS (
        SELECT 1
        FROM (
            SELECT user_id, payment_nonce, COUNT(*) AS c
            FROM public.offline_receiver_syncs
            GROUP BY user_id, payment_nonce
            HAVING COUNT(*) > 1
        ) x
    ) THEN
        RAISE NOTICE 'Skipping uq_offline_recv_user_nonce: duplicate (user_id, payment_nonce) rows exist.';
    ELSE
        ALTER TABLE public.offline_receiver_syncs
            ADD CONSTRAINT uq_offline_recv_user_nonce UNIQUE (user_id, payment_nonce);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_offline_receiver_syncs_user_id
    ON public.offline_receiver_syncs (user_id);

CREATE INDEX IF NOT EXISTS ix_offline_receiver_syncs_nonce
    ON public.offline_receiver_syncs (payment_nonce);

CREATE INDEX IF NOT EXISTS ix_offline_receiver_syncs_tx_id
    ON public.offline_receiver_syncs (tx_id);

-- ---------------------------------------------------------------------------
-- 3) device_ledger_heads: one tail per (user_id, device_fingerprint)
--    Fails if duplicates already exist — resolve duplicates then re-run.
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_device_ledger_user_device
    ON public.device_ledger_heads (user_id, device_fingerprint);

-- ---------------------------------------------------------------------------
-- 4) Deprecated schema cleanup — legacy user-to-user ledger (unused by mobile app)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS public.transactions CASCADE;
