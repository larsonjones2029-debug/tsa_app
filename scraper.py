"""
scraper.py — TSA Wait Time data fetcher
Data sources:
  1. FAA NASSTATUS XML API (live airport delays) — works great
  2. Historical pattern data (busyness by hour/day) — always available
  3. TSA wait time page scraper (best effort — crowdsourced)
"""

import os, json, requests, xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "tsa_data.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

AIRPORTS = {
    "ORD": "Chicago O'Hare",
    "MDW": "Chicago Midway",
    "LAX": "Los Angeles",
    "JFK": "New York JFK",
    "LGA": "New York LaGuardia",
    "EWR": "Newark",
    "ATL": "Atlanta",
    "DFW": "Dallas/Fort Worth",
    "DEN": "Denver",
    "SFO": "San Francisco",
    "SEA": "Seattle",
    "MIA": "Miami",
    "MSY": "New Orleans",
    "BOS": "Boston",
    "PHX": "Phoenix",
    "LAS": "Las Vegas",
    "MCO": "Orlando",
    "MSP": "Minneapolis",
    "DTW": "Detroit",
    "PHL": "Philadelphia",
    "CLT": "Charlotte",
    "IAH": "Houston Intercontinental",
    "SLC": "Salt Lake City",
    "BWI": "Baltimore",
    "DCA": "Washington Reagan",
    "IAD": "Washington Dulles",
    "PDX": "Portland",
    "SAN": "San Diego",
    "STL": "St. Louis",
}

# Busyness by hour 0-23, scale 0-100
HOURLY_PATTERN = {
    0: 5,  1: 3,  2: 2,  3: 3,  4: 15, 5: 55, 6: 80, 7: 75,
    8: 60, 9: 45, 10: 35, 11: 40, 12: 45, 13: 50, 14: 55,
    15: 70, 16: 85, 17: 90, 18: 80, 19: 65, 20: 50, 21: 35,
    22: 20, 23: 10,
}

DAY_PATTERN = {0: 0.85, 1: 0.80, 2: 0.82, 3: 0.88, 4: 1.10, 5: 0.95, 6: 1.05}
DAY_NAMES   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]


# ── FAA Delays (XML) ──────────────────────────────────────────────────────────

def fetch_faa_delays():
    """
    Fetch all current FAA delays from NASSTATUS XML API.
    Returns dict mapping airport code -> delay info.
    """
    url = "https://nasstatus.faa.gov/api/airport-status-information"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        update_time = root.findtext("Update_Time", "")

        delays_by_airport = {}

        for delay_type in root.findall("Delay_type"):
            type_name = delay_type.findtext("Name", "")

            # Arrival/Departure delays
            adl = delay_type.find("Arrival_Departure_Delay_List")
            if adl is not None:
                for delay in adl.findall("Delay"):
                    arpt = delay.findtext("ARPT", "").upper()
                    reason = delay.findtext("Reason", "")
                    ad = delay.find("Arrival_Departure")
                    if ad is not None:
                        min_delay = ad.findtext("Min", "")
                        max_delay = ad.findtext("Max", "")
                        trend     = ad.findtext("Trend", "")
                        ad_type   = ad.get("Type", "")
                        if arpt not in delays_by_airport:
                            delays_by_airport[arpt] = []
                        delays_by_airport[arpt].append({
                            "type": type_name,
                            "reason": reason,
                            "direction": ad_type,
                            "min": min_delay,
                            "max": max_delay,
                            "trend": trend,
                        })

            # Ground delays
            gdl = delay_type.find("Ground_Delay_List")
            if gdl is not None:
                for gd in gdl.findall("Ground_Delay"):
                    arpt = gd.findtext("ARPT", "").upper()
                    avg  = gd.findtext("Avg", "")
                    max_ = gd.findtext("Max", "")
                    reason = gd.findtext("Reason", "")
                    if arpt not in delays_by_airport:
                        delays_by_airport[arpt] = []
                    delays_by_airport[arpt].append({
                        "type": "Ground Delay",
                        "reason": reason,
                        "avg": avg,
                        "max": max_,
                    })

            # Ground stops
            gsl = delay_type.find("Ground_Stop_List")
            if gsl is not None:
                for gs in gsl.findall("Program"):
                    arpt = gs.findtext("ARPT", "").upper()
                    reason = gs.findtext("Reason", "")
                    end    = gs.findtext("End_Time", "")
                    if arpt not in delays_by_airport:
                        delays_by_airport[arpt] = []
                    delays_by_airport[arpt].append({
                        "type": "Ground Stop",
                        "reason": reason,
                        "end_time": end,
                    })

            # Closures
            cl = delay_type.find("Closure_List")
            if cl is not None:
                for c in cl.findall("Airport"):
                    arpt = c.findtext("ARPT", "").upper()
                    reason = c.findtext("Reason", "")
                    if arpt not in delays_by_airport:
                        delays_by_airport[arpt] = []
                    delays_by_airport[arpt].append({
                        "type": "Closure",
                        "reason": reason,
                    })

        print(f"[FAA] Got delays for {len(delays_by_airport)} airports: {list(delays_by_airport.keys())}")
        return delays_by_airport, update_time

    except Exception as e:
        print(f"[FAA] Error: {e}")
        return {}, ""


