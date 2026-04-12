---
description: Review current git changes against Nurture+ backend standards — security, architecture, performance, and migration correctness.
---

Perform a structured code review of the current changes in this repository.

## Step 1 — Gather the diff
Run `git diff main` (or `git diff HEAD` if on main) to see all changes. Also run `git status` to catch new untracked files.

## Step 2 — For each changed or new file, check:

**Models (`app/models/`)**
- [ ] UUID PK with `default=uuid.uuid4`
- [ ] `user_id` FK to `users.id` with `ondelete="CASCADE"`
- [ ] All timestamp columns use `DateTime(timezone=True)` and `datetime.now(timezone.utc)` defaults
- [ ] `__table_args__` has Index on `user_id` and `(user_id, <time_col>)`

**Schemas (`app/schemas/`)**
- [ ] `Update` schema has all fields as `Optional`
- [ ] `@field_validator` uses `@classmethod` decorator (Pydantic v2)
- [ ] Response schema has `model_config = {"from_attributes": True}`
- [ ] Validators on `Update` schemas re-check `if v is not None` before validating

**CRUD (`app/crud/`)**
- [ ] Every `select()` filters by `user_id`
- [ ] Total count uses `SELECT COUNT(*)`, not `len(result.scalars().all())`
- [ ] All functions log with `logger.info()`
- [ ] `update_*` uses `model_dump(exclude_unset=True)` for partial updates

**Routes (`app/api/routes.py`)**
- [ ] Every protected endpoint has `current_user: User = Depends(get_current_user)`
- [ ] UUID path params validated with `try: UUID(id) except ValueError: raise HTTPException(422)`
- [ ] Missing resources return 404 (not 403) to prevent existence leaks
- [ ] POST returns `status_code=status.HTTP_201_CREATED`
- [ ] DELETE returns `status_code=status.HTTP_204_NO_CONTENT`

**Migrations (`alembic/versions/`)**
- [ ] File exists for every model/schema change
- [ ] `down_revision` correctly chains from the previous migration
- [ ] `downgrade()` reverses everything in `upgrade()` in reverse order
- [ ] UUID PKs use `server_default=sa.text("gen_random_uuid()")`
- [ ] Timestamp columns use `server_default=sa.func.now()`

**Security**
- [ ] No hardcoded credentials, tokens, or secrets
- [ ] `DEV_BYPASS_AUTH` not referenced outside `app/core/security.py` and `app/core/config.py`
- [ ] Error messages are generic — no internal details exposed to clients

## Step 3 — Output a structured report

```
## Code Review

### Blockers (must fix before merge)
- [ ] ...

### Should Fix
- [ ] ...

### Suggestions
- [ ] ...

### Approved Patterns (looks good)
- ...
```

Be specific: cite file paths and line numbers for every finding.
