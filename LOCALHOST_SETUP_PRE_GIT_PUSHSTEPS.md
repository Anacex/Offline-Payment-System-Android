# Localhost Setup (Wi‑Fi) + Pre‑Git Push Safety Steps

Use this to run the backend + PostgreSQL locally, then connect from the Android app on your phone over the same home Wi‑Fi. This guide is written so Windows teammates can follow it too.

---

## 1) Start PostgreSQL locally (Docker Compose)
1. Open a terminal in the repo root (the folder that contains `docker-compose.yml`).
   - Windows: ensure your terminal points at the same folder.

2. Start Postgres:
   ```bash
   docker compose up -d
   ```

3. Confirm Postgres is running:
   ```bash
   docker compose ps
   ```

Local DB defaults (from `docker-compose.yml`):
- host: `localhost`
- port: `5432`
- database: `offlinepay`
- user: `offlinepay_user`
- password: `offlinepay123`

---

## 2) Configure backend `.env` for localhost DB
The backend uses `app/core/config.py` and loads `.env` automatically (via `env_file=".env"`).

1. Copy template if needed:
   ```bash
   cp .env.example .env
   ```
   (Windows: you can create/edit `.env` manually instead.)

2. Edit `.env` for local testing:
- `DATABASE_URL=postgresql+psycopg2://offlinepay_user:offlinepay123@localhost:5432/offlinepay`
- `REQUIRE_SSL=false`

Notes:
- Do not commit `.env` (it is gitignored).
- Keep your `SECRET_KEY` as a long random string for local JWT auth. You can reuse the existing one for dev.

---

## 3) Install Python dependencies + build schema locally
From the repo root:

### 3.1 Create venv + install deps
- Linux/macOS:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Windows:
  ```powershell
  py -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  ```

### 3.2 Build the schema (tables) on localhost
Run:
```bash
python -m app.db_init
```

You should see tables being created successfully (users, wallets, offline_transactions, transactions, refresh_tokens, otp_challenges).

---

## 4) Run the backend server so the phone can reach it
Start Uvicorn on all interfaces:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4.1) View logs and stop the server
The server can be running as either:
1) a normal CPU process (you launched `uvicorn`), or
2) a Docker container (if you started it with `docker run`).

### A) If you started with `uvicorn` directly
- Logs appear in the same terminal where you started Uvicorn.
- Stop it with `Ctrl+C`.

Optional: identify what is listening on port `8000`:
```bash
ss -ltnp | awk '$4 ~ /:8000$/ {print}'
```

### B) If you started with Docker (`docker run ...`)
1. List running containers:
   ```bash
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   ```
2. View logs (follow in real time):
   ```bash
   docker logs -f offlinepay-server-local
   ```
3. Stop the container:
   ```bash
   docker stop offlinepay-server-local
   ```
   If you need to force remove it:
   ```bash
   docker rm -f offlinepay-server-local
   ```
---

## 5) Verify localhost is reachable over the home Wi‑Fi

### 5.1 Find your laptop LAN IP
- Windows: run `ipconfig`, look for `IPv4 Address` (example: `192.168.2.133`)
- Linux/macOS: run `hostname -I` (or `ip a`)

Save it as `<YOUR_LAN_IP>`.

### 5.2 Check from laptop
```bash
curl http://<YOUR_LAN_IP>:8000/health
```
Expected:
```json
{"status":"ok"}
```

### 5.3 Check from the phone (recommended)
Open the phone browser and go to:
`http://<YOUR_LAN_IP>:8000/health`

If it returns `{"status":"ok"}`, networking is correct.

---

## 6) Build/install the Android app for local Wi‑Fi testing (debug)
The app uses `BuildConfig.API_BASE_URL` and we inject it at build time.

1. Build debug APK pointing to your laptop LAN IP:
   - Windows:
     ```powershell
     cd "Android App/Offlink-Android-App"
     .\gradlew.bat assembleDebug -PAPI_BASE_URL="http://<YOUR_LAN_IP>:8000/"
     ```
   - Linux/macOS:
     ```bash
     cd "Android App/Offlink-Android-App"
     ./gradlew assembleDebug -PAPI_BASE_URL="http://<YOUR_LAN_IP>:8000/"
     ```

2. Install the resulting debug build on your phone (Android Studio is fine).

HTTP note:
- Local testing uses `http://` (not `https://`). The debug build allows cleartext HTTP via a Gradle manifest placeholder.

---

## 7) Optional: confirm schema exists (quick)
If you want an extra confirmation, run:
```bash
python check_schema.py
```
It prints whether expected tables like `users` exist.

---

## 8) Before pushing to GitHub: revert to Cloud safely (do this every time)
Goal: ensure your PR does NOT contain local LAN/IP changes and does NOT break CI.

Checklist before `git add` / `git commit`:
1. Do not commit `.env` (it is gitignored). Still verify with:
   ```bash
   git status
   ```
2. Do not edit Android source files to hardcode your LAN IP.
   - Local testing must be done only via the Gradle property:
     `-PAPI_BASE_URL="http://<YOUR_LAN_IP>:8000/"`
3. Make sure `Android App/Offlink-Android-App/app/build.gradle.kts` still contains the Cloud default Render URL (the fallback value).
4. If you changed anything for local setup, revert those files back to the Cloud defaults before committing.

---

## 9) After pushing
- CI will run against your Cloud/Render configuration and Cloud DB connection settings (as configured by Render/GitHub Secrets).

