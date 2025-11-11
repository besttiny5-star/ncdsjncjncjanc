from aiogram.types import ReplyKeyboardMarkup

from payment_qa_bot.keyboards.common import back_cancel_keyboard


def tests_keyboard(language: str) -> ReplyKeyboardMarkup:
    rows = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["10"]]
    return back_cancel_keyboard(language, extra_rows=rows)
