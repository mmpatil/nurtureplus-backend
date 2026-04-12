---
description: Scaffold a complete new tracking resource following the Nurture+ 4-layer pattern (model + schema + crud + routes + migration). Usage: /new-resource <name> [owner: user|baby]
---

Scaffold a new tracking resource for the Nurture+ backend.

Resource name: $ARGUMENTS

## Instructions

Follow these steps in order. Do not skip any step.

### Step 1 — Read existing context
Before writing anything:
1. Read `app/models/recovery_entry.py` and `app/schemas/recovery.py` and `app/crud/recovery_entries.py` as reference implementations
2. Read the last migration in `alembic/versions/` to get the correct `down_revision`
3. Read the top of `app/api/routes.py` to see the current import block

### Step 2 — Clarify the resource design
Based on the resource name, determine:
- **Owner:** Does this belong directly to the `user` (like recovery_entries) or to a `baby` (like feeding_entries)? If ambiguous, ask.
- **Fields:** What domain fields make sense? Include timestamps and any enum-constrained fields.
- **Enum values:** List all valid string values for categorical fields.
- **Numeric bounds:** What are the valid ranges for numeric fields?

### Step 3 — Create the 5 files

**File 1: `app/models/<name>_entry.py`**
- UUID PK, `user_id` FK (+ `baby_id` FK if baby-owned), domain fields, `created_at`, `updated_at`
- `__table_args__` with Index on `user_id` and `(user_id, timestamp)`

**File 2: `app/schemas/<name>.py`**
- `<Name>Base` with `@field_validator` for all enums and bounds
- `<Name>Create(Base)`, `<Name>Update(BaseModel)` (all Optional), `<Name>Response(Base)` with `model_config`, `<Name>ListResponse`

**File 3: `app/crud/<name>_entries.py`**
- `create_<name>_entry(db, user_id, entry)` → Model
- `list_<name>_entries(db, user_id, limit, offset, from_time, to_time)` → (list, int)
- `get_<name>_entry(db, entry_id, user_id)` → Optional[Model]
- `update_<name>_entry(db, entry_id, user_id, update)` → Optional[Model]
- `delete_<name>_entry(db, entry_id, user_id)` → bool
- Every function filters by `user_id`, logs with `logger.info()`

**File 4: `app/api/routes.py`** — add at the end of the file:
- Import the new crud module and schemas at the top
- `POST /<name>` → 201
- `GET /<name>` → 200 (paginated, with optional `from_time`/`to_time` query params)
- `GET /<name>/{entry_id}` → 200
- `PUT /<name>/{entry_id}` → 200
- `DELETE /<name>/{entry_id}` → 204

**File 5: `alembic/versions/00N_add_<name>_entries.py`**
- Increment N from the latest migration
- Set `down_revision` to the latest migration's `revision` value
- `upgrade()` creates the table with all indexes
- `downgrade()` drops indexes then the table

### Step 4 — Verify
After creating all files, confirm:
- The migration `down_revision` matches the current latest migration's `revision` string exactly
- All CRUD functions include the `user_id` filter
- The route file imports are complete and the router decorator tags match the resource name
