from __future__ import annotations

from typing import List, Sequence

from aiogram.types import ReplyKeyboardMarkup

from payment_qa_bot.keyboards.common import back_cancel_keyboard


def _chunk_rows(items: Sequence[str], per_row: int) -> List[List[str]]:
    rows: List[List[str]] = []
    row: List[str] = []
    for item in items:
        row.append(item)
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def methods_keyboard(methods: Sequence[str], language: str) -> ReplyKeyboardMarkup:
    if not methods:
        return back_cancel_keyboard(language)
    return back_cancel_keyboard(language, extra_rows=_chunk_rows(methods, 2))


def payout_keyboard(options: Sequence[str], language: str) -> ReplyKeyboardMarkup:
    if not options:
        return back_cancel_keyboard(language)
    rows = [[option] for option in options]
    return back_cancel_keyboard(language, extra_rows=rows)
