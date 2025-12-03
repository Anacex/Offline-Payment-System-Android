-- Migration Script for Supabase Database
-- Purpose: Add missing unique constraints, indexes, and update foreign key constraints
-- Date: 2024
-- 
-- IMPORTANT: Backup your database before running this script!
-- Supabase Dashboard > Database > Backups > Create Backup

BEGIN;

-- ============================================================================
-- 1. OFFLINE_TRANSACTIONS TABLE
-- ============================================================================

-- Add unique constraint and index on nonce (prevents replay attacks)
-- Check if constraint already exists before adding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'offline_transactions_nonce_key'
    ) THEN
        ALTER TABLE public.offline_transactions 
        ADD CONSTRAINT offline_transactions_nonce_key UNIQUE (nonce);
    END IF;
END $$;

-- Add index on nonce if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_offline_transactions_nonce 
ON public.offline_transactions(nonce);

-- ============================================================================
-- 2. REFRESH_TOKENS TABLE
-- ============================================================================

-- Add unique constraint and index on token
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'refresh_tokens_token_key'
    ) THEN
        ALTER TABLE public.refresh_tokens 
        ADD CONSTRAINT refresh_tokens_token_key UNIQUE (token);
    END IF;
END $$;

-- Add index on token if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token 
ON public.refresh_tokens(token);

-- Update foreign key to CASCADE on delete (matches model definition)
-- Drop existing constraint and recreate with CASCADE
ALTER TABLE public.refresh_tokens
DROP CONSTRAINT IF EXISTS refresh_tokens_user_id_fkey;

ALTER TABLE public.refresh_tokens
ADD CONSTRAINT refresh_tokens_user_id_fkey 
FOREIGN KEY (user_id) 
REFERENCES public.users(id) 
ON DELETE CASCADE;

-- ============================================================================
-- 3. TRANSACTIONS TABLE
-- ============================================================================

-- Add unique constraint and index on reference
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'transactions_reference_key'
    ) THEN
        ALTER TABLE public.transactions 
        ADD CONSTRAINT transactions_reference_key UNIQUE (reference);
    END IF;
END $$;

-- Add index on reference if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_transactions_reference 
ON public.transactions(reference);

-- Add composite index for query optimization (sender_id, receiver_id, timestamp)
CREATE INDEX IF NOT EXISTS ix_transactions_sender_receiver_time 
ON public.transactions(sender_id, receiver_id, timestamp);

-- ============================================================================
-- 4. USERS TABLE
-- ============================================================================

-- Add unique constraint on email if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'users_email_key'
    ) THEN
        ALTER TABLE public.users 
        ADD CONSTRAINT users_email_key UNIQUE (email);
    END IF;
END $$;

-- Add index on email if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_users_email 
ON public.users(email);

-- ============================================================================
-- 5. WALLET_TRANSFERS TABLE
-- ============================================================================

-- Add unique constraint and index on reference
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'wallet_transfers_reference_key'
    ) THEN
        ALTER TABLE public.wallet_transfers 
        ADD CONSTRAINT wallet_transfers_reference_key UNIQUE (reference);
    END IF;
END $$;

-- Add index on reference if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_wallet_transfers_reference 
ON public.wallet_transfers(reference);

-- ============================================================================
-- 6. WALLETS TABLE
-- ============================================================================

-- Update foreign key to CASCADE on delete (matches model definition)
-- Drop existing constraint and recreate with CASCADE
ALTER TABLE public.wallets
DROP CONSTRAINT IF EXISTS wallets_user_id_fkey;

ALTER TABLE public.wallets
ADD CONSTRAINT wallets_user_id_fkey 
FOREIGN KEY (user_id) 
REFERENCES public.users(id) 
ON DELETE CASCADE;

-- ============================================================================
-- VERIFICATION QUERIES (Run these after migration to verify)
-- ============================================================================

-- Uncomment these to verify the changes:
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'public.offline_transactions'::regclass;
-- SELECT indexname FROM pg_indexes WHERE tablename = 'offline_transactions';
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'public.refresh_tokens'::regclass;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'public.transactions'::regclass;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'public.users'::regclass;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'public.wallet_transfers'::regclass;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'public.wallets'::regclass;

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (If you need to undo these changes)
-- ============================================================================
/*
BEGIN;

-- Remove unique constraints
ALTER TABLE public.offline_transactions DROP CONSTRAINT IF EXISTS offline_transactions_nonce_key;
ALTER TABLE public.refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_token_key;
ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS transactions_reference_key;
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_email_key;
ALTER TABLE public.wallet_transfers DROP CONSTRAINT IF EXISTS wallet_transfers_reference_key;

-- Remove indexes
DROP INDEX IF EXISTS idx_offline_transactions_nonce;
DROP INDEX IF EXISTS idx_refresh_tokens_token;
DROP INDEX IF EXISTS idx_transactions_reference;
DROP INDEX IF EXISTS ix_transactions_sender_receiver_time;
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_wallet_transfers_reference;

-- Restore foreign keys to original (no CASCADE)
ALTER TABLE public.refresh_tokens
DROP CONSTRAINT IF EXISTS refresh_tokens_user_id_fkey;
ALTER TABLE public.refresh_tokens
ADD CONSTRAINT refresh_tokens_user_id_fkey 
FOREIGN KEY (user_id) 
REFERENCES public.users(id);

ALTER TABLE public.wallets
DROP CONSTRAINT IF EXISTS wallets_user_id_fkey;
ALTER TABLE public.wallets
ADD CONSTRAINT wallets_user_id_fkey 
FOREIGN KEY (user_id) 
REFERENCES public.users(id);

COMMIT;
*/

