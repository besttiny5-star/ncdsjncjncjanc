from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PaymentMethodInfo:
    name: str
    markup_eur: int = 0


PAYMENT_METHODS: Dict[str, List[PaymentMethodInfo]] = {
    "IN": [
        PaymentMethodInfo("UPI"),
        PaymentMethodInfo("PhonePe"),
        PaymentMethodInfo("PayTM"),
        PaymentMethodInfo("Google Pay"),
        PaymentMethodInfo("Amazon Pay"),
    ],
    "BD": [
        PaymentMethodInfo("bKash"),
        PaymentMethodInfo("Nagad"),
        PaymentMethodInfo("Rocket"),
        PaymentMethodInfo("Upay"),
    ],
    "PK": [
        PaymentMethodInfo("JazzCash"),
        PaymentMethodInfo("Easypaisa"),
        PaymentMethodInfo("Nayapay"),
    ],
    "ID": [
        PaymentMethodInfo("GoPay"),
        PaymentMethodInfo("OVO"),
        PaymentMethodInfo("DANA"),
        PaymentMethodInfo("LinkAja"),
        PaymentMethodInfo("ShopeePay"),
        PaymentMethodInfo("GrabPay"),
        PaymentMethodInfo("Boost"),
        PaymentMethodInfo("QRIS"),
    ],
    "MY": [
        PaymentMethodInfo("Touch ’n Go"),
        PaymentMethodInfo("Boost"),
        PaymentMethodInfo("GrabPay"),
        PaymentMethodInfo("ShopeePay"),
        PaymentMethodInfo("DuitNow"),
    ],
    "TH": [
        PaymentMethodInfo("PromptPay"),
        PaymentMethodInfo("TrueMoney"),
    ],
    "PH": [
        PaymentMethodInfo("GCash"),
        PaymentMethodInfo("PayMaya"),
        PaymentMethodInfo("GrabPay"),
        PaymentMethodInfo("ShopeePay"),
    ],
    "EG": [
        PaymentMethodInfo("Vodafone Cash"),
        PaymentMethodInfo("Etisalat Cash"),
        PaymentMethodInfo("Orange Money"),
        PaymentMethodInfo("Fawry"),
        PaymentMethodInfo("Meeza"),
    ],
    "KZ": [
        PaymentMethodInfo("Kaspi Pay"),
        PaymentMethodInfo("Bank Transfer"),
    ],
    "UZ": [
        PaymentMethodInfo("Payme"),
        PaymentMethodInfo("UzCard"),
        PaymentMethodInfo("Humo"),
    ],
    "CI": [
        PaymentMethodInfo("Orange Money"),
        PaymentMethodInfo("MTN Money"),
        PaymentMethodInfo("Moov Money"),
        PaymentMethodInfo("Wave"),
    ],
    "AR": [
        PaymentMethodInfo("Mercado Pago"),
        PaymentMethodInfo("Bank Transfer"),
    ],
}


def get_payment_methods(geo: str) -> List[PaymentMethodInfo]:
    return PAYMENT_METHODS.get(geo.upper(), [])
