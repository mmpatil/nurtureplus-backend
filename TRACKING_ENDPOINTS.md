# Nurture+ Tracking & Analytics API Documentation

This document provides complete reference for feeding, diaper, sleep, mood, and analytics endpoints.

## Base URLs

```
Development:  http://localhost:8000
Production:   https://api.nurture.app  (your domain)
```

## Authentication

All endpoints (except `/health` and `/auth/session`) require Firebase authentication:

```bash
Authorization: Bearer <firebaseIdToken>
```

For development with `DEV_BYPASS_AUTH=true`:

```bash
X-Dev-Uid: <test-user-id>
```

## Common Response Codes

- `200`: Success
- `201`: Created
- `204`: No Content (successful deletion)
- `400`: Bad Request
- `401`: Unauthorized
- `404`: Not Found
- `422`: Validation Error
- `500`: Server Error

---

## Feeding Endpoints

Track baby feeding events (bottle, breastfeeding, etc.)

### GET /babies/{baby_id}/feedings

List feeding entries for a baby with optional time range filtering.

**Parameters:**
- `baby_id` (path): UUID of the baby
- `limit` (query, default=20): Items per page (1-100)
- `offset` (query, default=0): Items to skip
- `from_time` (query, optional): Start time (ISO 8601 format)
- `to_time` (query, optional): End time (ISO 8601 format)

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "baby_id": "uuid",
      "feeding_type": "bottle",
      "amount_ml": 120,
      "duration_min": 15,
      "timestamp": "2026-03-13T10:30:00Z",
      "notes": "Took well",
      "created_at": "2026-03-13T10:31:00Z",
      "updated_at": "2026-03-13T10:31:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Examples:**

```bash
# Basic list
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/feedings" \
  -H "X-Dev-Uid: alice@example.com"

# With time range (last 7 days)
FROM=$(date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/feedings?from_time=$FROM&to_time=$TO" \
  -H "X-Dev-Uid: alice@example.com"

# Paginated
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/feedings?limit=10&offset=20" \
  -H "X-Dev-Uid: alice@example.com"
```

### POST /babies/{baby_id}/feedings

Create a feeding entry.

**Request Body:**
```json
{
  "feeding_type": "bottle",
  "amount_ml": 120,
  "duration_min": 15,
  "timestamp": "2026-03-13T10:30:00Z",
  "notes": "Took well"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/feedings" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "feeding_type": "bottle",
    "amount_ml": 120,
    "duration_min": 15,
    "timestamp": "2026-03-13T10:30:00Z",
    "notes": "Took well"
  }'
```

### PUT /feedings/{feeding_id}

Update a feeding entry.

**Request Body:** (all fields optional)
```json
{
  "feeding_type": "breast_left",
  "amount_ml": 100,
  "duration_min": 12,
  "timestamp": "2026-03-13T10:30:00Z",
  "notes": "Updated notes"
}
```

**Example:**

```bash
curl -X PUT "http://localhost:8000/feedings/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_ml": 150
  }'
```

### DELETE /feedings/{feeding_id}

Delete a feeding entry.

**Example:**

```bash
curl -X DELETE "http://localhost:8000/feedings/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com"
```

---

## Diaper Endpoints

Track baby diaper changes.

### GET /babies/{baby_id}/diapers

List diaper entries for a baby.

**Parameters:** Same as feeding list endpoint.

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "baby_id": "uuid",
      "diaper_type": "both",
      "timestamp": "2026-03-13T09:45:00Z",
      "notes": "Full diaper",
      "created_at": "2026-03-13T09:46:00Z",
      "updated_at": "2026-03-13T09:46:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Examples:**

```bash
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/diapers" \
  -H "X-Dev-Uid: alice@example.com"

# With time range
FROM=$(date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/diapers?from_time=$FROM&to_time=$TO" \
  -H "X-Dev-Uid: alice@example.com"
```

### POST /babies/{baby_id}/diapers

Create a diaper entry.

**Request Body:**
```json
{
  "diaper_type": "both",
  "timestamp": "2026-03-13T09:45:00Z",
  "notes": "Full diaper"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/diapers" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "diaper_type": "wet",
    "timestamp": "2026-03-13T14:20:00Z"
  }'
```

### PUT /diapers/{diaper_id}

Update a diaper entry.

**Example:**

```bash
curl -X PUT "http://localhost:8000/diapers/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "diaper_type": "dirty",
    "notes": "Changed"
  }'
```

### DELETE /diapers/{diaper_id}

Delete a diaper entry.

**Example:**

```bash
curl -X DELETE "http://localhost:8000/diapers/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com"
```

