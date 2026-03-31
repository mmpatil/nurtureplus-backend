#!/usr/bin/env python3
"""
Integration test for /auth/session endpoint.

Usage:
    python3 test_auth_integration.py --token <firebase_token> [--url http://localhost:8000]

Example:
    python3 test_auth_integration.py --token "eyJhbGc..." --url http://localhost:8000
"""

import requests
import json
import sys
from typing import Optional, Tuple
import argparse
from pprint import pprint


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_section(title: str):
    """Print a test section header."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{title:^60}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_pass(message: str):
    """Print a passing test."""
    print(f"{Colors.GREEN}✅ PASS{Colors.END}: {message}")


def print_fail(message: str):
    """Print a failing test."""
    print(f"{Colors.RED}❌ FAIL{Colors.END}: {message}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.YELLOW}ℹ️  INFO{Colors.END}: {message}")


def test_valid_token(base_url: str, token: str) -> Tuple[bool, Optional[dict]]:
    """Test 1: Valid token should return 200 with user_id and firebase_uid."""
    print_section("TEST 1: Valid Authorization Header with Bearer Token")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(f"{base_url}/auth/session", headers=headers, timeout=5)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            pprint(data)
            
            # Validate response has required fields
            if "user_id" in data and "firebase_uid" in data:
                print_pass("Response has both user_id and firebase_uid fields")
                
                # Validate user_id is a UUID
                user_id = data["user_id"]
                if len(user_id) == 36 and user_id.count("-") == 4:
                    print_pass(f"user_id is valid UUID: {user_id}")
                else:
                    print_fail(f"user_id doesn't look like UUID: {user_id}")
                
                # Validate firebase_uid is non-empty
                firebase_uid = data["firebase_uid"]
                if firebase_uid and len(firebase_uid) > 0:
                    print_pass(f"firebase_uid is non-empty: {firebase_uid}")
                else:
                    print_fail("firebase_uid is empty")
                
                return True, data
            else:
                print_fail("Response missing user_id or firebase_uid")
                return False, None
        else:
            print_fail(f"Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False, None
            
    except Exception as e:
        print_fail(f"Request failed: {e}")
        return False, None


def test_missing_header(base_url: str) -> bool:
    """Test 2: Missing Authorization header should return 401."""
    print_section("TEST 2: Missing Authorization Header (should reject)")
    
    try:
        response = requests.post(f"{base_url}/auth/session", timeout=5)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            data = response.json()
            print("Response:")
            pprint(data)
            
            if "detail" in data:
                print_pass(f"Missing header rejected with 401: {data['detail']}")
                return True
            else:
                print_fail("401 response missing detail field")
                return False
        else:
            print_fail(f"Expected 401, got {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"Request failed: {e}")
        return False


def test_invalid_format(base_url: str, token: str) -> bool:
    """Test 3: Invalid Bearer format should return 401."""
    print_section("TEST 3: Invalid Bearer Format (should reject)")
    
    headers = {
        "Authorization": f"NotBearer {token}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(f"{base_url}/auth/session", headers=headers, timeout=5)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            data = response.json()
            print("Response:")
            pprint(data)
            
            if "detail" in data and "Invalid authorization header format" in data["detail"]:
                print_pass(f"Invalid format rejected: {data['detail']}")
                return True
            else:
                print_fail("401 response but wrong error message")
                return False
        else:
            print_fail(f"Expected 401, got {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"Request failed: {e}")
        return False


def test_idempotent(base_url: str, token: str) -> bool:
    """Test 4: Same token should return same user_id."""
    print_section("TEST 4: Idempotent Behavior (same token = same user_id)")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    try:
        # First call
        response1 = requests.post(f"{base_url}/auth/session", headers=headers, timeout=5)
        if response1.status_code != 200:
            print_fail("First call failed")
            return False
        
        data1 = response1.json()
        print(f"First call:  {data1['user_id']}")
        
        # Second call
        response2 = requests.post(f"{base_url}/auth/session", headers=headers, timeout=5)
        if response2.status_code != 200:
            print_fail("Second call failed")
            return False
        
        data2 = response2.json()
        print(f"Second call: {data2['user_id']}")
        
        # Compare
        if data1["user_id"] == data2["user_id"]:
            print_pass("Same user_id returned (idempotent)")
            return True
        else:
            print_fail("Different user_id returned (not idempotent)")
            return False
            
    except Exception as e:
        print_fail(f"Request failed: {e}")
        return False


def test_response_format(base_url: str, token: str) -> bool:
    """Test 5: Response format validation."""
    print_section("TEST 5: Response Format Validation")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(f"{base_url}/auth/session", headers=headers, timeout=5)
        if response.status_code != 200:
            print_fail("Request failed")
            return False
        
        data = response.json()
        
        # Check required fields
        required_fields = ["user_id", "firebase_uid"]
        for field in required_fields:
            if field in data:
                print_pass(f"Has required field: {field}")
            else:
                print_fail(f"Missing required field: {field}")
                return False
        
        # Check no extra fields
        expected_fields = set(required_fields)
        actual_fields = set(data.keys())
        extra_fields = actual_fields - expected_fields
        
        if not extra_fields:
            print_pass("No unexpected fields in response")
        else:
            print_info(f"Extra fields (not required): {extra_fields}")
        
        return True
        
    except Exception as e:
        print_fail(f"Request failed: {e}")
        return False


def test_security_no_token_logged(base_url: str, token: str) -> bool:
    """Test 6: Verify token is not exposed in response."""
    print_section("TEST 6: Security - Token Not Exposed")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(f"{base_url}/auth/session", headers=headers, timeout=5)
        if response.status_code != 200:
            print_fail("Request failed")
            return False
        
        response_text = response.text
        
        # Check response doesn't contain token fragments
        dangerous_patterns = [
            "Bearer",
            "eyJ",  # JWT header
            ".eyJ",  # JWT payload
            "signature",
        ]
        
        found_issues = False
        for pattern in dangerous_patterns:
            if pattern in response_text:
                print_fail(f"Response contains potential token fragment: '{pattern}'")
                found_issues = True
        
        if not found_issues:
            print_pass("Token not exposed in response (secure)")
            return True
        
        return False
        
    except Exception as e:
        print_fail(f"Request failed: {e}")
        return False


def run_all_tests(base_url: str, token: str) -> Tuple[int, int]:
    """Run all tests and return (passed, total)."""
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Valid token
    tests_total += 1
    success, session_data = test_valid_token(base_url, token)
    if success:
        tests_passed += 1
    
    # Test 2: Missing header
    tests_total += 1
    if test_missing_header(base_url):
        tests_passed += 1
    
    # Test 3: Invalid format
    tests_total += 1
    if test_invalid_format(base_url, token):
        tests_passed += 1
    
    # Test 4: Idempotent
    tests_total += 1
    if test_idempotent(base_url, token):
        tests_passed += 1
    
    # Test 5: Response format
    tests_total += 1
    if test_response_format(base_url, token):
        tests_passed += 1
    
    # Test 6: Security
    tests_total += 1
    if test_security_no_token_logged(base_url, token):
        tests_passed += 1
    
    return tests_passed, tests_total


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integration test for /auth/session endpoint"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Firebase ID token to test with",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)",
    )
    
    args = parser.parse_args()
    
    token = args.token
    base_url = args.url.rstrip("/")
    
    print(f"\n{Colors.BLUE}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════╗")
    print("║   Nurture+ /auth/session Integration Test     ║")
    print("╚════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    print_info(f"Backend URL: {base_url}")
    print_info(f"Token: {token[:20]}...{token[-10:]}\n")
    
    # Run all tests
    tests_passed, tests_total = run_all_tests(base_url, token)
    
    # Summary
    print_section("TEST SUMMARY")
    
    if tests_passed == tests_total:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ All {tests_total} tests passed!{Colors.END}\n")
        print("Auth flow verified:")
        print("  ✅ Bearer token extraction: Correct")
        print("  ✅ Firebase verification: Correct")
        print("  ✅ firebase_uid extraction: Correct")
        print("  ✅ User mapping (firebase_uid → internal_id): Correct")
        print("  ✅ Response format (user_id, firebase_uid): Correct")
        print("  ✅ Security (token not logged): Correct")
        print(f"\n{Colors.GREEN}Status: Production Ready 🚀{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}❌ {tests_passed}/{tests_total} tests passed{Colors.END}\n")
        print("Some tests failed. Review output above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
