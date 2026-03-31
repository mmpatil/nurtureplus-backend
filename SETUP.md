# Setup Instructions for Nurture+ Backend

## Prerequisites

- macOS, Linux, or Windows (WSL2)
- Docker & Docker Compose (for containerized setup)
- Python 3.11+ (for local development)
- PostgreSQL 16+ (for local non-Docker setup)
- Git

## Option 1: Docker Compose (Recommended for Quick Start)

### Step 1: Clone Repository

```bash
cd nurtureplus-backend
```

### Step 2: Set Up Firebase

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new Firebase project or select existing
3. Go to Project Settings → Service Accounts
4. Click "Generate New Private Key"
5. Save the JSON file as `service-account.json` in project root
6. **⚠️ Keep this file secret! Add to .gitignore**

### Step 3: Configure Environment

```bash
# Create .env from example
cp .env.example .env

# Edit .env with your settings (optional, defaults work for local dev)
nano .env
```

Default values are safe for local development:
- Database: Postgres in Docker
- Port: 8000
- CORS: localhost:3000, localhost:8000
- Dev bypass: disabled

### Step 4: Start Services

```bash
# Build and start all services
docker-compose up --build

# First run automatically:
# - Creates database schema
# - Runs migrations (alembic upgrade head)
# - Starts FastAPI server on :8000
```

### Step 5: Verify

```bash
# In another terminal
curl http://localhost:8000/health

# Should return: {"status": "ok"}
```

### Step 6: Open API Docs

```bash
open http://localhost:8000/docs
```

Interactive Swagger UI for testing all endpoints.

---

## Option 2: Local Development (Without Docker)

### Step 1: Install Python 3.11

**macOS (Homebrew):**
```bash
brew install python@3.11
```

**Ubuntu/Debian:**
```bash
sudo apt-get install python3.11 python3.11-venv
```

### Step 2: Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16

# Create database and user
createuser -d nurture_user -P  # Enter password: password123
createdb -O nurture_user nurtureplus_db
```

**Docker (easier):**
```bash
docker run -d \
  --name nurture_postgres \
  -e POSTGRES_USER=nurture_user \
  -e POSTGRES_PASSWORD=password123 \
  -e POSTGRES_DB=nurtureplus_db \
  -p 5432:5432 \
  postgres:16-alpine
```

### Step 5: Set Up Firebase

Same as Docker setup (Step 2 above).

### Step 6: Configure Environment

```bash
cp .env.example .env
nano .env

# Verify DATABASE_URL matches your local setup:
# DATABASE_URL=postgresql+asyncpg://nurture_user:password123@localhost:5432/nurtureplus_db
```

### Step 7: Run Database Migrations

```bash
alembic upgrade head
```

This creates all tables in your PostgreSQL database.

### Step 8: Start Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag auto-restarts on code changes.

### Step 9: Verify

```bash
# In another terminal
curl http://localhost:8000/health

open http://localhost:8000/docs
```

---

## Development Workflow

### Running Tests

(Coming soon - unit tests for auth, CRUD, etc.)

```bash
# pytest tests/
```

### Creating Database Migrations

After modifying models in `app/models/`:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add_feeding_table"

# Inspect generated migration in alembic/versions/
nano alembic/versions/*_add_feeding_table.py

# Apply migration
alembic upgrade head
```

### Checking Logs

When running locally:
```bash
# Set log level for more detail
LOG_LEVEL=DEBUG uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

With Docker:
```bash
docker-compose logs -f api
```

### Accessing Database Directly

**SQLAlchemy + psycopg:**
```bash
# Local PostgreSQL
psql -U nurture_user -d nurtureplus_db

# In psql:
\dt              # List tables
\d users         # Show users table schema
SELECT * FROM users;  # Query users

# Exit
\q
```

**From Docker:**
```bash
docker exec -it nurture_postgres psql -U nurture_user -d nurtureplus_db
```

### Resetting Database

```bash
# Local
dropdb -U nurture_user nurtureplus_db
createdb -O nurture_user nurtureplus_db
alembic upgrade head

# Docker
docker-compose down -v  # Remove volumes
docker-compose up       # Recreates database
```

---

## Dev Mode (Testing Without Firebase)

### Enable Dev Bypass

Edit `.env`:
```env
DEV_BYPASS_AUTH=true
```

Restart server:
```bash
# Docker
docker-compose restart api

