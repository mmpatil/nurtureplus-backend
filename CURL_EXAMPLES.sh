#!/bin/bash
# Curl examples for Nurture+ API
# 
# NOTE: Replace:
#   - <firebase_id_token> with actual Firebase ID token from iOS app
#   - <user_id> with UUID returned from /auth/session
#   - <baby_id> with UUID of a baby
#   - <dev_user_id> with any string (only when DEV_BYPASS_AUTH=true)

BASE_URL="http://localhost:8000"

echo "=== Nurture+ API Curl Examples ==="
echo ""

# 1. Health Check
echo "1. Health Check:"
echo "curl $BASE_URL/health"
curl "$BASE_URL/health"
echo ""
echo ""

# 2. Create Session (Production - with Firebase token)
echo "2. Create Session (Production):"
echo "curl -X POST $BASE_URL/auth/session \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>' \\"
echo "  -H 'Content-Type: application/json'"
echo ""
echo "EXAMPLE:"
echo "curl -X POST $BASE_URL/auth/session \\"
echo "  -H 'Authorization: Bearer your_firebase_token_here' \\"
echo "  -H 'Content-Type: application/json'"
echo ""

# 3. Create Session (Dev - with bypass)
echo "3. Create Session (Dev Bypass - if DEV_BYPASS_AUTH=true):"
echo "curl -X POST $BASE_URL/auth/session \\"
echo "  -H 'X-Dev-Uid: test-user-123' \\"
echo "  -H 'Content-Type: application/json'"
echo ""
echo "Response example:"
echo "{"
echo '  "user_id": "123e4567-e89b-12d3-a456-426614174000",'
echo '  "firebase_uid": "test-user-123"'
echo "}"
echo ""
echo ""

# 4. Create a Baby
echo "4. Create a Baby:"
echo "curl -X POST $BASE_URL/babies \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo '    "name": "Emma",'
echo '    "birth_date": "2024-01-15",'
echo '    "photo_url": "https://example.com/photo.jpg"'
echo "  }'"
echo ""

# 5. List Babies (Paginated)
echo "5. List Babies (Paginated):"
echo "curl '$BASE_URL/babies?limit=10&offset=0' \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>'"
echo ""

# 6. Get Single Baby
echo "6. Get Single Baby:"
echo "curl '$BASE_URL/babies/<baby_id>' \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>'"
echo ""

# 7. Update Baby
echo "7. Update Baby (partial update):"
echo "curl -X PUT '$BASE_URL/babies/<baby_id>' \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo '    "name": "Emma Rose",'
echo '    "photo_url": "https://example.com/new-photo.jpg"'
echo "  }'"
echo ""

# 8. Delete Baby
echo "8. Delete Baby:"
echo "curl -X DELETE '$BASE_URL/babies/<baby_id>' \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>'"
echo ""
echo "(Returns 204 No Content on success)"
echo ""

# 9. Test Auth Error
echo "9. Test 401 Unauthorized (missing token):"
echo "curl '$BASE_URL/babies'"
echo ""

# 10. Test Baby Not Found
echo "10. Test 404 Not Found (invalid baby ID):"
echo "curl '$BASE_URL/babies/invalid-uuid' \\"
echo "  -H 'Authorization: Bearer <firebase_id_token>'"
echo ""

echo "=== Interactive Example ==="
echo ""
echo "# 1. Create a session and save the user_id"
echo "RESPONSE=\$(curl -s -X POST $BASE_URL/auth/session \\"
echo "  -H 'X-Dev-Uid: test-user' \\"
echo "  -H 'Content-Type: application/json')"
echo "USER_ID=\$(echo \$RESPONSE | grep -o '\"user_id\":\"[^\"]*' | cut -d'\"' -f4)"
echo "echo \"User ID: \$USER_ID\""
echo ""
echo "# 2. Create a baby"
echo "BABY_RESPONSE=\$(curl -s -X POST $BASE_URL/babies \\"
echo "  -H 'X-Dev-Uid: test-user' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo '    \"name\": \"Emma\", \"birth_date\": \"2024-01-15\"'
echo "  }')"
echo "BABY_ID=\$(echo \$BABY_RESPONSE | grep -o '\"id\":\"[^\"]*' | head -1 | cut -d'\"' -f4)"
echo "echo \"Baby ID: \$BABY_ID\""
echo ""
echo "# 3. List babies"
echo "curl -s '\$BASE_URL/babies' \\"
echo "  -H 'X-Dev-Uid: test-user' | python -m json.tool"
echo ""
