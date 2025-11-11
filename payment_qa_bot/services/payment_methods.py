from __future__ import annotations

from typing import Dict, List

PAYMENT_METHODS: Dict[str, List[str]] = {
    "IN": ["UPI", "PhonePe", "PayTM", "Google Pay", "Amazon Pay"],
    "BD": ["bKash", "Nagad", "Rocket", "Upay"],
    "PK": ["JazzCash", "Easypaisa", "Nayapay"],
    "ID": ["GoPay", "OVO", "DANA", "LinkAja", "ShopeePay", "GrabPay", "Boost", "QRIS"],
    "MY": ["Touch 'n Go", "Boost", "GrabPay", "ShopeePay", "DuitNow"],
    "TH": ["PromptPay", "TrueMoney"],
    "PH": ["GCash", "PayMaya", "GrabPay", "ShopeePay"],
    "EG": ["Vodafone Cash", "Etisalat Cash", "Orange Money", "Fawry", "Meeza"],
    "KZ": ["Kaspi Pay", "Bank Transfer"],
    "UZ": ["Payme", "UzCard", "Humo"],
    "CI": ["Orange Money", "MTN Money", "Moov Money", "Wave"],
    "AR": ["Mercado Pago", "Bank Transfer"],
}


def get_methods_for_geo(geo: str | None) -> List[str]:
    if not geo:
        return []
    return PAYMENT_METHODS.get(geo.upper(), [])
