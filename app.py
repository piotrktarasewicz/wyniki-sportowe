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
# Pobieranie danych z 90minut
# ---------------------------

def fetch_league(url, league_name):
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    matches = []

    for row in soup.find_all("tr"):
        text = row.get_text(" ", strip=True)

        if " - " in text and ":" in text:
            matches.append(text)

    return {
        "league": league_name,
        "matches": matches
    }


def fetch_polish_matches():

    leagues = [
        ("Ekstraklasa", "https://www.90minut.pl/liga/1/liga12694.html"),
        ("I liga", "https://www.90minut.pl/liga/1/liga12695.html"),
        ("II liga", "https://www.90minut.pl/liga/1/liga12696.html"),
        ("III liga", "https://www.90minut.pl/liga/1/liga12697.html")
    ]

    data = []

    for name, url in leagues:
        try:
            league_data = fetch_league(url, name)
            data.append(league_data)
        except Exception as e:
            print("League fetch error:", name, e)

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


Thread(target=scheduler, daemon=True).start()


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
    }

    </script>
    """, leagues=leagues, updated=updated)


# pierwsze pobranie danych
update_cache(force=True)
