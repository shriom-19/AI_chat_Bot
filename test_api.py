import requests
from requests.auth import HTTPBasicAuth
import time

base_url = "http://127.0.0.1:8000/api"
auth = HTTPBasicAuth("ADMIN", "ADMIN123")

print("Checking API root...")
try:
    res = requests.get("http://127.0.0.1:8000/")
    print(res.json())
except Exception as e:
    print("API not reachable yet:", e)

print("\nListing bots...")
res = requests.get(f"{base_url}/bots", auth=auth)
print(res.status_code, res.json())
