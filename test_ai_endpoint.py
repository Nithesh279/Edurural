import requests
try:
    print("Testing /api/ai-chat...")
    response = requests.post(
        "http://127.0.0.1:5000/api/ai-chat",
        json={"video_id": None, "query": "what is python"},
        timeout=15
    )
    print("Status code:", response.status_code)
    print("Response body:", response.text)
except Exception as e:
    print("Error:", str(e))
