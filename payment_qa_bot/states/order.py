from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    GEO = State()
    METHOD = State()
    PAYOUT = State()
    COMMENTS = State()
    REVIEW = State()
    CONFIRM = State()