---

## Sleep Endpoints

Track baby sleep periods.

### GET /babies/{baby_id}/sleep

List sleep entries for a baby.

**Parameters:** Same as feeding list endpoint (uses `start_time` for date range).

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "baby_id": "uuid",
      "start_time": "2026-03-13T20:00:00Z",
      "end_time": "2026-03-13T22:30:00Z",
      "duration_min": 150,
      "quality": "good",
      "notes": "Slept well",
      "created_at": "2026-03-13T20:01:00Z",
      "updated_at": "2026-03-13T20:01:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Examples:**

```bash
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/sleep" \
  -H "X-Dev-Uid: alice@example.com"

# Last 7 days of sleep
FROM=$(date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/sleep?from_time=$FROM&to_time=$TO" \
  -H "X-Dev-Uid: alice@example.com"
```

### POST /babies/{baby_id}/sleep

Create a sleep entry.

**Request Body:**
```json
{
  "start_time": "2026-03-13T20:00:00Z",
  "end_time": "2026-03-13T22:30:00Z",
  "quality": "good",
  "notes": "Slept well"
}
```

**Note:** `duration_min` is auto-calculated if `end_time` is provided; otherwise provide it manually.

**Example:**

```bash
curl -X POST "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/sleep" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "2026-03-13T20:00:00Z",
    "end_time": "2026-03-13T22:30:00Z",
    "quality": "great"
  }'

# Or with manual duration (ongoing sleep)
curl -X POST "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/sleep" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "2026-03-13T20:00:00Z",
    "duration_min": 90
  }'
```

### PUT /sleep/{sleep_id}

Update a sleep entry.

**Example:**

```bash
# Mark sleep as ended
curl -X PUT "http://localhost:8000/sleep/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "end_time": "2026-03-13T22:30:00Z"
  }'
```

### DELETE /sleep/{sleep_id}

Delete a sleep entry.

**Example:**

```bash
curl -X DELETE "http://localhost:8000/sleep/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com"
```

---

## Mood Endpoints

Track baby or parent mood check-ins.

### GET /babies/{baby_id}/moods

List mood entries for a baby.

**Parameters:** Same as feeding list endpoint.

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "baby_id": "uuid",
      "mood": "happy",
      "energy": "high",
      "timestamp": "2026-03-13T15:00:00Z",
      "notes": "Very playful today",
      "created_at": "2026-03-13T15:01:00Z",
      "updated_at": "2026-03-13T15:01:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Examples:**

```bash
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/moods" \
  -H "X-Dev-Uid: alice@example.com"

# Last 30 days of moods
FROM=$(date -u -d "30 days ago" +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/moods?from_time=$FROM&to_time=$TO" \
  -H "X-Dev-Uid: alice@example.com"
```

### POST /babies/{baby_id}/moods

Create a mood entry.

**Request Body:**
```json
{
  "mood": "happy",
  "energy": "high",
  "timestamp": "2026-03-13T15:00:00Z",
  "notes": "Very playful today"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/moods" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "ok",
    "energy": "medium",
    "timestamp": "2026-03-13T15:30:00Z",
    "notes": "Settled down after lunch"
  }'
```

### PUT /moods/{mood_id}

Update a mood entry.

**Example:**

```bash
curl -X PUT "http://localhost:8000/moods/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "happy",
    "energy": "high"
  }'
```

### DELETE /moods/{mood_id}

Delete a mood entry.

**Example:**

```bash
curl -X DELETE "http://localhost:8000/moods/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Dev-Uid: alice@example.com"
```

---

## Analytics Endpoints

Retrieve aggregated statistics for charts and dashboards.

### GET /babies/{baby_id}/analytics/summary

Get analytics summary including feeding counts, diaper counts, and sleep hours per day.

**Parameters:**
- `baby_id` (path): UUID of the baby
- `range_days` (query, default=7): Number of days to analyze (1-365)

**Response:**
```json
{
  "rangeDays": 7,
  "feedingCountByDay": [
    {
      "date": "2026-03-07",
      "count": 6
    },
    {
      "date": "2026-03-08",
      "count": 5
    }
  ],
  "diaperCountByDay": [
    {
      "date": "2026-03-07",
      "count": 8
    },
    {
      "date": "2026-03-08",
      "count": 7
    }
  ],
  "sleepHoursByDay": [
    {
      "date": "2026-03-07",
      "hours": 8.5
    },
    {
      "date": "2026-03-08",
      "hours": 9.2
    }
  ],
  "totals": {
    "feedings": 41,
    "diapers": 56,
    "avgSleepHoursPerDay": 8.6
  }
}
```

