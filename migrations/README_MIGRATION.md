# Database migrations (Supabase / Postgres)

**Primary one-shot cleanup + sync link columns:** [`supabase_offline_sync_link_timestamps.sql`](supabase_offline_sync_link_timestamps.sql) — adds `receiver_attestation_at` / `sender_settlement_recorded_at`, receiver sync indexes + unique `(user_id, payment_nonce)`, device ledger unique index, and **drops deprecated `public.transactions`**.

**Also see:**
- [`supabase_ledger_and_account_blocking.sql`](supabase_ledger_and_account_blocking.sql) — `device_ledger_heads` and `users` suspension / fraud-review columns  
- [`supabase_offline_receiver_syncs.sql`](supabase_offline_receiver_syncs.sql) — `offline_receiver_syncs` table  

---

# Older script: `001_update_schema_constraints.sql`

> **If you already ran `supabase_offline_sync_link_timestamps.sql`**, the `public.transactions` table may be **gone**. Skip or comment out the **`transactions`** section inside `001_update_schema_constraints.sql` when applying it, or the script will error.

## What `001_update_schema_constraints` Does

This migration adds missing constraints and indexes to align your Supabase database with the SQLAlchemy model definitions.

### Changes Made:

1. **offline_transactions**:
   - ✅ Adds `UNIQUE` constraint on `nonce` column (prevents replay attacks)
   - ✅ Adds index on `nonce` for faster lookups

2. **refresh_tokens**:
   - ✅ Adds `UNIQUE` constraint on `token` column
   - ✅ Adds index on `token` for faster lookups
   - ✅ Updates foreign key to `CASCADE` on delete (matches model)

3. **transactions** (legacy — **table removed** by `supabase_offline_sync_link_timestamps.sql`; skip this block if the table does not exist):
   - Adds `UNIQUE` on `reference`, indexes (historical only)

4. **users**:
   - ✅ Adds `UNIQUE` constraint on `email` column (if not already exists)
   - ✅ Adds index on `email` for faster lookups

5. **wallet_transfers**:
   - ✅ Adds `UNIQUE` constraint on `reference` column
   - ✅ Adds index on `reference` for faster lookups

6. **wallets**:
   - ✅ Updates foreign key to `CASCADE` on delete (matches model)

## How to Run

### Step 1: Backup Your Database
**CRITICAL**: Always backup before running migrations!

1. Go to Supabase Dashboard
2. Navigate to **Database** → **Backups**
3. Click **Create Backup** (or use scheduled backup)

### Step 2: Run the Migration

1. Go to Supabase Dashboard
2. Navigate to **SQL Editor**
3. Open the file `migrations/001_update_schema_constraints.sql`
4. Copy the entire SQL script
5. Paste it into the SQL Editor
6. Click **Run** (or press Ctrl+Enter)

### Step 3: Verify the Changes

After running the migration, verify the changes:

```sql
-- Check unique constraints
SELECT 
    tc.table_name, 
    tc.constraint_name, 
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'UNIQUE'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_name;

-- Check indexes
SELECT 
    tablename, 
    indexname, 
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Check foreign keys with CASCADE
SELECT
    tc.table_name,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
    ON rc.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
    AND rc.delete_rule = 'CASCADE'
ORDER BY tc.table_name;
```

## Rollback

If you need to rollback these changes, use the rollback script included at the bottom of the migration file (commented out). Uncomment and run it.

## Safety Features

- ✅ Uses `IF NOT EXISTS` checks to prevent errors if constraints already exist
- ✅ Wrapped in a transaction (`BEGIN`/`COMMIT`) for atomicity
- ✅ Idempotent - safe to run multiple times

## Notes

- This migration is **safe** to run on production (uses IF NOT EXISTS checks)
- No data will be lost or modified
- Only adds constraints and indexes (no column changes)
- The migration is idempotent (can be run multiple times safely)

## Troubleshooting

### Error: "constraint already exists"
- This is expected if you've run the migration before
- The script uses `IF NOT EXISTS` checks, so it should handle this gracefully
- If you still get errors, check which constraint already exists and comment out that section

### Error: "index already exists"
- Similar to above, the script uses `CREATE INDEX IF NOT EXISTS`
- Should not cause issues

### Foreign Key Update Errors
- If you have existing data that violates the CASCADE constraint, you may need to clean it up first
- Check for orphaned records before running the migration

## Questions?

If you encounter any issues:
1. Check the Supabase logs in Dashboard → Logs
2. Verify your database connection
3. Ensure you have proper permissions
4. Review the error message for specific constraint/index names

