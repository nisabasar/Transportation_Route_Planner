# models/route_planner.py
import math
import heapq
from models.stop import Stop
from models.vehicle import Taxi
from utils.distance import haversine
from models.passenger import Genel, Ogrenci, Yasli

# Ortalama hızlar (km/dk cinsinden)
AVERAGE_TAXI_SPEED = 0.67      # Yaklaşık 40 km/saat
AVERAGE_WALK_SPEED = 0.083     # Yaklaşık 5 km/saat

# Taksi kullanım eşik mesafesi (km)
TAXI_THRESHOLD = 3.0

class RoutePlanner:
    def __init__(self, data, taxi_pricing):
        self.city = data.get("city", "")
        self.taxi_info = data.get("taxi", taxi_pricing)
        self.taxi = Taxi(self.taxi_info["openingFee"], self.taxi_info["costPerKm"])
        # Durakları id'ye göre sakla
        self.stops = {}
        for stop_data in data["duraklar"]:
            stop_obj = Stop(stop_data)
            self.stops[stop_obj.id] = stop_obj
        # Grafik yapısını oluştur
        self.graph = self.build_graph()

    def build_graph(self):
        graph = {}
        for stop_id, stop in self.stops.items():
            edges = []
            # nextStops üzerinden bağlantılar (süre, mesafe, ücret bilgileri)
            for ns in stop.nextStops:
                edge = {
                    "to": ns["stopId"],
                    "time": ns["sure"],
                    "distance": ns["mesafe"],
                    "cost": ns["ucret"],
                    "mode": stop.type  # bus veya tram
                }
                edges.append(edge)
            # Transfer bağlantısı varsa ekle
            if stop.transfer:
                edge = {
                    "to": stop.transfer["transferStopId"],
                    "time": stop.transfer["transferSure"],
                    "distance": 0,  # transferde mesafe hesaplanmaz
                    "cost": stop.transfer["transferUcret"],
                    "mode": "transfer"
                }
                edges.append(edge)
            graph[stop_id] = edges
        return graph

    def get_nearest_stop(self, lat, lon, mode_filter=None):
        nearest = None
        min_dist = float("inf")
        for stop in self.stops.values():
            if mode_filter and stop.type != mode_filter:
                continue
            d = haversine(lat, lon, stop.lat, stop.lon)
            if d < min_dist:
                min_dist = d
                nearest = stop
        return nearest, min_dist

    def dijkstra(self, start_id, end_id, mode_filter=None):
        queue = []
        heapq.heappush(queue, (0, start_id, []))
        distances = {stop_id: float("inf") for stop_id in self.stops}
        distances[start_id] = 0

        while queue:
            current_time, current_id, path = heapq.heappop(queue)
            path = path + [current_id]
            if current_id == end_id:
                return current_time, path
            for edge in self.graph.get(current_id, []):
                if mode_filter and edge["mode"] not in [mode_filter, "transfer"]:
                    continue
                neighbor = edge["to"]
                new_time = current_time + edge["time"]
                if new_time < distances[neighbor]:
                    distances[neighbor] = new_time
                    heapq.heappush(queue, (new_time, neighbor, path))
        return None, []

    def plan_public_route(self, start_stop, dest_stop, mode_filter=None):
        total_time, path = self.dijkstra(start_stop.id, dest_stop.id, mode_filter)
        if not path or total_time is None:
            return None
        total_distance = 0
        total_cost = 0
        steps = []
        for i in range(len(path) - 1):
            current = path[i]
            next_stop = path[i+1]
            edge = next(e for e in self.graph[current] if e["to"] == next_stop)
            steps.append({
                "from": current,
                "to": next_stop,
                "mode": edge["mode"],
                "time": edge["time"],
                "distance": edge["distance"],
                "cost": edge["cost"]
            })
            total_distance += edge["distance"]
            total_cost += edge["cost"]
        return {
            "steps": steps,
            "total_time": total_time,
            "total_distance": total_distance,
            "total_cost": total_cost
        }

    def plan_taxi_route(self, start_lat, start_lon, dest_lat, dest_lon):
        distance = haversine(start_lat, start_lon, dest_lat, dest_lon)
        time = distance / AVERAGE_TAXI_SPEED
        cost = self.taxi.calculate_cost(distance)
        return {
            "steps": [{
                "from": "Başlangıç",
                "to": "Varış",
                "mode": "taksi",
                "time": round(time, 1),
                "distance": round(distance, 2),
                "cost": round(cost, 2)
            }],
            "total_time": round(time, 1),
            "total_distance": round(distance, 2),
            "total_cost": round(cost, 2)
        }

    def get_alternative_routes(self, start_lat, start_lon, dest_lat, dest_lon, passenger_type="genel"):
        alternatives = {}

        # 1. Direkt Taksi Rotası
        taxi_route = self.plan_taxi_route(start_lat, start_lon, dest_lat, dest_lon)
        alternatives["taksi"] = taxi_route

        # 2. Toplu Taşıma Rotası (karma rota)
        start_stop, start_walk = self.get_nearest_stop(start_lat, start_lon)
        dest_stop, dest_walk = self.get_nearest_stop(dest_lat, dest_lon)

        walk_time_start = start_walk / AVERAGE_WALK_SPEED  # dakika
        walk_time_end = dest_walk / AVERAGE_WALK_SPEED

        public_route = self.plan_public_route(start_stop, dest_stop)
        steps = []
        if public_route:
            # Başlangıç segmenti: yürüme veya taksi
            if start_walk > TAXI_THRESHOLD:
                taxi_segment = self.plan_taxi_route(start_lat, start_lon, start_stop.lat, start_stop.lon)
                steps.append({
                    "from": "Başlangıç",
                    "to": start_stop.id,
                    "mode": "taksi",
                    "time": taxi_segment["total_time"],
                    "distance": taxi_segment["total_distance"],
                    "cost": taxi_segment["total_cost"]
                })
            else:
                steps.append({
                    "from": "Başlangıç",
                    "to": start_stop.id,
                    "mode": "yürüme",
                    "time": round(walk_time_start, 1),
                    "distance": round(start_walk, 2),
                    "cost": 0
                })
            # Toplu taşıma adımları
            steps.extend(public_route["steps"])
            # Varış segmenti: yürüme veya taksi
            if dest_walk > TAXI_THRESHOLD:
                taxi_segment = self.plan_taxi_route(dest_stop.lat, dest_stop.lon, dest_lat, dest_lon)
                steps.append({
                    "from": dest_stop.id,
                    "to": "Varış",
                    "mode": "taksi",
                    "time": taxi_segment["total_time"],
                    "distance": taxi_segment["total_distance"],
                    "cost": taxi_segment["total_cost"]
                })
            else:
                steps.append({
                    "from": dest_stop.id,
                    "to": "Varış",
                    "mode": "yürüme",
                    "time": round(walk_time_end, 1),
                    "distance": round(dest_walk, 2),
                    "cost": 0
                })

            total_time = walk_time_start + public_route["total_time"] + walk_time_end
            total_distance = start_walk + public_route["total_distance"] + dest_walk
            total_cost = public_route["total_cost"]

            alternatives["toplu"] = {
                "steps": steps,
                "total_time": round(total_time, 1),
                "total_distance": round(total_distance, 2),
                "total_cost": round(total_cost, 2)
            }
        else:
            alternatives["toplu"] = None

        # 3. Sadece Otobüs Rotası (mode filter: "bus")
        bus_start, _ = self.get_nearest_stop(start_lat, start_lon, mode_filter="bus")
        bus_dest, _ = self.get_nearest_stop(dest_lat, dest_lon, mode_filter="bus")
        bus_route = self.plan_public_route(bus_start, bus_dest, mode_filter="bus")
        alternatives["sadece_otobus"] = bus_route if bus_route else None

        # 4. Sadece Tramvay Rotası (mode filter: "tram")
        tram_start, _ = self.get_nearest_stop(start_lat, start_lon, mode_filter="tram")
        tram_dest, _ = self.get_nearest_stop(dest_lat, dest_lon, mode_filter="tram")
        tram_route = self.plan_public_route(tram_start, tram_dest, mode_filter="tram")
        alternatives["sadece_tramvay"] = tram_route if tram_route else None

        # Uygulanan indirim oranı (yolcu tipi)
        if passenger_type == "ogrenci":
            discount_rate = Ogrenci().get_discount_rate()
        elif passenger_type == "65+":
            discount_rate = Yasli().get_discount_rate()
        else:
            discount_rate = Genel().get_discount_rate()

        for key in alternatives:
            route = alternatives[key]
            if route is not None:
                route["discounted_cost"] = round(route["total_cost"] * (1 - discount_rate), 2)

        return alternatives
