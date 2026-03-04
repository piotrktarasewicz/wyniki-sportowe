from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return """
    <h1>Test aplikacji</h1>
    <p>Jeśli to widzisz, Railway działa poprawnie.</p>
    """
