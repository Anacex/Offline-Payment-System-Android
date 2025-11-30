# Test Commands for Render Web Service

**Service URL:** `https://offline-payment-system-android-f8hr.onrender.com`

## Quick Test Commands (PowerShell)

### Test 1: Root Endpoint (Basic Connectivity)
```powershell
Invoke-WebRequest -Uri "https://offline-payment-system-android-f8hr.onrender.com/" -Method GET -UseBasicParsing
```
**Expected:** Status 200, Response: `{"service":"offline-payment-system","version":"1.0.0"}`

### Test 2: Health Check
```powershell
Invoke-WebRequest -Uri "https://offline-payment-system-android-f8hr.onrender.com/health" -Method GET -UseBasicParsing
```
**Expected:** Status 200, Response: `{"status":"ok"}`

### Test 3: Signup (Tests DB Write + Supabase Logging)
```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$body = @{
    email = "test_$timestamp@example.com"
    password = "TestPassword123!"
    name = "Test User $timestamp"
    phone = "+1234567890"
} | ConvertTo-Json

Invoke-WebRequest -Uri "https://offline-payment-system-android-f8hr.onrender.com/auth/signup" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
```
**Expected:** 
- Status 201 (if new user) or 400 (if user exists)
- Check Supabase `server_logs` table for:
  - Request/response logs
  - OTP generation log entry

### Test 4: Protected Endpoint (Tests Auth + DB Read)
```powershell
Invoke-WebRequest -Uri "https://offline-payment-system-android-f8hr.onrender.com/api/v1/users/" -Method GET -UseBasicParsing
```
**Expected:** Status 401 (Unauthorized) - This confirms DB connection works, just needs auth

### Test 5: Invalid Endpoint (Tests Routing)
```powershell
Invoke-WebRequest -Uri "https://offline-payment-system-android-f8hr.onrender.com/invalid-endpoint-12345" -Method GET -UseBasicParsing
```
**Expected:** Status 404 (Not Found) - Confirms service is routing correctly

## Run All Tests

Run the complete test script:
```powershell
.\test_render_commands.ps1
```

Or run individual commands from above.

## Verify Supabase Connection

After running tests, check Supabase:

1. **Go to Supabase Dashboard** → Your Project → Table Editor
2. **Open `server_logs` table**
3. **Look for entries with:**
   - `level`: "info"
   - `message`: Contains "Request:" or "Response:"
   - `meta`: Contains request/response details
   - For signup test: Look for OTP log with `"type": "email_verification"`

## Verify Database Connection

Check Render logs for:
- `Database tables ready`
- `Application startup complete`
- No database connection errors

## Expected Results

✅ **Service is working if:**
- Root endpoint returns 200
- Health check returns 200
- Signup creates user (201) or returns validation error (400)
- Protected endpoints return 401 (not 500)
- Invalid endpoints return 404 (not 500)

✅ **Supabase logging is working if:**
- `server_logs` table has entries for each request
- OTP logs appear after signup
- Request/response metadata is captured

✅ **Database connection is working if:**
- No database errors in Render logs
- Signup creates user in `users` table
- Logs are written to `server_logs` table

## Troubleshooting

### Service returns 503 or timeout
- Service might be spinning up (free tier sleeps after inactivity)
- Wait 30-60 seconds and try again
- Check Render dashboard for service status

### No logs in Supabase
- Verify `DATABASE_URL` is set correctly in Render
- Verify `SUPABASE_LOG_TABLE=server_logs` is set
- Check Render logs for connection errors

### Signup fails with 500
- Check Render logs for database errors
- Verify `DATABASE_URL` connection string is correct
- Check if Supabase allows connections from Render IPs



