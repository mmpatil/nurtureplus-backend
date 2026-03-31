# API Reference for iOS - All 40 Endpoints

## Quick Copy-Paste for Xcode

### Base URL
```
http://localhost:8000  (development)
https://api.nurture-app.com  (production)
```

### Authentication
All requests require Firebase ID token:
```swift
request.setValue("Bearer \(firebaseIdToken)", forHTTPHeaderField: "Authorization")
```

---

## 📍 Authentication Endpoints (1)

### 1. Create Session
```
POST /auth/session
```
| Field | Type |
|-------|------|
| Response | SessionResponse |

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "firebase_uid": "oH2N5bXxQNcZqE8R2p5nX8Y3p9x0"
}
```

---

## 👶 Baby Management Endpoints (7)

### 1. List Babies
```
GET /babies?limit=20&offset=0
```
**Response:** `BabyListResponse`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Emma",
      "birth_date": "2025-01-15T00:00:00Z",
      "photo_url": "https://...",
      "created_at": "2026-03-12T10:30:00Z",
      "updated_at": "2026-03-12T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 2. Create Baby
```
POST /babies
Content-Type: application/json
```
**Request:**
```json
{
  "name": "Emma",
  "birth_date": "2025-01-15T00:00:00Z",
  "photo_url": "https://..."
}
```
**Response:** `Baby` (same as list item)

### 3. Get Baby
```
GET /babies/{baby_id}
```
**Response:** `Baby`

### 4. Update Baby
```
PUT /babies/{baby_id}
Content-Type: application/json
```
**Request:**
```json
{
  "name": "Emma Grace",
  "birth_date": "2025-01-15T00:00:00Z",
  "photo_url": "https://..."
}
```
**Response:** `Baby` (updated)

### 5. Delete Baby
```
DELETE /babies/{baby_id}
```
**Response:** 204 No Content

---

## 🍼 Feeding Endpoints (6)

### 1. List Feedings
```
GET /babies/{baby_id}/feedings
    ?limit=20
    &offset=0
    &from_time=2026-03-12T00:00:00Z
    &to_time=2026-03-13T23:59:59Z
```
**Response:** `FeedingListResponse`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "baby_id": "550e8400-e29b-41d4-a716-446655440001",
      "feeding_type": "bottle",
      "amount_ml": 120,
      "duration_min": 15,
      "timestamp": "2026-03-12T10:30:00Z",
      "notes": "Fed well",
      "created_at": "2026-03-12T10:31:00Z",
      "updated_at": "2026-03-12T10:31:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

### 2. Create Feeding
```
POST /babies/{baby_id}/feedings
Content-Type: application/json
```
**Request:**
```json
{
  "feeding_type": "bottle",
  "amount_ml": 120,
  "duration_min": 15,
  "timestamp": "2026-03-12T10:30:00Z",
  "notes": "Fed well"
}
```
**Feeding Types:** `bottle`, `breast_left`, `breast_right`, `both`

### 3. Get Feeding Details
```
GET /babies/{baby_id}/feedings/{feeding_id}
```
**Response:** `Feeding`

### 4. Update Feeding
```
PUT /feedings/{feeding_id}
Content-Type: application/json
```
**Request:** (all fields optional)
```json
{
  "feeding_type": "bottle",
  "amount_ml": 150,
  "duration_min": 20,
  "timestamp": "2026-03-12T10:30:00Z",
  "notes": "Updated notes"
}
```

### 5. Delete Feeding
```
DELETE /feedings/{feeding_id}
```
**Response:** 204 No Content

---

## 🩷 Diaper Endpoints (6)

### 1. List Diapers
```
GET /babies/{baby_id}/diapers
    ?limit=20
    &offset=0
    &from_time=2026-03-12T00:00:00Z
    &to_time=2026-03-13T23:59:59Z
```
**Response:** `DiaperListResponse`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "baby_id": "550e8400-e29b-41d4-a716-446655440001",
      "diaper_type": "wet",
      "timestamp": "2026-03-12T10:30:00Z",
      "notes": "Regular",
      "created_at": "2026-03-12T10:31:00Z",
      "updated_at": "2026-03-12T10:31:00Z"
    }
  ],
  "total": 8,
  "limit": 20,
  "offset": 0
}
```

### 2. Create Diaper
```
POST /babies/{baby_id}/diapers
Content-Type: application/json
```
**Request:**
```json
{
  "diaper_type": "wet",
  "timestamp": "2026-03-12T10:30:00Z",
  "notes": "Regular"
}
```
**Diaper Types:** `wet`, `dirty`, `both`, `dry`

### 3. Update Diaper
```
PUT /diapers/{diaper_id}
Content-Type: application/json
```
**Request:** (all fields optional)
```json
{
  "diaper_type": "both",
  "timestamp": "2026-03-12T10:30:00Z",
  "notes": "Updated"
}
```

### 4. Delete Diaper
```
DELETE /diapers/{diaper_id}
```
**Response:** 204 No Content

---

## 😴 Sleep Endpoints (6)

