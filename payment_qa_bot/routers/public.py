from __future__ import annotations

from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from payment_qa_bot.config import Config
from payment_qa_bot.keyboards.common import (
    back_cancel_keyboard,
    confirmation_keyboard,
    payment_keyboard,
    skip_keyboard,
    yes_no_keyboard,
)
from payment_qa_bot.keyboards.geo import geo_keyboard
from payment_qa_bot.models.db import OrderCreate, OrdersRepository
from payment_qa_bot.services.geo import format_country
from payment_qa_bot.services.payload import PayloadData, PayloadParseResult, SignatureMismatchError, parse_payload
from payment_qa_bot.services.pricing import calculate_price
from payment_qa_bot.services.security import CredentialEncryptor, mask_secret
from payment_qa_bot.states.order import OrderStates
from payment_qa_bot.texts.catalog import TEXTS


STATE_FLOW = [
    OrderStates.GEO,
    OrderStates.METHOD,
    OrderStates.TESTS,
    OrderStates.ADDONS_WITHDRAW,
    OrderStates.ADDONS_CUSTOM,
    OrderStates.ADDONS_CUSTOM_TEXT,
    OrderStates.ADDONS_KYC,
    OrderStates.COMMENTS,
    OrderStates.SITE_URL,
    OrderStates.CREDS_LOGIN,
    OrderStates.CREDS_PASS,
]


