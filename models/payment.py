# models/payment.py
from abc import ABC, abstractmethod

class Payment(ABC):
    @abstractmethod
    def process_payment(self, amount):
        pass

class Nakit(Payment):
    def process_payment(self, amount):
        return f"Nakit ödemeden {amount} TL tahsil edildi."

class KrediKarti(Payment):
    def process_payment(self, amount):
        return f"Kredi kartından {amount} TL ödeniyor."

class KentKart(Payment):
    def process_payment(self, amount):
        return f"KentKart ile {amount} TL ödeniyor."
