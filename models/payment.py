# models/payment.py
from abc import ABC, abstractmethod

class Payment(ABC):
    @abstractmethod
    def pay(self, amount):
        pass

class Nakit(Payment):
    def __init__(self, cash_amount):
        self.cash_amount = cash_amount

    def pay(self, amount):
        if self.cash_amount >= amount:
            self.cash_amount -= amount
            return True, f"Nakit ile {round(amount, 2)} TL ödendi. Kalan bakiye: {round(self.cash_amount, 2)} TL"
        else:
            return False, "Yetersiz nakit."

class KrediKarti(Payment):
    def __init__(self, credit_limit):
        self.credit_limit = credit_limit

    def pay(self, amount):
        if self.credit_limit >= amount:
            self.credit_limit -= amount
            return True, f"Kredi kartından {round(amount, 2)} TL ödendi. Kalan limit: {round(self.credit_limit, 2)} TL"
        else:
            return False, "Kredi kartı limiti yetersiz."

class KentKart(Payment):
    def __init__(self, kentkart_balance):
        self.kentkart_balance = kentkart_balance

    def pay(self, amount):
        if self.kentkart_balance >= amount:
            self.kentkart_balance -= amount
            return True, f"KentKart ile {round(amount, 2)} TL ödendi. Kalan bakiye: {round(self.kentkart_balance, 2)} TL"
        else:
            return False, "KentKart bakiyesi yetersiz."
