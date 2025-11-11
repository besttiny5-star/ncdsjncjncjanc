from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class PayoutOption:
    option_id: str
    title_en: str
    description_en: str
    title_ru: str
    description_ru: str
    fee_eur: int
    withdraw_required: bool
    kyc_required: bool

    def title(self, language: str) -> str:
        if language == "ru":
            return self.title_ru
        return self.title_en

    def description(self, language: str) -> str:
        if language == "ru":
            return self.description_ru
        return self.description_en


PAYOUT_OPTIONS: Iterable[PayoutOption] = (
    PayoutOption(
        option_id="none",
        title_en="No payout needed (0 €)",
        description_en="",
        title_ru="Без вывода средств (0 €)",
        description_ru="",
        fee_eur=0,
        withdraw_required=False,
        kyc_required=False,
    ),
    PayoutOption(
        option_id="payout_check",
        title_en="Need payout verification (+10 €)",
        description_en="Requires account with withdrawal capability.",
        title_ru="Нужно подтвердить вывод (+10 €)",
        description_ru="Требуется аккаунт с возможностью вывода средств.",
        fee_eur=10,
        withdraw_required=True,
        kyc_required=False,
    ),
    PayoutOption(
        option_id="full_kyc",
        title_en="Need full KYC verification (+25 €)",
        description_en="Requires tester’s personal data for KYC.",
        title_ru="Нужна полная верификация KYC (+25 €)",
        description_ru="Требуются персональные данные тестера для KYC.",
        fee_eur=25,
        withdraw_required=True,
        kyc_required=True,
    ),
)


def get_payout_option(option_id: str) -> Optional[PayoutOption]:
    for option in PAYOUT_OPTIONS:
        if option.option_id == option_id:
            return option
    return None
