# 🚀 Deployment Verification Checklist

## ✅ Step-by-Step Verification

### 1. Update Git Repo ✅
**Status**: Ready to commit and push

**Actions**:
```bash
git add .
git commit -m "Add Docker deployment config, Render setup, and Supabase integration"
git push origin main  # or your branch name
```

**Files to verify are committed**:
- ✅ `render.yaml` (Docker-based Render config)
- ✅ `Dockerfile` (Docker image definition)
- ✅ `requirements.txt` (cleaned dependencies)
- ✅ `main.py` (root entrypoint)
- ✅ `ENV_EXAMPLE.txt` (environment template)
- ✅ Updated `README.md` (deployment docs)

---

### 2. Supabase Connection String (SQLAlchemy Format) ✅

**How to get the correct format**:

1. **Go to Supabase Dashboard**:
   - Project Settings → Database → Connection String
   - Select **"URI"** tab (not "Session pooler")

2. **Supabase provides this format**:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```

3. **Convert to SQLAlchemy format**:
   - Replace `postgresql://` with `postgresql+psycopg2://`
   - **Example**:
     ```
     postgresql+psycopg2://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
     ```

4. **Alternative: Direct connection (non-pooler)**:
   - Use port `5432` instead of `6543`
   - Format: `postgresql+psycopg2://postgres:[PASSWORD]@db.[project-ref].supabase.co:5432/postgres`

**⚠️ Important Notes**:
- **Session Pooler (port 6543)**: Better for serverless/Render (recommended)
- **Direct Connection (port 5432)**: Simpler but fewer concurrent connections
- **Password**: Found in Project Settings → Database → Database Password
- **SSL**: Our code automatically adds `sslmode=require` when `REQUIRE_SSL=true`

**Test the connection string locally**:
```bash
# In your .env file, temporarily set:
DATABASE_URL=postgresql+psycopg2://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres
REQUIRE_SSL=true

# Test connection
python -c "from app.core.db import engine; engine.connect(); print('✅ Connection successful!')"
```

---

### 3. Render Auto-Deploy with Docker ✅

**What happens**:
1. Render detects `render.yaml` in your repo
2. Sees `env: docker` and `dockerfilePath: Dockerfile`
3. Builds Docker image from `Dockerfile`
4. Runs container with `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Auto-deploys on every push to connected branch

**Verify in Render Dashboard**:
- Service Type: **Web Service**
- Environment: **Docker**
- Build Command: (auto-detected from Dockerfile)
- Start Command: (auto-detected from Dockerfile CMD)

**Manual trigger** (if needed):
- Render Dashboard → Your Service → Manual Deploy → Deploy latest commit

---

### 4. Tables Auto-Create on Supabase ✅

**How it works**:
- On app startup, `app/main.py` runs `startup_event()`
- This executes: `Base.metadata.create_all(bind=engine)`
- SQLAlchemy creates all tables defined in your models:
  - `users`
  - `wallets`
  - `wallet_transfers`
  - `offline_transactions`
  - `transactions`
  - `refresh_tokens`

**Verify tables created**:
1. Go to Supabase Dashboard → Table Editor
2. You should see all tables listed
3. Or check Render logs: `Base.metadata.create_all` should show success

**If tables don't auto-create**:
- Check Render logs for database connection errors
- Verify `DATABASE_URL` is correct in Render environment variables
- Ensure `REQUIRE_SSL=true` is set (Supabase requires SSL)

---

### 5. Link Android App to Render API ✅

**Get your Render API URL**:
- Render Dashboard → Your Service → Settings → URL
- Example: `https://offline-payment-system.onrender.com`

**Update Android app**:
```kotlin
// In your Android app's config/constants
const val API_BASE_URL = "https://offline-payment-system.onrender.com"
```

**Test connection**:
```bash
# Health check
curl https://your-render-url.onrender.com/health

# API docs
curl https://your-render-url.onrender.com/docs
```

**CORS Configuration**:
- In Render, set `CORS_ORIGINS` to your Android app's domain (if web-based)
- For native Android apps, you may need to allow all origins temporarily:
  - `CORS_ORIGINS=*` (⚠️ Only for development/testing)

---

## 🔍 Pre-Deployment Checklist

Before pushing to GitHub:

- [ ] All code changes committed
- [ ] `render.yaml` uses `env: docker`
- [ ] `Dockerfile` exists and is correct
- [ ] `requirements.txt` is clean (no unused deps)
- [ ] `.env` file is **NOT** committed (should be in `.gitignore`)
- [ ] `ENV_EXAMPLE.txt` is committed (template for team)

---

## 🚀 Post-Deployment Checklist

After Render deploys:

- [ ] Render service shows "Live" status
- [ ] Health endpoint works: `https://your-url.onrender.com/health`
- [ ] API docs accessible: `https://your-url.onrender.com/docs`
- [ ] Supabase tables created (check Table Editor)
- [ ] Test signup endpoint works
- [ ] Test login endpoint works
- [ ] Android app can connect to Render URL

---

## 🐛 Troubleshooting

### Connection String Issues
- **Error**: "SSL required but not supported"
  - ✅ Set `REQUIRE_SSL=true` in Render
  - ✅ Use Supabase pooler URL (port 6543)

- **Error**: "Database does not exist"
  - ✅ Use `postgres` as database name (Supabase default)
  - ✅ Check project reference in connection string

### Render Deployment Issues
- **Build fails**: Check Dockerfile syntax
- **Container crashes**: Check Render logs for Python errors
- **Port issues**: Render sets `$PORT` automatically, don't hardcode

### Table Creation Issues
- **Tables not created**: Check Render logs for SQLAlchemy errors
- **Permission errors**: Verify Supabase connection string has correct password
- **SSL errors**: Ensure `REQUIRE_SSL=true` and using pooler URL

---

## 📝 Quick Reference

**Supabase Connection String Format**:
```
postgresql+psycopg2://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

**Render Environment Variables**:
```
DATABASE_URL=<supabase-connection-string>
SECRET_KEY=<strong-random-hex>
DEBUG=false
REQUIRE_SSL=true
CORS_ORIGINS=https://your-frontend.com
```

**Test Commands**:
```bash
# Local test with Supabase
python -m app.db_init

# Test Render API
curl https://your-url.onrender.com/health
curl https://your-url.onrender.com/docs
```

---

✅ **All steps verified and ready for deployment!**

