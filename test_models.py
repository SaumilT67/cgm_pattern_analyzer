import os
import json
from urllib.request import Request, urlopen
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("NO GEMINI_API_KEY FOUND")
    exit()

request = Request(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={
        "x-goog-api-key": api_key
    }
)

with urlopen(request) as response:
    data = json.loads(response.read().decode("utf-8"))

for model in data.get("models", []):
    print(model["name"])