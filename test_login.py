import requests
import json

BASE_URL = "http://127.0.0.1:5000"
EMAIL = "test_user_123@example.com"
PASSWORD = "password123"

s = requests.Session()

print(f"1. Attempting to Register {EMAIL}...")
try:
    res = s.post(f"{BASE_URL}/register", json={"email": EMAIL, "password": PASSWORD, "role": "student"})
    print(f"   Status: {res.status_code}")
    print(f"   Body: {res.text}")
except Exception as e:
    print(f"   Error: {e}")

print(f"\n2. Attempting to Login...")
try:
    res = s.post(f"{BASE_URL}/login", json={"email": EMAIL, "password": PASSWORD})
    print(f"   Status: {res.status_code}")
    print(f"   Body: {res.text}")
    
    if res.status_code == 200:
        print("\n✅ Login SUCCESS!")
    else:
        print("\n❌ Login FAILED!")
except Exception as e:
    print(f"   Error: {e}")
