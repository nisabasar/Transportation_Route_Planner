# factories.py
from models.payment import Nakit, KrediKarti, KentKart

class PaymentFactory:
    @staticmethod
    def create_payment(payment_type, amount):
        if payment_type == "kredi":
            return KrediKarti(amount)
        elif payment_type == "kentkart":
            return KentKart(amount)
        else:
            return Nakit(amount)
