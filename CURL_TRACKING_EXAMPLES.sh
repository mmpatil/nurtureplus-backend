#!/bin/bash
# Complete Nurture+ Tracking API - Curl Examples
# Usage: source this file or run individual sections
# Requires: bash, curl, jq (for JSON parsing)

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEV_UID="${DEV_UID:-alice@example.com}"  # For DEV_BYPASS_AUTH=true
BABY_ID="${BABY_ID:-550e8400-e29b-41d4-a716-446655440000}"  # Replace with actual UUID

echo "🍼 Nurture+ Tracking API Curl Examples"
echo "Base URL: $BASE_URL"
echo "Dev User: $DEV_UID"
echo ""

# ============================================================================
# FEEDING ENDPOINTS
# ============================================================================

echo "📝 FEEDING ENDPOINTS"
echo ""

echo "1️⃣  Create a feeding entry..."
curl -X POST "$BASE_URL/babies/$BABY_ID/feedings" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{
    "feeding_type": "bottle",
    "amount_ml": 120,
    "duration_min": 15,
    "timestamp": "'$(date -u +'%Y-%m-%dT%H:%M:%SZ')'",
    "notes": "Took well"
  }' | jq .

echo ""
echo "2️⃣  List feeding entries (last 7 days)..."
FROM=$(date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -X GET "$BASE_URL/babies/$BABY_ID/feedings?from_time=$FROM&to_time=$TO&limit=10" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "3️⃣  List all feedings (paginated)..."
curl -X GET "$BASE_URL/babies/$BABY_ID/feedings?limit=5&offset=0" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "4️⃣  Update a feeding (use an ID from above)..."
FEEDING_ID="550e8400-e29b-41d4-a716-446655440000"  # Replace with actual feeding ID
curl -X PUT "$BASE_URL/feedings/$FEEDING_ID" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{"amount_ml": 150}' | jq .

echo ""
echo "5️⃣  Delete a feeding..."
curl -X DELETE "$BASE_URL/feedings/$FEEDING_ID" \
  -H "X-Dev-Uid: $DEV_UID" \
  -w "\nStatus: %{http_code}\n"

echo ""
echo ""

# ============================================================================
# DIAPER ENDPOINTS
# ============================================================================

echo "🩷 DIAPER ENDPOINTS"
echo ""

echo "1️⃣  Create a diaper entry..."
curl -X POST "$BASE_URL/babies/$BABY_ID/diapers" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{
    "diaper_type": "wet",
    "timestamp": "'$(date -u +'%Y-%m-%dT%H:%M:%SZ')'",
    "notes": "Regular change"
  }' | jq .

echo ""
echo "2️⃣  List diaper entries..."
curl -X GET "$BASE_URL/babies/$BABY_ID/diapers?limit=10" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "3️⃣  Update a diaper..."
DIAPER_ID="550e8400-e29b-41d4-a716-446655440000"  # Replace with actual diaper ID
curl -X PUT "$BASE_URL/diapers/$DIAPER_ID" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{"diaper_type": "dirty"}' | jq .

echo ""
echo ""

# ============================================================================
# SLEEP ENDPOINTS
# ============================================================================

echo "😴 SLEEP ENDPOINTS"
echo ""

echo "1️⃣  Create a sleep entry (with end time)..."
START_TIME=$(date -u +'%Y-%m-%dT20:00:00Z')
END_TIME=$(date -u +'%Y-%m-%dT22:30:00Z')
curl -X POST "$BASE_URL/babies/$BABY_ID/sleep" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "'$START_TIME'",
    "end_time": "'$END_TIME'",
    "quality": "great",
    "notes": "Slept very well"
  }' | jq .

echo ""
echo "2️⃣  Create sleep entry (with manual duration)..."
curl -X POST "$BASE_URL/babies/$BABY_ID/sleep" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "'$(date -u +'%Y-%m-%dT18:00:00Z')'",
    "duration_min": 90,
    "quality": "good"
  }' | jq .

echo ""
echo "3️⃣  List sleep entries..."
curl -X GET "$BASE_URL/babies/$BABY_ID/sleep?limit=10" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "4️⃣  Mark ongoing sleep as complete..."
SLEEP_ID="550e8400-e29b-41d4-a716-446655440000"  # Replace with actual sleep ID
curl -X PUT "$BASE_URL/sleep/$SLEEP_ID" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{"end_time": "'$(date -u +'%Y-%m-%dT22:00:00Z')'"}' | jq .

echo ""
echo ""

# ============================================================================
# MOOD ENDPOINTS
# ============================================================================

echo "😊 MOOD ENDPOINTS"
echo ""

echo "1️⃣  Create a mood entry..."
curl -X POST "$BASE_URL/babies/$BABY_ID/moods" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "happy",
    "energy": "high",
    "timestamp": "'$(date -u +'%Y-%m-%dT%H:%M:%SZ')'",
    "notes": "Very playful"
  }' | jq .

echo ""
echo "2️⃣  List mood entries..."
curl -X GET "$BASE_URL/babies/$BABY_ID/moods?limit=10" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "3️⃣  Update a mood..."
MOOD_ID="550e8400-e29b-41d4-a716-446655440000"  # Replace with actual mood ID
curl -X PUT "$BASE_URL/moods/$MOOD_ID" \
  -H "X-Dev-Uid: $DEV_UID" \
  -H "Content-Type: application/json" \
  -d '{"mood": "ok", "energy": "low"}' | jq .

echo ""
echo ""

# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

echo "📊 ANALYTICS ENDPOINTS"
echo ""

echo "1️⃣  Get 7-day summary..."
curl -X GET "$BASE_URL/babies/$BABY_ID/analytics/summary?range_days=7" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "2️⃣  Get 30-day summary..."
curl -X GET "$BASE_URL/babies/$BABY_ID/analytics/summary?range_days=30" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "3️⃣  Get 90-day summary..."
curl -X GET "$BASE_URL/babies/$BABY_ID/analytics/summary?range_days=90" \
  -H "X-Dev-Uid: $DEV_UID" | jq .

echo ""
echo "✅ Examples complete!"
