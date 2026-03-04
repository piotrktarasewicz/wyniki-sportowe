import os
import requests
from flask import Flask, jsonify, render_template_string
from datetime import datetime, timedelta
from threading import Thread
import time

API_KEY = os.getenv("API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"

app = Flask(__name__)

cache = {
    "data": None,
    "last_update": None,
    "last_api_call": None
}

AUTO_REFRESH_MINUTES = 30
MANUAL_REFRESH_MINUTES = 5


def fetch_matches_for_date(date_str):
    headers = {"x-apisports-key": API_KEY}
    params = {"date": date_str}
    response = requests.get(API_URL, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def process_data(raw):
    live = []
    scheduled = []
    finished = []

    for item in raw.get("response", []):
        league = item["league"]["name"]
        country = item["league"]["country"]

        if country != "Poland":
            continue

        match = {
            "league": league,
            "home": item["teams"]["home"]["name"],
            "away": item["teams"]["away"]["name"],
            "score": f'{item["goals"]["home"]}-{item["goals"]["away"]}',
            "status": item["fixture"]["status"]["short"]
        }

        status = item["fixture"]["status"]["short"]

        if status == "FT":
            finished.append(match)
        elif status == "NS":
            scheduled.append(match)
        else:
            live.append(match)

    return {
        "live": live,
        "scheduled": scheduled,
        "finished": finished
    }


def update_cache(force=False):
    now = datetime.utcnow()

    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        raw = fetch_matches_for_date(today)
        processed = process_data(raw)

        if not processed["live"] and not processed["scheduled"] and not processed["finished"]:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            raw = fetch_matches_for_date(yesterday)
            processed = process_data(raw)

        cache["data"] = processed
        cache["last_update"] = now
        cache["last_api_call"] = now

    except Exception as e:
        print("API error:", e)
        # NIE przerywamy działania aplikacji
        if cache["data"] is None:
            cache["data"] = {
                "live": [],
                "scheduled": [],
                "finished": []
            }


def scheduler():
    while True:
        update_cache(force=True)
        time.sleep(AUTO_REFRESH_MINUTES * 60)


@app.route("/api/matches")
def api_matches():
    return jsonify({
        "updated_at": cache["last_update"],
        "data": cache["data"]
    })


@app.route("/refresh")
def manual_refresh():
    now = datetime.utcnow()

    if cache["last_api_call"]:
        if now - cache["last_api_call"] < timedelta(minutes=MANUAL_REFRESH_MINUTES):
            return jsonify({"message": "Odświeżenie możliwe co 5 minut."})

    update_cache(force=True)
    return jsonify({"message": "Dane odświeżone."})


@app.route("/")
def index():
    data = cache["data"] or {"live": [], "scheduled": [], "finished": []}
    updated = cache["last_update"]

    return render_template_string("""
    <h1>Wyniki piłki nożnej – Polska</h1>
    <p>Aktualizacja: {{ updated }}</p>
    <button onclick="refresh()">Odśwież teraz</button>

    <h2>Mecze trwające</h2>
    {% for m in data.live %}
        <p>{{ m.league }}: {{ m.home }} - {{ m.away }} {{ m.score }}</p>
    {% endfor %}

    <h2>Mecze zaplanowane</h2>
    {% for m in data.scheduled %}
        <p>{{ m.league }}: {{ m.home }} - {{ m.away }}</p>
    {% endfor %}

    <h2>Mecze zakończone</h2>
    {% for m in data.finished %}
        <p>{{ m.league }}: {{ m.home }} - {{ m.away }} {{ m.score }}</p>
    {% endfor %}

    <script>
    function refresh() {
        fetch('/refresh')
        .then(res => res.json())
        .then(data => alert(data.message));
    }
    </script>
    """, data=data, updated=updated)


# Uruchom scheduler przy starcie aplikacji (działa w Railway)
Thread(target=scheduler, daemon=True).start()

# Wykonaj pierwsze pobranie danych przy starcie
update_cache(force=True)
