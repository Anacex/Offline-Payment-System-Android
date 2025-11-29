# Render Environment Variables Setup

## Required Environment Variables for Render

Add these environment variables in your Render Dashboard:

### 1. Go to Render Dashboard
- Navigate to your service → **Environment** tab
- Click **Add Environment Variable**

### 2. Add These Variables:

#### Email Configuration (Required for OTP emails)
```
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=fypofflinepay@gmail.com
SMTP_PASSWORD=rsnmpwvbjsbxxsej
EMAIL_FROM=fypofflinepay@gmail.com
```

#### Supabase Logging (Optional - has defaults)
```
SUPABASE_LOG_TABLE=server_logs
```
*Note: This defaults to "server_logs" if not set, so it's optional*

### 3. Already Configured (Verify these exist):
- ✅ `DATABASE_URL` - Should already be set (for Supabase connection)
- ✅ `SECRET_KEY` - Should already be set
- ✅ `DEBUG` - Should already be set (probably "false" for production)
- ✅ `REQUIRE_SSL` - Should already be set (probably "true")
- ✅ `CORS_ORIGINS` - Should already be set

---

## Quick Copy-Paste for Render Dashboard

Copy and paste these one by one in Render:

**Variable 1:**
- Key: `EMAIL_PROVIDER`
- Value: `smtp`

**Variable 2:**
- Key: `SMTP_HOST`
- Value: `smtp.gmail.com`

**Variable 3:**
- Key: `SMTP_PORT`
- Value: `587`

**Variable 4:**
- Key: `SMTP_USER`
- Value: `fypofflinepay@gmail.com`

**Variable 5:**
- Key: `SMTP_PASSWORD`
- Value: `rsnmpwvbjsbxxsej`

**Variable 6:**
- Key: `EMAIL_FROM`
- Value: `fypofflinepay@gmail.com`

**Variable 7 (Optional):**
- Key: `SUPABASE_LOG_TABLE`
- Value: `server_logs`

---

## After Adding Variables

1. **Redeploy your service** (or wait for auto-deploy if enabled)
2. **Test email sending** by creating a new user
3. **Check Supabase logs** to verify emails are being sent

---

## Security Notes

- ✅ App password is safe to store in Render (it's a read-only password)
- ✅ Never commit these to Git (they're in `.gitignore`)
- ✅ Render encrypts environment variables at rest

---

## Troubleshooting

If emails don't send after deployment:
1. Verify all 6 email variables are set correctly
2. Check Render logs for SMTP connection errors
3. Verify the app password is correct (16 characters, no spaces)
4. Check Supabase `server_logs` table for email sending errors

