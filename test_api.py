import google.generativeai as genai
import traceback
import sys

genai.configure(api_key='AIzaSyAGAvV-RfHCL_XR27pKqZnieScOIyVEIUE')
model = genai.GenerativeModel('gemini-pro')

try:
    print(model.generate_content('Hi', request_options={"timeout": 10}).text)
except Exception as e:
    with open("api_error.txt", "w") as f:
        f.write(str(e))
        f.write("\n")
        traceback.print_exc(file=f)
    print("Error saved to api_error.txt")
