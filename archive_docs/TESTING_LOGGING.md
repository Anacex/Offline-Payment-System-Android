# Step-by-Step Guide: Testing Supabase Logging System

## Prerequisites Checklist

Before testing, ensure you have:

- [ ] `DATABASE_URL` environment variable set (your Supabase Postgres connection string)
- [ ] `SUPABASE_LOG_TABLE` environment variable set (defaults to "server_logs" if not set)
- [ ] The `server_logs` table exists in your Supabase database with this schema:
  ```sql
  CREATE TABLE server_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT now(),
    level TEXT,
    message TEXT,
    meta JSONB
  );
  ```
- [ ] Python virtual environment activated (if using one)
- [ ] All dependencies installed

---

## Step 1: Install/Update Dependencies

```bash
# Make sure you're in the project root directory
cd C:\Users\akana\Desktop\Offline-Payment-System-Android

# Install/update dependencies
pip install -r requirements.txt
```

**Verify installation:**
```bash
pip show asyncpg
```
You should see `asyncpg` version 0.27.0 or higher.

---

## Step 2: Set Environment Variables

### Option A: Using .env file (Recommended for local testing)

Create or update a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@host:port/database
SUPABASE_LOG_TABLE=server_logs
```

**Important:** Make sure `.env` is in your `.gitignore` file!

### Option B: Set in PowerShell (Temporary for testing)

```powershell
$env:DATABASE_URL="postgresql://user:password@host:port/database"
$env:SUPABASE_LOG_TABLE="server_logs"
```

### Option C: Set in Command Prompt (Temporary for testing)

```cmd
set DATABASE_URL=postgresql://user:password@host:port/database
set SUPABASE_LOG_TABLE=server_logs
```

**Get your DATABASE_URL from Supabase:**
1. Go to your Supabase project dashboard
2. Navigate to Settings → Database
3. Find "Connection string" → "URI"
4. Copy the connection string (it should look like: `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`)

---

## Step 3: Verify Database Table Exists

### Check in Supabase Dashboard:

1. Go to your Supabase project
2. Navigate to **Table Editor**
3. Verify `server_logs` table exists with columns:
   - `id` (SERIAL PRIMARY KEY)
   - `timestamp` (TIMESTAMPTZ, default: now())
   - `level` (TEXT)
   - `message` (TEXT)
   - `meta` (JSONB)

### If table doesn't exist, create it:

Go to **SQL Editor** in Supabase and run:

```sql
CREATE TABLE IF NOT EXISTS server_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT now(),
    level TEXT,
    message TEXT,
    meta JSONB
);
```

---

## Step 4: Test Basic Logging (Standalone Script)

Test the logging function directly without starting the server:

```bash
python tests/send_test_log.py
```

**Expected output:**
```
Sent log (fire-and-forget). Check Supabase table.
```

**Verify in Supabase:**
1. Go to **Table Editor** → `server_logs`
2. You should see a new row with:
   - `level`: "info"
   - `message`: "test log from script"
   - `meta`: `{"test": true}`

**If this fails:**
- Check that `DATABASE_URL` is set correctly
- Verify the connection string format
- Check that your Supabase database is accessible
- Look for error messages in the console

---

## Step 5: Test with FastAPI Server (Full Integration)

### 5.1 Start the FastAPI Server

```bash
# From project root
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected startup output:**
- Server should start without errors
- You should see your normal startup logs
- No errors about `DATABASE_URL` or `asyncpg`

### 5.2 Make Test API Requests

Open a new terminal/PowerShell window and test various endpoints:

#### Test 1: Health Check (GET request)
```bash
curl http://localhost:8000/health
```

