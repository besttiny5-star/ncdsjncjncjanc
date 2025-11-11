from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    GEO = State()
    METHOD = State()
    TESTS = State()
    PAYOUT = State()
    COMMENTS = State()
    SITE_URL = State()
    CREDS_LOGIN = State()
    CREDS_PASS = State()
    CONFIRM = State()
    PAYMENT = State()
    CHECK_UPLOAD = State()
