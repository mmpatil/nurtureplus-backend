---
description: Generate a complete pytest test file for a given resource or endpoint. Usage: /add-tests <resource name, e.g. recovery or growth>
---

Generate a complete test file for: $ARGUMENTS

## Step 1 — Read the source files
Read these files for the resource:
- `app/schemas/<resource>.py` — to understand all fields, validators, and constraints
- `app/crud/<resource>_entries.py` — to understand all functions
- The relevant route definitions in `app/api/routes.py` — to find all endpoints and status codes

## Step 2 — Generate `tests/test_<resource>_entries.py`

Structure:
```python
"""Tests for <resource> entries."""
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.core.security import get_current_user
from app.schemas.<resource> import <Resource>Create

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_mock_user():
    from app.models.users import User
    user = User()
    user.id = uuid4()
    user.firebase_uid = f"test_{user.id}"
    return user

MOCK_USER = make_mock_user()


# ---------------------------------------------------------------------------
# Schema Validation Tests (synchronous, no DB, no auth)
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_valid_payload(self): ...
    def test_invalid_enum_field(self): ...      # one test per enum field
    def test_numeric_bounds_low(self): ...
    def test_numeric_bounds_high(self): ...
    def test_optional_fields_default(self): ...


# ---------------------------------------------------------------------------
# Endpoint Tests (with dependency override)
# ---------------------------------------------------------------------------

class TestCreate<Resource>:
    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_create_returns_201(self): ...
    def test_create_invalid_payload_returns_422(self): ...
    def test_create_missing_auth_returns_401(self): ...


class TestList<Resource>:
    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_list_returns_200_with_pagination_shape(self): ...
    def test_list_with_limit_and_offset(self): ...
    def test_list_with_time_filter(self): ...
    def test_list_missing_auth_returns_401(self): ...


class TestGet<Resource>:
    def test_get_not_found_returns_404(self): ...
    def test_get_other_users_resource_returns_404(self): ...


class TestUpdate<Resource>:
    def test_update_invalid_field_returns_422(self): ...
    def test_update_not_found_returns_404(self): ...


class TestDelete<Resource>:
    def test_delete_not_found_returns_404(self): ...
```

## Step 3 — Rules for the generated tests

1. **Schema tests are synchronous** (`def test_`, not `async def test_`)
2. **Endpoint tests use `setup_method`/`teardown_method`** to set and clear `app.dependency_overrides`
3. **404 for cross-user access** — always include a test that proves user B can't see user A's data
4. **Every enum field gets its own invalid-value test**
5. **Numeric bound tests** — test one below min and one above max
6. **Tests that need a real DB** should be clearly marked with `@pytest.mark.skip(reason="requires DB")` for now if no test DB is configured

## Step 4 — Verify
After writing the file, run:
```bash
pytest tests/test_<resource>_entries.py -v
```

Note which tests pass (schema validation tests should pass immediately), and which need a running DB or further setup.
