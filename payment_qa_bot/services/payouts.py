from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True, slots=True)
class PayoutOption:
    key: str
    surcharge: int
    withdraw_required: bool
    kyc_required: bool


PAYOUT_OPTIONS: List[PayoutOption] = [
    PayoutOption(key="payout.option.none", surcharge=0, withdraw_required=False, kyc_required=False),
    PayoutOption(key="payout.option.withdraw", surcharge=10, withdraw_required=True, kyc_required=False),
    PayoutOption(key="payout.option.kyc", surcharge=25, withdraw_required=True, kyc_required=True),
]


_OPTIONS_BY_KEY: Dict[str, PayoutOption] = {option.key: option for option in PAYOUT_OPTIONS}


def iter_payout_options() -> Iterable[PayoutOption]:
    return list(PAYOUT_OPTIONS)


def get_payout_option(key: Optional[str]) -> Optional[PayoutOption]:
    if not key:
        return None
    return _OPTIONS_BY_KEY.get(key)
