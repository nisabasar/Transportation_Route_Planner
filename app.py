# app.py
from flask import Flask, render_template, request, redirect, url_for
import json
import os

from models.route_planner import RoutePlanner

app = Flask(__name__)

# JSON veri seti
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    stops_data = json.load(f)

# Taksi ücret bilgileri
taxi_pricing = stops_data.get("taxi", {"openingFee": 10.0, "costPerKm": 4.0})
route_planner = RoutePlanner(stops_data, taxi_pricing)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # Form verilerini işle
        # ...
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/route")
def route_page():
    return render_template("route.html")

@app.route("/plan", methods=["POST"])
def plan():
    # Form verilerini al
    start_lat = float(request.form["start_lat"])
    start_lon = float(request.form["start_lon"])
    dest_lat = float(request.form["dest_lat"])
    dest_lon = float(request.form["dest_lon"])
    passenger_type = request.form.get("passenger_type", "genel").lower()
    
    # (Opsiyonel) Ödeme ve zaman bilgileri
    start_time = request.form.get("start_time", "")
    cash_amount = request.form.get("cash_amount", "")
    credit_limit = request.form.get("credit_limit", "")
    kentkart_balance = request.form.get("kentkart_balance", "")

    # Rotaları hesapla
    routes = route_planner.get_alternative_routes(start_lat, start_lon, dest_lat, dest_lon, passenger_type)

    return render_template("results.html", routes=routes)

if __name__ == "__main__":
    app.run(debug=True)
