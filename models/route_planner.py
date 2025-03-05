# models/route_planner.py
import math
import heapq
from datetime import datetime, timedelta
from models.stop import Stop
from models.vehicle import Taxi
from models.passenger import Genel, Ogrenci, Yasli
from utils.distance import haversine

# Ortalama hızlar (km/dk)
AVERAGE_TAXI_SPEED = 0.67   # ~40 km/s
AVERAGE_WALK_SPEED = 0.083  # ~5 km/s
TAXI_THRESHOLD = 3.0

# Mode => renk eşlemesi (haritada farklı renk polylineler)
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
                    "time": ns["sure"],      # dakika
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

    def dijkstra(self, start_id, end_id, mode_filter=None):
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
        steps = []
        total_distance = 0
        total_cost = 0
        latlon_segments = []  # her adımın latlon listesi (renkli çizim için)
        for i in range(len(path) - 1):
            current = path[i]
            next_stop = path[i+1]
            edge = next(e for e in self.graph[current] if e["to"] == next_stop)
            mode = edge["mode"]
            color = MODE_COLORS.get(mode, "black")

            step_distance = edge["distance"]
            step_cost = edge["cost"]
            step_time = edge["time"]

            steps.append({
                "from": current,
                "to": next_stop,
                "mode": mode,
                "time": step_time,
                "distance": step_distance,
                "cost": step_cost,
                "color": color
            })
            total_distance += step_distance
            total_cost += step_cost

            # lat/lon
            latlon_segments.append({
                "color": color,
                "points": [
                    (self.stops[current].lat, self.stops[current].lon),
                    (self.stops[next_stop].lat, self.stops[next_stop].lon)
                ]
            })
        return {
            "steps": steps,
            "total_time": total_time,
            "total_distance": total_distance,
            "total_cost": total_cost,
            "latlon_segments": latlon_segments
        }

    def plan_taxi_route(self, start_lat, start_lon, dest_lat, dest_lon):
        dist = haversine(start_lat, start_lon, dest_lat, dest_lon)
        time = dist / AVERAGE_TAXI_SPEED
        cost = self.taxi.calculate_cost(dist)
        color = MODE_COLORS["taksi"]
        return {
            "steps": [{
                "from": "Başlangıç",
                "to": "Varış",
                "mode": "taksi",
                "time": round(time, 1),
                "distance": round(dist, 2),
                "cost": round(cost, 2),
                "color": color
            }],
            "total_time": round(time, 1),
            "total_distance": round(dist, 2),
            "total_cost": round(cost, 2),
            "latlon_segments": [{
                "color": color,
                "points": [
                    (start_lat, start_lon),
                    (dest_lat, dest_lon)
                ]
            }]
        }

    def get_alternative_routes(self, start_lat, start_lon, dest_lat, dest_lon,
                               passenger_type="genel", start_time=None):
        # Yolcu indirimi
        if passenger_type == "ogrenci":
            discount_rate = Ogrenci().get_discount_rate()
        elif passenger_type == "65+":
            discount_rate = Yasli().get_discount_rate()
        else:
            discount_rate = Genel().get_discount_rate()

        # 1) Direkt Taksi
        taksi_route = self.plan_taxi_route(start_lat, start_lon, dest_lat, dest_lon)

        # 2) Karma (toplu) Rota
        start_stop, dist_start = self.get_nearest_stop(start_lat, start_lon)
        dest_stop, dist_dest = self.get_nearest_stop(dest_lat, dest_lon)

        walk_time_start = dist_start / AVERAGE_WALK_SPEED
        walk_time_end = dist_dest / AVERAGE_WALK_SPEED

        public_core = self.plan_public_route(start_stop, dest_stop)
        if public_core:
            steps_combined = []
            total_time = 0
            total_cost = 0
            total_dist = 0
            latlon_segments = []

            # 2a) Başlangıç segmenti
            if dist_start > TAXI_THRESHOLD:
                # taksi
                seg = self.plan_taxi_route(start_lat, start_lon, start_stop.lat, start_stop.lon)
                steps_combined.extend(seg["steps"])
                total_time += seg["total_time"]
                total_cost += seg["total_cost"]
                total_dist += seg["total_distance"]
                latlon_segments.extend(seg["latlon_segments"])
            else:
                # yürüme
                steps_combined.append({
                    "from": "Başlangıç",
                    "to": start_stop.id,
                    "mode": "yürüme",
                    "time": round(walk_time_start, 1),
                    "distance": round(dist_start, 2),
                    "cost": 0,
                    "color": MODE_COLORS["yürüme"]
                })
                total_time += walk_time_start
                total_dist += dist_start
                latlon_segments.append({
                    "color": MODE_COLORS["yürüme"],
                    "points": [
                        (start_lat, start_lon),
                        (start_stop.lat, start_stop.lon)
                    ]
                })

            # 2b) Toplu taşıma
            steps_combined.extend(public_core["steps"])
            total_time += public_core["total_time"]
            total_cost += public_core["total_cost"]
            total_dist += public_core["total_distance"]
            latlon_segments.extend(public_core["latlon_segments"])

            # 2c) Varış segmenti
            if dist_dest > TAXI_THRESHOLD:
                seg = self.plan_taxi_route(dest_stop.lat, dest_stop.lon, dest_lat, dest_lon)
                steps_combined.extend(seg["steps"])
                total_time += seg["total_time"]
                total_cost += seg["total_cost"]
                total_dist += seg["total_distance"]
                latlon_segments.extend(seg["latlon_segments"])
            else:
                steps_combined.append({
                    "from": dest_stop.id,
                    "to": "Varış",
                    "mode": "yürüme",
                    "time": round(walk_time_end, 1),
                    "distance": round(dist_dest, 2),
                    "cost": 0,
                    "color": MODE_COLORS["yürüme"]
                })
                total_time += walk_time_end
                total_dist += dist_dest
                latlon_segments.append({
                    "color": MODE_COLORS["yürüme"],
                    "points": [
                        (dest_stop.lat, dest_stop.lon),
                        (dest_lat, dest_lon)
                    ]
                })

            toplu_route = {
                "steps": steps_combined,
                "total_time": round(total_time, 1),
                "total_distance": round(total_dist, 2),
                "total_cost": round(total_cost, 2),
                "latlon_segments": latlon_segments
            }
        else:
            toplu_route = None

        # 3) Sadece Otobüs
        bus_start, _ = self.get_nearest_stop(start_lat, start_lon, mode_filter="bus")
        bus_dest, _ = self.get_nearest_stop(dest_lat, dest_lon, mode_filter="bus")
        bus_route = self.plan_public_route(bus_start, bus_dest, mode_filter="bus")

        # 4) Sadece Tramvay
        tram_start, _ = self.get_nearest_stop(start_lat, start_lon, mode_filter="tram")
        tram_dest, _ = self.get_nearest_stop(dest_lat, dest_lon, mode_filter="tram")
        tram_route = self.plan_public_route(tram_start, tram_dest, mode_filter="tram")

        # Rota sözlüğü
        alternatives = {
            "toplu": toplu_route,
            "sadece_otobus": bus_route,
            "sadece_tramvay": tram_route,
            "taksi": taksi_route
        }

        # İndirim uygula
        for key, route in alternatives.items():
            if route:
                route["discounted_cost"] = round(route["total_cost"] * (1 - discount_rate), 2)

        # Varış saati (start_time + total_time)
        if start_time:
            for key, route in alternatives.items():
                if route:
                    arrival_dt = start_time + timedelta(minutes=route["total_time"])
                    route["arrival_time"] = arrival_dt.strftime("%d.%m.%Y %H:%M")

        return alternatives