# ── Historical estimates ───────────────────────────────────────────────────────

def get_historical_estimate(hour=None, day_of_week=None):
    now = datetime.now()
    h   = hour if hour is not None else now.hour
    dow = day_of_week if day_of_week is not None else now.weekday()
    score = min(100, int(HOURLY_PATTERN.get(h, 50) * DAY_PATTERN.get(dow, 1.0)))
    if score < 20:   label, color = "Very light", "success"
    elif score < 40: label, color = "Light",      "success"
    elif score < 60: label, color = "Moderate",   "warning"
    elif score < 80: label, color = "Busy",        "warning"
    else:            label, color = "Very busy",   "danger"
    return {"score": score, "label": label, "color": color,
            "day": DAY_NAMES[dow], "hour": h}


def get_best_times(day_of_week=None):
    now = datetime.now()
    dow = day_of_week if day_of_week is not None else now.weekday()
    mult = DAY_PATTERN.get(dow, 1.0)
    hours = []
    for h in range(4, 23):
        score = min(100, int(HOURLY_PATTERN.get(h, 50) * mult))
        hd = h % 12 or 12
        suffix = "am" if h < 12 else "pm"
        hours.append({"hour": h, "score": score, "label": f"{hd}{suffix}"})
    s = sorted(hours, key=lambda x: x["score"])
    return {"best": s[:3], "worst": s[-3:][::-1], "all": hours}


def get_arrival_recommendation(faa_delays, flight_hour, has_precheck=False, tsawait=None):
    base = 30   # gate buffer
    walk = 20   # walk to gate

    # Look up the specific hour slot matching when they'd go through security
    hourly_wait, period = get_wait_for_hour(tsawait, flight_hour) if tsawait else (None, None)

    if hourly_wait is not None:
        raw_wait = hourly_wait
        source = f"tsawaittimes.com ({period})"
    elif tsawait and tsawait.get("avg_minutes"):
        raw_wait = tsawait["avg_minutes"]
        source = "tsawaittimes.com (daily avg)"
    else:
        busy = get_historical_estimate(hour=max(4, flight_hour - 2))
        raw_wait = int(busy["score"] * 0.4)
        source = "historical estimate"

    wait_add = max(5, int(raw_wait * 0.5) if has_precheck else raw_wait)
    delay_add = 20 if faa_delays else 0
    total = min(180, max(60, base + walk + wait_add + delay_add))
    return {
        "total_minutes": total,
        "source": source,
        "breakdown": {
            "gate_buffer": base,
            "walk_time": walk,
            "security_wait": wait_add,
            "delay_buffer": delay_add,
        }
    }


