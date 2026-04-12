---
description: Create a new Alembic migration file for schema changes. Usage: /db-migrate <description of change>
---

Create a new Alembic migration for the following change: $ARGUMENTS

## Steps

### 1. Check the current migration chain
Run: `alembic current` to see what's applied.
Read the latest file in `alembic/versions/` to get:
- The exact `revision` string (e.g., `"004_add_growth_and_milestone_entries"`)
- The numbering to determine the next N

### 2. Check what model changes need to be migrated
Read the relevant files in `app/models/` to understand the schema.
Compare against the existing migration files to confirm what's new.

### 3. Write the migration file

File: `alembic/versions/00N_<description>.py`

```python
"""<Description of change>

Revision ID: 00N_<description>
Revises: <previous_revision_id>
Create Date: <today's date>

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "00N_<description>"
down_revision = "<previous_revision_id>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Table creation or column additions
    pass


def downgrade() -> None:
    # Reverse of upgrade, in reverse order
    pass
```

### 4. Migration conventions
- **New table:** Use `op.create_table()` with all columns, then `op.create_index()` for each index
- **New column:** Use `op.add_column("table_name", sa.Column(...))`
  - If not nullable, must provide `server_default` or the table must be empty
  - Remove server_default after initial fill with `op.alter_column()` if needed
- **New index:** Use `op.create_index("ix_table_col", "table", ["col"])`
- **Drop:** Always drop indexes before dropping tables or columns

### 5. Verify the migration
After writing, run:
```bash
alembic upgrade head
```
Then verify with:
```bash
alembic current
```

If there's a problem, roll back with:
```bash
alembic downgrade -1
```

### 6. Column type reference
| Python type | SQLAlchemy | Alembic |
|---|---|---|
| UUID | `UUID(as_uuid=True)` | `postgresql.UUID(as_uuid=True)` |
| str | `String(N)` | `sa.String(N)` |
| int | `Integer` | `sa.Integer()` |
| datetime | `DateTime(timezone=True)` | `sa.DateTime(timezone=True)` |
| text | `Text` | `sa.Text()` |
| list[str] | `ARRAY(String)` | `postgresql.ARRAY(sa.String())` |
| bool | `Boolean` | `sa.Boolean()` |