Or use PowerShell:
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health -Method GET
```

#### Test 2: Root Endpoint (GET request)
```bash
curl http://localhost:8000/
```

#### Test 3: Invalid Endpoint (to test error logging)
```bash
curl http://localhost:8000/nonexistent
```

### 5.3 Verify Logs in Supabase

After making requests, check the `server_logs` table:

1. Go to Supabase Dashboard → **Table Editor** → `server_logs`
2. Sort by `timestamp` DESC (newest first)
3. You should see logs like:

   **Request received:**
   - `level`: "info"
   - `message`: "Request received"
   - `meta`: `{"method": "GET", "path": "/health", "client": "127.0.0.1"}`

   **Response sent:**
   - `level`: "info"
   - `message`: "Response sent"
   - `meta`: `{"status": 200, "path": "/health", "method": "GET", "duration_ms": 15}`

4. For the invalid endpoint, you might see:
   - `level`: "info" (request received)
   - `level`: "info" (response sent with status 404)
   - Or `level`: "error" (if an exception occurred)

---

## Step 6: Test Error Logging

Create a test endpoint that raises an exception to verify error logging works:

### Option A: Use an existing endpoint that might fail
- Try accessing a protected endpoint without authentication
- Try invalid request data

### Option B: Check existing error scenarios
- Make requests that trigger validation errors
- Make requests that trigger authentication errors

**Verify error logs:**
- Check for `level`: "error" entries
- Verify `meta` contains `error` and `traceback` fields

---

## Step 7: Performance Check

Verify logging doesn't slow down requests:

1. Make 10-20 rapid requests to your API
2. Check response times (should be similar to before logging was added)
3. Verify all requests are logged (may take a moment to appear in Supabase)

**Example:**
```bash
# Run multiple requests quickly
for i in {1..10}; do curl http://localhost:8000/health; done
```

Or PowerShell:
```powershell
1..10 | ForEach-Object { Invoke-WebRequest -Uri http://localhost:8000/health -Method GET }
```

---

## Step 8: Verify Non-Blocking Behavior

The logging should be fire-and-forget. Test this:

1. Temporarily break the `DATABASE_URL` (set to invalid value)
2. Make API requests
3. **API requests should still work** (logging failures shouldn't block requests)
4. Restore correct `DATABASE_URL`

---

## Troubleshooting

### Issue: "DATABASE_URL must be set in the environment"
**Solution:** Make sure `DATABASE_URL` is set in your environment or `.env` file

### Issue: "asyncpg" module not found
**Solution:** Run `pip install -r requirements.txt`

### Issue: Connection errors
**Solution:** 
- Verify `DATABASE_URL` format is correct
- Check Supabase database is running
- Verify network connectivity
- Check firewall settings

### Issue: Table doesn't exist
**Solution:** Create the table using the SQL provided in Step 3

### Issue: Logs not appearing
**Solution:**
- Wait a few seconds (async logging may have a small delay)
- Check Supabase table permissions
- Verify `SUPABASE_LOG_TABLE` matches your actual table name
- Check server logs for any error messages

### Issue: Server won't start
**Solution:**
- Check all imports are correct
- Verify middleware registration syntax
- Check for syntax errors in new files

---

## Final Checklist Before Pushing to Repo

- [ ] All tests pass (Steps 4-7)
- [ ] Logs appear correctly in Supabase
- [ ] No errors in server logs
- [ ] API requests still work normally
- [ ] `.env` file is in `.gitignore` (don't commit secrets!)
- [ ] `requirements.txt` is updated
- [ ] All new files are created correctly
- [ ] No breaking changes to existing functionality

---

## Quick Test Summary

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables (use your actual DATABASE_URL)
$env:DATABASE_URL="your-database-url-here"
$env:SUPABASE_LOG_TABLE="server_logs"

# 3. Test standalone logging
python tests/send_test_log.py

# 4. Start server
uvicorn app.main:app --reload

# 5. Make test requests (in another terminal)
curl http://localhost:8000/health

# 6. Check Supabase table for logs
```

---

## Ready to Push?

Once all tests pass and you've verified:
- ✅ Logs are being written to Supabase
- ✅ API requests work normally
- ✅ No errors in server logs
- ✅ Performance is acceptable

You're ready to commit and push to your repository!

