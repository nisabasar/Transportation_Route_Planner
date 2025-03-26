import math
from datetime import timedelta
from models.stop import Stop
from models.vehicle import Taxi
from utils.distance import haversine

# Sabit hız değerleri
AVERAGE_WALK_SPEED = 0.083   # km/dk (~5 km/s)
AVERAGE_TAXI_SPEED = 0.67    # km/dk (~40 km/s)

# Harita renkleri
MODE_COLORS = {
    "walk": "gray",
    "taksi": "red",
    "bus": "blue",
    "tram": "orange",
    "transfer": "purple"
}

class RoutePlanner:
    def __init__(self, data, taxi_pricing):
        self.data = data
        self.city = data.get("city", "")
        self.taxi_info = taxi_pricing
        self.taxi = Taxi(taxi_pricing["openingFee"], taxi_pricing["costPerKm"])
        self.stops = {}
        for s in data["duraklar"]:
            st = Stop(s)
            self.stops[st.id] = st
        # Transfer ücretinde indirim uygulanmayacak.
        self.transferIndirimOrani = 0.3

    def merge_consecutive_steps(self, steps):
        if not steps or len(steps) < 2:
            return steps
        merged = []
        current = steps[0].copy()
        for i in range(1, len(steps)):
            nxt = steps[i]
            if nxt["mode"] == current["mode"] and current["mode"] in ["walk", "taksi"]:
                current["time"] += nxt["time"]
                current["distance"] += nxt["distance"]
                current["base_cost"] += nxt["base_cost"]
                current["final_cost"] += nxt["final_cost"]
                current["to"] = nxt["to"]
                current["discount_explanation"] += " + " + nxt["discount_explanation"]
            else:
                merged.append(current)
                current = nxt.copy()
        merged.append(current)
        return merged

    def rebuild_steps_with_latlon(self, steps, start_lat, start_lon, end_lat, end_lon):
        latlon_segments = []
        for stp in steps:
            if stp["from"] == "Başlangıç":
                from_lat, from_lon = (start_lat, start_lon)
            elif stp["from"] == "Varış":
                from_lat, from_lon = (end_lat, end_lon)
            else:
                fs = self.stops.get(stp["from"], None)
                if not fs:
                    continue
                from_lat, from_lon = (fs.lat, fs.lon)
            if stp["to"] == "Başlangıç":
                to_lat, to_lon = (start_lat, start_lon)
            elif stp["to"] == "Varış":
                to_lat, to_lon = (end_lat, end_lon)
            else:
                ts = self.stops.get(stp["to"], None)
                if not ts:
                    continue
                to_lat, to_lon = (ts.lat, ts.lon)
            latlon_segments.append({
                "color": stp["color"],
                "points": [(from_lat, from_lon), (to_lat, to_lon)]
            })
        return latlon_segments

    #----------------------------------------------------------------------
    # 1) Sadece Taksi (Hiç yürüyüş, direkt taksi)
    #----------------------------------------------------------------------
    def plan_sadece_taksi(self, start_lat, start_lon, dest_lat, dest_lon,
                          passenger_type, payment_type, special_day, start_time):
        if payment_type == "kentkart":
            return None
        dist = haversine(start_lat, start_lon, dest_lat, dest_lon)
        time_min = dist / AVERAGE_TAXI_SPEED
        base_c = self.taxi.calculate_cost(dist)
        final_c = base_c
        steps = [{
            "from": "Başlangıç",
            "to": "Varış",
            "mode": "taksi",
            "time": round(time_min, 1),
            "distance": round(dist, 2),
            "base_cost": round(base_c, 2),
            "final_cost": round(final_c, 2),
            "discount_explanation": "Sadece Taksi => tam",
            "color": MODE_COLORS["taksi"]
        }]
        merged = steps
        total_time = round(time_min, 1)
        total_dist = round(dist, 2)
        total_cost = round(final_c, 2)
        latlon_segments = self.rebuild_steps_with_latlon(merged, start_lat, start_lon, dest_lat, dest_lon)
        route = {
            "steps": merged,
            "total_time": total_time,
            "total_distance": total_dist,
            "total_cost": total_cost,
            "latlon_segments": latlon_segments
        }
        if start_time:
            arr = start_time + timedelta(minutes=total_time)
            route["arrival_time"] = arr.strftime("%d.%m.%Y %H:%M")
        return route

    #----------------------------------------------------------------------
    # 2) Sadece Otobüs (Yürüme + Otobüs BFS + Yürüme)
    #    Nakit ile otobüs rotası kullanılamaz.
    #----------------------------------------------------------------------
    def plan_sadece_otobus(self, start_lat, start_lon, dest_lat, dest_lon,
                           passenger_type, payment_type, special_day, start_time):
        if payment_type == "nakit":
            return None
        steps = []
        startStop, distStart = self.get_nearest_stop(start_lat, start_lon, "bus")
        if not startStop:
            return None
        walkA = distStart / AVERAGE_WALK_SPEED
        steps.append({
            "from": "Başlangıç",
            "to": startStop.id,
            "mode": "walk",
            "time": round(walkA, 1),
            "distance": round(distStart, 2),
            "base_cost": 0,
            "final_cost": 0,
            "discount_explanation": "Yürüme => ücretsiz",
            "color": MODE_COLORS["walk"]
        })
        endStop, distEnd = self.get_nearest_stop(dest_lat, dest_lon, "bus")
        if not endStop:
            return None
        busSteps = self.bus_bfs(startStop.id, endStop.id, passenger_type, payment_type, special_day)
        if not busSteps:
            return None
        steps.extend(busSteps)
        walkB = distEnd / AVERAGE_WALK_SPEED
        steps.append({
            "from": endStop.id,
            "to": "Varış",
            "mode": "walk",
            "time": round(walkB, 1),
            "distance": round(distEnd, 2),
            "base_cost": 0,
            "final_cost": 0,
            "discount_explanation": "Yürüme => ücretsiz",
            "color": MODE_COLORS["walk"]
        })
        merged = self.merge_consecutive_steps(steps)
        total_time = sum(s["time"] for s in merged)
        total_dist = sum(s["distance"] for s in merged)
        total_cost = sum(s["final_cost"] for s in merged)
        latlon_segments = self.rebuild_steps_with_latlon(merged, start_lat, start_lon, dest_lat, dest_lon)
        route = {
            "steps": merged,
            "total_time": round(total_time, 1),
            "total_distance": round(total_dist, 2),
            "total_cost": round(total_cost, 2),
            "latlon_segments": latlon_segments
        }
        if start_time:
            arr = start_time + timedelta(minutes=route["total_time"])
            route["arrival_time"] = arr.strftime("%d.%m.%Y %H:%M")
        return route

    #----------------------------------------------------------------------
    # 3) Sadece Tramvay:
    # Başlangıçtan en yakın tramvay durağına yürü, ardından saf tramvay BFS, sonrasında varışa en yakın tramvay durağından yürüyerek ulaş.
    # Nakit ile tramvay rotası kullanılamaz.
    #----------------------------------------------------------------------
    def plan_sadece_tramvay(self, start_lat, start_lon, dest_lat, dest_lon,
                            passenger_type, payment_type, special_day, start_time):
        # Nakit ödeme ile tramvay rotası hesaplanamaz.
        if payment_type == "nakit":
            return None
        steps = []
        # 1. Başlangıç → En Yakın Tramvay Durağı (örneğin, tram_sekapark)
        startTram, distA = self.get_nearest_stop(start_lat, start_lon, "tram")
        if not startTram:
            return None
        walkA = distA / AVERAGE_WALK_SPEED
        steps.append({
            "from": "Başlangıç",
            "to": startTram.id,
            "mode": "walk",
            "time": round(walkA, 1),
            "distance": round(distA, 2),
            "base_cost": 0,
            "final_cost": 0,
            "discount_explanation": "Yürüme => ücretsiz",
            "color": MODE_COLORS["walk"]
        })
        # 2. Tramvay seferi: Saf tramvay hattı üzerinden BFS (örneğin, tram_sekapark → tram_halkevi)
        # Eğer varış noktası tramvay hattı dışında ise; yine de, en yakın tramvay durağı kullanılır.
        endTram, distB = self.get_nearest_stop(dest_lat, dest_lon, "tram")
        if not endTram:
            return None
        tramSteps = self.tram_bfs(startTram.id, endTram.id, passenger_type, payment_type, special_day)
        if not tramSteps:
            return None
        steps.extend(tramSteps)
        # 3. Varış → En Yakın Tramvay Durağından Varışa Yürüme
        walkB = distB / AVERAGE_WALK_SPEED
        steps.append({
            "from": endTram.id,
            "to": "Varış",
            "mode": "walk",
            "time": round(walkB, 1),
            "distance": round(distB, 2),
            "base_cost": 0,
            "final_cost": 0,
            "discount_explanation": "Yürüme => ücretsiz",
            "color": MODE_COLORS["walk"]
        })
        merged = self.merge_consecutive_steps(steps)
        total_time = sum(s["time"] for s in merged)
        total_dist = sum(s["distance"] for s in merged)
        total_cost = sum(s["final_cost"] for s in merged)
        latlon_segments = self.rebuild_steps_with_latlon(merged, start_lat, start_lon, dest_lat, dest_lon)
        route = {
            "steps": merged,
            "total_time": round(total_time, 1),
            "total_distance": round(total_dist, 2),
            "total_cost": round(total_cost, 2),
            "latlon_segments": latlon_segments
        }
        if start_time:
            arr = start_time + timedelta(minutes=route["total_time"])
            route["arrival_time"] = arr.strftime("%d.%m.%Y %H:%M")
        return route


    #----------------------------------------------------------------------
    # 4) Otobüs + Tramvay:
    # Başlangıç ve varış segmentleri yürüyerek, arada stateful BFS (otobüs, tramvay, transfer)
    # En az 1 otobüs ve en az 1 tramvay kullanılmalı.
    #----------------------------------------------------------------------
    def plan_otobus_tramvay(self, start_lat, start_lon, dest_lat, dest_lon,
                            passenger_type, payment_type, special_day, start_time):
        if payment_type == "nakit":
            return None
        steps = []
        startStop, distStart = self.get_nearest_stop_any_bus_tram(start_lat, start_lon)
        if not startStop:
            return None
        steps.append({
            "from": "Başlangıç",
            "to": startStop.id,
            "mode": "walk",
            "time": round(distStart / AVERAGE_WALK_SPEED, 1),
            "distance": round(distStart, 2),
            "base_cost": 0,
            "final_cost": 0,
            "discount_explanation": "Yürüme => ücretsiz",
            "color": MODE_COLORS["walk"]
        })
        endStop, distEnd = self.get_nearest_stop_any_bus_tram(dest_lat, dest_lon)
        if not endStop:
            return None
        midSteps = self.stateful_bfs_bus_tram_transfer(
            startStop.id, endStop.id,
            passenger_type, payment_type, special_day,
            mustUseBus=True, mustUseTram=True
        )
        if not midSteps:
            return None
        steps.extend(midSteps)
        steps.append({
            "from": endStop.id,
            "to": "Varış",
            "mode": "walk",
            "time": round(distEnd / AVERAGE_WALK_SPEED, 1),
            "distance": round(distEnd, 2),
            "base_cost": 0,
            "final_cost": 0,
            "discount_explanation": "Yürüme => ücretsiz",
            "color": MODE_COLORS["walk"]
        })
        merged = self.merge_consecutive_steps(steps)
        total_time = sum(s["time"] for s in merged)
        total_dist = sum(s["distance"] for s in merged)
        total_cost = sum(s["final_cost"] for s in merged)
        latlon_segments = self.rebuild_steps_with_latlon(merged, start_lat, start_lon, dest_lat, dest_lon)
        route = {
            "steps": merged,
            "total_time": round(total_time, 1),
            "total_distance": round(total_dist, 2),
            "total_cost": round(total_cost, 2),
            "latlon_segments": latlon_segments
        }
        if start_time:
            arr = start_time + timedelta(minutes=route["total_time"])
            route["arrival_time"] = arr.strftime("%d.%m.%Y %H:%M")
        return route

    #----------------------------------------------------------------------
    # 5) Taksi + Otobüs/Tramvay:
    # Hiç yürüme; başlangıç ve varış segmentleri kesin taksiyle, arada BFS (otobüs/tramvay, transfer)
    # Nakit ve KentKart ile bu senaryo çalışmaz.
    #----------------------------------------------------------------------
    def plan_taksi_otobus_tramvay(self, start_lat, start_lon, dest_lat, dest_lon,
                                  passenger_type, payment_type, special_day, start_time):
        if payment_type in ["nakit", "kentkart"]:
            return None
        steps = []
        # Başlangıç segmenti: Taksi
        startStop, distStart = self.get_nearest_stop_any_bus_tram(start_lat, start_lon)
        if not startStop:
            return None
        tA = distStart / AVERAGE_TAXI_SPEED
        bcA = self.taxi.calculate_cost(distStart)
        steps.append({
            "from": "Başlangıç",
            "to": startStop.id,
            "mode": "taksi",
            "time": round(tA, 1),
            "distance": round(distStart, 2),
            "base_cost": round(bcA, 2),
            "final_cost": round(bcA, 2),
            "discount_explanation": "Taksi => tam",
            "color": MODE_COLORS["taksi"]
        })
        usedTaksi = True
        # BFS: Otobüs/Tramvay + transfer (hiç yürüme)
        endStop, distEnd = self.get_nearest_stop_any_bus_tram(dest_lat, dest_lon)
        if not endStop:
            return None
        midSteps = self.stateful_bfs_bus_tram_transfer(
            startStop.id, endStop.id,
            passenger_type, payment_type, special_day,
            mustUseBusOrTram=True
        )
        if not midSteps:
            return None
        if any(s["mode"] in ["bus", "tram"] for s in midSteps):
            usedBusOrTram = True
        else:
            usedBusOrTram = False
        steps.extend(midSteps)
        # Varış segmenti: Taksi
        tB = distEnd / AVERAGE_TAXI_SPEED
        bcB = self.taxi.calculate_cost(distEnd)
        steps.append({
            "from": endStop.id,
            "to": "Varış",
            "mode": "taksi",
            "time": round(tB, 1),
            "distance": round(distEnd, 2),
            "base_cost": round(bcB, 2),
            "final_cost": round(bcB, 2),
            "discount_explanation": "Taksi => tam",
            "color": MODE_COLORS["taksi"]
        })
        usedTaksi = True
        if not usedTaksi or not usedBusOrTram:
            return None
        merged = self.merge_consecutive_steps(steps)
        total_time = sum(s["time"] for s in merged)
        total_dist = sum(s["distance"] for s in merged)
        total_cost = sum(s["final_cost"] for s in merged)
        latlon_segments = self.rebuild_steps_with_latlon(merged, start_lat, start_lon, dest_lat, dest_lon)
        route = {
            "steps": merged,
            "total_time": round(total_time, 1),
            "total_distance": round(total_dist, 2),
            "total_cost": round(total_cost, 2),
            "latlon_segments": latlon_segments
        }
        if start_time:
            arr = start_time + timedelta(minutes=route["total_time"])
            route["arrival_time"] = arr.strftime("%d.%m.%Y %H:%M")
        return route

    #----------------------------------------------------------------------
    # Yardımcı BFS Fonksiyonları
    #----------------------------------------------------------------------
    def get_nearest_stop(self, lat, lon, mode_filter=None):
        best = None
        bestDist = math.inf
        for st in self.stops.values():
            if mode_filter and st.type != mode_filter:
                continue
            d = haversine(lat, lon, st.lat, st.lon)
            if d < bestDist:
                bestDist = d
                best = st
        return best, bestDist

    def get_nearest_stop_any_bus_tram(self, lat, lon):
        best = None
        bestDist = math.inf
        for st in self.stops.values():
            if st.type in ["bus", "tram"]:
                d = haversine(lat, lon, st.lat, st.lon)
                if d < bestDist:
                    bestDist = d
                    best = st
        return best, bestDist

    def bus_bfs(self, start_id, end_id, passenger_type, payment_type, special_day):
        from collections import deque
        visited = set()
        queue = deque()
        queue.append((start_id, []))
        visited.add(start_id)
        foundPath = None
        while queue:
            cur, path = queue.popleft()
            if cur == end_id:
                foundPath = path + [cur]
                break
            st = self.stops.get(cur)
            if not st or st.type != "bus":
                continue
            for e in st.nextStops:
                nxtId = e["stopId"]
                if nxtId not in visited:
                    visited.add(nxtId)
                    queue.append((nxtId, path + [cur]))
        if not foundPath:
            return None
        steps = []
        for i in range(len(foundPath) - 1):
            c = foundPath[i]
            n = foundPath[i + 1]
            eData = None
            for ed in self.stops[c].nextStops:
                if ed["stopId"] == n:
                    eData = ed
                    break
            if not eData:
                return None
            base_c = eData["ucret"]
            final_c = base_c
            explanation = "Otobüs => tam"
            if special_day:
                final_c = 0
                explanation = "Özel gün => ücretsiz (Bus)"
            elif payment_type == "kredi":
                explanation = "Kredi => indirim yok"
            else:
                disc = 0.0
                if passenger_type == "ogrenci":
                    disc = 0.5
                    explanation = "Otobüs (Öğrenci)"
                elif passenger_type == "65+":
                    disc = 0.3
                    explanation = "Otobüs (Yaşlı)"
                final_c = base_c * (1 - disc)
            steps.append({
                "from": c,
                "to": n,
                "mode": "bus",
                "time": eData["sure"],
                "distance": eData["mesafe"],
                "base_cost": round(base_c, 2),
                "final_cost": round(final_c, 2),
                "discount_explanation": explanation,
                "color": MODE_COLORS["bus"]
            })
        return steps

    def tram_bfs(self, start_id, end_id, passenger_type, payment_type, special_day):
        from collections import deque
        visited = set()
        queue = deque()
        queue.append((start_id, []))
        visited.add(start_id)
        foundPath = None
        while queue:
            cur, path = queue.popleft()
            if cur == end_id:
                foundPath = path + [cur]
                break
            st = self.stops.get(cur)
            if not st or st.type != "tram":
                continue
            for e in st.nextStops:
                nxtId = e["stopId"]
                if nxtId not in visited:
                    visited.add(nxtId)
                    queue.append((nxtId, path + [cur]))
        if not foundPath:
            return None
        steps = []
        for i in range(len(foundPath) - 1):
            c = foundPath[i]
            n = foundPath[i + 1]
            eData = None
            for ed in self.stops[c].nextStops:
                if ed["stopId"] == n:
                    eData = ed
                    break
            if not eData:
                return None
            base_c = eData["ucret"]
            final_c = base_c
            explanation = "Tramvay => tam"
            if special_day:
                final_c = 0
                explanation = "Özel gün => ücretsiz (Tram)"
            elif payment_type == "kredi":
                explanation = "Kredi => indirim yok"
            else:
                disc = 0.0
                if passenger_type == "ogrenci":
                    disc = 0.5
                    explanation = "Tramvay (Öğrenci)"
                elif passenger_type == "65+":
                    disc = 0.3
                    explanation = "Tramvay (Yaşlı)"
                final_c = base_c * (1 - disc)
            steps.append({
                "from": c,
                "to": n,
                "mode": "tram",
                "time": eData["sure"],
                "distance": eData["mesafe"],
                "base_cost": round(base_c, 2),
                "final_cost": round(final_c, 2),
                "discount_explanation": explanation,
                "color": MODE_COLORS["tram"]
            })
        return steps

    #----------------------------------------------------------------------
    # Stateful BFS for bus+tram+transfer with transfer discount flag.
    # Eğer transfer kenarı kullanılırsa, sonraki boarding adımında (bus veya tram) ekstra indirim
    # uygulanır. Ancak, transfer ücretinde hiçbir indirim uygulanmayacak.
    #----------------------------------------------------------------------
    def stateful_bfs_bus_tram_transfer(self, start_id, end_id,
                                       passenger_type, payment_type, special_day,
                                       mustUseBus=False, mustUseTram=False,
                                       mustUseBusOrTram=False):
        from collections import deque
        # State: (node, last_mode, usedBus, usedTram, transfer_pending)
        start_state = (start_id, None, False, False, False)
        visited = {start_state: []}
        queue = deque()
        queue.append(start_state)
        while queue:
            (cur, last_mode, usedBus, usedTram, transfer_pending) = queue.popleft()
            pathEdges = visited[(cur, last_mode, usedBus, usedTram, transfer_pending)]
            if cur == end_id:
                if mustUseBus and not usedBus:
                    continue
                if mustUseTram and not usedTram:
                    continue
                if mustUseBusOrTram and (not usedBus and not usedTram):
                    continue
                return pathEdges
            st = self.stops.get(cur, None)
            if not st:
                continue
            edges = []
            if st.type == "bus":
                for e in st.nextStops:
                    edges.append((e["stopId"], "bus", e))
            if st.type == "tram":
                for e in st.nextStops:
                    edges.append((e["stopId"], "tram", e))
            if st.transfer and last_mode in ["bus", "tram"]:
                edges.append((st.transfer["transferStopId"], "transfer", st.transfer))
            for (nxtId, edgeMode, eData) in edges:
                new_usedBus = usedBus
                new_usedTram = usedTram
                new_transfer_pending = False
                if edgeMode == "bus":
                    new_usedBus = True
                    base_c = eData["ucret"]
                    # Transfer ücretinde indirim uygulanmayacak; eğer transfer_pending varsa, sadece 
                    # ödeme türü kredi ise değişiklik yok, aksi halde ekstra indirim uygulanmaz.
                    if transfer_pending and payment_type == "kentkart":
                        final_c = base_c  # ekstra indirim iptal!
                        explanation = "Otobüs (Transfer: ek indirim uygulanmaz)"
                    else:
                        final_c = base_c
                        if special_day:
                            final_c = 0
                            explanation = "Özel gün => ücretsiz (Bus)"
                        elif payment_type == "kredi":
                            explanation = "Kredi => indirim yok"
                        else:
                            disc = 0.0
                            if passenger_type == "ogrenci":
                                disc = 0.5
                                explanation = "Otobüs (Öğrenci)"
                            elif passenger_type == "65+":
                                disc = 0.3
                                explanation = "Otobüs (Yaşlı)"
                            final_c = base_c * (1 - disc)
                    new_transfer_pending = False
                elif edgeMode == "tram":
                    new_usedTram = True
                    base_c = eData["ucret"]
                    if transfer_pending and payment_type == "kentkart":
                        final_c = base_c  # ekstra indirim iptal!
                        explanation = "Tramvay (Transfer: ek indirim uygulanmaz)"
                    else:
                        final_c = base_c
                        if special_day:
                            final_c = 0
                            explanation = "Özel gün => ücretsiz (Tram)"
                        elif payment_type == "kredi":
                            explanation = "Kredi => indirim yok"
                        else:
                            disc = 0.0
                            if passenger_type == "ogrenci":
                                disc = 0.5
                                explanation = "Tramvay (Öğrenci)"
                            elif passenger_type == "65+":
                                disc = 0.3
                                explanation = "Tramvay (Yaşlı)"
                            final_c = base_c * (1 - disc)
                    new_transfer_pending = False
                elif edgeMode == "transfer":
                    # Transfer ücretinde hiçbir indirim uygulanmayacak.
                    base_c = eData.get("transferUcret", 0)
                    final_c = base_c
                    explanation = f"Transfer => {base_c} TL"
                    new_transfer_pending = True  # Sonraki boarding adımında bildirilsin.
                new_edge = {
                    "from": cur,
                    "to": nxtId,
                    "mode": edgeMode,
                    "time": eData.get("sure", 0),
                    "distance": eData.get("mesafe", 0),
                    "base_cost": round(eData.get("ucret", base_c), 2) if edgeMode != "transfer" else round(eData.get("transferUcret", base_c), 2),
                    "final_cost": round(final_c, 2),
                    "discount_explanation": explanation,
                    "color": MODE_COLORS.get(edgeMode, "purple" if edgeMode=="transfer" else "black")
                }
                new_state = (nxtId, edgeMode, new_usedBus, new_usedTram, new_transfer_pending)
                new_path = pathEdges + [new_edge]
                if new_state not in visited:
                    visited[new_state] = new_path
                    queue.append(new_state)
        return None

    #----------------------------------------------------------------------
    # get_alternative_routes: Tüm senaryoları hesaplar ve en uygun rotayı seçer.
    #----------------------------------------------------------------------
    def get_alternative_routes(self, start_lat, start_lon, end_lat, end_lon,
                               passenger_type="genel", payment_type="nakit",
                               start_time=None, special_day=False):
        r_sadece_taksi = self.plan_sadece_taksi(start_lat, start_lon, end_lat, end_lon,
                                                 passenger_type, payment_type, special_day, start_time)
        r_sadece_otobus = self.plan_sadece_otobus(start_lat, start_lon, end_lat, end_lon,
                                                   passenger_type, payment_type, special_day, start_time)
        r_sadece_tramvay = self.plan_sadece_tramvay(start_lat, start_lon, end_lat, end_lon,
                                                    passenger_type, payment_type, special_day, start_time)
        r_otobus_tramvay = self.plan_otobus_tramvay(start_lat, start_lon, end_lat, end_lon,
                                                    passenger_type, payment_type, special_day, start_time)
        r_taksi_otobus_tramvay = self.plan_taksi_otobus_tramvay(start_lat, start_lon, end_lat, end_lon,
                                                               passenger_type, payment_type, special_day, start_time)
        def pick_best(routes_list):
            best = None
            for rr in routes_list:
                if rr:
                    if not best:
                        best = rr
                    else:
                        if rr["total_cost"] < best["total_cost"]:
                            best = rr
                        elif abs(rr["total_cost"] - best["total_cost"]) < 1e-9:
                            if rr["total_time"] < best["total_time"]:
                                best = rr
            return best
        best_route = pick_best([
            r_sadece_taksi,
            r_sadece_otobus,
            r_sadece_tramvay,
            r_otobus_tramvay,
            r_taksi_otobus_tramvay
        ])
        routes = {
            "rotaniz": best_route,
            "sadece_taksi": r_sadece_taksi,
            "sadece_otobus": r_sadece_otobus,
            "sadece_tramvay": r_sadece_tramvay,
            "otobus_tramvay": r_otobus_tramvay,
            "taksi_otobus_tramvay": r_taksi_otobus_tramvay
        }
        return routes
