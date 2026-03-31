# 🚀 Quick Start

Get **Nurture+ Backend running in 5 minutes**.

## TL;DR (Docker)

```bash
# 1. Clone and enter directory
cd nurtureplus-backend

# 2. Copy environment template
cp .env.example .env

# 3. Add your Firebase service account JSON
# Go to: Firebase Console → Project Settings → Service Accounts
# Download private key JSON
# Save as: service-account.json (in this directory)

# 4. Start services
docker-compose up --build

# 5. Verify
curl http://localhost:8000/health
open http://localhost:8000/docs
```

**That's it!** Your API is running at `http://localhost:8000`

---

## TL;DR (Local Python)

```bash
# 1. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL (via Docker is easier)
docker run -d \
  --name nurture_postgres \
  -e POSTGRES_USER=nurture_user \
  -e POSTGRES_PASSWORD=password123 \
  -e POSTGRES_DB=nurtureplus_db \
  -p 5432:5432 \
  postgres:16-alpine

# 4. Run migrations
alembic upgrade head

# 5. Start server
uvicorn app.main:app --reload --port 8000
```

---

## Testing (without Firebase setup)

### Enable Dev Mode

Edit `.env`:
```env
DEV_BYPASS_AUTH=true
```

Restart server.

### Create a Session

```bash
curl -X POST http://localhost:8000/auth/session \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json"
```

Response:
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "firebase_uid": "alice@example.com"
}
```

### Create a Baby

```bash
curl -X POST http://localhost:8000/babies \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Emma",
    "birth_date": "2024-01-15"
  }'
```

### List Babies

```bash
curl http://localhost:8000/babies \
  -H "X-Dev-Uid: alice@example.com" | python -m json.tool
```

---

## Next Steps

1. **Review**: [SETUP.md](./SETUP.md) - Detailed setup instructions
2. **Explore**: [README.md](./README.md) - Full API documentation
3. **Understand**: [ARCHITECTURE.md](./ARCHITECTURE.md) - System design
4. **Test**: [CURL_EXAMPLES.sh](./CURL_EXAMPLES.sh) - Example requests
5. **Extend**: Add new endpoints following the patterns in the code

---

## Troubleshooting

### Port 8000 already in use

```bash
# Kill process using port 8000
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8080
```

### PostgreSQL connection error

```bash
# Check if postgres is running
docker ps | grep postgres

# Start if not running
docker-compose up postgres
```

### Firebase token error

1. Ensure `service-account.json` exists and is valid
2. Check file is in project root: `ls service-account.json`
3. Validate JSON: `python -m json.tool service-account.json`
4. For dev mode: Enable `DEV_BYPASS_AUTH=true` in `.env`

---

## Project Structure

```
nurtureplus-backend/
├── app/                      # FastAPI application
│   ├── main.py              # App entry point
│   ├── api/routes.py        # All endpoints
│   ├── core/                # Config, security
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── crud/                # Database operations
│   └── db/                  # Database setup
├── alembic/                 # Database migrations
├── docker-compose.yml       # Services (API + PG)
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
├── service-account.json    # Firebase credentials
└── Documentation
    ├── README.md           # Full documentation
    ├── SETUP.md            # Detailed setup
    ├── ARCHITECTURE.md     # System design
    └── CURL_EXAMPLES.sh    # Example requests
```

---

## Key Features

✅ Firebase authentication
✅ PostgreSQL with async SQLAlchemy
✅ User-scoped data queries
✅ Pagination on all list endpoints
✅ Production-ready error handling
✅ Structured logging
✅ Database migrations with Alembic
✅ Docker Compose for local dev
✅ CORS configurable via env

---

## Production Readiness

- Token verification on every request
- User isolation (can't access other user's data)
- Proper indexing for query optimization
- Connection pooling
- Structured logging
- Error handling
- CORS security

Setup production deployment using [README.md](./README.md#production-deployment) guide.

---

## Support

- Detailed setup: [SETUP.md](./SETUP.md)
- API reference: [README.md](./README.md)
- Architecture: [ARCHITECTURE.md](./ARCHITECTURE.md)
- Curl examples: [CURL_EXAMPLES.sh](./CURL_EXAMPLES.sh)

**API Docs (when running):** http://localhost:8000/docs
