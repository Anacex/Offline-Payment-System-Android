# GitHub Secrets - Quick Setup Checklist

## 🚀 Quick Setup (5 minutes)

### Step 1: Generate SECRET_KEY

**PowerShell (Windows)**:
```powershell
[Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

**Python**:
```python
import secrets
print(secrets.token_hex(32))
```

Copy the output (e.g., `a7f3e9c2b5d8a1f4e6c9b2d5a8f3e7c0b4d9f2e5a8c1b4d7f0e3a6c9f2e5b8`)

### Step 2: Add Secrets to GitHub

1. Go to: **https://github.com/Anacex/Offline-Payment-System-Android/settings/secrets/actions**
2. Click **New repository secret** (top right)

**First Secret:**
  ```
  postgresql://postgres.pnvgnapukrshnnxveogv:[password]@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres
  ```

**Second Secret:**

### Step 3: Verify

You should see both secrets listed on the Secrets page (values will be masked).


## ✅ Done!

Your CI/CD pipeline is now ready to use. Test it by:
1. Making a commit: `git commit -am "test ci/cd"`
2. Pushing: `git push origin main`
3. Go to **Actions** tab on GitHub
4. Watch your workflow run!


## 📋 Secrets Reference

| Secret Name | Value | Where to Get It |
|---|---|---|
| `SUPABASE_DB_URL` | Your Supabase connection string | Supabase dashboard → Settings → Database |
| `SECRET_KEY` | Random 64-character hex string | Generate with command in Step 1 |


## 🔗 Important Links



## 🆘 Troubleshooting

**Secrets not working?**

**Tests failing in CI?**

