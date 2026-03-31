# Postpartum Recovery Tracking API

This document describes the recovery entry endpoints for the Nurture+ backend. Recovery entries allow authenticated users (mothers) to log postpartum recovery check-ins.

## Feature Overview

Users can log recovery check-ins with:
- **mood**: emotional state (great, good, okay, struggling, overwhelmed)
- **energy_level**: energy state (veryLow, low, moderate, high, veryHigh)
- **water_intake_oz**: water consumed in ounces (0-128)
- **symptoms**: array of physical/emotional symptoms
- **notes**: optional additional notes
- **timestamp**: when the check-in occurred

## Allowed Values

### Mood Options
- `great`
- `good`
- `okay`
- `struggling`
- `overwhelmed`

### Energy Level Options
- `veryLow`
- `low`
- `moderate`
- `high`
- `veryHigh`

### Symptom Options
- `soreness`
- `bleeding`
- `cramping`
- `breastPain`
- `headache`
- `nausea`
- `anxiety`
- `sadness`
- `insomnia`
- `hotFlashes`

## Validation Rules

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `timestamp` | ISO 8601 datetime | Yes | Must be valid UTC datetime |
| `mood` | string | Yes | Must be in MOOD_OPTIONS |
| `energy_level` | string | Yes | Must be in ENERGY_LEVEL_OPTIONS |
| `water_intake_oz` | integer | Yes | 0-128 inclusive |
| `symptoms` | string array | Yes | Each must be in SYMPTOM_OPTIONS; default empty |
| `notes` | text | No | Optional; no length limit |

## Endpoints

### 1. POST /recovery

Create a new recovery entry for the authenticated user.

**Request:**
```bash
curl -X POST http://localhost:8000/recovery \
  -H "Authorization: Bearer <firebase_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 48,
    "symptoms": ["soreness", "insomnia"],
    "notes": "Feeling a bit better today"
  }'
```

**Response:** 201 Created
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2026-03-31T10:00:00+00:00",
  "mood": "good",
  "energy_level": "moderate",
  "water_intake_oz": 48,
  "symptoms": ["soreness", "insomnia"],
  "notes": "Feeling a bit better today",
  "created_at": "2026-03-31T10:00:00+00:00",
  "updated_at": "2026-03-31T10:00:00+00:00"
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token
- `422 Unprocessable Entity`: Validation error (invalid mood, energy_level, symptoms, or water_intake_oz out of bounds)

---

### 2. GET /recovery

List recovery entries for the authenticated user (newest first), with optional pagination and time filtering.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Results per page (1-100) |
| `offset` | integer | 0 | Number of results to skip |
| `from_time` | ISO 8601 string | none | Start of time range (inclusive) |
| `to_time` | ISO 8601 string | none | End of time range (inclusive) |

**Request:**
```bash
# Basic listing
curl -X GET http://localhost:8000/recovery \
  -H "Authorization: Bearer <firebase_token>"

# With pagination
curl -X GET "http://localhost:8000/recovery?limit=10&offset=20" \
  -H "Authorization: Bearer <firebase_token>"

# Last 7 days
FROM=$(date -u -d "7 days ago" +"%Y-%m-%dT%H:%M:%SZ")
TO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
curl -X GET "http://localhost:8000/recovery?from_time=${FROM}&to_time=${TO}" \
  -H "Authorization: Bearer <firebase_token>"
```

**Response:** 200 OK
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "timestamp": "2026-03-31T10:00:00+00:00",
      "mood": "good",
      "energy_level": "moderate",
      "water_intake_oz": 48,
      "symptoms": ["soreness"],
      "notes": "Feeling a bit better today",
      "created_at": "2026-03-31T10:00:00+00:00",
      "updated_at": "2026-03-31T10:00:00+00:00"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token
- `422 Unprocessable Entity`: Invalid date format in from_time/to_time

---

### 3. GET /recovery/{entry_id}

Get a single recovery entry owned by the authenticated user.

**Request:**
```bash
curl -X GET "http://localhost:8000/recovery/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <firebase_token>"
```

