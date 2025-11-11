from __future__ import annotations

from dataclasses import dataclass

BASE_PRICE_PER_TEST = 85


@dataclass(slots=True)
class PriceBreakdown:
    tests_count: int
    base_total: int
    payout_surcharge: int

    @property
    def total(self) -> int:
        return self.base_total + self.payout_surcharge


def calculate_price(tests_count: int, payout_surcharge: int) -> PriceBreakdown:
    if tests_count < 1:
        raise ValueError("tests_count must be >= 1")
    if payout_surcharge < 0:
        raise ValueError("payout_surcharge must be >= 0")
    base_total = tests_count * BASE_PRICE_PER_TEST
    return PriceBreakdown(
        tests_count=tests_count,
        base_total=base_total,
        payout_surcharge=payout_surcharge,
    )


def format_eur(amount: int) -> str:
    return f"€{amount}"
