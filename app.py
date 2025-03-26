# app.py
from flask import Flask, render_template, request
import os
import json
from datetime import datetime
from models.route_planner import RoutePlanner
from factories import PaymentFactory

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    stops_data = json.load(f)

taxi_pricing = stops_data["taxi"]
route_planner = RoutePlanner(stops_data, taxi_pricing)

def pick_best_route(routes):
    best=None
    best_key=None
    for k,v in routes.items():
        if v:
            if not best:
                best=v
                best_key=k
            else:
                if v["total_cost"]<best["total_cost"]:
                    best=v
                    best_key=k
                elif abs(v["total_cost"]-best["total_cost"])<1e-9:
                    if v["total_time"]<best["total_time"]:
                        best=v
                        best_key=k
    return best_key,best

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/route")
def route_page():
    return render_template("route.html")

@app.route("/plan", methods=["POST"])
def plan():
    start_lat=float(request.form["start_lat"])
    start_lon=float(request.form["start_lon"])
    dest_lat=float(request.form["dest_lat"])
    dest_lon=float(request.form["dest_lon"])

    start_time_str=request.form.get("start_time","")
    if start_time_str:
        start_dt=datetime.strptime(start_time_str,"%Y-%m-%dT%H:%M")
    else:
        start_dt=None

    passenger_type=request.form.get("passenger_type","genel").lower()
    payment_type=request.form.get("payment_type","nakit")
    payment_amount=float(request.form.get("payment_amount","0"))
    special_day=(request.form.get("special_day")=="on")

    payment_method=PaymentFactory.create_payment(payment_type, payment_amount)
    payment_label={"kredi":"Kredi Kartı","kentkart":"KentKart","nakit":"Nakit"}.get(payment_type,"Nakit")

    routes = route_planner.get_alternative_routes(
        start_lat, start_lon, dest_lat, dest_lon,
        passenger_type, payment_type,
        start_time=start_dt, special_day=special_day
    )

    if not routes:
        return render_template("results.html", routes={}, payment_results={})

    best_key,best_val= pick_best_route(routes)
    final_routes={
        "rotaniz": best_val,
        "sadece_taksi": routes.get("sadece_taksi"),
        "sadece_otobus": routes.get("sadece_otobus"),
        "sadece_tramvay": routes.get("sadece_tramvay"),
        "otobus_tramvay": routes.get("otobus_tramvay"),
        "taksi_otobus_tramvay": routes.get("taksi_otobus_tramvay")
    }

    import copy
    payment_results={}
    for rkey,r in final_routes.items():
        if r:
            pay_copy=copy.deepcopy(payment_method)
            cost=r["total_cost"]
            success,msg=pay_copy.pay(cost)
            payment_results[rkey]={"success":success,"message":f"{payment_label}: {msg}"}
        else:
            payment_results[rkey]=None

    return render_template("results.html", routes=final_routes, payment_results=payment_results)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__=="__main__":
    app.run(debug=True)
