# Testing documentation

This document consolidates the project's testing guidance, the local test database strategy we implemented, and a short history of the test stabilisation work done in this repository.

## Purpose

- Describe how to run the unit and integration tests.
- Explain the local test DB strategy (so tests don't touch production Supabase).
- Summarise the fixes and changes made while stabilising the unit suite.

## Quick commands

Run unit tests (fast, local):

```powershell
pytest -m unit -q
```

Run all tests (unit + integration):

```powershell
pytest -v
```

Run a single test file or test:

```powershell
# Example: single test
pytest tests/test_auth.py::test_logout_success -q -s
```

## Test DB strategy (local unit tests)

The repository uses a safe local test database configuration so unit tests do not hit Supabase or production resources. Key points:

- `tests/conftest.py` sets `os.environ['DATABASE_URL']` before importing the application so the app's SQLAlchemy engine is created against the test DB.
- A temporary file-based SQLite database is used for tests (not an in-memory DB). The engine is created with:

```py
create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```

- A per-test SQLAlchemy connection + transaction pattern is used:
  - For each test, open a connection and begin a transaction.
  - Bind a Session to that connection and yield it to the app via dependency override.
  - Roll back the transaction at teardown so tests are isolated and don't persist rows between tests.

This avoids:
- SQLite "created in a thread" errors that appear with in-memory DBs when TestClient uses separate threads.
- UNIQUE/duplicate key errors caused by state persisting across tests.

If you want CI parity, consider using a real Postgres service in CI (recommended) or run tests inside a container using the same Supabase/Postgres connection string.

## What we changed during test stabilisation

Summary of important edits that brought the unit suite from many failures/errors down to green:

- Rewrote `tests/conftest.py` to create a temporary file-based SQLite DB and to create tables prior to app import.
- Implemented per-test transactional sessions that begin a connection and roll back at teardown to isolate tests.
- Overrode `app.dependency_overrides[get_db]` in tests to force the app to use the test session.
- Fixed code / test mismatches:
  - Switched Pydantic usage to `.dict()` where `.model_dict()` was used incorrectly.
  - Included the `/sync` router in `app/main.py` so sync-related tests can exercise those routes.
  - Relaxed router-level authentication in offline transaction endpoints where verification should be public.
  - Normalised amount serialization (format amounts with two decimal places in offline transaction creation) so tests and API agree on formatting.
  - Adjusted test expectations (status codes and seeded balances) to reflect the app's intended behaviour.

## Tests we ran and results

- After the final fixes the run used:

```powershell
pytest tests/ -m unit -q
```

- Result observed at the time of consolidation: `46 passed, 1 deselected, 10 warnings`.

## Conftest summary (implementation notes)

- Create temp directory for DB files and set `DATABASE_URL` to a `sqlite:///` path inside that dir.
- Create `test_engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})`.
- Call `Base.metadata.create_all(bind=test_engine)` once at test session start.
- For each test:
  - `connection = test_engine.connect()`
  - `transaction = connection.begin()`
  - `session = Session(bind=connection)`
  - yield session to the test and app dependency override
  - after test: `session.close()` and `transaction.rollback()` and `connection.close()`

This provides both thread-safety and isolation between tests.

## How to reproduce locally

1. Ensure your local `.env` or environment variables don't point to production Supabase when running unit tests (the `conftest` sets `DATABASE_URL` for tests so this is safe by default, but double-check envs when debugging).
2. Run unit tests: `pytest -m unit -q`.
3. For verbose output or debugging prints use `-s` and `-v`.

## Troubleshooting

- If you see `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`:
  - Confirm `check_same_thread=False` is set on the test engine.
  - Ensure a file-based sqlite DB is used, not `:memory:`.

- If you see UNIQUE constraint errors across tests:
  - Confirm transactional per-test rollback is configured correctly in `tests/conftest.py`.

- If you see 422 body validation on logout or other endpoints:
  - Inspect endpoint signatures (body param shape). Tests were aligned to the expected shapes; update either tests or endpoint parameter to match.

## Notes for CI

- CI should either:
  - Run unit tests using the same temporary SQLite strategy (fast, simple), or
  - Use a Postgres service in CI for closer parity with production. If you use Postgres, set `SUPABASE_DB_URL` or `DATABASE_URL` in GitHub Secrets and ensure tests create and tear down schemas or run inside isolated containers.

- Ensure `SECRET_KEY` is set in GitHub Secrets for any tests that depend on JWT creation/verification.

## Next steps (optional cleanup)

- Move tests that require real DB behaviour into an `integration` marker and run them separately against Postgres in CI.
- Add test coverage reporting (`pytest --cov=app`) to CI job artifacts.

---

If you'd like, I can commit these new docs and archive or delete the older duplicates. Tell me whether you prefer deleting the original files or moving them to an `archive_docs/` folder in the repo (I can do either).
