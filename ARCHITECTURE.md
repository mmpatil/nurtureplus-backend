# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    iOS App (Nurture+)                        │
│  - Uses Firebase Auth SDK                                    │
│  - Obtains Firebase ID tokens                                │
│  - All API calls include Bearer token or dev header          │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS (Production)
                     │ HTTP (Local Dev)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Python)                    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ routes.py (endpoints):                              │    │
│  │  - GET  /health                                      │    │
│  │  - POST /auth/session                                │    │
│  │  - GET  /babies (list with pagination)              │    │
│  │  - POST /babies (create)                            │    │
│  │  - GET  /babies/{id}                                │    │
│  │  - PUT  /babies/{id} (update)                       │    │
│  │  - DELETE /babies/{id}                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                   │
│  ┌────────────────────────┴─────────────────────────────┐   │
│  │                                                       │    │
│  ▼                                                       ▼    │
│  ┌──────────────────────┐                  ┌──────────────┐  │
│  │ security.py          │                  │ crud/        │  │
│  │                      │                  │ ├─ users.py  │  │
│  │ ▪ verify_firebase... │◄─────────────────┤ └─ babies.py │  │
│  │ ▪ get_current_user   │                  └──────────────┘  │
│  │ ▪ DevBypass support  │                                    │
│  └──────────────────────┘                                    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Dependency Injection:                                │   │
│  │  - get_db() → AsyncSession                          │   │
│  │  - get_current_user() → User (scope all queries)    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                     │
                     ├─────────────────────────────┐
                     │                             │
                     ▼                             ▼
        ┌──────────────────────┐      ┌──────────────────────┐
        │  Firebase Admin SDK  │      │   PostgreSQL (Local  │
        │  - Token verification│      │   or RDS/Cloud SQL)  │
        │  - UID extraction    │      │                      │
        └──────────────────────┘      │  Tables:             │
                                      │  - users             │
                                      │  - babies            │
                                      │                      │
                                      │  Indexes:            │
                                      │  - firebase_uid (u)  │
                                      │  - baby.user_id      │
                                      │  - baby.(user, date) │
                                      └──────────────────────┘
```

## Request Flow

### Authenticated Request (Production)

```
1. iOS App (Firebase Auth SDK)
   - User logs in with email/password
   - Firebase returns ID token (signed JWT)
   
2. iOS App → Backend
   POST /auth/session
   Header: Authorization: Bearer <id_token>
   
3. Backend (security.py)
   - Extract token from header
   - Verify signature using Firebase public keys
   - Extract uid from token claims
   - Check if user exists in DB
   - If not, create new User row (idempotent)
   - Return user_id and firebase_uid
   
4. iOS App stores user_id locally
   - All subsequent requests include Bearer token
   - Server can identify user from token UID
   
5. Backend (routes.py + CRUD)
   - get_current_user dependency:
     * Verify token again
     * Load User from DB
     * Inject into endpoint
   - All queries filtered by current_user.id
   - Return data scoped to user
```

### Authenticated Request (Dev Mode)

```
1. Dev (testing without iOS)
   - Set DEV_BYPASS_AUTH=true in .env
   
2. Test Request
   POST /auth/session
   Header: X-Dev-Uid: test-user-alice
   
3. Backend (security.py)
   - Check if DEV_BYPASS_AUTH enabled
   - Extract X-Dev-Uid header
   - Use header value as firebase_uid
   - Create/fetch User row
   - Return user_id and firebase_uid
   
4. Subsequent requests
   Can use same X-Dev-Uid header
   (DEV_BYPASS_AUTH must remain enabled)
```

## Data Model

### ER Diagram

```
┌────────────────────────────────────────┐
│              users                      │
├────────────────────────────────────────┤
│ id: UUID (PK)                           │
│ firebase_uid: String (unique, indexed)  │
│ created_at: DateTime(UTC)               │
├────────────────────────────────────────┤
│ Indexes:                                │
│  - firebase_uid (unique) -- look by uid │
└────────┬─────────────────────────────────┘
         │ (1:N)
         │ FK: babies.user_id
         │
