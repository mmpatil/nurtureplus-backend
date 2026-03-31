# Nurture+ Backend API

Production-friendly Python backend for the Nurture+ iOS app.

## Stack

- **Python 3.11** with FastAPI
- **PostgreSQL 16** with async SQLAlchemy 2.0
- **Firebase Admin SDK** for authentication
- **Alembic** for database migrations
- **Docker Compose** for local development
- **Structured logging** for production observability

## Features

✅ Firebase ID token authentication with local user persistence
✅ DEV_BYPASS_AUTH mode for testing (dev only)
✅ Pagination on list endpoints
✅ SQL query optimization with proper indexes
✅ Comprehensive error handling
✅ CORS configurable via environment
✅ Structured logging for all operations
✅ Async database operations for performance
✅ User-scoped queries (all DB queries filtered by authenticated user)

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Python 3.11 (for local development without Docker)
- PostgreSQL 16 (if running without Docker)

### 2. Set Up Environment

```bash
cp .env.example .env
nano .env
```

### 3. Set Up Firebase Service Account

1. Download your Firebase service account JSON from Google Cloud Console
2. Save as `service-account.json` in the project root

### 4. Run with Docker Compose

```bash
docker-compose up --build
```

API available at http://localhost:8000

### 5. Verify Installation

```bash
curl http://localhost:8000/health
open http://localhost:8000/docs
```

## Configuration

### Environment Variables (.env file)

```env
DATABASE_URL=postgresql+asyncpg://nurture_user:password123@localhost:5432/nurtureplus_db
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
DEV_BYPASS_AUTH=false
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
LOG_LEVEL=INFO
```

## API Endpoints

### Authentication
- `POST /auth/session` - Create session (Firebase token or dev bypass)

### Babies (Authenticated)
- `GET /babies` - List babies (paginated)
- `POST /babies` - Create baby
- `GET /babies/{baby_id}` - Get baby
- `PUT /babies/{baby_id}` - Update baby
- `DELETE /babies/{baby_id}` - Delete baby

### Health
- `GET /health` - Health check

## Example Usage

### Production: Create Session with Firebase Token

```bash
curl -X POST http://localhost:8000/auth/session \
  -H "Authorization: Bearer <firebase_id_token>" \
  -H "Content-Type: application/json"
```

### Development: Create Session with Dev Bypass

Enable `DEV_BYPASS_AUTH=true` in `.env`, then:

```bash
curl -X POST http://localhost:8000/auth/session \
  -H "X-Dev-Uid: test-user-123" \
  -H "Content-Type: application/json"
```

### Create a Baby

```bash
curl -X POST http://localhost:8000/babies \
  -H "Authorization: Bearer <firebase_id_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Emma",
    "birth_date": "2024-01-15",
    "photo_url": "https://example.com/photo.jpg"
  }'
```

### List Babies (Paginated)

```bash
curl http://localhost:8000/babies?limit=10&offset=0 \
  -H "Authorization: Bearer <firebase_id_token>"
```

### Update Baby

```bash
curl -X PUT http://localhost:8000/babies/{baby_id} \
  -H "Authorization: Bearer <firebase_id_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Emma Rose"}'
```

### Delete Baby

```bash
curl -X DELETE http://localhost:8000/babies/{baby_id} \
  -H "Authorization: Bearer <firebase_id_token>"
```

## Development

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL (macOS)
brew services start postgresql@16

# Or use Docker
docker run -d \
  -e POSTGRES_USER=nurture_user \
  -e POSTGRES_PASSWORD=password123 \
  -e POSTGRES_DB=nurtureplus_db \
  -p 5432:5432 \
  postgres:16-alpine

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Logging

Structured logs output to console:

```
2024-01-20 14:30:00 - app.api.routes - INFO - Session created for user: 123e4567-...
2024-01-20 14:30:01 - app.crud.babies - INFO - Created baby: 456e7890-... for user: 123e4567-...
```

Configure via `LOG_LEVEL` env var: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Security

### Authentication & Authorization

✅ Every query scoped to `current_user.id`
✅ Baby endpoints verify user ownership
✅ Firebase token validated on every request
✅ `401 Unauthorized` for missing/invalid tokens
✅ `404 Not Found` for unauthorized baby access (prevents data leaks)

### DEV_BYPASS_AUTH ⚠️

**Never enable in production.**

For testing only:
```env
DEV_BYPASS_AUTH=true
```

Then use `X-Dev-Uid: <user_id>` header instead of Bearer token.

Each unique dev UID creates a separate local user.

### Firebase Token Verification

Tokens verified server-side via Firebase Admin SDK:
- Token signature correct
- Token not expired
- Matches Firebase project
- Claims valid

## Extending the API

### Add Feeding Records (Example)

1. **Model** - `app/models/feeding.py`
2. **Schema** - `app/schemas/feeding.py`
3. **CRUD** - `app/crud/feeding.py`
4. **Routes** - Add endpoints to `app/api/routes.py`
5. **Migration** - `alembic revision --autogenerate -m "add_feedings"`

### Key Principles

- **User-scoped queries**: Always filter by `current_user.id`
- **Pagination**: Use `limit`/`offset` for lists
- **Indexes**: Add on foreign keys and frequent filters
- **Timestamps**: UTC `created_at` and `updated_at`
- **Soft deletes**: Add `deleted_at` column for audit trails
- **Validation**: Use Pydantic schemas
- **Logging**: Log all CRUD operations

## Production Deployment

### Pre-Deployment Checklist

- [ ] `DEV_BYPASS_AUTH=false`
- [ ] Firebase credentials secure
- [ ] Database URL points to production
- [ ] `ALLOWED_ORIGINS` restricted
- [ ] `LOG_LEVEL=INFO` or higher
- [ ] Migrations run successfully
- [ ] Health check passes
- [ ] CORS verified

### Recommended Architecture

```
Load Balancer (HTTPS)
  ↓
Kubernetes/ECS/Cloud Run (multiple instances)
  ↓
PostgreSQL (AWS RDS / Google Cloud SQL)
  ↓
Cloud Backup
```

### Monitoring

Track:
- Response time (p95 < 200ms)
- Error rate (< 0.1%)
- DB connection pool
- Log frequencies
- Auth failures

Tools: DataDog, New Relic, Sentry, CloudWatch, Prometheus

## Troubleshooting

### "Error: could not connect to server"

PostgreSQL not running. Start with:
```bash
docker-compose up postgres
```

### "Firebase token verification failed"

Check:
1. `service-account.json` exists and is valid
2. `GOOGLE_APPLICATION_CREDENTIALS=./service-account.json`
3. Service account has correct Firebase project
4. Validate JSON: `python -m json.tool service-account.json`

### "401 Unauthorized"

Check:
1. Token is valid Firebase ID token
2. Token not expired (1 hour expiry)
3. Header format: `Authorization: Bearer <token>`
4. Check logs for details

### "404 Not Found"

Check:
1. Baby ID is valid UUID
2. Baby created by current user
3. Baby not deleted
4. Migrations completed

## License

MIT