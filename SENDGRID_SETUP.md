# SendGrid Setup - No Domain Required!

## Why SendGrid?

✅ **No domain needed** - Just verify a single email address  
✅ **Send to any email** - Works immediately after setup  
✅ **Free tier** - 100 emails/day  
✅ **Works on Render free tier** - Uses HTTPS API  

---

## Step-by-Step Setup

### Step 1: Sign up for SendGrid

1. Go to [sendgrid.com](https://signup.sendgrid.com/)
2. Create a free account
3. Verify your email address

### Step 2: Verify a Single Sender

1. Go to SendGrid Dashboard → **Settings** → **Sender Authentication**
2. Click **"Verify a Single Sender"**
3. Fill in the form:
   - **From Email**: `fypofflinepay@gmail.com` (your Gmail)
   - **From Name**: `Offline Payment System`
   - **Reply To**: `fypofflinepay@gmail.com`
   - **Company Address**: (your address)
   - **Website**: `https://offline-payment-system-android.onrender.com`
4. Click **"Create"**
5. **Check your Gmail** (`fypofflinepay@gmail.com`) for verification email
6. Click the verification link in the email

### Step 3: Create API Key

1. Go to SendGrid Dashboard → **Settings** → **API Keys**
2. Click **"Create API Key"**
3. Name it: **"Offline Payment System"**
4. Give it **"Mail Send"** permissions
5. Click **"Create & View"**
6. **Copy the API key** (starts with `SG.`) - you'll only see it once!

### Step 4: Update Render Environment Variables

Go to **Render Dashboard → Your Service → Environment**:

#### DELETE These:
- ❌ `EMAIL_PROVIDER` (if set to `resend`)
- ❌ `RESEND_API_KEY` (if exists)
- ❌ All SMTP variables (if any remain)

#### ADD These:

**Variable 1:**
- Key: `EMAIL_PROVIDER`
- Value: `sendgrid`

**Variable 2:**
- Key: `SENDGRID_API_KEY`
- Value: `SG.your_actual_api_key_here` (paste your SendGrid key)

**Variable 3:**
- Key: `EMAIL_FROM`
- Value: `fypofflinepay@gmail.com` (your verified sender email)

---

## After Setup

1. **Save changes** in Render
2. **Render will auto-redeploy**
3. **Test signup** - create a new user with any email address
4. **Check email inbox** - OTP should arrive!

---

## Why This Works Better Than Resend

| Feature | Resend | SendGrid |
|---------|--------|----------|
| Domain Required | ✅ Yes | ❌ No |
| Single Email Verification | ❌ No | ✅ Yes |
| Send to Any Email | ❌ Need domain | ✅ Works immediately |
| Free Tier | 100/day | 100/day |
| Setup Time | Hours (DNS) | 5 minutes |

---

## Testing

After updating Render variables, test with:

```bash
curl -X POST https://offline-payment-system-android.onrender.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "any-email@example.com",
    "password": "Test123!@#",
    "phone": "1234567890"
  }'
```

The email should arrive at `any-email@example.com`!

---

## Troubleshooting

**If emails don't send:**
- Verify the sender email is verified in SendGrid
- Check API key is correct (starts with `SG.`)
- Verify `EMAIL_FROM` matches your verified sender email
- Check Supabase `server_logs` for SendGrid errors

**SendGrid API errors:**
- 401: Invalid API key - check your key
- 403: Sender not verified - verify the sender email
- 429: Rate limit - free tier is 100/day

---

## Quick Summary

1. Sign up at sendgrid.com
2. Verify single sender: `fypofflinepay@gmail.com`
3. Create API key
4. Update Render: `EMAIL_PROVIDER=sendgrid`, `SENDGRID_API_KEY=SG.xxx`, `EMAIL_FROM=fypofflinepay@gmail.com`
5. Done! Emails work immediately!

