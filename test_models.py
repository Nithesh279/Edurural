import os
import google.generativeai as genai

env_path = ".env"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip()

api_key = os.environ.get("GEMINI_API_KEY", "")
print("API KEY:", api_key[:10] + "...")
genai.configure(api_key=api_key)

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print("Error listing models:", e)

try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    print("Model initialized.")
    response = model.generate_content("Hello")
    print("Response:", response.text)
except Exception as e:
    print("Error generating content:", e)