# ── Main data builder ─────────────────────────────────────────────────────────

def fetch_airport_data(airport_code, faa_delays_cache=None):
    code = airport_code.upper()
    print(f"[Scraper] Building data for {code}...")

    faa      = faa_delays_cache.get(code, []) if faa_delays_cache else []
    current  = get_historical_estimate()
    times    = get_best_times()
    tsawait  = fetch_tsawait_data(code)

    # Use real wait time from tsawaittimes.com if available
    if tsawait and tsawait.get("avg_minutes") is not None:
        current["real_avg_minutes"] = tsawait["avg_minutes"]
        # Override hourly pattern with real data if we have it
        if tsawait.get("hourly"):
            current["has_real_hourly"] = True

    return {
        "airport_code": code,
        "airport_name": AIRPORTS.get(code, code),
        "fetched_at": datetime.now().isoformat(),
        "faa_delays": faa,
        "has_delay": len(faa) > 0,
        "current_busyness": current,
        "best_worst_times": times,
        "tsawait": tsawait,
    }


def run_scraper(airport_codes=None):
    codes = airport_codes or list(AIRPORTS.keys())
    print(f"[Scraper] Fetching FAA delay data...")
    faa_all, faa_time = fetch_faa_delays()

    results = {}
    for code in codes:
        try:
            results[code] = fetch_airport_data(code, faa_delays_cache=faa_all)
        except Exception as e:
            print(f"[Scraper] Failed {code}: {e}")

    # Tag any airport with FAA delays that isn't in our list
    for code, delays in faa_all.items():
        if code not in results and delays:
            name = AIRPORTS.get(code, code)
            results[code] = {
                "airport_code": code,
                "airport_name": name,
                "fetched_at": datetime.now().isoformat(),
                "faa_delays": delays,
                "has_delay": True,
                "current_busyness": get_historical_estimate(),
                "best_worst_times": get_best_times(),
            }

    output = {
        "last_updated": datetime.now().isoformat(),
        "faa_update_time": faa_time,
        "airports_with_delays": list(faa_all.keys()),
        "airports": results,
        "airport_list": [{"code": k, "name": v} for k, v in AIRPORTS.items()],
    }

    with open(DATA_FILE, "w") as f:
        json.dump(output, f, indent=2)

    delayed = [c for c,d in results.items() if d.get("has_delay")]
    print(f"[OK] {len(results)} airports saved. {len(delayed)} with active FAA delays: {delayed}")
    return output




# ── tsawaittimes.com scraper ──────────────────────────────────────────────────

# URL slugs for tsawaittimes.com — not all airports are listed
TSAWAIT_SLUGS = {
    "ATL": "ATL/Hartsfield-Jackson-Atlanta-International",
    "ORD": "ORD/Chicago-OHare-International",
    "LAX": "LAX/Los-Angeles-International",
    "JFK": "JFK/John-F-Kennedy-International",
    "LGA": "LGA/LaGuardia",
    "EWR": "EWR/Newark-Liberty-International",
    "DFW": "DFW/Dallas-Fort-Worth-International",
    "DEN": "DEN/Denver-International",
    "SFO": "SFO/San-Francisco-International",
    "SEA": "SEA/Seattle-Tacoma-International",
    "MIA": "MIA/Miami-International",
    "BOS": "BOS/Boston-Logan-International",
    "PHX": "PHX/Phoenix-Sky-Harbor-International",
    "LAS": "LAS/Las-Vegas-Harry-Reid-International",
    "MCO": "MCO/Orlando-International",
    "MSP": "MSP/Minneapolis-Saint-Paul-International",
    "DTW": "DTW/Detroit-Metropolitan-Wayne-County",
    "PHL": "PHL/Philadelphia-International",
    "CLT": "CLT/Charlotte-Douglas-International",
    "IAH": "IAH/Houston-George-Bush-Intercontinental",
    "SLC": "SLC/Salt-Lake-City-International",
    "BWI": "BWI/Baltimore-Washington-International",
    "DCA": "DCA/Ronald-Reagan-Washington-National",
    "IAD": "IAD/Washington-Dulles-International",
    "PDX": "PDX/Portland-International",
    "SAN": "SAN/San-Diego-International",
    "MDW": "MDW/Chicago-Midway-International",
    "MSY": "MSY/Louis-Armstrong-New-Orleans-International",
}


