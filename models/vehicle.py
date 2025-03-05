# models/vehicle.py
from abc import ABC, abstractmethod

class Vehicle(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def calculate_cost(self, distance):
        pass

class Bus(Vehicle):
    def __init__(self):
        super().__init__("Otobüs")

    def calculate_cost(self, distance):
        # Otobüs ücretleri veri seti üzerinden sağlanabilir; burada basit hesaplama yapılmamıştır.
        return None

class Tram(Vehicle):
    def __init__(self):
        super().__init__("Tramvay")

    def calculate_cost(self, distance):
        return None

class Taxi(Vehicle):
    def __init__(self, opening_fee, cost_per_km):
        super().__init__("Taksi")
        self.opening_fee = opening_fee
        self.cost_per_km = cost_per_km

    def calculate_cost(self, distance):
        return self.opening_fee + (self.cost_per_km * distance)
