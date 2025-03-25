# models/route_planner.py

import heapq
from datetime import timedelta
from models.stop import Stop
from models.vehicle import Taxi
from models.passenger import Genel, Ogrenci, Yasli
from utils.distance import haversine

AVERAGE_TAXI_SPEED = 0.67   # km/dk
AVERAGE_WALK_SPEED = 0.083  # km/dk
TAXI_THRESHOLD = 3.0

MODE_COLORS = {
    "taksi": "red",
    "bus": "blue",
    "tram": "orange",
    "yürüme": "gray",
    "transfer": "purple"
}

class RoutePlanner:
    def __init__(self, data, taxi_pricing):
        self.city = data.get("city", "")
        self.taxi_info = taxi_pricing
        self.taxi = Taxi(self.taxi_info["openingFee"], self.taxi_info["costPerKm"])
        self.stops = {}
        for stop_data in data["duraklar"]:
            stop_obj = Stop(stop_data)
            self.stops[stop_obj.id] = stop_obj
        self.graph = self.build_graph()

    def build_graph(self):
        graph = {}
        for stop_id, stop in self.stops.items():
            edges = []
            for ns in stop.nextStops:
                edge = {
                    "to": ns["stopId"],
                    "time": ns["sure"],
                    "distance": ns["mesafe"],
                    "cost": ns["ucret"],
                    "mode": stop.type
                }
                edges.append(edge)
            if stop.transfer:
                edge = {
                    "to": stop.transfer["transferStopId"],
                    "time": stop.transfer["transferSure"],
                    "distance": 0,
                    "cost": stop.transfer["transferUcret"],
                    "mode": "transfer"
                }
                edges.append(edge)
            graph[stop_id] = edges
        return graph

    def get_nearest_stop(self, lat, lon, mode_filter=None):
        """
        Verilen konuma en yakın durağı bulur. mode_filter ile sadece belirli tipte duraklar (ör. "bus", "tram") seçilebilir.
        """
        nearest = None
        min_dist = float("inf")
        for s in self.stops.values():
            if mode_filter and s.type != mode_filter:
                continue
            d = haversine(lat, lon, s.lat, s.lon)
            if d < min_dist:
                min_dist = d
                nearest = s
        return nearest, min_dist

    def dijkstra(self, start_id, end_id, mode_filter=None, exclude_transfer=False):
        distances = {k: float("inf") for k in self.stops}
        queue = []
        heapq.heappush(queue, (0, start_id, []))
        distances[start_id] = 0

        while queue:
            current_time, current_id, path = heapq.heappop(queue)
            path = path + [current_id]
            if current_id == end_id:
                return current_time, path

            for edge in self.graph[current_id]:
                if exclude_transfer and edge["mode"] == "transfer":
                    continue
                if mode_filter and edge["mode"] not in [mode_filter, "transfer"]:
                    continue
                neighbor = edge["to"]
                new_time = current_time + edge["time"]
                if new_time < distances[neighbor]:
                    distances[neighbor] = new_time
                    heapq.heappush(queue, (new_time, neighbor, path))
        return None, []

    def calculate_step_cost(self, base_cost, mode, passenger_type, payment_type, special_day):
        """
        Base ücrete göre, mode, yolcu tipi, ödeme yöntemi ve özel gün bilgisine göre final cost ve açıklama hesaplar.
        """
        final_cost = base_cost
        explanation = ""

        if mode == "taksi":
            explanation = "Taksi => indirim yok"
            return round(final_cost, 2), explanation

        if mode == "yürüme":
            return 0, "Yürüme => ücret yok"

        if special_day and mode in ["bus", "tram", "transfer"]:
            return 0, "Özel gün => ücretsiz"

        if mode in ["bus", "tram", "transfer"] and payment_type == "kredi":
            return round(base_cost, 2), "Kredi kartıyla => indirim yok"

        if mode in ["bus", "tram", "transfer"] and payment_type in ["nakit", "kentkart"]:
            if passenger_type == "ogrenci":
                disc = 0.5
                final_cost = base_cost * (1 - disc)
                explanation = "Öğrenci indirimi (Nakit/KentKart)"
            elif passenger_type == "65+":
                disc = 0.3
                final_cost = base_cost * (1 - disc)
                explanation = "Yaşlı indirimi (Nakit/KentKart)"
            else:
                explanation = "Genel yolcu (Nakit/KentKart)"

        return round(final_cost, 2), explanation

    def plan_taxi_route(self, start_lat, start_lon, dest_lat, dest_lon,
                        passenger_type="genel", payment_type="nakit", special_day=False):
        dist = haversine(start_lat, start_lon, dest_lat, dest_lon)
        time = dist / AVERAGE_TAXI_SPEED
        base_cost = self.taxi.calculate_cost(dist)
        final_cost, explanation = self.calculate_step_cost(
            base_cost, "taksi", passenger_type, payment_type, special_day
        )
        color = MODE_COLORS["taksi"]

        steps = [{
            "from": "Başlangıç",
            "to": "Varış",
            "mode": "taksi",
            "time": round(time, 1),
            "distance": round(dist, 2),
            "base_cost": round(base_cost, 2),
            "final_cost": final_cost,
            "discount_explanation": explanation,
            "color": color
        }]

        return {
            "steps": steps,
            "total_time": round(time, 1),
            "total_distance": round(dist, 2),
            "total_cost": round(final_cost, 2),
            "latlon_segments": [{
                "color": color,
                "points": [
                    (start_lat, start_lon),
                    (dest_lat, dest_lon)
                ]
            }]
        }

    def plan_public_route(self, start_stop, dest_stop,
                          passenger_type="genel", payment_type="nakit",
                          special_day=False, mode_filter=None):
        total_time, path = self.dijkstra(start_stop.id, dest_stop.id,
                                         mode_filter=mode_filter,
                                         exclude_transfer=False)
        if not path or total_time is None:
            return None

        steps = []
        total_distance = 0
        total_cost = 0
        latlon_segments = []

        for i in range(len(path) - 1):
            cur = path[i]
            nxt = path[i+1]
            edge = next(e for e in self.graph[cur] if e["to"] == nxt)
            mode = edge["mode"]
            color = MODE_COLORS.get(mode, "black")
            base_cost = edge["cost"]
            final_cost, explanation = self.calculate_step_cost(
                base_cost, mode, passenger_type, payment_type, special_day
            )

            steps.append({
                "from": cur,
                "to": nxt,
                "mode": mode,
                "time": edge["time"],
                "distance": edge["distance"],
                "base_cost": round(base_cost, 2),
                "final_cost": final_cost,
                "discount_explanation": explanation,
                "color": color
            })

            total_distance += edge["distance"]
            total_cost += final_cost
            latlon_segments.append({
                "color": color,
                "points": [
                    (self.stops[cur].lat, self.stops[cur].lon),
                    (self.stops[nxt].lat, self.stops[nxt].lon)
                ]
            })

        return {
            "steps": steps,
            "total_time": round(total_time, 1),
            "total_distance": round(total_distance, 2),
            "total_cost": round(total_cost, 2),
            "latlon_segments": latlon_segments
        }

    def plan_public_route_no_transfer(self, start_stop, dest_stop,
                                      passenger_type="genel", payment_type="nakit",
                                      special_day=False):
        total_time, path = self.dijkstra(start_stop.id, dest_stop.id,
                                         mode_filter=None,
                                         exclude_transfer=True)
        if not path or total_time is None:
            return None

        steps = []
        total_distance = 0
        total_cost = 0
        latlon_segments = []

        for i in range(len(path) - 1):
            cur = path[i]
            nxt = path[i+1]
            possible_edges = [e for e in self.graph[cur] if e["to"] == nxt and e["mode"] != "transfer"]
            if not possible_edges:
                return None
            edge = possible_edges[0]
            mode = edge["mode"]
            color = MODE_COLORS.get(mode, "black")
            base_cost = edge["cost"]
            final_cost, explanation = self.calculate_step_cost(
                base_cost, mode, passenger_type, payment_type, special_day
            )
            steps.append({
                "from": cur,
                "to": nxt,
                "mode": mode,
                "time": edge["time"],
                "distance": edge["distance"],
                "base_cost": round(base_cost, 2),
                "final_cost": final_cost,
                "discount_explanation": explanation,
                "color": color
            })
            total_distance += edge["distance"]
            total_cost += final_cost
            latlon_segments.append({
                "color": color,
                "points": [
                    (self.stops[cur].lat, self.stops[cur].lon),
                    (self.stops[nxt].lat, self.stops[nxt].lon)
                ]
            })

        return {
            "steps": steps,
            "total_time": round(total_time, 1),
            "total_distance": round(total_distance, 2),
            "total_cost": round(total_cost, 2),
            "latlon_segments": latlon_segments
        }

    def get_alternative_routes(self, start_lat, start_lon, dest_lat, dest_lon,
                               passenger_type="genel", payment_type="nakit",
                               start_time=None, special_day=False):
        # 1) Sadece Taksi
        sadece_taksi = self.plan_taxi_route(
            start_lat, start_lon, dest_lat, dest_lon,
            passenger_type, payment_type, special_day
        )

        # 2) Sadece Otobüs
        bus_start, _ = self.get_nearest_stop(start_lat, start_lon, mode_filter="bus")
        bus_dest, _  = self.get_nearest_stop(dest_lat, dest_lon, mode_filter="bus")
        sadece_otobus = None
        if bus_start and bus_dest:
            route_bus = self.plan_public_route(bus_start, bus_dest,
                                               passenger_type, payment_type,
                                               special_day, mode_filter="bus")
            sadece_otobus = route_bus

        # 3) Tramvay Öncelikli
        tram_start, _ = self.get_nearest_stop(start_lat, start_lon, mode_filter="tram")
        tram_dest, _  = self.get_nearest_stop(dest_lat, dest_lon, mode_filter="tram")
        tramvay_oncelikli = None
        if tram_start and tram_dest:
            route_tram = self.plan_public_route(tram_start, tram_dest,
                                                passenger_type, payment_type,
                                                special_day, mode_filter="tram")
            tramvay_oncelikli = route_tram

        # 4) En Az Aktarmalı (transfer edge'leri hariç)
        start_stop, _ = self.get_nearest_stop(start_lat, start_lon)
        dest_stop, _  = self.get_nearest_stop(dest_lat, dest_lon)
        en_az_aktarmali = None
        if start_stop and dest_stop:
            route_no_transfer = self.plan_public_route_no_transfer(
                start_stop, dest_stop,
                passenger_type, payment_type, special_day
            )
            en_az_aktarmali = route_no_transfer

        # 5) Karma: Otobüs/Tramvay/Transfer adımlarını içeren karma senaryo
        karma = None
        if start_stop and dest_stop:
            public_core = self.plan_public_route(
                start_stop, dest_stop,
                passenger_type, payment_type, special_day,
                mode_filter=None
            )
            if public_core:
                karma = public_core

        routes = {
            "sadece_taksi": sadece_taksi,
            "sadece_otobus": sadece_otobus,
            "tramvay_oncelikli": tramvay_oncelikli,
            "en_az_aktarmali": en_az_aktarmali,
            "karma": karma
        }

        if start_time:
            for key, r in routes.items():
                if r:
                    arrival_dt = start_time + timedelta(minutes=r["total_time"])
                    r["arrival_time"] = arrival_dt.strftime("%d.%m.%Y %H:%M")

        return routes
