from __future__ import annotations

from typing import List, Optional, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _inline_button(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback)


def payment_methods_keyboard(
    options: Sequence[tuple[str, str]],
    *,
    additional_text: Optional[str],
    cancel_text: str,
) -> InlineKeyboardMarkup:
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for key, label in options:
        row.append(_inline_button(label, f"method:{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    controls: List[InlineKeyboardButton] = [_inline_button(cancel_text, "method:cancel")]
    if additional_text:
        controls.insert(0, _inline_button(additional_text, "method:add"))
    buttons.append(controls)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payout_options_keyboard(
    options: Sequence[tuple[str, str]],
    *,
    back_text: Optional[str],
    cancel_text: str,
) -> InlineKeyboardMarkup:
    buttons: List[List[InlineKeyboardButton]] = []
    for key, label in options:
        buttons.append([_inline_button(label, f"payout:{key}")])
    controls: List[InlineKeyboardButton] = [_inline_button(cancel_text, "payout:cancel")]
    if back_text:
        controls.insert(0, _inline_button(back_text, "payout:back"))
    buttons.append(controls)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def review_keyboard(
    *,
    confirm_text: str,
    back_text: str,
    additional_text: str,
    cancel_text: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_inline_button(confirm_text, "review:confirm")],
            [_inline_button(back_text, "review:back")],
            [_inline_button(additional_text, "review:add")],
            [_inline_button(cancel_text, "review:cancel")],
        ]
    )


def order_created_keyboard(
    *,
    create_text: str,
    view_text: str,
    done_text: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_inline_button(create_text, "final:create")],
            [_inline_button(view_text, "final:view")],
            [_inline_button(done_text, "final:done")],
        ]
    )
