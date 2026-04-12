---
description: Run the pre-deployment checklist for the Nurture+ backend — validates security config, migration state, and deployment readiness before pushing to production.
---

Run the pre-deployment checklist for Nurture+ backend.

## Step 1 — Security configuration audit

Check for dangerous settings:
```bash
# Verify DEV_BYPASS_AUTH is not true in any production config
grep -rn "DEV_BYPASS_AUTH" . --include="*.py" --include="*.env" --include="*.toml" --include="*.json" | grep -v ".git" | grep -v "__pycache__"
```

- [ ] `DEV_BYPASS_AUTH=false` (or not set) in all production environment files
- [ ] `docker-compose.yml` DEV_BYPASS_AUTH is `"true"` — this is expected for local dev only, **not** deployed
- [ ] `fly.toml` does not contain `DEV_BYPASS_AUTH=true`

## Step 2 — Credential safety

```bash
# Check service account is gitignored
grep "service-account" .gitignore

# Check for any committed credentials
git log --all --full-history -- "service-account.json"
git log --all --full-history -- ".env"
```

- [ ] `service-account.json` is in `.gitignore`
- [ ] No `.env` with real credentials committed to git
- [ ] Firebase service account will be injected via `FIREBASE_SERVICE_ACCOUNT_JSON` env var on Vercel

## Step 3 — Migration state

```bash
# Check current migration head
alembic current

# Check for any pending model changes not covered by migrations
alembic check 2>/dev/null || echo "Note: 'alembic check' may not be available"
```

- [ ] `alembic current` shows the latest migration ID
- [ ] All new model files in `app/models/` have corresponding migration files in `alembic/versions/`
- [ ] Untracked migration files: check `git status` for any `alembic/versions/*.py` that are new

## Step 4 — Code health check

```bash
# Check for obvious Python syntax errors
python3 -c "import app.main" 2>&1 || echo "Import failed"

# Verify all new model imports are in alembic/env.py or db/base.py
grep "import" alembic/env.py app/db/base.py
```

- [ ] `python3 -c "import app.main"` succeeds without errors
- [ ] New models are imported somewhere that Alembic can discover them for `--autogenerate`

## Step 5 — Health check (if server is running)

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status": "ok"}`

## Step 6 — CORS configuration

Read `app/core/config.py` and verify `ALLOWED_ORIGINS` in production will be:
- [ ] A specific list of domains, not `*`
- [ ] Includes the iOS app's domain (if any web frontend is used)

## Step 7 — Deployment target check

**For Vercel:**
- [ ] `vercel.json` routes correctly point to `api/index.py`
- [ ] `api/index.py` imports from `app.main` correctly
- [ ] All dependencies in `requirements.txt` are pinned

**For Fly.io:**
- [ ] `fly.toml` has the correct `DATABASE_URL` configuration
- [ ] Release command runs `alembic upgrade head`

## Summary

Print a final checklist summary:
```
Pre-Deployment Checklist Results
=================================
Security: PASS/FAIL
Credentials: PASS/FAIL
Migrations: PASS/FAIL
Code health: PASS/FAIL
CORS: PASS/FAIL

Overall: READY / NOT READY
```

If anything fails, list the specific issues and how to fix them.
