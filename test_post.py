import json, requests, os
p = "samples/valid.json"
print("cwd:", os.getcwd())
with open(p, "r", encoding="utf-8-sig") as f:
    payload = json.load(f)
r = requests.post("http://127.0.0.1:8001/validate", json=payload, timeout=10)
print("status:", r.status_code)
print("body:", r.text)
