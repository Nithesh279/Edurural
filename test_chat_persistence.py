import requests
import json
import uuid

session = requests.Session()
BASE_URL = "http://127.0.0.1:5000"

# Register a test user
email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
password = "testpassword123"

print(f"Registering user: {email}")
register_res = session.post(f"{BASE_URL}/register", json={"username": email, "email": email, "password": password, "role": "student"})
if register_res.status_code != 200:
    print("Registration failed/skipped:", register_res.text)

print("Logging in...")
login_res = session.post(f"{BASE_URL}/login", json={"email": email, "password": password})
if login_res.status_code != 200:
    print("Login failed:", login_res.text)
    exit(1)

# Ask a question
video_id = 1
query1 = "My name is John. What is python?"
print(f"Asking: {query1}")
chat_res1 = session.post(f"{BASE_URL}/api/ai-chat", json={"video_id": video_id, "query": query1})
print("Response 1:", chat_res1.text)

# Ask a follow up question to test persistence
query2 = "What did I just say my name was?"
print(f"Asking: {query2}")
chat_res2 = session.post(f"{BASE_URL}/api/ai-chat", json={"video_id": video_id, "query": query2})
print("Response 2:", chat_res2.text)

# Fetch history
print("Fetching history...")
hist_res = session.get(f"{BASE_URL}/api/ai-chat/history/{video_id}")
print("History:", hist_res.text)
