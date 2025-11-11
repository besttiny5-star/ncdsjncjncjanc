from __future__ import annotations

from dataclasses import dataclass

BASE_PRICE_PER_TEST = 85


@dataclass(slots=True)
class PriceBreakdown:
    tests_count: int
    base_total: int
    method_markup_total: int
    payout_total: int

    @property
    def total(self) -> int:
        return self.base_total + self.method_markup_total + self.payout_total


def calculate_price(tests_count: int, method_markup: int, payout_fee: int) -> PriceBreakdown:
    if tests_count < 1:
        raise ValueError("tests_count must be >= 1")
    base_total = tests_count * BASE_PRICE_PER_TEST
    method_markup_total = max(0, int(method_markup))
    payout_total = max(0, int(payout_fee))
    return PriceBreakdown(
        tests_count=tests_count,
        base_total=base_total,
        method_markup_total=method_markup_total,
        payout_total=payout_total,
    )


def format_eur(amount: int) -> str:
    return f"€{amount}"
