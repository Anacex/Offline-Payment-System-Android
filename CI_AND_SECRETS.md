# CI & GitHub Secrets — consolidated guide

This file consolidates the CI/CD and GitHub Secrets related documentation into a single reference.

## Purpose

- Explain which repository secrets are required for tests and deployment.
- Summarise the CI pipeline structure and test marker usage.
- Short steps to add secrets and validate the pipeline.

## Required repository secrets

- `SUPABASE_DB_URL` or `DATABASE_URL`
  - Example (SQLAlchemy format):
    `postgresql+psycopg2://postgres.<project_ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`

- `SECRET_KEY`
  - A 32-byte (64 hex char) random string used to sign JWTs.
  - Generate locally (PowerShell):

```powershell
[Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

## CI test markers and jobs

- Tests are categorised with pytest markers in `pytest.ini`:
  - `@pytest.mark.unit` — unit tests (fast) run on every push
  - `@pytest.mark.integration` — integration tests (run against Render/prod) — usually only on main
  - `@pytest.mark.smoke` / `@pytest.mark.slow` — optional categories

- Typical CI flow (recommended):
  1. Checkout
  2. Setup Python 3.11
  3. Install dependencies
  4. Run linting (optional)
  5. Run unit tests: `pytest -m unit` (fast)
  6. On `main` branch, wait for Render health and run: `pytest -m integration`

## Add GitHub secrets (short)

1. Go to: `https://github.com/<org>/<repo>/settings/secrets/actions`
2. Add `SUPABASE_DB_URL` (value: SQLAlchemy-formatted Supabase/Postgres URL)
3. Add `SECRET_KEY` (value: generated hex string)
4. Optionally add `DEBUG`, `REQUIRE_SSL`, `CORS_ORIGINS` as repo-level environment variables

## Validate CI

1. Push a commit to a non-main branch and watch Actions: unit tests should run.
2. Push a commit to `main` to run integration jobs (if configured).
3. Inspect job logs for failures — the CI job will print test output and any errors.

## Notes and best practices

- Never commit secrets to the repository. Keep them in GitHub Secrets and Render environment.
- If your tests need a DB that matches production, run a Postgres service in CI instead of SQLite.
- Keep unit tests fast — they should not depend on network resources.

---

This file replaces the older `README_CI_CD.md`, `CI_CD_SETUP_COMPLETE.md`, and the separate `GITHUB_SECRETS_*` quick guides. The older files have been archived or removed to reduce duplication.