┌────────▼─────────────────────────────────────┐
│              babies                          │
├──────────────────────────────────────────────┤
│ id: UUID (PK)                                │
│ user_id: UUID (FK → users.id, indexed)      │
│ name: String (100 chars)                     │
│ birth_date: Date                             │
│ photo_url: String (500 chars, nullable)     │
│ created_at: DateTime(UTC)                    │
│ updated_at: DateTime(UTC)                    │
├──────────────────────────────────────────────┤
│ Indexes:                                     │
│  - user_id -- for user's babies             │
│  - (user_id, birth_date) -- for queries    │
└──────────────────────────────────────────────┘
```

### Query Optimization

**Key principle: Every query filtered by user_id**

```python
# ✅ Optimized - indexed query
SELECT * FROM babies
WHERE user_id = <current_user_id>
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;

# ✅ Optimized - indexed lookup
SELECT * FROM babies
WHERE user_id = <current_user_id>
AND id = <baby_id>;

# ❌ Unoptimized - full table scan
SELECT * FROM babies
WHERE birth_date > '2024-01-01';
```

**Indexes applied:**
- `users(firebase_uid)` - rapid authentication lookup
- `babies(user_id)` - user's baby list
- `babies(user_id, birth_date)` - date-range by user

## Code Organization

### Core Modules

**app/core/config.py**
- Environment variable loading
- Settings object (singleton)
- Logging configuration

**app/core/security.py**
- Firebase Admin SDK initialization
- Token verification
- get_current_user dependency (injects authenticated user)
- Dev bypass implementation

**app/db/session.py**
- AsyncEngine creation (connection pool)
- AsyncSessionLocal factory
- get_db dependency (injects database session)

**app/db/base.py**
- SQLAlchemy declarative base
- Base class for all models

### Models (SQLAlchemy ORM)

**app/models/users.py**
- User table + metadata
- Indexes defined at table level

**app/models/babies.py**
- Baby table + metadata
- Foreign key to users
- Multi-column indexes

### Schemas (Pydantic)

**app/schemas/auth.py**
- SessionResponse - returned from /auth/session

**app/schemas/user.py**
- User - for responses

**app/schemas/baby.py**
- BabyCreate - request body for POST
- BabyUpdate - request body for PUT
- Baby - response body
- BabyListResponse - paginated response

### CRUD Layer

**app/crud/users.py**
- get_user_by_firebase_uid(db, uid)
- get_user_by_id(db, user_id)
- create_user(db, UserCreate) → User

**app/crud/babies.py**
- get_babies_for_user(db, user_id, limit, offset) → (list, total)
- get_baby_by_id(db, baby_id, user_id) → Baby | None
- create_baby(db, user_id, BabyCreate) → Baby
- update_baby(db, baby_id, user_id, BabyUpdate) → Baby | None
- delete_baby(db, baby_id, user_id) → bool

All CRUD ops **scoped to user_id**.

### API Layer

**app/api/routes.py**
- Endpoints with path operations
- Uses dependencies: get_db, get_current_user
- Calls CRUD functions
- Returns Pydantic schemas
- Error handling (401, 404, 422, etc.)

**app/main.py**
- FastAPI app creation
- Middleware (CORS)
- Router registration
- Lifespan events (startup/shutdown)

## Dependency Injection Flow

```
FastAPI Request
  │
  ├─ Route handler needs: db, current_user
  │
  ├─→ get_db() dependency
  │   └─→ AsyncSessionLocal()
  │       └─→ AsyncSession (auto-closed after request)
  │
  └─→ get_current_user(authorization, x_dev_uid, db)
      ├─ Parse Authorization header
      ├─ Verify Firebase token (or check dev bypass)
      ├─ Extract firebase_uid
      ├─ Query: SELECT * FROM users WHERE firebase_uid = ?
      ├─ Create User if not exists (idempotent)
      └─→ User object injected into route

