# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run locally (without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL via Docker
docker-compose up postgres

# Apply migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run with Docker Compose
```bash
docker-compose up --build
```
API available at http://localhost:8000, interactive docs at http://localhost:8000/docs.

### Database migrations
```bash
alembic revision --autogenerate -m "description"  # create
alembic upgrade head                               # apply
alembic downgrade -1                              # rollback one
```

### Run tests
```bash
pytest
pytest tests/test_recovery_entries.py  # single file
```

## Architecture

The app follows a strict four-layer pattern: **models → schemas → crud → routes**.

```
app/
├── main.py              # FastAPI app, CORS middleware, router registration, lifespan events
├── api/routes.py        # All HTTP endpoints (single file)
├── core/
│   ├── config.py        # Settings loaded from env vars
│   └── security.py      # Firebase token verification + get_current_user dependency
├── db/
│   ├── base.py          # SQLAlchemy declarative base
│   └── session.py       # Async engine, get_db dependency
├── models/              # SQLAlchemy ORM table definitions
├── schemas/             # Pydantic request/response models
└── crud/                # All database query logic
```

### Authentication flow

Every protected endpoint uses two FastAPI dependencies injected via `Depends`:
- `get_db` → yields an `AsyncSession`
- `get_current_user` → verifies Firebase token, finds-or-creates the `User` row, returns it

In dev mode (`DEV_BYPASS_AUTH=true`), pass `X-Dev-Uid: <any-string>` instead of a Bearer token. Each unique dev UID creates a separate user.

### User-scoped data

Every CRUD function accepts `user_id` and filters all queries by it. Resources return 404 (not 403) when a user tries to access another user's data, to avoid leaking existence.

### Adding a new resource

Follow this pattern (already used for feeding, diaper, sleep, mood, recovery, growth, milestone entries):

1. `app/models/<name>.py` — SQLAlchemy model; include `user_id` FK + indexes
2. `app/schemas/<name>.py` — Pydantic schemas for Create, Update, Response, ListResponse
3. `app/crud/<name>_entries.py` — async CRUD functions, always filtered by `user_id`
4. `app/api/routes.py` — add endpoints importing from the new crud/schema modules
5. `alembic revision --autogenerate -m "add_<name>_table"` then `alembic upgrade head`

### Deployment

- **Local dev**: Docker Compose (`docker-compose.yml`)
- **Production**: Vercel via `api/index.py` (routes all traffic) + `vercel.json`; also supports Fly.io via `fly.toml`
- Migrations run automatically in Docker Compose on startup before `uvicorn`

## Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://nurture_user:password123@localhost:5432/nurtureplus_db
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
DEV_BYPASS_AUTH=false   # set true for local testing without Firebase tokens
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
LOG_LEVEL=INFO
```

`service-account.json` (Firebase service account) must exist in the project root for auth to work. Never set `DEV_BYPASS_AUTH=true` in production.
