from __future__ import annotations

from typing import Iterable, List

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from payment_qa_bot.services.geo import format_country
from payment_qa_bot.texts.catalog import TEXTS


def geo_keyboard(codes: Iterable[str], language: str) -> ReplyKeyboardMarkup:
    buttons: List[List[KeyboardButton]] = []
    row: List[KeyboardButton] = []
    for code in codes:
        row.append(KeyboardButton(text=format_country(code)))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(
        [
            KeyboardButton(text=TEXTS.button("wizard.cancel", language)),
        ]
    )
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