def fetch_tsawait_data(airport_code):
    """
    Scrape tsawaittimes.com for a given airport.
    Returns dict with hourly breakdown and PreCheck status.

    The "average" shown on the page reflects only recent crowdsourced reports
    (often near-zero at off-peak hours). We ignore it and use the hourly
    breakdown instead, which is far more reliable.
    """
    slug = TSAWAIT_SLUGS.get(airport_code.upper())
    if not slug:
        return None

    url = f"https://www.tsawaittimes.com/security-wait-times/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Extract hourly breakdown
        # Format on page: "12 pm - 1 pm" followed by "15 m" on next line
        hourly = []
        for i, line in enumerate(lines):
            if ("am -" in line or "pm -" in line) and i + 1 < len(lines):
                wait_line = lines[i + 1]
                # Must look like "15 m" or "0 m" — not a dropdown option
                cleaned = wait_line.replace(" m", "").strip()
                if cleaned.isdigit() and len(cleaned) <= 3:
                    try:
                        mins = int(cleaned)
                        # Parse the start hour from period label
                        start = line.split(" - ")[0].strip()  # e.g. "12 pm"
                        parts = start.split()
                        hour_num = int(parts[0])
                        suffix = parts[1].lower() if len(parts) > 1 else "am"
                        if suffix == "pm" and hour_num != 12:
                            hour_num += 12
                        if suffix == "am" and hour_num == 12:
                            hour_num = 0
                        hd = hour_num % 12 or 12
                        suf = "am" if hour_num < 12 else "pm"
                        hourly.append({
                            "period": line,
                            "hour": hour_num,
                            "label": f"{hd}{suf}",
                            "minutes": mins,
                        })
                    except Exception:
                        pass

        # Extract PreCheck status
        precheck_info = []
        in_precheck = False
        for line in lines:
            if "TSA Pre" in line or "PreCheck" in line:
                in_precheck = True
            if in_precheck:
                if "Open" in line or "Closed" in line:
                    precheck_info.append(line)
                if len(precheck_info) > 10:
                    break

        has_shutdown_notice = "government shutdown" in r.text.lower()

        # Compute a true average from the hourly data (ignoring zero-slots)
        nonzero = [h["minutes"] for h in hourly if h["minutes"] > 0]
        avg_minutes = round(sum(nonzero) / len(nonzero)) if nonzero else None

        result = {
            "source": "tsawaittimes.com",
            "url": url,
            "avg_minutes": avg_minutes,
            "hourly": hourly,
            "precheck_info": precheck_info,
            "has_shutdown_notice": has_shutdown_notice,
        }
        print(f"[TSAWAIT] {airport_code}: computed avg={avg_minutes}min from {len(hourly)} hourly slots")
        return result

    except Exception as e:
        print(f"[TSAWAIT] Error for {airport_code}: {e}")
        return None


def get_wait_for_hour(tsawait, flight_hour):
    """
    Return the wait time for the hour BEFORE the flight
    (since that's when you'll be going through security).
    Falls back to the hourly average if no match.
    """
    if not tsawait or not tsawait.get("hourly"):
        return None, None

    security_hour = max(0, flight_hour - 1)
    hourly = tsawait["hourly"]

    # Find the slot matching security_hour
    for slot in hourly:
        if slot["hour"] == security_hour:
            return slot["minutes"], slot["period"]

    # Fall back to nearest slot
    closest = min(hourly, key=lambda s: abs(s["hour"] - security_hour))
    return closest["minutes"], closest["period"]

if __name__ == "__main__":
    run_scraper()
