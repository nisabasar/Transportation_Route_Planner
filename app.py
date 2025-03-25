# app.py
from flask import Flask, render_template, request
import json
import os
from datetime import datetime

from models.route_planner import RoutePlanner
from factories import PaymentFactory

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    stops_data = json.load(f)

taxi_pricing = stops_data.get("taxi", {"openingFee": 10.0, "costPerKm": 4.0})
route_planner = RoutePlanner(stops_data, taxi_pricing)

def pick_best_route(routes):
    best = None
    for key, route in routes.items():
        if route is not None:
            if best is None:
                best = (key, route)
            else:
                best_cost = best[1]["total_cost"]
                new_cost = route["total_cost"]
                if new_cost < best_cost:
                    best = (key, route)
                elif abs(new_cost - best_cost) < 0.0001:
                    if route["total_time"] < best[1]["total_time"]:
                        best = (key, route)
    return best

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

    start_time_str = request.form.get("start_time", "")
    if start_time_str:
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
    else:
        start_dt = None

    passenger_type = request.form.get("passenger_type", "genel").lower()
    payment_type = request.form.get("payment_type", "nakit")
    payment_amount = float(request.form.get("payment_amount", 0))
    special_day = (request.form.get("special_day") == "on")

    payment_method = PaymentFactory.create_payment(payment_type, payment_amount)
    payment_label = {
        "kredi": "Kredi Kartı",
        "kentkart": "KentKart",
        "nakit": "Nakit"
    }.get(payment_type, "Nakit")

    raw_routes = route_planner.get_alternative_routes(
        start_lat, start_lon, dest_lat, dest_lon,
        passenger_type=passenger_type,
        payment_type=payment_type,
        start_time=start_dt,
        special_day=special_day
    )

    # Ödeme kısıtlamaları
    if payment_type == "kentkart":
        raw_routes["sadece_taksi"] = None
    if payment_type == "nakit":
        raw_routes["sadece_otobus"] = None
        raw_routes["tramvay_oncelikli"] = None
        raw_routes["en_az_aktarmali"] = None
        raw_routes["karma"] = None

    best_tuple = pick_best_route(raw_routes)
    if best_tuple:
        best_key, best_route = best_tuple
    else:
        best_key, best_route = (None, None)

    final_routes = {
        "rotaniz": best_route,
        "sadece_taksi": raw_routes["sadece_taksi"],
        "sadece_otobus": raw_routes["sadece_otobus"],
        "tramvay_oncelikli": raw_routes["tramvay_oncelikli"],
        "en_az_aktarmali": raw_routes["en_az_aktarmali"],
        "karma": raw_routes["karma"]
    }

    payment_results = {}
    for rkey, r in final_routes.items():
        if r:
            cost_to_pay = r["total_cost"]
            success, msg = payment_method.pay(cost_to_pay)
            payment_results[rkey] = {
                "success": success,
                "message": f"{payment_label}: {msg}"
            }
        else:
            payment_results[rkey] = None

    return render_template("results.html", routes=final_routes, payment_results=payment_results)

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    app.run(debug=True)
