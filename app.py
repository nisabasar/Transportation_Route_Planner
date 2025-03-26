from flask import Flask, render_template, request, flash, redirect, url_for
import os
import json
from datetime import datetime, timedelta
from models.route_planner import RoutePlanner
from factories import PaymentFactory

app = Flask(__name__)
app.secret_key = "secret-key"  # flash mesajları için

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    stops_data = json.load(f)

taxi_pricing = stops_data["taxi"]
route_planner = RoutePlanner(stops_data, taxi_pricing)

def fix_latlon_if_swapped(lat, lon):
    # Örneğin Kocaeli civarında lat ~ 40.x, lon ~ 29.x olmalı.
    # Eğer lat < 35 ve lon > 35 ise ters girilmiş olabilir.
    if lat < 35 and lon > 35:
        return lon, lat
    return lat, lon

def pick_best_route(routes):
    best = None
    best_key = None
    for k, v in routes.items():
        if v:
            if not best:
                best = v
                best_key = k
            else:
                if v["total_cost"] < best["total_cost"]:
                    best = v
                    best_key = k
                elif abs(v["total_cost"] - best["total_cost"]) < 1e-9:
                    if v["total_time"] < best["total_time"]:
                        best = v
                        best_key = k
    return best_key, best

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/route")
def route_page():
    return render_template("route.html")

@app.route("/plan", methods=["POST"])
def plan():
    # Form verilerini al
    try:
        start_lat = float(request.form["start_lat"])
        start_lon = float(request.form["start_lon"])
        dest_lat = float(request.form["dest_lat"])
        dest_lon = float(request.form["dest_lon"])
    except (KeyError, ValueError):
        flash("Lütfen haritada başlangıç ve varış noktalarını seçiniz.")
        return redirect(url_for("route_page"))
        
    # Opsiyonel: Koordinatları ters girildiyse düzelt
    start_lat, start_lon = fix_latlon_if_swapped(start_lat, start_lon)
    dest_lat, dest_lon = fix_latlon_if_swapped(dest_lat, dest_lon)

    # Basit range kontrolü (örneğin Kocaeli civarı için)
    if not (38 < start_lat < 42 and 27 < start_lon < 31 and 38 < dest_lat < 42 and 27 < dest_lon < 31):
        flash("Girilen koordinatlar geçerli görünmüyor. Lütfen Kocaeli civarında nokta seçiniz.")
        return redirect(url_for("route_page"))

    start_time_str = request.form.get("start_time", "")
    if start_time_str:
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
    else:
        start_dt = None

    passenger_type = request.form.get("passenger_type", "genel").lower()
    payment_type = request.form.get("payment_type", "nakit")
    payment_amount = float(request.form.get("payment_amount", "0"))
    special_day = (request.form.get("special_day") == "on")

    # Ödeme nesnesi oluştur
    payment_method = PaymentFactory.create_payment(payment_type, payment_amount)
    payment_label = {"kredi": "Kredi Kartı",
                     "kentkart": "KentKart",
                     "nakit": "Nakit"}.get(payment_type, "Nakit")

    # Rotaları hesapla
    routes = route_planner.get_alternative_routes(
        start_lat, start_lon, dest_lat, dest_lon,
        passenger_type, payment_type,
        start_time=start_dt, special_day=special_day
    )

    if not routes:
        # Duraklar yine de haritaya basılabilsin diye stops_data'yı gönderelim
        duraklar = stops_data["duraklar"]
        return render_template("results.html",
                               routes={},
                               payment_results={},
                               duraklar=duraklar)

    # En iyi rota (rotaniz) seç
    best_key, best_val = pick_best_route(routes)
    final_routes = {
        "rotaniz": best_val,
        "sadece_taksi": routes.get("sadece_taksi"),
        "sadece_otobus": routes.get("sadece_otobus"),
        "sadece_tramvay": routes.get("sadece_tramvay"),
        "otobus_tramvay": routes.get("otobus_tramvay"),
        "taksi_otobus_tramvay": routes.get("taksi_otobus_tramvay")
    }

    # Ödeme sonuçları
    import copy
    payment_results = {}
    for rkey, r in final_routes.items():
        if r:
            pay_copy = copy.deepcopy(payment_method)
            cost = r["total_cost"]
            success, msg = pay_copy.pay(cost)
            payment_results[rkey] = {
                "success": success,
                "message": f"{payment_label}: {msg}"
            }
        else:
            payment_results[rkey] = None

    # Durakları da template'e gönderiyoruz ki haritada göstersin
    duraklar = stops_data["duraklar"]

    return render_template("results.html",
                           routes=final_routes,
                           payment_results=payment_results,
                           duraklar=duraklar)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/results")
def results():
    """
    Bu örnek endpoint test amaçlı.
    Normalde /plan ile rota hesaplayıp sonuç gösteriyorsanız, buna ihtiyacınız olmayabilir.
    """
    with open("data/stops.json", encoding="utf-8") as f:
        stops_data_local = json.load(f)
    duraklar_local = stops_data_local["duraklar"]

    routes_example = {
        "rotaniz": {
            "steps": [
                {"from": "Otogar", "to": "Sekapark", "mode": "bus",
                 "time": 10, "distance": 3.5, "base_cost": 3.0, "final_cost": 3.0,
                 "discount_explanation": "", "color": "blue"},
            ],
            "total_time": 10,
            "total_distance": 3.5,
            "total_cost": 3.0,
            "latlon_segments": [
                {
                    "points": [[40.78259, 29.94628], [40.76520, 29.96190]],
                    "color": "blue"
                }
            ]
        }
    }

    payment_results_example = {
        "rotaniz": {"success": True, "message": "Nakit: Ödeme başarılı"}
    }

    return render_template("results.html",
                           routes=routes_example,
                           payment_results=payment_results_example,
                           duraklar=duraklar_local)

if __name__ == "__main__":
    app.run(debug=True)
