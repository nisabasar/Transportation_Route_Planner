# utils/distance_strategy.py
from abc import ABC, abstractmethod
import math

class DistanceStrategy(ABC):
    """
    Strategy Pattern için mesafe hesaplama arayüzü.
    Farklı mesafe algoritmaları (Haversine, Euclidean, Manhattan vb.) eklenebilir.
    """
    @abstractmethod
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        pass

class HaversineStrategy(DistanceStrategy):
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 6371.0  # Dünya yarıçapı (km)
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance

class EuclideanStrategy(DistanceStrategy):
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Basit Öklid mesafesi (coğrafi koordinatlar için tam uygun değil ama örnek).
        """
        return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111  # kabaca dönüştürme
