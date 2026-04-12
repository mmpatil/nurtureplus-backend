---
description: Generate curl examples and test a specific endpoint against a local running server. Usage: /test-endpoint <endpoint path, e.g. POST /recovery>
---

Generate and run curl test commands for the endpoint: $ARGUMENTS

## Step 1 — Read the endpoint definition
Find the relevant route in `app/api/routes.py` and the corresponding schema in `app/schemas/`.
Identify:
- HTTP method and path
- Required vs optional request body fields
- Expected response structure and status code
- Query parameters (for list endpoints)

## Step 2 — Generate test cases

Generate curl commands for each scenario:

### Happy path
```bash
# Create (POST)
curl -s -X POST http://localhost:8000/<resource> \
  -H "Content-Type: application/json" \
  -H "X-Dev-Uid: test-user-1" \
  -d '{ ... valid payload ... }' | python3 -m json.tool

# List with pagination (GET)
curl -s "http://localhost:8000/<resource>?limit=10&offset=0" \
  -H "X-Dev-Uid: test-user-1" | python3 -m json.tool

# Get by ID (GET)
curl -s http://localhost:8000/<resource>/<uuid> \
  -H "X-Dev-Uid: test-user-1" | python3 -m json.tool

# Update (PUT)
curl -s -X PUT http://localhost:8000/<resource>/<uuid> \
  -H "Content-Type: application/json" \
  -H "X-Dev-Uid: test-user-1" \
  -d '{ ... partial update ... }' | python3 -m json.tool

# Delete (DELETE)
curl -s -X DELETE http://localhost:8000/<resource>/<uuid> \
  -H "X-Dev-Uid: test-user-1" -w "\nHTTP Status: %{http_code}\n"
```

### Error cases
```bash
# Missing auth → 401
curl -s -X GET http://localhost:8000/<resource> -w "\nHTTP Status: %{http_code}\n"

# Invalid enum value → 422
curl -s -X POST http://localhost:8000/<resource> \
  -H "Content-Type: application/json" \
  -H "X-Dev-Uid: test-user-1" \
  -d '{ ... invalid enum ... }' | python3 -m json.tool

# Non-existent ID → 404
curl -s http://localhost:8000/<resource>/00000000-0000-0000-0000-000000000000 \
  -H "X-Dev-Uid: test-user-1" -w "\nHTTP Status: %{http_code}\n"

# Cross-user access → 404 (use test-user-2 for a resource created by test-user-1)
curl -s http://localhost:8000/<resource>/<uuid-from-user-1> \
  -H "X-Dev-Uid: test-user-2" -w "\nHTTP Status: %{http_code}\n"
```

## Step 3 — Prerequisites check
Before running, verify:
1. Server is running: `curl -s http://localhost:8000/health`
2. `DEV_BYPASS_AUTH=true` in your environment (required for `X-Dev-Uid` header to work)
3. Migrations applied: `alembic upgrade head`

If the server is not running, start it:
```bash
docker-compose up --build
# or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Step 4 — Run the commands
Execute each curl command and show the output. Note:
- Status codes in the response
- Whether the response body matches the schema
- Whether error cases return the correct status codes
