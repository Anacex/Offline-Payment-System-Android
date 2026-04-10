# PRACTICAL_TESTING_GUIDE (ARCHIVED)

This file has been archived and its contents merged into `TESTING.md` at the repository root.

If you previously used this file, please consult `TESTING.md` which contains the current consolidated testing guidance, the test DB strategy, and the history of test stabilisation work.

Content moved to: `TESTING.md` (root)

- [ ] Can access protected endpoints with token

---

## 🚀 Quick Command Reference

```bash
# Unit tests only (fast)
pytest -m unit -v

# Integration tests only (slow)
pytest -m integration -v

# All tests
pytest -v

# Specific test file
pytest tests/test_health.py -v

# Run and show prints
pytest -v -s

# With coverage
pytest --cov=app tests/

# Parallel execution (faster)
pytest -n auto

# Stop on first failure
pytest -x

# Show slow tests
pytest --durations=10
```

---

## 📚 Next Steps

1. **Add SECRET_KEY to Render** (CRITICAL!)
2. **Create integration test files** (copy examples above)
3. **Run local tests** to verify setup
4. **Push to GitHub** and watch CI/CD run
5. **Monitor Actions tab** for any failures
6. **Check Render deployment** after push
7. **Test your mobile app** against production

Once all working, you have a complete CI/CD pipeline! 🎉
