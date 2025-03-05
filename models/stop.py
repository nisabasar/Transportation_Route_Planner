# models/stop.py
class Stop:
    def __init__(self, stop_data):
        self.id = stop_data["id"]
        self.name = stop_data["name"]
        self.type = stop_data["type"]
        self.lat = stop_data["lat"]
        self.lon = stop_data["lon"]
        self.sonDurak = stop_data["sonDurak"]
        self.nextStops = stop_data.get("nextStops", [])
        self.transfer = stop_data.get("transfer", None)

    def __repr__(self):
        return f"<Stop {self.id}: {self.name}>"
