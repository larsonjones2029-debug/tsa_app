"""
run.py — Start the TSA Wait Time Dashboard

    python run.py

Fetches fresh data then opens http://localhost:5000
"""

import threading, webbrowser, time, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from scraper import run_scraper
from app import app

if __name__ == "__main__":
    print("\n  TSA Wait Time Dashboard")
    print("  Fetching airport data...\n")

    # Fetch the most useful airports first (fast startup)
    priority = None
    run_scraper(priority)

    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=open_browser, daemon=True).start()
    print("\n  Dashboard running at http://localhost:5000\n")
    app.run(port=5000, debug=False, use_reloader=False)
