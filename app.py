# app.py
from flask import Flask, render_template, request
import json
import os
from datetime import datetime

from models.route_planner import RoutePlanner
from models.payment import Nakit, KrediKarti, KentKart

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    stops_data = json.load(f)

taxi_pricing = stops_data.get("taxi", {"openingFee": 10.0, "costPerKm": 4.0})
route_planner = RoutePlanner(stops_data, taxi_pricing)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/route")
def route_page():
    return render_template("route.html")

@app.route("/plan", methods=["POST"])
def plan():
    start_lat = float(request.form["start_lat"])
    start_lon = float(request.form["start_lon"])
    dest_lat = float(request.form["dest_lat"])
    dest_lon = float(request.form["dest_lon"])

    # Tarih-saat parse
    start_time_str = request.form.get("start_time", "")
    if start_time_str:
        # "2025-03-22T18:44" formatında gelir
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
    else:
        start_dt = None

    passenger_type = request.form.get("passenger_type", "genel").lower()

    # Ödeme bilgileri
    payment_type = request.form.get("payment_type", "nakit")
    payment_amount = float(request.form.get("payment_amount", 0))

    # Rota alternatiflerini hesapla
    routes = route_planner.get_alternative_routes(
        start_lat, start_lon, dest_lat, dest_lon,
        passenger_type=passenger_type,
        start_time=start_dt
    )

    # Ödeme sınıfı seçimi
    if payment_type == "kredi":
        payment_method = KrediKarti(payment_amount)
        payment_label = "Kredi Kartı"
    elif payment_type == "kentkart":
        payment_method = KentKart(payment_amount)
        payment_label = "KentKart"
    else:
        payment_method = Nakit(payment_amount)
        payment_label = "Nakit"

    # Her rota için ödeme deneyelim (örnek)
    # Aslında kullanıcı hangi rotayı seçecek? Hepsi gösterilir, user seçebilir.
    # Burada sadece "taksi" rotası için ödeme örneği yapıyoruz
    payment_results = {}
    for rkey, r in routes.items():
        if r:
            cost_to_pay = r["discounted_cost"]
            success, msg = payment_method.pay(cost_to_pay)
            payment_results[rkey] = {
                "success": success,
                "message": f"{payment_label}: {msg}"
            }
            # Ödeme sınıfı bakiyesi/limiti düşer, bu nedenle
            # her rota denemesi öncesi kopya Payment nesnesi oluşturmak gerekebilir.
            # (Kısa tutmak için burada tek Payment nesnesi kullandık.)
        else:
            payment_results[rkey] = None

    return render_template("results.html", routes=routes, payment_results=payment_results)

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    app.run(debug=True)