**Response:** 200 OK
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2026-03-31T10:00:00+00:00",
  "mood": "good",
  "energy_level": "moderate",
  "water_intake_oz": 48,
  "symptoms": ["soreness"],
  "notes": "Feeling a bit better today",
  "created_at": "2026-03-31T10:00:00+00:00",
  "updated_at": "2026-03-31T10:00:00+00:00"
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token
- `404 Not Found`: Entry does not exist or belongs to another user
- `422 Unprocessable Entity`: Invalid entry ID format

---

### 4. PUT /recovery/{entry_id}

Update an existing recovery entry owned by the authenticated user. Supports partial updates (only provided fields are updated).

**Request:**
```bash
# Update single field
curl -X PUT "http://localhost:8000/recovery/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <firebase_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "great"
  }'

# Update multiple fields
curl -X PUT "http://localhost:8000/recovery/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <firebase_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "great",
    "energy_level": "high",
    "water_intake_oz": 64,
    "notes": "Updated - feeling much better"
  }'
```

**Response:** 200 OK (same schema as single get)

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token
- `404 Not Found`: Entry does not exist or belongs to another user
- `422 Unprocessable Entity`: Invalid entry ID or validation error

---

### 5. DELETE /recovery/{entry_id}

Delete a recovery entry owned by the authenticated user.

**Request:**
```bash
curl -X DELETE "http://localhost:8000/recovery/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <firebase_token>"
```

**Response:** 204 No Content

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token
- `404 Not Found`: Entry does not exist or belongs to another user
- `422 Unprocessable Entity`: Invalid entry ID format

---

### 6. GET /recovery/latest

Get the most recent recovery entry for the authenticated user, or null if none exists. Used for home screen summary card.

**Request:**
```bash
curl -X GET "http://localhost:8000/recovery/latest" \
  -H "Authorization: Bearer <firebase_token>"
```

**Response:** 200 OK
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2026-03-31T10:00:00+00:00",
  "mood": "good",
  "energy_level": "moderate",
  "water_intake_oz": 48,
  "symptoms": ["soreness"],
  "notes": "Feeling a bit better today",
  "created_at": "2026-03-31T10:00:00+00:00",
  "updated_at": "2026-03-31T10:00:00+00:00"
}
```

or null if no entries exist

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token

---

### 7. GET /recovery/summary

Get summary metrics for the authenticated user over a specified time window. Useful for history screen analytics.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 7 | Number of days to summarize (1-365) |

**Request:**
```bash
# 7-day summary (default)
curl -X GET "http://localhost:8000/recovery/summary" \
  -H "Authorization: Bearer <firebase_token>"

# 14-day summary
curl -X GET "http://localhost:8000/recovery/summary?days=14" \
  -H "Authorization: Bearer <firebase_token>"

# 30-day summary (monthly)
curl -X GET "http://localhost:8000/recovery/summary?days=30" \
  -H "Authorization: Bearer <firebase_token>"
