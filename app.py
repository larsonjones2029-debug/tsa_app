"""
app.py — TSA Wait Time Dashboard server
"""

import os, json, threading
from flask import Flask, jsonify, render_template, request

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "tsa_data.json")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
_state = {"running": False, "error": None}


def _load():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE) as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    data = _load()
    if not data:
        return jsonify({"error": "No data yet"}), 404
    return jsonify(data)


@app.route("/api/airport/<code>")
def api_airport(code):
    from scraper import fetch_airport_data, get_arrival_recommendation, fetch_faa_delays
    try:
        code = code.upper()
        faa_all, _ = fetch_faa_delays()
        data = fetch_airport_data(code, faa_delays_cache=faa_all)
        flight_hour  = int(request.args.get("flight_hour", 12))
        has_precheck = request.args.get("precheck", "false").lower() == "true"
        data["recommendation"] = get_arrival_recommendation(
            data.get("faa_delays", []), flight_hour, has_precheck,
            tsawait=data.get("tsawait"))
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if _state["running"]:
        return jsonify({"status": "already_running"}), 202

    def _run():
        _state["running"] = True
        _state["error"] = None
        try:
            from scraper import run_scraper
            run_scraper()
        except Exception as e:
            _state["error"] = str(e)
        finally:
            _state["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"}), 202


@app.route("/api/refresh/status")
def api_refresh_status():
    data = _load()
    return jsonify({
        "running": _state["running"],
        "error":   _state["error"],
        "last_updated": data.get("last_updated") if data else None,
    })
