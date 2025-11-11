from __future__ import annotations

from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from payment_qa_bot.config import Config
from payment_qa_bot.keyboards.common import (
    back_cancel_keyboard,
    confirmation_keyboard,
    payment_keyboard,
    skip_keyboard,
)
from payment_qa_bot.keyboards.geo import geo_keyboard
from payment_qa_bot.keyboards.options import methods_keyboard, payout_keyboard
from payment_qa_bot.models.db import OrderCreate, OrdersRepository
from payment_qa_bot.services.geo import format_country
from payment_qa_bot.services.payment_methods import get_methods_for_geo
from payment_qa_bot.services.payload import (
    PayloadData,
    PayloadParseResult,
    SignatureMismatchError,
    build_payload_hash,
    parse_payload,
)
from payment_qa_bot.services.pricing import calculate_price
from payment_qa_bot.services.security import CredentialEncryptor, mask_secret
from payment_qa_bot.services.payouts import PayoutOption, get_payout_option, iter_payout_options
from payment_qa_bot.states.order import OrderStates
from payment_qa_bot.texts.catalog import TEXTS


STATE_FLOW = [
    OrderStates.GEO,
    OrderStates.METHOD,
    OrderStates.TESTS,
    OrderStates.PAYOUT,
    OrderStates.COMMENTS,
    OrderStates.SITE_URL,
    OrderStates.CREDS_LOGIN,
    OrderStates.CREDS_PASS,
]