```

**Response:** 200 OK
```json
{
  "days": 7,
  "average_water_intake_oz": 48.6,
  "check_in_count": 5,
  "latest_entry": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "550e8400-e29b-41d4-a716-446655440001",
    "timestamp": "2026-03-31T10:00:00+00:00",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 48,
    "symptoms": ["soreness"],
    "notes": "Feeling a bit better today",
    "created_at": "2026-03-31T10:00:00+00:00",
    "updated_at": "2026-03-31T10:00:00+00:00"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid Firebase token
- `422 Unprocessable Entity`: Invalid days parameter (not 1-365)

---

## Data Model

### recovery_entries table

```sql
CREATE TABLE recovery_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    mood VARCHAR(20) NOT NULL,
    energy_level VARCHAR(20) NOT NULL,
    water_intake_oz INTEGER NOT NULL,
    symptoms TEXT[] NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX ix_recovery_entries_user_id ON recovery_entries(user_id);
CREATE INDEX ix_recovery_entries_user_timestamp ON recovery_entries(user_id, timestamp);
CREATE INDEX ix_recovery_entries_timestamp ON recovery_entries(timestamp);
```

---

## iOS Implementation Guide

### Decoding Recovery Entries

```swift
let decoder = JSONDecoder()
decoder.dateDecodingStrategy = .iso8601

let response = try decoder.decode(RecoveryEntryResponse.self, from: data)
```

### Displaying Recovery Entry

**Recovery Card (History View):**
```
┌─────────────────────────────────────┐
│ 😊 Good                  Yesterday  │
│ Energy: Moderate                    │
│ Water: 48 oz                        │
│ Symptoms: 2                         │
└─────────────────────────────────────┘
```

**Recovery Detail (Tap to Edit):**
```
Mood:           Good
Energy Level:   Moderate
Water Intake:   48 oz
Symptoms:       Soreness, Insomnia
Notes:          Feeling a bit better today
```

### Summary Display (Home Screen)

```
7-Day Recovery Summary
─────────────────────
Avg Water:      48.6 oz
Check-ins:      5
Last Check-in:  Today at 10:00 AM
```

---

## Implementation Notes

### User Scoping

All recovery entries are automatically scoped to the authenticated user. The `user_id` is extracted from the Firebase token and enforced at the database level. Users cannot:
- Access another user's entries
- Modify another user's entries
- Delete another user's entries

### Timestamp Handling

- All timestamps are stored in UTC
- Timestamps can be in the past (backdated entries)
- ISO 8601 format required for API requests
- Responses include UTC offset (+00:00)

### Empty Symptoms Array

- If no symptoms are present, return empty array `[]`
- Symptoms array defaults to empty on create
- Update with empty array to clear symptoms

### Pagination

- Default limit: 20 entries
- Maximum limit: 100 entries
- Results ordered newest first (descending by timestamp)
- Use offset for pagination

### Water Intake Validation

Water intake is constrained to 0-128 oz (typical maximum daily intake):
- Minimum: 0 oz (no water logged)
- Maximum: 128 oz (< 1 gallon)
- Invalid values rejected with 422 error

---

## Error Handling

### Common Error Scenarios

| Scenario | Status | Response |
|----------|--------|----------|
| Missing Firebase token | 401 | `{"detail": "Not authenticated"}` |
| Invalid token | 401 | `{"detail": "Not authenticated"}` |
| Entry not found | 404 | `{"detail": "Recovery entry not found"}` |
| Invalid mood value | 422 | Validation error with location |
| Water intake > 128 | 422 | Validation error |
| Invalid timestamp format | 422 | Validation error |
| User tries to access other's entry | 404 | Entry appears not found |

### Validation Error Example

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "mood"],
      "msg": "mood must be one of {'great', 'good', 'okay', 'struggling', 'overwhelmed'}, got invalid",
      "input": "invalid"
    }
  ]
}
```

---

## Testing

Run the test suite:
```bash
pytest tests/test_recovery_entries.py -v

# Specific test
pytest tests/test_recovery_entries.py::test_create_recovery_entry -v

# With coverage
pytest tests/test_recovery_entries.py --cov=app.crud.recovery_entries
```

See `RECOVERY_CURL_EXAMPLES.sh` for curl-based testing examples.

---

## Logging

All recovery operations are logged with structured logging:
- `action`: operation type (create, list, get, update, delete)
- `user_id`: authenticated user
- `entry_id`: recovery entry ID (for single operations)
- `timestamp`: operation timestamp

Example logs:
```
Created recovery entry: id=550e8400-..., user_id=550e8400-..., mood=good
Updated recovery entry: id=550e8400-..., user_id=550e8400-...
Deleted recovery entry: id=550e8400-..., user_id=550e8400-...
```

---

## Future Enhancements

Potential additions if needed:
- **Mood trends**: 7-day trend graph
- **Symptom tracking**: Which symptoms are most common?
- **Recovery milestones**: Week 1, week 2, month 1, etc.
- **Health alerts**: Flag entries that suggest PPD (persistent overwhelmed mood)
- **Export**: CSV export of recovery history
- **Shared access**: Allow partner/doctor access to recovery data (with permission)
