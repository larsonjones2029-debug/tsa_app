import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

airports = {
    "ORD": "ORD/Chicago-OHare-International",
    "ATL": "ATL/Hartsfield-Jackson-Atlanta-International",
    "MSY": "MSY/Louis-Armstrong-New-Orleans-International",
}

for code, slug in airports.items():
    url = f"https://www.tsawaittimes.com/security-wait-times/{slug}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    print(f"\n=== {code} ===")
    # Print all lines that look like wait time data
    for i, line in enumerate(lines):
        if "minute" in line.lower() or ("am -" in line) or ("pm -" in line) or (line.endswith(" m") and i > 0):
            print(f"  [{i}] {repr(line)}")