Route Handler gets:
  - db: AsyncSession (connected, ready to query)
  - current_user: User (authenticated, scoped to their data)

Example:
  @router.get("/babies")
  async def list_babies(
      db: AsyncSession = Depends(get_db),  ← Injected by framework
      current_user: User = Depends(get_current_user),  ← Injected
      limit: int = Query(20),
      offset: int = Query(0),
  ):
      babies, total = await babies_crud.get_babies_for_user(
          db,
          current_user.id,  ← Already authenticated!
          limit,
          offset,
      )
```

## Security Architecture

### Token Flow

```
┌─────────────────────────────────────────────────────────┐
│                     iOS App                              │
│  Firebase Auth SDK manages tokens                        │
└─────────────────────────────────────────────────────────┘
                        │
        Firebase automatically refreshes token
        when expires (1 hour expiry)
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Bearer Token in Request                     │
│  Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI... │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│          Backend Verification (app/core/security.py)    │
│                                                          │
│  1. Extract token from Authorization header             │
│  2. Verify JWT signature                                │
│     - Fetch Firebase public keys                        │
│     - Validate signature                                │
│  3. Check expiration time                               │
│  4. Extract UID from 'sub' or 'uid' claim              │
│  5. Query users table for user                          │
│  6. Create if new (idempotent)                          │
│  7. Return User object                                  │
│                                                          │
│  Errors:                                                │
│  - InvalidIdTokenError → 401                            │
│  - ExpiredSignInError → 401                             │
│  - Missing header → 401                                 │
│                                                          │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Dependency Injected into Route Handler           │
│  current_user: User(id, firebase_uid, created_at)       │
│                                                          │
│  All DB queries automatically filtered:                 │
│  WHERE user_id = current_user.id                        │
└─────────────────────────────────────────────────────────┘
```

### Authorization Pattern

**Every resource query includes user check:**

```python
# Babies endpoint - verify user owns the baby
async def get_baby(baby_id: str, current_user: User = Depends(...)):
    # This query automatically scoped to user
    baby = await babies_crud.get_baby_by_id(
        db,
        UUID(baby_id),
        current_user.id  ← Always passed
    )
    
    if not baby:
        raise HTTPException(404, "Not found")
    
    return baby

# In CRUD layer:
async def get_baby_by_id(db, baby_id, user_id):
    result = await db.execute(
        select(Baby).where(
            (Baby.id == baby_id) &
            (Baby.user_id == user_id)  ← User-scoped filter!
        )
    )
    return result.scalar_one_or_none()
```

**Result:**
- User can only access their own babies
- 404 returned (not 403) to prevent leaking existence
- No data leaks across user boundaries

## Extension Points

### Adding New Resources

**Pattern used for feeding/sleep/diaper records:**

1. **Model** - Define SQLAlchemy table in app/models/
2. **Schema** - Define Pydantic schemas in app/schemas/
3. **CRUD** - Implement queries in app/crud/
4. **Routes** - Add endpoints in app/api/routes.py
5. **Migration** - Run alembic to create table

### Example: Feeding Records

```python
# Step 1: app/models/feeding.py
class Feeding(Base):
    __tablename__ = "feedings"
    id = Column(UUID, primary_key=True)
    baby_id = Column(UUID, FK "babies.id")
    user_id = Column(UUID, FK "users.id")  # For direct user-scoped queries
    started_at = Column(DateTime)
    duration_minutes = Column(Integer)
    created_at = Column(DateTime)
    
    __table_args__ = (
        Index("ix_feeding_user_baby", "user_id", "baby_id"),
    )

# Step 2: app/schemas/feeding.py
class FeedingCreate(BaseModel):
    baby_id: str
    started_at: datetime
    duration_minutes: int

