from __future__ import annotations

from dataclasses import dataclass

BASE_ORDER_PRICE = 85
PAYOUT_MARKUPS = {
    "none": 0,
    "withdraw": 10,
    "kyc": 25,
}


@dataclass(slots=True)
class PriceBreakdown:
    base_price: int
    payout_option: str
    payout_markup: int
    method_markup: int

    @property
    def total(self) -> int:
        return self.base_price + self.payout_markup + self.method_markup


def calculate_price(payout_option: str, method_markup: int) -> PriceBreakdown:
    markup = PAYOUT_MARKUPS.get(payout_option, 0)
    return PriceBreakdown(
        base_price=BASE_ORDER_PRICE,
        payout_option=payout_option,
        payout_markup=markup,
        method_markup=method_markup,
    )


def format_eur(amount: int) -> str:
    return f"€{amount}"
