from __future__ import annotations

from typing import Iterable, List, Sequence

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from payment_qa_bot.texts.catalog import TEXTS


def _button(text: str) -> KeyboardButton:
    return KeyboardButton(text=text)


def back_cancel_keyboard(language: str, extra_rows: Sequence[Sequence[str]] | None = None) -> ReplyKeyboardMarkup:
    rows: List[List[KeyboardButton]] = []
    if extra_rows:
        for row in extra_rows:
            rows.append([_button(text) for text in row])
    rows.append(
        [
            _button(TEXTS.button("wizard.back", language)),
            _button(TEXTS.button("wizard.cancel", language)),
        ]
    )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def yes_no_keyboard(language: str) -> ReplyKeyboardMarkup:
    return back_cancel_keyboard(
        language,
        extra_rows=[[TEXTS.button("wizard.yes", language), TEXTS.button("wizard.no", language)]],
    )


def skip_keyboard(language: str) -> ReplyKeyboardMarkup:
    return back_cancel_keyboard(
        language,
        extra_rows=[[TEXTS.button("wizard.skip", language)]],
    )


def confirmation_keyboard(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [_button(TEXTS.button("confirmation.confirm", language))],
            [_button(TEXTS.button("confirmation.back", language))],
            [_button(TEXTS.button("confirmation.add_order", language))],
        ],
        resize_keyboard=True,
    )


def payment_keyboard(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [_button(TEXTS.button("payment.button.paid", language))],
            [_button(TEXTS.button("payment.button.help", language))],
            [_button(TEXTS.button("payment.button.support", language))],
            [_button(TEXTS.button("wizard.cancel", language))],
        ],
        resize_keyboard=True,
    )