class Feeding(FeedingCreate):
    id: str
    user_id: str
    created_at: datetime

# Step 3: app/crud/feeding.py
async def get_feedings_for_baby(db, user_id, baby_id, limit=20, offset=0):
    # Query: filter by BOTH user AND baby
    count = await db.execute(
        select(func.count()).where(
            (Feeding.user_id == user_id) &
            (Feeding.baby_id == baby_id)
        )
    )
    results = await db.execute(
        select(Feeding)
        .where(...)
        .limit(limit)
        .offset(offset)
    )

# Step 4: app/api/routes.py
@router.get("/babies/{baby_id}/feedings")
async def list_feedings(
    baby_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_user),
):
    feedings, total = await feeding_crud.get_feedings_for_baby(
        db,
        current_user.id,
        UUID(baby_id),
    )
    return FeedingListResponse(items=..., total=...)

# Step 5: Migration
$ alembic revision --autogenerate -m "add_feedings_table"
$ alembic upgrade head
```

## Deployment Architecture

### Development

```
Laptop
├─ Docker Container: FastAPI (port 8000)
│  └─ SQLAlchemy async → PostgreSQL
├─ Docker Container: PostgreSQL (port 5432)
│  └─ Volume-mounted data
└─ .env file (local passwords OK)
```

### Production

```
Internet (HTTPS required)
   │
   ▼
Load Balancer (CloudFlare, AWS ELB)
   │
   ├─ API Instance 1 (Kubernetes Pod / ECS Task)
   ├─ API Instance 2
   └─ API Instance 3
   │
   ▼
Managed PostgreSQL
   (AWS RDS / Google Cloud SQL / Azure Database)
   │
   ├─ Automated backups
   ├─ Read replicas (optional)
   └─ Connection pooling (pgBouncer)

Environment Variables (AWS Secrets Manager / Vault):
- DATABASE_URL (production DB)
- GOOGLE_APPLICATION_CREDENTIALS (service account)
- ALLOWED_ORIGINS (your domain)
- DEV_BYPASS_AUTH=false (mandatory)
```

## Monitoring & Observability

```
FastAPI App
├─ Structured Logs → CloudWatch / Datadog / Splunk
│  (Request ID, user_id, action, duration, errors)
│
├─ Error Tracking → Sentry / DataDog
│  (Exceptions, stack traces, context)
│
├─ Metrics → Prometheus / DataDog
│  (Response time, error rate, DB pool usage)
│
└─ Distributed Tracing → Jaeger / DataDog
   (Request flow across services)
```

## Performance Considerations

### Database

- **Connection pooling** - SQLAlchemy pool_size=20, max_overflow=10
- **Query optimization** - Indexes on foreign keys and common filters
- **Pagination** - Always limit/offset for list endpoints
- **Async operations** - Non-blocking queries with asyncpg

### API

- **Caching** - Can add Redis for frequently-accessed data
- **Compression** - gzip for JSON responses
- **Rate limiting** - Can add via middleware for auth endpoints
- **Timeout** - Set on database queries to prevent hanging

### Monitoring Performance

```python
# Log query performance
import time

async def slow_endpoint():
    start = time.time()
    data = await db.execute(...)
    duration = time.time() - start
    logger.info(f"Query took {duration:.2f}s")
```

---

## Summary

**Nurture+ Backend** follows a production-ready architecture with:

- **Clear separation of concerns** (models, schemas, CRUD, routes)
- **Strong authentication** (Firebase token verification)
- **User-scoped data** (every query filtered by user)
- **Query optimization** (proper indexes, pagination)
- **Easy extensibility** (add new resources following the pattern)
- **Production-ready** (error handling, logging, monitoring)

The design prioritizes:
1. **Security** - No data leaks, user isolation
2. **Performance** - Indexes, connection pooling, pagination
3. **Maintainability** - Clear code organization, dependency injection
4. **Observability** - Structured logging, error tracking