**Examples:**

```bash
# Last 7 days (default)
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/analytics/summary" \
  -H "X-Dev-Uid: alice@example.com"

# Last 30 days
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/analytics/summary?range_days=30" \
  -H "X-Dev-Uid: alice@example.com"

# Last 90 days
curl -X GET "http://localhost:8000/babies/550e8400-e29b-41d4-a716-446655440000/analytics/summary?range_days=90" \
  -H "X-Dev-Uid: alice@example.com"
```

---

## iOS Integration Guide

### Base Implementation

```swift
import Foundation

class NurturePlusAPI {
    let baseURL = "https://api.nurture.app"
    let authToken: String  // From Firebase
    
    // MARK: - Feeding
    
    func createFeeding(babyId: UUID, feedingData: FeedingCreate) async throws -> Feeding {
        let endpoint = "\(baseURL)/babies/\(babyId)/feedings"
        return try await post(endpoint: endpoint, body: feedingData)
    }
    
    func listFeedings(
        babyId: UUID,
        limit: Int = 20,
        offset: Int = 0,
        fromTime: Date? = nil,
        toTime: Date? = nil
    ) async throws -> FeedingListResponse {
        var endpoint = "\(baseURL)/babies/\(babyId)/feedings?limit=\(limit)&offset=\(offset)"
        
        if let fromTime {
            endpoint += "&from_time=\(ISO8601DateFormatter().string(from: fromTime))"
        }
        if let toTime {
            endpoint += "&to_time=\(ISO8601DateFormatter().string(from: toTime))"
        }
        
        return try await get(endpoint: endpoint)
    }
    
    // MARK: - Helper Methods
    
    private func get<T: Decodable>(endpoint: String) async throws -> T {
        var request = URLRequest(url: URL(string: endpoint)!)
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw NetworkError.unauthorized
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
    
    private func post<T: Decodable, U: Encodable>(
        endpoint: String,
        body: U
    ) async throws -> T {
        var request = URLRequest(url: URL(string: endpoint)!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 201 else {
            throw NetworkError.failed
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}
```

### Usage Examples

```swift
// Create a feeding
let feeding = FeedingCreate(
    feedingType: "bottle",
    amountMl: 120,
    durationMin: 15,
    timestamp: Date(),
    notes: "Took well"
)
let newFeeding = try await api.createFeeding(babyId: babyId, feedingData: feeding)

// Get analytics for 7-day chart
let analytics = try await api.getAnalyticsSummary(babyId: babyId, rangeDays: 7)

// Display in SwiftUI Chart
ForEach(analytics.feedingCountByDay, id: \.date) { day in
    BarMark(
        x: .value("Date", day.date),
        y: .value("Count", day.count)
    )
}
```

---

## Database Indexes

All tracking tables include optimized indexes:

- `feeding_entries`: 
  - `ix_feeding_entries_baby_id`
  - `ix_feeding_entries_baby_id_timestamp` (primary for filtered queries)
  
- `diaper_entries`:
  - `ix_diaper_entries_baby_id`
  - `ix_diaper_entries_baby_id_timestamp` (primary for filtered queries)
  
- `sleep_entries`:
  - `ix_sleep_entries_baby_id`
  - `ix_sleep_entries_baby_id_start_time` (primary for filtered queries)
  
- `mood_entries`:
  - `ix_mood_entries_baby_id`
  - `ix_mood_entries_baby_id_timestamp` (primary for filtered queries)

These composite indexes enable efficient range queries for analytics.

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message",
  "status": 404
}
```

Common errors:

- `404 Baby not found`: Baby doesn't exist or doesn't belong to authenticated user
- `401 Unauthorized`: Missing or invalid authentication
- `422 Validation Error`: Invalid request data or format
- `400 Bad Request`: Malformed request

---

## Migration & Deployment

### Run Migrations

```bash
# Local development
docker-compose exec api alembic upgrade head

# Production
ssh your-server
cd /app
alembic upgrade head
```

### Test After Deployment

```bash
# Health check
curl https://api.nurture.app/health

# Auth check  
curl -H "Authorization: Bearer <token>" https://api.nurture.app/auth/session

# Create test data
curl -X POST "https://api.nurture.app/babies/<baby_id>/feedings" \
  -H "Authorization: Bearer <token>" \
  -d '{...}'
```

---

## Performance Considerations

- Time range queries use indexed `(baby_id, timestamp)` columns for O(log n) lookups
- Analytics aggregation databases on UTC date, not per-hour
- Pagination default limit=20, max 100 to prevent large transfers
- All timestamps stored in UTC for consistency across timezones