def get_public_router(
    config: Config,
    repo: OrdersRepository,
    encryptor: CredentialEncryptor,
    bot_username: str,
) -> Router:
    router = Router()
    router.message.filter(F.chat.type == ChatType.PRIVATE)
    payout_options: List[PayoutOption] = list(iter_payout_options())

    group_router = Router()
    group_router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))

    async def send_private_redirect(chat_id: int, bot_markup: InlineKeyboardMarkup, event_bot) -> None:
        try:
            await event_bot.send_message(chat_id, TEXTS.get("group.redirect", config.default_language), reply_markup=bot_markup)
        except Exception:  # noqa: BLE001 - avoid crashing if bot cannot send
            return

    @group_router.message()
    async def ignore_group_messages(message: Message) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=TEXTS.get("group.button", config.default_language), url=f"https://t.me/{bot_username}")]]
        )
        await message.answer(TEXTS.get("group.redirect", config.default_language), reply_markup=keyboard)

    @router.my_chat_member()
    async def handle_my_chat_member(event: ChatMemberUpdated) -> None:
        if event.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return
        if event.new_chat_member.status not in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR}:
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=TEXTS.get("group.button", config.default_language), url=f"https://t.me/{bot_username}")]]
        )
        await send_private_redirect(event.chat.id, keyboard, event.bot)

    router.include_router(group_router)

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

    def resolve_payout(key: Optional[str]) -> Optional[PayoutOption]:
        if not key:
            return None
        for option in payout_options:
            if option.key == key:
                return option
        return None

    async def cancel_flow(message: Message, state: FSMContext, language: str) -> None:
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id and not data.get("existing_order"):
            await repo.update_order(order_id, status="cancelled")
        await state.clear()
        await message.answer(TEXTS.get("confirmation.cancelled", language), reply_markup=ReplyKeyboardRemove())

    def next_in_flow(current: OrderStates, draft: Dict[str, Any]) -> Optional[OrderStates]:
        if current not in STATE_FLOW:
            return None
        idx = STATE_FLOW.index(current)
        for candidate in STATE_FLOW[idx + 1 :]:
            return candidate
        return None

    def previous_in_flow(current: OrderStates, draft: Dict[str, Any]) -> Optional[OrderStates]:
        if current not in STATE_FLOW:
            return None
        idx = STATE_FLOW.index(current)
        for candidate in reversed(STATE_FLOW[:idx]):
            return candidate
        return None

    def find_next_missing(draft: Dict[str, Any]) -> Optional[OrderStates]:
        checks = [
            (OrderStates.GEO, lambda d: bool(d.get("geo"))),
            (OrderStates.METHOD, lambda d: bool(d.get("payment_method"))),
            (OrderStates.TESTS, lambda d: int(d.get("tests_count") or 0) >= 1),
            (OrderStates.PAYOUT, lambda d: bool(d.get("payout_option"))),
            (OrderStates.COMMENTS, lambda d: "comments" in d),
            (OrderStates.SITE_URL, lambda d: "site_url" in d),
            (OrderStates.CREDS_LOGIN, lambda d: "login" in d),
            (OrderStates.CREDS_PASS, lambda d: "password" in d),
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
            methods = get_methods_for_geo(draft.get("geo"))
            keyboard = methods_keyboard(methods, language)
            await message.answer(prompt, reply_markup=keyboard)
        elif target == OrderStates.TESTS:
            await message.answer(
                TEXTS.get("wizard.tests", language),
                reply_markup=back_cancel_keyboard(language),
            )
        elif target == OrderStates.PAYOUT:
            options = [TEXTS.button(option.key, language) for option in payout_options]
            await message.answer(
                TEXTS.get("wizard.payout", language),
                reply_markup=payout_keyboard(options, language),
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
        tests = int(draft.get("tests_count") or 1)
        payout_key = draft.get("payout_option")
        payout_option = resolve_payout(payout_key)
        payout_text = TEXTS.button(payout_option.key, language) if payout_option else TEXTS.button("payout.option.none", language)
        surcharge = payout_option.surcharge if payout_option else int(draft.get("payout_surcharge") or 0)
        price = calculate_price(tests, surcharge)
        summary = TEXTS.get(
            "confirmation.body",
            language,
            geo=format_country(draft.get("geo", "—")),
            method=draft.get("payment_method") or "—",
            tests=tests,
            payout=payout_text,
            site=draft.get("site_url") or "—",
            login=mask_secret(draft.get("login")),
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
        await state.update_data(existing_order=False, payload_fingerprint=None)
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
                tests_count = parsed.data.tests_count if parsed.data.tests_count and parsed.data.tests_count >= 1 else 1
                draft["tests_count"] = tests_count
                if parsed.data.payment_method:
                    draft["payment_method"] = parsed.data.payment_method
                if parsed.data.site_url is not None:
                    draft["site_url"] = parsed.data.site_url
                if parsed.data.login is not None:
                    draft["login"] = parsed.data.login
                if parsed.data.password is not None:
                    draft["password"] = parsed.data.password
                if parsed.data.comments is not None:
                    draft["comments"] = parsed.data.comments

                payout_option = None
                if parsed.data.payout_key:
                    payout_option = get_payout_option(parsed.data.payout_key)
                if payout_option is None:
                    if parsed.data.kyc_required:
                        payout_option = get_payout_option("payout.option.kyc")
                    elif parsed.data.withdraw_required:
                        payout_option = get_payout_option("payout.option.withdraw")
                if payout_option is None:
                    payout_option = get_payout_option("payout.option.none")

                if payout_option:
                    draft["payout_option"] = payout_option.key
                    draft["payout_surcharge"] = payout_option.surcharge
                    draft["withdraw_required"] = payout_option.withdraw_required
                    draft["kyc_required"] = payout_option.kyc_required
                else:
                    draft.setdefault("payout_surcharge", 0)
                    draft.setdefault("withdraw_required", False)
                    draft.setdefault("kyc_required", False)

                await state.update_data(
                    draft=draft,
                    lang=lang,
                    payload_fingerprint=parsed.data.payload_fingerprint,
                    site_price_hint=parsed.data.price_total,
                )
                missing = find_next_missing(draft)
                if missing is None:
                    await show_confirmation(message, state, lang)
                else:
                    await state.set_state(missing)
                    await ask_state(message, state, missing, lang)
                return
            await message.answer(TEXTS.get("start.site.invalid", lang), reply_markup=ReplyKeyboardRemove())
            await set_mode(state, "wizard")
            await state.update_data(
                draft={
                    "source": "tg",
                    "tests_count": 1,
                    "withdraw_required": False,
                    "kyc_required": False,
                    "payout_surcharge": 0,
                },
                payload_fingerprint=None,
                lang=lang,
            )
            await state.set_state(OrderStates.GEO)
            await ask_state(message, state, OrderStates.GEO, lang)
            return

        await set_mode(state, "wizard")
        await state.update_data(
            draft={
                "source": "tg",
                "tests_count": 1,
                "withdraw_required": False,
                "kyc_required": False,
                "payout_surcharge": 0,
            },
            payload_fingerprint=None,
            lang=lang,
        )
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
        draft = await get_draft(state)
        methods = get_methods_for_geo(draft.get("geo"))
        if methods:
            if text not in methods:
                await message.answer(TEXTS.get("wizard.invalid.method", lang), reply_markup=methods_keyboard(methods, lang))
                return
        else:
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
            tests_value = int(text)
        except ValueError:
            await message.answer(TEXTS.get("wizard.invalid.tests", lang), reply_markup=back_cancel_keyboard(lang))
            return
        if not 1 <= tests_value <= 100:
            await message.answer(TEXTS.get("wizard.invalid.tests", lang), reply_markup=back_cancel_keyboard(lang))
            return
        await update_draft(state, tests_count=tests_value)
        await continue_flow(message, state, OrderStates.TESTS, lang)

    @router.message(OrderStates.PAYOUT)
    async def payout_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await handle_back(message, state, OrderStates.PAYOUT, lang)
            return
        option = None
        for item in payout_options:
            if text == TEXTS.button(item.key, lang):
                option = item
                break
        if option is None:
            options = [TEXTS.button(item.key, lang) for item in payout_options]
            await message.answer(TEXTS.get("wizard.invalid.payout", lang), reply_markup=payout_keyboard(options, lang))
            return
        await update_draft(
            state,
            payout_option=option.key,
            payout_surcharge=option.surcharge,
            withdraw_required=option.withdraw_required,
            kyc_required=option.kyc_required,
        )
        await continue_flow(message, state, OrderStates.PAYOUT, lang)

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
        data_snapshot = await state.get_data()
        total = data_snapshot.get("price_eur") or calculate_price(
            int(draft.get("tests_count") or 1),
            int(draft.get("payout_surcharge") or 0),
        ).total
        payload_hash = build_payload_hash(data_snapshot.get("payload_fingerprint"), message.from_user.id)
        if payload_hash:
            existing = await repo.get_by_payload(payload_hash)
            if existing:
                await state.update_data(
                    order_id=existing.order_id,
                    existing_order=True,
                    price_eur=existing.price_eur or total,
                )
                await message.answer(
                    TEXTS.get(
                        "confirmation.duplicate",
                        lang,
                        order_id=existing.order_id,
                        status=existing.status,
                    )
                )
                if existing.status == "awaiting_payment":
                    await show_payment(message, state, lang)
                else:
                    await state.clear()
                return
        encrypted_login = encryptor.encrypt(draft.get("login"))
        encrypted_password = encryptor.encrypt(draft.get("password"))
        order_id = await repo.create_order(
            OrderCreate(
                user_id=message.from_user.id,
                username=message.from_user.username,
                source=draft.get("source", "tg"),
                geo=draft.get("geo", ""),
                method_user_text=draft.get("payment_method", ""),
                tests_count=int(draft.get("tests_count") or 1),
                withdraw_required=bool(draft.get("withdraw_required")),
                custom_test_required=False,
                custom_test_text=None,
                kyc_required=bool(draft.get("kyc_required")),
                comments=draft.get("comments"),
                site_url=draft.get("site_url"),
                login=encrypted_login,
                password_enc=encrypted_password,
                price_eur=total,
                status="awaiting_payment",
                payment_network="USDT TRC-20",
                payment_wallet=config.wallet_trc20,
                payload_hash=payload_hash,
            )
        )
        await state.update_data(order_id=order_id, existing_order=False, payload_fingerprint=None, price_eur=total)
        await message.answer(TEXTS.get("confirmation.accepted", lang, order_id=order_id))
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
