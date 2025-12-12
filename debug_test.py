import json, requests, os, sys
p = "samples/valid.json"
print("cwd:", os.getcwd())
print("exists:", os.path.exists(p))
print("size:", os.path.getsize(p))
s = open(p, "rb").read()
print("first_bytes:", s[:4])
try:
    data = json.loads(s.decode("utf-8"))
    print("json loaded OK. keys:", list(data.keys()))
except Exception as e:
    print("json load error:", repr(e))
    print("preview (first 300 chars):")
    try:
        print(s.decode("utf-8")[:300])
    except:
        print(s[:300])
# attempt request (ensure server is running separately)
try:
    r = requests.post("http://127.0.0.1:8001/validate", json=data, timeout=10)
    print("status:", r.status_code)
    print("body:", r.text)
except Exception as e:
    print("request error:", repr(e))
