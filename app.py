import requests
from flask import Flask, jsonify, render_template_string
from datetime import datetime, timedelta
from threading import Thread
import time
from bs4 import BeautifulSoup

app = Flask(__name__)

cache = {
    "data": None,
    "last_update": None,
    "last_fetch": None
}

AUTO_REFRESH_MINUTES = 30
MANUAL_REFRESH_MINUTES = 5


# ---------------------------
# Pobieranie wyników
# ---------------------------

def fetch_polish_matches():

    leagues = [
        ("Ekstraklasa", "https://www.laczynaspilka.pl/rozgrywki/ekstraklasa/wyniki"),
        ("I liga", "https://www.laczynaspilka.pl/rozgrywki/1-liga/wyniki"),
        ("II liga", "https://www.laczynaspilka.pl/rozgrywki/2-liga/wyniki")
    ]

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    data = []

    for league_name, url in leagues:

        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            matches = []

            for line in soup.get_text("\n").splitlines():
                line = line.strip()
                if " - " in line and ":" in line:
                    matches.append(line)

            data.append({
                "league": league_name,
                "matches": matches[:20]
            })

        except Exception as e:
            print("League fetch error:", league_name, e)

    return data


# ---------------------------
# Aktualizacja cache
# ---------------------------

def update_cache(force=False):

    now = datetime.utcnow()

    if not force and cache["last_fetch"]:
        if now - cache["last_fetch"] < timedelta(minutes=AUTO_REFRESH_MINUTES):
            return

    try:

        leagues = fetch_polish_matches()

        cache["data"] = leagues
        cache["last_update"] = now
        cache["last_fetch"] = now

    except Exception as e:
        print("Update error:", e)


# ---------------------------
# Scheduler
# ---------------------------

def scheduler():

    while True:

        try:
            update_cache(force=True)
        except Exception as e:
            print("Scheduler error:", e)

        time.sleep(AUTO_REFRESH_MINUTES * 60)


def start_scheduler():

    thread = Thread(target=scheduler)
    thread.daemon = True
    thread.start()


# uruchom scheduler przy starcie aplikacji
start_scheduler()


# ---------------------------
# API endpoint
# ---------------------------

@app.route("/api/matches")
def api_matches():

    return jsonify({
        "updated_at": cache["last_update"],
        "data": cache["data"]
    })


# ---------------------------
# Ręczne odświeżanie
# ---------------------------

@app.route("/refresh")
def manual_refresh():

    now = datetime.utcnow()

    if cache["last_fetch"]:
        if now - cache["last_fetch"] < timedelta(minutes=MANUAL_REFRESH_MINUTES):
            return jsonify({"message": "Dane były odświeżane niedawno."})

    update_cache(force=True)

    return jsonify({"message": "Dane odświeżone."})


# ---------------------------
# Strona główna
# ---------------------------

@app.route("/")
def index():

    leagues = cache["data"] or []
    updated = cache["last_update"]

    return render_template_string("""

    <h1>Wyniki piłki nożnej – Polska</h1>

    <p>Ostatnia aktualizacja: {{updated}}</p>

    <button onclick="refresh()">Odśwież teraz</button>

    {% for league in leagues %}

        <h2>{{league.league}}</h2>

        {% if league.matches %}

            <ul>
            {% for match in league.matches %}
                <li>{{match}}</li>
            {% endfor %}
            </ul>

        {% else %}

            <p>Brak meczów</p>

        {% endif %}

    {% endfor %}

    <script>

    function refresh(){

        fetch('/refresh')
        .then(r => r.json())
        .then(data => alert(data.message))
        .then(() => location.reload())

    }

    </script>

    """, leagues=leagues, updated=updated)