def get_public_router(
    config: Config,
    repo: OrdersRepository,
    encryptor: CredentialEncryptor,
) -> Router:
    router = Router()

    async def get_language(state: FSMContext, user_id: int) -> str:
        data = await state.get_data()
        lang = data.get("lang")
        if lang:
            return lang
        stored = await repo.get_language(user_id)
        if stored:
            lang = stored
        else:
            lang = config.default_language
            await repo.set_language(user_id, lang)
        await state.update_data(lang=lang)
        return lang

    async def set_language(state: FSMContext, user_id: int, language: str) -> None:
        await repo.set_language(user_id, language)
        await state.update_data(lang=language)

    async def update_draft(state: FSMContext, **fields: Any) -> Dict[str, Any]:
        data = await state.get_data()
        draft = dict(data.get("draft", {}))
        draft.update(fields)
        await state.update_data(draft=draft)
        return draft

    async def get_draft(state: FSMContext) -> Dict[str, Any]:
        data = await state.get_data()
        return dict(data.get("draft", {}))

    async def set_mode(state: FSMContext, mode: str) -> None:
        await state.update_data(mode=mode)

    async def get_mode(state: FSMContext) -> str:
        data = await state.get_data()
        return data.get("mode", "wizard")

    def is_button(text: Optional[str], key: str, language: str) -> bool:
        return text == TEXTS.button(key, language)

    async def cancel_flow(message: Message, state: FSMContext, language: str) -> None:
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            await repo.update_order(order_id, status="cancelled")
        await state.clear()
        await message.answer(TEXTS.get("confirmation.cancelled", language), reply_markup=ReplyKeyboardRemove())

    def next_in_flow(current: OrderStates, draft: Dict[str, Any]) -> Optional[OrderStates]:
        if current not in STATE_FLOW:
            return None
        idx = STATE_FLOW.index(current)
        for candidate in STATE_FLOW[idx + 1 :]:
            if candidate == OrderStates.ADDONS_CUSTOM_TEXT and not draft.get("custom_test_required"):
                continue
            if candidate in (OrderStates.CREDS_LOGIN, OrderStates.CREDS_PASS) and draft.get("kyc_required"):
                continue
            return candidate
        return None

    def previous_in_flow(current: OrderStates, draft: Dict[str, Any]) -> Optional[OrderStates]:
        if current not in STATE_FLOW:
            return None
        idx = STATE_FLOW.index(current)
        for candidate in reversed(STATE_FLOW[:idx]):
            if candidate == OrderStates.ADDONS_CUSTOM_TEXT and not draft.get("custom_test_required"):
                continue
            if candidate in (OrderStates.CREDS_LOGIN, OrderStates.CREDS_PASS) and draft.get("kyc_required"):
                continue
            return candidate
        return None

    def find_next_missing(draft: Dict[str, Any]) -> Optional[OrderStates]:
        checks = [
            (OrderStates.GEO, lambda d: bool(d.get("geo"))),
            (OrderStates.METHOD, lambda d: bool(d.get("payment_method"))),
            (
                OrderStates.TESTS,
                lambda d: isinstance(d.get("tests_count"), int) and d.get("tests_count", 0) >= 1,
            ),
            (OrderStates.ADDONS_WITHDRAW, lambda d: "withdraw_required" in d),
            (OrderStates.ADDONS_CUSTOM, lambda d: "custom_test_required" in d),
            (
                OrderStates.ADDONS_CUSTOM_TEXT,
                lambda d: not d.get("custom_test_required") or bool(d.get("custom_test_text")),
            ),
            (OrderStates.ADDONS_KYC, lambda d: "kyc_required" in d),
            (OrderStates.SITE_URL, lambda d: "site_url" in d),
            (
                OrderStates.CREDS_LOGIN,
                lambda d: d.get("kyc_required") or "login" in d,
            ),
            (
                OrderStates.CREDS_PASS,
                lambda d: d.get("kyc_required") or "password" in d,
            ),
        ]
        for state, predicate in checks:
            if not predicate(draft):
                return state
        return None

    async def ask_state(message: Message, state: FSMContext, target: OrderStates, language: str) -> None:
        draft = await get_draft(state)
        if target == OrderStates.GEO:
            await message.answer(
                TEXTS.get("wizard.geo", language),
                reply_markup=geo_keyboard(config.geo_whitelist, language),
            )
        elif target == OrderStates.METHOD:
            geo_label = format_country(draft.get("geo", "")) if draft.get("geo") else ""
            prompt = TEXTS.get("wizard.method", language)
            if geo_label:
                prompt += f"\n\n{geo_label}"
            await message.answer(prompt, reply_markup=back_cancel_keyboard(language))
        elif target == OrderStates.TESTS:
            await message.answer(
                TEXTS.get("wizard.tests", language),
                reply_markup=back_cancel_keyboard(language),
            )
        elif target == OrderStates.ADDONS_WITHDRAW:
            await message.answer(
                TEXTS.get("wizard.withdraw", language),
                reply_markup=yes_no_keyboard(language),
            )
        elif target == OrderStates.ADDONS_CUSTOM:
            await message.answer(
                TEXTS.get("wizard.custom", language),
                reply_markup=yes_no_keyboard(language),
            )
        elif target == OrderStates.ADDONS_CUSTOM_TEXT:
            await message.answer(
                TEXTS.get("wizard.custom.text", language),
                reply_markup=back_cancel_keyboard(language),
            )
        elif target == OrderStates.ADDONS_KYC:
            await message.answer(
                TEXTS.get("wizard.kyc", language),
                reply_markup=yes_no_keyboard(language),
            )
        elif target == OrderStates.COMMENTS:
            await message.answer(
                TEXTS.get("wizard.comments", language),
                reply_markup=skip_keyboard(language),
            )
        elif target == OrderStates.SITE_URL:
            await message.answer(
                TEXTS.get("wizard.site", language),
                reply_markup=skip_keyboard(language),
            )
        elif target == OrderStates.CREDS_LOGIN:
            await message.answer(
                TEXTS.get("wizard.login", language),
                reply_markup=skip_keyboard(language),
            )
        elif target == OrderStates.CREDS_PASS:
            await message.answer(
                TEXTS.get("wizard.password", language),
                reply_markup=skip_keyboard(language),
            )

    async def show_confirmation(message: Message, state: FSMContext, language: str) -> None:
        draft = await get_draft(state)
        tests = draft.get("tests_count", 1)
        kyc = bool(draft.get("kyc_required"))
        price = calculate_price(tests, kyc)
        summary = TEXTS.get(
            "confirmation.body",
            language,
            geo=format_country(draft.get("geo", "—")),
            tests=tests,
            withdraw=TEXTS.get("wizard.yes", language)
            if draft.get("withdraw_required")
            else TEXTS.get("wizard.no", language),
            custom=(
                TEXTS.get("wizard.yes", language)
                if draft.get("custom_test_required")
                else TEXTS.get("wizard.no", language)
            ),
            kyc=TEXTS.get("wizard.yes", language) if kyc else TEXTS.get("wizard.no", language),
            site=draft.get("site_url") or "—",
            login=mask_secret(draft.get("login")),
            method=draft.get("payment_method") or "—",
            comments=draft.get("comments") or "—",
            total=price.total,
        )
        await state.set_state(OrderStates.CONFIRM)
        await state.update_data(price_eur=price.total)
        await message.answer(
            f"<b>{TEXTS.get('confirmation.title', language)}</b>\n\n{summary}",
            reply_markup=confirmation_keyboard(language),
        )

    async def show_payment(message: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.PAYMENT)
        await message.answer(
            TEXTS.get("confirmation.ready", language)
            + "\n\n"
            + TEXTS.get("payment.instructions", language, wallet=config.wallet_trc20 or "—"),
            reply_markup=payment_keyboard(language),
        )

    async def continue_flow(
        message: Message,
        state: FSMContext,
        current: OrderStates,
        language: str,
    ) -> None:
        draft = await get_draft(state)
        mode = await get_mode(state)
        if mode == "site":
            missing = find_next_missing(draft)
            if missing is None:
                await show_confirmation(message, state, language)
            else:
                await state.set_state(missing)
                await ask_state(message, state, missing, language)
            return

        next_state = next_in_flow(current, draft)
        if next_state is None:
            await show_confirmation(message, state, language)
            return
        await state.set_state(next_state)
        await ask_state(message, state, next_state, language)

    async def handle_back(message: Message, state: FSMContext, current: OrderStates, language: str) -> None:
        draft = await get_draft(state)
        previous = previous_in_flow(current, draft)
        if previous is None:
            await ask_state(message, state, current, language)
            return
        await state.set_state(previous)
        await ask_state(message, state, previous, language)

    def parse_geo_text(text: str) -> Optional[str]:
        for code in config.geo_whitelist:
            if text == format_country(code):
                return code
        return None

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext, command: CommandObject) -> None:
        await state.clear()
        lang = await get_language(state, message.from_user.id)
        payload_value = (command.args or "").strip() if command else ""
        if payload_value:
            try:
                parsed: PayloadParseResult = parse_payload(payload_value, config.payload_secret)
            except SignatureMismatchError:
                parsed = PayloadParseResult(ok=False, data=PayloadData(source="tg"), error="invalid_signature")
            if parsed.ok:
                await set_mode(state, "site")
                draft = {"source": "site"}
                if parsed.data.geo:
                    draft["geo"] = parsed.data.geo
                if parsed.data.tests_count is not None:
                    draft["tests_count"] = parsed.data.tests_count
                if parsed.data.withdraw_required is not None:
                    draft["withdraw_required"] = parsed.data.withdraw_required
                if parsed.data.custom_test_required is not None:
                    draft["custom_test_required"] = parsed.data.custom_test_required
                if parsed.data.custom_test_text:
                    draft["custom_test_text"] = parsed.data.custom_test_text
                if parsed.data.kyc_required is not None:
                    draft["kyc_required"] = parsed.data.kyc_required
                if parsed.data.payment_method:
                    draft["payment_method"] = parsed.data.payment_method
                if parsed.data.site_url:
                    draft["site_url"] = parsed.data.site_url
                if parsed.data.login is not None:
                    draft["login"] = parsed.data.login
                if parsed.data.password is not None:
                    draft["password"] = parsed.data.password
                if parsed.data.comments is not None:
                    draft["comments"] = parsed.data.comments
                await state.update_data(draft=draft, lang=lang)
                missing = find_next_missing(draft)
                if missing is None:
                    await show_confirmation(message, state, lang)
                else:
                    await state.set_state(missing)
                    await ask_state(message, state, missing, lang)
                return
            await message.answer(TEXTS.get("start.site.invalid", lang), reply_markup=ReplyKeyboardRemove())
            await set_mode(state, "wizard")
            await state.update_data(draft={"source": "tg"})
            await state.set_state(OrderStates.GEO)
            await ask_state(message, state, OrderStates.GEO, lang)
            return

        await set_mode(state, "wizard")
        await state.update_data(draft={"source": "tg"})
        await message.answer(TEXTS.get("start.tg", lang), reply_markup=ReplyKeyboardRemove())
        await state.set_state(OrderStates.GEO)
        await ask_state(message, state, OrderStates.GEO, lang)

    @router.message(Command("help"))
    async def help_command(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        await message.answer(TEXTS.get("help.text", lang))

    @router.message(Command("cancel"))
    async def cancel_command(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        await cancel_flow(message, state, lang)

    @router.message(Command("lang"))
    async def language_command(message: Message, state: FSMContext) -> None:
        current = await get_language(state, message.from_user.id)
        new_lang = "ru" if current == "en" else "en"
        await set_language(state, message.from_user.id, new_lang)
        await message.answer(TEXTS.get("lang.updated", new_lang))
        await message.answer(TEXTS.get("lang.prompt", new_lang))

    @router.message(Command("status"))
    async def status_command(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        order = await repo.get_last_order(message.from_user.id)
        if not order:
            await message.answer(TEXTS.get("status.none", lang))
            return
        total = order.price_eur or 0
        await message.answer(
            TEXTS.get(
                "status.last",
                lang,
                order_id=order.order_id,
                status=order.status,
                total=total,
            )
        )

    @router.message(OrderStates.GEO)
    async def geo_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await ask_state(message, state, OrderStates.GEO, lang)
            return
        code = parse_geo_text(text)
        if not code:
            await message.answer(TEXTS.get("wizard.invalid.geo", lang), reply_markup=geo_keyboard(config.geo_whitelist, lang))
            return
        await update_draft(state, geo=code)
        await continue_flow(message, state, OrderStates.GEO, lang)

    @router.message(OrderStates.METHOD)
    async def method_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.METHOD, lang)
            return
        if len(text) < 2 or len(text) > 100:
            await message.answer(TEXTS.get("wizard.invalid.method", lang), reply_markup=back_cancel_keyboard(lang))
            return
        await update_draft(state, payment_method=text)
        await continue_flow(message, state, OrderStates.METHOD, lang)

    @router.message(OrderStates.TESTS)
    async def tests_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.TESTS, lang)
            return
        try:
            value = int(text)
        except ValueError:
            await message.answer(TEXTS.get("wizard.invalid.tests", lang), reply_markup=back_cancel_keyboard(lang))
            return
        if value < 1 or value > 100:
            await message.answer(TEXTS.get("wizard.invalid.tests", lang), reply_markup=back_cancel_keyboard(lang))
            return
        await update_draft(state, tests_count=value)
        await continue_flow(message, state, OrderStates.TESTS, lang)

    @router.message(OrderStates.ADDONS_WITHDRAW)
    async def withdraw_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.ADDONS_WITHDRAW, lang)
            return
        if is_button(text, "wizard.yes", lang):
            await update_draft(state, withdraw_required=True)
        elif is_button(text, "wizard.no", lang):
            await update_draft(state, withdraw_required=False)
        else:
            await message.answer(TEXTS.get("wizard.withdraw", lang), reply_markup=yes_no_keyboard(lang))
            return
        await continue_flow(message, state, OrderStates.ADDONS_WITHDRAW, lang)

    @router.message(OrderStates.ADDONS_CUSTOM)
    async def custom_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.ADDONS_CUSTOM, lang)
            return
        if is_button(text, "wizard.yes", lang):
            await update_draft(state, custom_test_required=True)
        elif is_button(text, "wizard.no", lang):
            await update_draft(state, custom_test_required=False, custom_test_text=None)
        else:
            await message.answer(TEXTS.get("wizard.custom", lang), reply_markup=yes_no_keyboard(lang))
            return
        await continue_flow(message, state, OrderStates.ADDONS_CUSTOM, lang)

    @router.message(OrderStates.ADDONS_CUSTOM_TEXT)
    async def custom_text_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.ADDONS_CUSTOM_TEXT, lang)
            return
        if not text:
            await message.answer(TEXTS.get("wizard.missing.custom_text", lang), reply_markup=back_cancel_keyboard(lang))
            return
        await update_draft(state, custom_test_text=text)
        await continue_flow(message, state, OrderStates.ADDONS_CUSTOM_TEXT, lang)

    @router.message(OrderStates.ADDONS_KYC)
    async def kyc_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.ADDONS_KYC, lang)
            return
        if is_button(text, "wizard.yes", lang):
            await update_draft(state, kyc_required=True)
        elif is_button(text, "wizard.no", lang):
            await update_draft(state, kyc_required=False)
        else:
            await message.answer(TEXTS.get("wizard.kyc", lang), reply_markup=yes_no_keyboard(lang))
            return
        await continue_flow(message, state, OrderStates.ADDONS_KYC, lang)

    @router.message(OrderStates.COMMENTS)
    async def comments_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.COMMENTS, lang)
            return
        if is_button(text, "wizard.skip", lang):
            await update_draft(state, comments=None)
        else:
            if len(text) > 1000:
                await message.answer(TEXTS.get("wizard.invalid.comment", lang), reply_markup=skip_keyboard(lang))
                return
            await update_draft(state, comments=text)
        await continue_flow(message, state, OrderStates.COMMENTS, lang)

    @router.message(OrderStates.SITE_URL)
    async def site_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.SITE_URL, lang)
            return
        if is_button(text, "wizard.skip", lang):
            await update_draft(state, site_url=None)
        else:
            if not (text.startswith("http://") or text.startswith("https://")):
                await message.answer(TEXTS.get("wizard.invalid.url", lang), reply_markup=skip_keyboard(lang))
                return
            await update_draft(state, site_url=text)
        await continue_flow(message, state, OrderStates.SITE_URL, lang)

    @router.message(OrderStates.CREDS_LOGIN)
    async def login_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        draft = await get_draft(state)
        if draft.get("kyc_required"):
            await continue_flow(message, state, OrderStates.CREDS_LOGIN, lang)
            return
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.CREDS_LOGIN, lang)
            return
        if is_button(text, "wizard.skip", lang):
            await update_draft(state, login=None)
        else:
            if len(text) < 2 or len(text) > 120:
                await message.answer(TEXTS.get("wizard.invalid.login", lang), reply_markup=skip_keyboard(lang))
                return
            await update_draft(state, login=text)
        await continue_flow(message, state, OrderStates.CREDS_LOGIN, lang)

    @router.message(OrderStates.CREDS_PASS)
    async def password_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        draft = await get_draft(state)
        if draft.get("kyc_required"):
            await continue_flow(message, state, OrderStates.CREDS_PASS, lang)
            return
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.CREDS_PASS, lang)
            return
        if is_button(text, "wizard.skip", lang):
            await update_draft(state, password=None)
        else:
            if len(text) < 2 or len(text) > 120:
                await message.answer(TEXTS.get("wizard.invalid.password", lang), reply_markup=skip_keyboard(lang))
                return
            await update_draft(state, password=text)
        await continue_flow(message, state, OrderStates.CREDS_PASS, lang)

    @router.message(OrderStates.CONFIRM)
    async def confirm_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "confirmation.cancel", lang) or is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "confirmation.edit", lang):
            await set_mode(state, "wizard")
            await state.set_state(OrderStates.GEO)
            await ask_state(message, state, OrderStates.GEO, lang)
            return
        if not is_button(text, "confirmation.confirm", lang):
            await message.answer(TEXTS.get("confirmation.title", lang), reply_markup=confirmation_keyboard(lang))
            return
        draft = await get_draft(state)
        price_total = await state.get_data()
        total = price_total.get("price_eur") or calculate_price(draft.get("tests_count", 1), bool(draft.get("kyc_required"))).total
        encrypted_login = encryptor.encrypt(draft.get("login"))
        encrypted_password = encryptor.encrypt(draft.get("password"))
        order_id = await repo.create_order(
            OrderCreate(
                user_id=message.from_user.id,
                username=message.from_user.username,
                source=draft.get("source", "tg"),
                geo=draft.get("geo", ""),
                method_user_text=draft.get("payment_method", ""),
                tests_count=draft.get("tests_count", 1),
                withdraw_required=bool(draft.get("withdraw_required")),
                custom_test_required=bool(draft.get("custom_test_required")),
                custom_test_text=draft.get("custom_test_text"),
                kyc_required=bool(draft.get("kyc_required")),
                comments=draft.get("comments"),
                site_url=draft.get("site_url"),
                login=encrypted_login,
                password_enc=encrypted_password,
                price_eur=total,
                status="awaiting_payment",
                payment_network="USDT TRC-20",
                payment_wallet=config.wallet_trc20,
            )
        )
        await state.update_data(order_id=order_id)
        await notify_admins(
            message,
            TEXTS.get(
                "admin.notify.new",
                lang,
                order_id=order_id,
                username=message.from_user.username or message.from_user.id,
                geo=format_country(draft.get("geo", "")),
                total=total,
            ),
        )
        await show_payment(message, state, lang)

    async def notify_admins(message: Message, text: str) -> None:
        if not config.admin_ids:
            return
        for admin_id in config.admin_ids:
            try:
                await message.bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001 - notification errors should not break user flow
                continue

    @router.message(OrderStates.PAYMENT)
    async def payment_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "payment.button.help", lang):
            await message.answer(TEXTS.get("payment.help", lang, contact=config.help_contact))
            return
        if is_button(text, "payment.button.support", lang):
            await message.answer(TEXTS.get("payment.support", lang, contact=config.help_contact))
            return
        if is_button(text, "payment.button.paid", lang):
            await state.set_state(OrderStates.CHECK_UPLOAD)
            await message.answer(TEXTS.get("payment.request.proof", lang))
            return
        await message.answer(TEXTS.get("payment.instructions", lang, wallet=config.wallet_trc20 or "—"), reply_markup=payment_keyboard(lang))

    @router.message(OrderStates.CHECK_UPLOAD, F.photo)
    async def payment_photo(message: Message, state: FSMContext) -> None:
        await handle_payment_proof(message, state, file_id=message.photo[-1].file_id, txid=None)

    @router.message(OrderStates.CHECK_UPLOAD, F.document)
    async def payment_document(message: Message, state: FSMContext) -> None:
        await handle_payment_proof(message, state, file_id=message.document.file_id, txid=None)

    @router.message(OrderStates.CHECK_UPLOAD, F.text)
    async def payment_txid(message: Message, state: FSMContext) -> None:
        text = (message.text or "").strip()
        lang = await get_language(state, message.from_user.id)
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if len(text) < 5:
            await message.answer(TEXTS.get("payment.request.proof", lang))
            return
        await handle_payment_proof(message, state, file_id=None, txid=text)

    async def handle_payment_proof(
        message: Message,
        state: FSMContext,
        file_id: Optional[str],
        txid: Optional[str],
    ) -> None:
        lang = await get_language(state, message.from_user.id)
        data = await state.get_data()
        order_id = data.get("order_id")
        if not order_id:
            await message.answer(TEXTS.get("payment.request.proof", lang))
            return
        update_fields: Dict[str, Any] = {
            "status": "proof_received",
        }
        if file_id:
            update_fields["payment_proof_file_id"] = file_id
        if txid:
            update_fields["payment_txid"] = txid
        await repo.update_order(order_id, **update_fields)
        await notify_admins(message, TEXTS.get("admin.notify.payment", lang, order_id=order_id))
        await message.answer(TEXTS.get("payment.thanks", lang), reply_markup=ReplyKeyboardRemove())
        await state.clear()

    return router
