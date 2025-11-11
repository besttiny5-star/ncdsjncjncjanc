from __future__ import annotations

from dataclasses import dataclass

BASE_PRICE_PER_TEST = 85
KYC_SURCHARGE = 45


@dataclass(slots=True)
class PriceBreakdown:
    tests_count: int
    base_total: int
    kyc_required: bool
    kyc_total: int

    @property
    def total(self) -> int:
        return self.base_total + self.kyc_total


def calculate_price(tests_count: int, kyc_required: bool) -> PriceBreakdown:
    if tests_count < 1:
        raise ValueError("tests_count must be >= 1")
    base_total = tests_count * BASE_PRICE_PER_TEST
    kyc_total = KYC_SURCHARGE if kyc_required else 0
    return PriceBreakdown(
        tests_count=tests_count,
        base_total=base_total,
        kyc_required=kyc_required,
        kyc_total=kyc_total,
    )


def format_eur(amount: int) -> str:
    return f"€{amount}"
