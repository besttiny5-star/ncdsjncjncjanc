from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class PayoutOption:
    key: str
    title: str
    description: str
    markup_eur: int
    withdraw_required: bool
    kyc_required: bool


_PAYOUT_OPTIONS: Dict[str, PayoutOption] = {
    "none": PayoutOption(
        key="none",
        title="No payout needed (0 €)",
        description="",
        markup_eur=0,
        withdraw_required=False,
        kyc_required=False,
    ),
    "withdraw": PayoutOption(
        key="withdraw",
        title="Need payout verification (+10 €)",
        description="Requires account with withdrawal capability.",
        markup_eur=10,
        withdraw_required=True,
        kyc_required=False,
    ),
    "kyc": PayoutOption(
        key="kyc",
        title="Need full KYC verification (+25 €)",
        description="Requires tester’s personal data for KYC.",
        markup_eur=25,
        withdraw_required=True,
        kyc_required=True,
    ),
}


def iter_payout_options() -> Iterable[PayoutOption]:
    return _PAYOUT_OPTIONS.values()


def get_payout_option(key: str) -> Optional[PayoutOption]:
    return _PAYOUT_OPTIONS.get(key)
