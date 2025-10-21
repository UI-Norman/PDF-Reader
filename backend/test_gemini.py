import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file")
    exit(1)

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')
try:
    response = model.generate_content("Test prompt: Write a short sentence.")
    print("API Response:", response.text)
except Exception as e:
    print("API Error:", str(e))