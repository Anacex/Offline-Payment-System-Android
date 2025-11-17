# README_CI_CD (ARCHIVED)

This document has been moved to `archive_docs/README_CI_CD.md`.

For up-to-date CI and secrets guidance, see `CI_AND_SECRETS.md` at the repository root and `TESTING.md` for testing guidance.

**Benefits:**
- ✅ Credentials are NOT exposed in the repository
- ✅ Secrets are encrypted by GitHub
- ✅ Can be rotated independently
- ✅ Follows security best practices

### 2. Pytest Markers Added ✅
Test categorization system implemented:
- `@pytest.mark.unit` - Tests that run locally against your code
- `@pytest.mark.integration` - Tests that run against production Render server
- `@pytest.mark.smoke` - Quick validation tests
- `@pytest.mark.slow` - Long-running tests

**Benefits:**
- ✅ Run specific test types without running all tests
- ✅ Separate unit tests from production integration tests
- ✅ Better CI/CD pipeline control

### 3. Enhanced CI/CD Pipeline ✅
Two-stage testing system:

**Stage 1: Unit Tests** (runs on every push)
- Code checkout
- Python 3.11 setup
- Flake8 linting
- Unit tests against Supabase
- Health endpoint validation

**Stage 2: Integration Tests** (only on main branch, after unit tests pass)
- Production server health checks (30 attempts with backoff)
- Tests marked with `@pytest.mark.integration`
- API endpoint validation against Render
# README_CI_CD (ARCHIVED)

The CI/CD documentation has been consolidated into `CI_AND_SECRETS.md` and the test-related material merged into `TESTING.md`.

Please consult those two files for up-to-date CI, secrets, and testing guidance.
