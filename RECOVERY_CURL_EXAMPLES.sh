#!/bin/bash

# Recovery Endpoint Examples
# =========================
# Usage: source this file or run individual curl commands
# Make sure the API is running at http://localhost:8000

BASE_URL="http://localhost:8000"
FIREBASE_TOKEN="YOUR_FIREBASE_ID_TOKEN_HERE"

# Helper function to print section headers
print_section() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}


# ============================================================================
# AUTHENTICATION
# ============================================================================

print_section "1. GET SESSION (Verify auth works)"

curl -X POST "${BASE_URL}/auth/session" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  | jq .


# ============================================================================
# CREATE RECOVERY ENTRY
# ============================================================================

print_section "2. CREATE RECOVERY ENTRY"

# Basic entry
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 48,
    "symptoms": ["soreness", "insomnia"],
    "notes": "Feeling a bit better today"
  }' \
  | jq .

# Entry with no symptoms
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T14:30:00Z",
    "mood": "great",
    "energy_level": "high",
    "water_intake_oz": 56,
    "symptoms": [],
    "notes": "Had a good rest today"
  }' \
  | jq .

# Entry with multiple symptoms
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-30T08:15:00Z",
    "mood": "struggling",
    "energy_level": "low",
    "water_intake_oz": 32,
    "symptoms": ["soreness", "bleeding", "cramping", "headache"],
    "notes": "Rough morning, lots of pain"
  }' \
  | jq .


# ============================================================================
# LIST RECOVERY ENTRIES
# ============================================================================

print_section "3. LIST RECOVERY ENTRIES"

# Get all entries (default pagination)
curl -X GET "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .

# With pagination
curl -X GET "${BASE_URL}/recovery?limit=10&offset=0" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .

# With time filter (last 7 days)
FROM_TIME=$(date -u -d "7 days ago" +"%Y-%m-%dT%H:%M:%SZ")
TO_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

curl -X GET "${BASE_URL}/recovery?from_time=${FROM_TIME}&to_time=${TO_TIME}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .

# Just yesterday
YESTERDAY=$(date -u -d "1 day ago" +"%Y-%m-%dT00:00:00Z")
TODAY=$(date -u +"%Y-%m-%dT00:00:00Z")

curl -X GET "${BASE_URL}/recovery?from_time=${YESTERDAY}&to_time=${TODAY}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .


# ============================================================================
# GET LATEST RECOVERY ENTRY
# ============================================================================

print_section "4. GET LATEST RECOVERY ENTRY"

curl -X GET "${BASE_URL}/recovery/latest" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .


# ============================================================================
# GET RECOVERY SUMMARY
# ============================================================================

print_section "5. GET RECOVERY SUMMARY"

# 7-day summary (default)
curl -X GET "${BASE_URL}/recovery/summary" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .

# 14-day summary
curl -X GET "${BASE_URL}/recovery/summary?days=14" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .

# 30-day summary (monthly overview)
curl -X GET "${BASE_URL}/recovery/summary?days=30" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .


# ============================================================================
# GET SINGLE RECOVERY ENTRY
# ============================================================================

print_section "6. GET SINGLE RECOVERY ENTRY"

# First, get the ID of an entry from the list
ENTRY_ID=$(curl -s -X GET "${BASE_URL}/recovery?limit=1" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq -r '.items[0].id')

echo "Fetching entry: ${ENTRY_ID}"

curl -X GET "${BASE_URL}/recovery/${ENTRY_ID}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  | jq .


# ============================================================================
# UPDATE RECOVERY ENTRY
# ============================================================================

print_section "7. UPDATE RECOVERY ENTRY (PARTIAL)"

# Update only the mood
curl -X PUT "${BASE_URL}/recovery/${ENTRY_ID}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "okay"
  }' \
  | jq .

# Update mood and notes
curl -X PUT "${BASE_URL}/recovery/${ENTRY_ID}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "good",
    "notes": "Updated - feeling better now"
  }' \
  | jq .

# Update water intake
curl -X PUT "${BASE_URL}/recovery/${ENTRY_ID}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "water_intake_oz": 64
  }' \
  | jq .


# ============================================================================
# DELETE RECOVERY ENTRY
# ============================================================================

print_section "8. DELETE RECOVERY ENTRY"

curl -X DELETE "${BASE_URL}/recovery/${ENTRY_ID}" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -v


# ============================================================================
# VALIDATION EXAMPLES
# ============================================================================

print_section "9. VALIDATION TESTS"

# Invalid mood (should fail)
echo "Testing invalid mood (should fail with 422):"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "terrible",
    "energy_level": "moderate",
    "water_intake_oz": 48,
    "symptoms": []
  }' \
  | jq .

# Invalid energy level (should fail)
echo "Testing invalid energy level (should fail with 422):"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "good",
    "energy_level": "superHigh",
    "water_intake_oz": 48,
    "symptoms": []
  }' \
  | jq .

# Water intake too low (should fail)
echo "Testing water intake below bounds (should fail with 422):"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": -5,
    "symptoms": []
  }' \
  | jq .

# Water intake too high (should fail)
echo "Testing water intake above bounds (should fail with 422):"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 150,
    "symptoms": []
  }' \
  | jq .

# Invalid symptom (should fail)
echo "Testing invalid symptom (should fail with 422):"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-31T10:00:00Z",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 48,
    "symptoms": ["soreness", "invalidSymptom"]
  }' \
  | jq .


# ============================================================================
# REAL-WORLD USAGE EXAMPLES
# ============================================================================

print_section "10. REAL-WORLD USAGE EXAMPLES"

# Daily morning check-in (6 AM)
echo "Morning check-in:"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "'$(date -u +"%Y-%m-%dT06:00:00Z")'",
    "mood": "okay",
    "energy_level": "veryLow",
    "water_intake_oz": 8,
    "symptoms": ["soreness", "insomnia"],
    "notes": "Just woke up, haven't had much water yet"
  }' \
  | jq .

# Afternoon check-in (2 PM)
echo "Afternoon check-in:"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "'$(date -u +"%Y-%m-%dT14:00:00Z")'",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 32,
    "symptoms": ["soreness"],
    "notes": "Getting better as the day goes on"
  }' \
  | jq .

# Evening check-in (8 PM)
echo "Evening check-in:"
curl -X POST "${BASE_URL}/recovery" \
  -H "Authorization: Bearer ${FIREBASE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "'$(date -u +"%Y-%m-%dT20:00:00Z")'",
    "mood": "good",
    "energy_level": "moderate",
    "water_intake_oz": 64,
    "symptoms": [],
    "notes": "Good day overall, pain management working"
  }' \
  | jq .

print_section "Examples Complete!"
