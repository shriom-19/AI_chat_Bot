import requests
from requests.auth import HTTPBasicAuth
import time
import sys

base_url = "http://127.0.0.1:8001/api"
auth = HTTPBasicAuth("ADMIN", "ADMIN123")

print("1. Creating a test bot...")
bot_payload = {
    "name": "Test Bot",
    "website_url": "https://en.wikipedia.org/wiki/Chatbot",
    "description": "A test bot",
    "system_prompt": "You are a helpful assistant."
}
res = requests.post(f"{base_url}/bots", json=bot_payload, auth=auth)
if res.status_code != 201:
    print("Failed to create bot:", res.status_code, res.text)
    sys.exit(1)

bot_id = res.json()["id"]
print(f"Bot created with ID: {bot_id}")

print("2. Waiting for bot to be ready...")
for _ in range(10):
    res = requests.get(f"{base_url}/bots/{bot_id}", auth=auth)
    bot = res.json()
    if bot["status"] == "ready":
        print("Bot is ready!")
        break
    elif bot["status"] == "error":
        print("Bot failed to index.")
        sys.exit(1)
    time.sleep(2)
else:
    print("Bot indexing timed out.")
    sys.exit(1)

print("3. Testing chat with bot...")
chat_payload = {
    "session_id": "test_session",
    "message": "What domain is this for?"
}
res = requests.post(f"{base_url}/bots/{bot_id}/chat", json=chat_payload, auth=auth)
if res.status_code != 200:
    print("Chat failed:", res.status_code, res.text)
    sys.exit(1)

print("Chat response:", res.json())
print("Test completed successfully!")
