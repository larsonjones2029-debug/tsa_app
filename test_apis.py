import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

# Test TSA API
print("=== TSA API ===")
try:
    r = requests.get("http://apps.tsa.dhs.gov/MyTSAWebService/GetTSOWaitTimes.ashx",
                     params={"ap": "ORD", "output": "json"}, headers=HEADERS, timeout=10)
    print("Status:", r.status_code)
    print("Headers:", dict(r.headers))
    print("Body:", repr(r.text[:500]))
except Exception as e:
    print("Error:", e)

print()

# Test TSA API with XML instead
print("=== TSA API (XML) ===")
try:
    r = requests.get("http://apps.tsa.dhs.gov/MyTSAWebService/GetTSOWaitTimes.ashx",
                     params={"ap": "ORD", "output": "xml"}, headers=HEADERS, timeout=10)
    print("Status:", r.status_code)
    print("Body:", repr(r.text[:500]))
except Exception as e:
    print("Error:", e)

print()

# Test FAA NASSTATUS
print("=== FAA NASSTATUS ===")
try:
    r = requests.get("https://nasstatus.faa.gov/api/airport-status-information",
                     params={"airport": "ORD"}, headers=HEADERS, timeout=10)
    print("Status:", r.status_code)
    print("Body:", repr(r.text[:500]))
except Exception as e:
    print("Error:", e)

print()

# Test FAA Delays API (alternative endpoint)
print("=== FAA Delays API ===")
try:
    r = requests.get("https://soa.smext.faa.gov/asws/api/airport/delays",
                     headers=HEADERS, timeout=10)
    print("Status:", r.status_code)
    print("Body:", repr(r.text[:500]))
except Exception as e:
    print("Error:", e)

print()

# Test alternative TSA endpoint
print("=== MyTSA app API ===")
try:
    r = requests.get("https://apps.tsa.dhs.gov/mytsa/cco_index.aspx",
                     headers=HEADERS, timeout=10)
    print("Status:", r.status_code)
    print("Body:", repr(r.text[:300]))
except Exception as e:
    print("Error:", e)