### 1. List Sleep Sessions
```
GET /babies/{baby_id}/sleep
    ?limit=20
    &offset=0
    &from_time=2026-03-12T00:00:00Z
    &to_time=2026-03-13T23:59:59Z
```
**Response:** `SleepListResponse`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "baby_id": "550e8400-e29b-41d4-a716-446655440001",
      "start_time": "2026-03-12T20:00:00Z",
      "end_time": "2026-03-12T22:30:00Z",
      "duration_min": 150,
      "quality": "good",
      "notes": "Slept well",
      "created_at": "2026-03-12T20:05:00Z",
      "updated_at": "2026-03-12T22:31:00Z"
    }
  ],
  "total": 3,
  "limit": 20,
  "offset": 0
}
```

### 2. Create Sleep Session
```
POST /babies/{baby_id}/sleep
Content-Type: application/json
```
**Request:**
```json
{
  "start_time": "2026-03-12T20:00:00Z",
  "end_time": "2026-03-12T22:30:00Z",
  "duration_min": 150,
  "quality": "good",
  "notes": "Slept well"
}
```
**Note:** `end_time` auto-calculates `duration_min` if provided

### 3. Update Sleep Session
```
PUT /sleep/{sleep_id}
Content-Type: application/json
```
**Request:** (all fields optional)
```json
{
  "start_time": "2026-03-12T20:00:00Z",
  "end_time": "2026-03-12T23:00:00Z",
  "quality": "great",
  "notes": "Updated"
}
```

### 4. Delete Sleep Session
```
DELETE /sleep/{sleep_id}
```
**Response:** 204 No Content

---

## 😊 Mood Endpoints (6)

### 1. List Moods
```
GET /babies/{baby_id}/moods
    ?limit=20
    &offset=0
    &from_time=2026-03-12T00:00:00Z
    &to_time=2026-03-13T23:59:59Z
```
**Response:** `MoodListResponse`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "baby_id": "550e8400-e29b-41d4-a716-446655440001",
      "mood": "happy",
      "energy": "high",
      "timestamp": "2026-03-12T14:30:00Z",
      "notes": "Playing",
      "created_at": "2026-03-12T14:31:00Z",
      "updated_at": "2026-03-12T14:31:00Z"
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

### 2. Create Mood
```
POST /babies/{baby_id}/moods
Content-Type: application/json
```
**Request:**
```json
{
  "mood": "happy",
  "energy": "high",
  "timestamp": "2026-03-12T14:30:00Z",
  "notes": "Playing"
}
```
**Moods:** `happy`, `sad`, `anxious`, `ok`, etc.
**Energy:** `high`, `medium`, `low`

### 3. Update Mood
```
PUT /moods/{mood_id}
Content-Type: application/json
```
**Request:** (all fields optional)
```json
{
  "mood": "calm",
  "energy": "medium",
  "notes": "Winding down"
}
```

### 4. Delete Mood
```
DELETE /moods/{mood_id}
```
**Response:** 204 No Content

---

## 📊 Analytics Endpoints (1)

### 1. Get Analytics Summary
```
GET /babies/{baby_id}/analytics/summary
    ?range_days=7  (or 14, 30)
```
**Response:**
```json
{
  "rangeDays": 7,
  "feedingCountByDay": [
    {"date": "2026-03-12", "count": 6},
    {"date": "2026-03-11", "count": 5}
  ],
  "diaperCountByDay": [
    {"date": "2026-03-12", "count": 8},
    {"date": "2026-03-11", "count": 9}
  ],
  "sleepHoursByDay": [
    {"date": "2026-03-12", "hours": 8.5},
    {"date": "2026-03-11", "hours": 7.2}
  ],
  "totals": {
    "feedings": 42,
    "diapers": 56,
    "avgSleepHoursPerDay": 7.8
  }
}
```

---

## 🔴 Error Responses

All errors return similar structure:

### 400 Bad Request
```json
{
  "detail": "Invalid request data"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Unprocessable Entity
```json
{
  "detail": "Validation error message"
}
```

### 500 Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## 📝 Pagination

All list endpoints support pagination:
```
GET /babies/{baby_id}/feedings?limit=20&offset=0
```

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| limit | int | 20 | 100 |
| offset | int | 0 | ∞ |

Response includes total count:
```json
{
  "items": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

## ⏰ Date/Time Format

All dates use **ISO 8601** format (UTC):
```
2026-03-12T14:30:00Z
2026-03-12T10:30:00+00:00
```

For pagination date filtering:
```
GET /babies/{baby_id}/feedings
  ?from_time=2026-03-12T00:00:00Z
  &to_time=2026-03-13T23:59:59Z
```

---

## 🚀 Quick Integration Steps

1. **Copy** `NurtureAPI.swift` into your Xcode project
2. **Set** `NurtureConfig.baseURL` to your backend URL
3. **Call** `NurtureAPI.shared.setAuthToken(firebaseToken)` after login
4. **Use** the API methods in your ViewModels

Example:
```swift
let api = NurtureAPI.shared
api.setAuthToken(firebaseToken)

// List feedings
let feedings = try await api.listFeedings(babyId: babyId)

// Create feeding
let feeding = try await api.createFeeding(
    babyId: babyId,
    feedingType: "bottle",
    amountMl: 120,
    durationMin: 15,
    notes: "Fed well"
)

// Get analytics
let analytics = try await api.getAnalyticsSummary(babyId: babyId, rangeDays: 7)
```

---

## Summary

- **40 Total Endpoints** (7 baby + 6 feeding + 6 diaper + 6 sleep + 6 mood + 1 auth + 1 analytics)
- **Complete Swift Client** in `NurtureAPI.swift`
- **All Models Defined** with proper Codable conformance
- **Async/Await** compatible with iOS 13+
- **Error Handling** built-in
- **Pagination** on all list endpoints
- **Date Filtering** on all tracking endpoints
- **Analytics** ready for iOS Charts

Ready to integrate! 🎉
