import json, requests, os, sys, textwrap

FILES = ["samples/valid.json", "samples/invalid.json"]
URL = "http://127.0.0.1:8001/validate"

def post_file(path):
    print("="*60)
    print("Posting:", path)
    with open(path, "r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    try:
        r = requests.post(URL, json=payload, timeout=10)
        print("status:", r.status_code)
        print("body:")
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)
    except Exception as e:
        print("request error:", repr(e))

def main():
    print("cwd:", os.getcwd())
    for p in FILES:
        if not os.path.exists(p):
            print("Missing sample file:", p)
            sys.exit(1)
        post_file(p)

if __name__ == '__main__':
    main()
