from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class PaymentMethodOption:
    """Represents a selectable payment method for a GEO."""

    key: str
    title: str
    markup_eur: int = 0


_METHODS_BY_COUNTRY: Dict[str, List[PaymentMethodOption]] = {
    "IN": [
        PaymentMethodOption("upi", "UPI"),
        PaymentMethodOption("phonepe", "PhonePe"),
        PaymentMethodOption("paytm", "PayTM"),
        PaymentMethodOption("google_pay", "Google Pay"),
        PaymentMethodOption("amazon_pay", "Amazon Pay"),
    ],
    "BD": [
        PaymentMethodOption("bkash", "bKash"),
        PaymentMethodOption("nagad", "Nagad"),
        PaymentMethodOption("rocket", "Rocket"),
        PaymentMethodOption("upay", "Upay"),
    ],
    "PK": [
        PaymentMethodOption("jazzcash", "JazzCash"),
        PaymentMethodOption("easypaisa", "Easypaisa"),
        PaymentMethodOption("nayapay", "Nayapay"),
    ],
    "ID": [
        PaymentMethodOption("gopay", "GoPay"),
        PaymentMethodOption("ovo", "OVO"),
        PaymentMethodOption("dana", "DANA"),
        PaymentMethodOption("linkaja", "LinkAja"),
        PaymentMethodOption("shopeepay", "ShopeePay"),
        PaymentMethodOption("grabpay", "GrabPay"),
        PaymentMethodOption("boost", "Boost"),
        PaymentMethodOption("qris", "QRIS"),
    ],
    "MY": [
        PaymentMethodOption("touch_n_go", "Touch ’n Go"),
        PaymentMethodOption("boost", "Boost"),
        PaymentMethodOption("grabpay", "GrabPay"),
        PaymentMethodOption("shopeepay", "ShopeePay"),
        PaymentMethodOption("duitnow", "DuitNow"),
    ],
    "TH": [
        PaymentMethodOption("promptpay", "PromptPay"),
        PaymentMethodOption("truemoney", "TrueMoney"),
    ],
    "PH": [
        PaymentMethodOption("gcash", "GCash"),
        PaymentMethodOption("paymaya", "PayMaya"),
        PaymentMethodOption("grabpay", "GrabPay"),
        PaymentMethodOption("shopeepay", "ShopeePay"),
    ],
    "EG": [
        PaymentMethodOption("vodafone_cash", "Vodafone Cash"),
        PaymentMethodOption("etisalat_cash", "Etisalat Cash"),
        PaymentMethodOption("orange_money", "Orange Money"),
        PaymentMethodOption("fawry", "Fawry", markup_eur=15),
        PaymentMethodOption("meeza", "Meeza"),
    ],
    "KZ": [
        PaymentMethodOption("kaspi_pay", "Kaspi Pay"),
        PaymentMethodOption("bank_transfer", "Bank Transfer"),
    ],
    "UZ": [
        PaymentMethodOption("payme", "Payme"),
        PaymentMethodOption("uzcard", "UzCard"),
        PaymentMethodOption("humo", "Humo"),
    ],
    "CI": [
        PaymentMethodOption("orange_money", "Orange Money"),
        PaymentMethodOption("mtn_money", "MTN Money"),
        PaymentMethodOption("moov_money", "Moov Money"),
        PaymentMethodOption("wave", "Wave"),
    ],
    "AR": [
        PaymentMethodOption("mercado_pago", "Mercado Pago"),
        PaymentMethodOption("bank_transfer", "Bank Transfer"),
    ],
}


def get_methods_for_country(geo: str) -> List[PaymentMethodOption]:
    return list(_METHODS_BY_COUNTRY.get(geo.upper(), ()))


def get_method_by_key(geo: str, key: str) -> Optional[PaymentMethodOption]:
    key = key.lower()
    for option in get_methods_for_country(geo):
        if option.key == key:
            return option
    return None


def iter_supported_geos() -> Iterable[str]:
    return _METHODS_BY_COUNTRY.keys()