# Local
# Ctrl+C to stop, then restart
```

### Test Without Firebase Token

```bash
# Create session with mock user
curl -X POST http://localhost:8000/auth/session \
  -H "X-Dev-Uid: test-user-alice" \
  -H "Content-Type: application/json"

# Returns:
# {
#   "user_id": "550e8400-e29b-41d4-a716-446655440000",
#   "firebase_uid": "test-user-alice"
# }

# Create baby with that session
curl -X POST http://localhost:8000/babies \
  -H "X-Dev-Uid: test-user-alice" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Baby",
    "birth_date": "2024-01-15"
  }'

# List babies
curl http://localhost:8000/babies \
  -H "X-Dev-Uid: test-user-alice"
```

**⚠️ Never leave DEV_BYPASS_AUTH=true in production!**

---

## Troubleshooting

### "connection refused" when starting API

PostgreSQL not running or `DATABASE_URL` incorrect.

**Fix:**
1. Verify Postgres is running: `pg_isready -h localhost`
2. Check `.env` DATABASE_URL is correct
3. If using Docker: `docker-compose logs postgres`

### "Firebase token verification failed"

Service account JSON invalid or missing.

**Fix:**
1. Verify `service-account.json` exists and is valid JSON
2. Check file permissions: `ls -la service-account.json`
3. Validate JSON: `python -m json.tool service-account.json`
4. Ensure file is in project root, not subdirectory

### "alembic: command not found"

Python dependencies not installed.

**Fix:**
```bash
source venv/bin/activate
pip install -r requirements.txt
alembic --version  # Verify
```

### Port 8000 already in use

Another service using port 8000.

**Fix:**
```bash
# Find process using port 8000 (macOS/Linux)
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

### Database migration fails with "table already exists"

Alembic state out of sync.

**Fix:**
```bash
# Check current revision
alembic current

# See all revisions
alembic history

# Reset (caution: deletes all data)
alembic downgrade base
alembic upgrade head
```

---

## Docker Compose Reference

```bash
# Start all services
docker-compose up

# Rebuild images
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f postgres

# Stop services
docker-compose stop

# Stop and remove volumes (data)
docker-compose down -v

# SSH into running container
docker-compose exec api bash
docker-compose exec postgres bash

# Run one-off command in container
docker-compose exec api alembic upgrade head
docker-compose exec postgres psql -U nurture_user -d nurtureplus_db
```

---

## Project Structure

```
nurtureplus-backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── core/
│   │   ├── config.py        # Settings from .env
│   │   └── security.py      # Firebase auth & user dependency
│   ├── api/
│   │   └── routes.py        # All API endpoints
│   ├── models/
│   │   ├── users.py         # User SQLAlchemy model
│   │   └── babies.py        # Baby SQLAlchemy model
│   ├── schemas/
│   │   ├── auth.py          # Auth request/response schemas
│   │   ├── user.py          # User schemas
│   │   └── baby.py          # Baby schemas
│   ├── crud/
│   │   ├── users.py         # User queries
│   │   └── babies.py        # Baby queries
│   └── db/
│       ├── base.py          # SQLAlchemy declarative base
│       └── session.py       # Database connection & session
├── alembic/
│   ├── env.py               # Alembic configuration
│   ├── versions/            # Migration files
│   └── script.py.mako       # Migration template
├── docker-compose.yml       # Docker services (API + PostgreSQL)
├── Dockerfile               # API container image
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template (copy to .env)
├── service-account.json     # Firebase credentials (not in git!)
└── README.md                # Complete documentation
```

---

## Next Steps

1. **Test endpoints** - Use http://localhost:8000/docs
2. **Read API docs** - See README.md for detailed endpoint documentation
3. **Extend API** - Follow "Extending the API" section in README.md to add new resources
4. **Setup CI/CD** - Add GitHub Actions for automated testing
5. **Deploy** - Follow Production Deployment section in README.md

---

## Support

- Documentation: [README.md](README.md)
- API Docs: http://localhost:8000/docs (when running)
- Curl Examples: See [CURL_EXAMPLES.sh](CURL_EXAMPLES.sh)
- Architecture: See [ARCHITECTURE.md](ARCHITECTURE.md)
