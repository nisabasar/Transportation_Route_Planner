# models/passenger.py
from abc import ABC, abstractmethod

class Passenger(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def get_discount_rate(self):
        pass

class Genel(Passenger):
    def __init__(self):
        super().__init__("Genel")

    def get_discount_rate(self):
        return 0.0

class Ogrenci(Passenger):
    def __init__(self):
        super().__init__("Öğrenci")

    def get_discount_rate(self):
        return 0.5  # %50 indirim

class Yasli(Passenger):
    def __init__(self):
        super().__init__("65+")
        
    def get_discount_rate(self):
        return 0.3  # Örneğin %30 indirim
