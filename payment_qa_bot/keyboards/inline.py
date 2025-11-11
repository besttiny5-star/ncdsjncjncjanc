from __future__ import annotations

from typing import Iterable, List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _build_rows(buttons: Iterable[InlineKeyboardButton], width: int = 2) -> List[List[InlineKeyboardButton]]:
    row: List[InlineKeyboardButton] = []
    rows: List[List[InlineKeyboardButton]] = []
    for button in buttons:
        row.append(button)
        if len(row) >= width:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def payment_methods_keyboard(
    geo: str,
    methods: List[tuple[str, str]],
    *,
    include_extra_button: bool = True,
) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=title, callback_data=f"m:sel:{geo}:{key}") for key, title in methods]
    rows = _build_rows(buttons, width=2)
    if include_extra_button:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➕ Create additional order (another method)",
                    callback_data=f"m:add:{geo}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="m:back"), InlineKeyboardButton(text="❌ Cancel", callback_data="m:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payout_options_keyboard(
    options: Iterable[tuple[str, str, Optional[str]]],
    *,
    selected: Optional[str] = None,
) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for key, title, _ in options:
        label = title
        if selected == key:
            label = f"✅ {label}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"p:sel:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="p:back"), InlineKeyboardButton(text="❌ Cancel", callback_data="p:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
