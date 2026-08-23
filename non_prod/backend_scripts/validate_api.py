import urllib.request
import json
import time

def check_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req)
        return res.getcode(), res.read().decode('utf-8')
    except Exception as e:
        if hasattr(e, 'code'):
            return e.code, str(e)
        return 500, str(e)

urls_to_test = [
    'http://127.0.0.1:8000/api/stations/',
    'http://127.0.0.1:8000/api/routes/',
    'http://127.0.0.1:8000/api/alerts/',
    'http://127.0.0.1:8000/api/tickets/'
]

for url in urls_to_test:
    code, data = check_url(url)
    print(f"{url}: {code} - Length: {len(data)}")
    if code == 200:
        try:
            js = json.loads(data)
            print(f"  Valid JSON: Yes, Type: {type(js)}")
        except Exception as e:
            print(f"  Valid JSON: No ({e})")
