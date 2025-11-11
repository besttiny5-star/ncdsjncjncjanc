from __future__ import annotations

from dataclasses import dataclass

BASE_PRICE_PER_ORDER = 85


@dataclass(slots=True)
class PriceBreakdown:
    base_total: int
    method_markup: int
    payout_markup: int

    @property
    def total(self) -> int:
        return self.base_total + self.method_markup + self.payout_markup


def calculate_price(
    *,
    method_markup: int = 0,
    payout_markup: int = 0,
    base_price: int = BASE_PRICE_PER_ORDER,
) -> PriceBreakdown:
    if base_price < 0:
        raise ValueError("base_price must be >= 0")
    return PriceBreakdown(
        base_total=base_price,
        method_markup=max(method_markup, 0),
        payout_markup=max(payout_markup, 0),
    )


def format_eur(amount: int) -> str:
    return f"€{amount}"
