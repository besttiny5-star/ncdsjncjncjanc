from __future__ import annotations

from typing import Any, Dict, Optional, Union

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from payment_qa_bot.config import Config
from payment_qa_bot.keyboards.common import (
    confirmation_keyboard,
    payment_keyboard,
    skip_keyboard,
)
from payment_qa_bot.keyboards.geo import geo_keyboard
from payment_qa_bot.keyboards.inline import payment_methods_keyboard, payout_options_keyboard
from payment_qa_bot.models.db import OrderCreate, OrdersRepository
from payment_qa_bot.services.geo import format_country
from payment_qa_bot.services.payment_methods import get_method_by_key, get_methods_for_country
from payment_qa_bot.services.payout_options import get_payout_option, iter_payout_options
from payment_qa_bot.services.payload import PayloadParseResult, SignatureMismatchError, parse_payload
from payment_qa_bot.services.pricing import BASE_PRICE_PER_ORDER, calculate_price
from payment_qa_bot.services.security import CredentialEncryptor
from payment_qa_bot.states.order import OrderStates
from payment_qa_bot.texts.catalog import TEXTS


MessageLike = Union[Message, CallbackQuery]


def get_public_router(
    config: Config,
    repo: OrdersRepository,
    encryptor: CredentialEncryptor,
) -> Router:
    router = Router()
    _ = encryptor  # keep interface compatibility

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

    async def get_draft(state: FSMContext) -> Dict[str, Any]:
        data = await state.get_data()
        return dict(data.get("draft", {}))

    async def update_draft(state: FSMContext, **fields: Any) -> Dict[str, Any]:
        draft = await get_draft(state)
        if "source" not in draft:
            draft["source"] = "tg"
        draft.update(fields)
        await state.update_data(draft=draft)
        return draft

    def is_button(text: Optional[str], key: str, language: str) -> bool:
        return text == TEXTS.button(key, language)

    async def cancel_flow(message: Message, state: FSMContext, language: str) -> None:
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            await repo.update_order(order_id, status="cancelled")
        await state.clear()
        await message.answer(TEXTS.get("confirmation.cancelled", language), reply_markup=ReplyKeyboardRemove())

    def extract_message(target: MessageLike) -> Optional[Message]:
        if isinstance(target, Message):
            return target
        return target.message

    async def send_geo_prompt(message: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.GEO)
        await update_draft(state, source="tg")
        await message.answer(
            TEXTS.get("wizard.geo", language),
            reply_markup=geo_keyboard(config.geo_whitelist, language),
        )

    async def send_method_prompt(message: Message, state: FSMContext, language: str) -> None:
        draft = await get_draft(state)
        geo = draft.get("geo")
        if not geo:
            await send_geo_prompt(message, state, language)
            return
        methods = get_methods_for_country(geo)
        if not methods:
            await message.answer(TEXTS.get("wizard.no_methods", language), reply_markup=ReplyKeyboardRemove())
            await send_geo_prompt(message, state, language)
            return
        keyboard = payment_methods_keyboard(geo, [(item.key, item.title) for item in methods])
        prompt = TEXTS.get("wizard.method", language)
        prompt += f"\n\n{format_country(geo)}"
        await state.set_state(OrderStates.METHOD)
        await message.answer(prompt, reply_markup=keyboard)

    async def send_payout_prompt(message: Message, state: FSMContext, language: str) -> None:
        options = list(iter_payout_options())
        lines = [TEXTS.get("wizard.payout", language)]
        for option in options:
            description = option.description
            if description:
                lines.append(f"• {option.title}\n  {description}")
            else:
                lines.append(f"• {option.title}")
        keyboard = payout_options_keyboard(
            [(option.key, option.title, option.description) for option in options]
        )
        await state.set_state(OrderStates.PAYOUT)
        await message.answer("\n".join(lines), reply_markup=keyboard)

    async def send_comments_prompt(message: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.COMMENTS)
        await message.answer(TEXTS.get("wizard.comments", language), reply_markup=skip_keyboard(language))

    async def show_review(message: Message, state: FSMContext, language: str) -> None:
        draft = await get_draft(state)
        price = calculate_price(
            method_markup=int(draft.get("method_markup", 0)),
            payout_markup=int(draft.get("payout_markup", 0)),
            base_price=BASE_PRICE_PER_ORDER,
        )
        await state.update_data(price_eur=price.total)
        summary = TEXTS.get(
            "confirmation.body",
            language,
            geo=format_country(draft.get("geo", "—")),
            method=draft.get("payment_method", "—"),
            payout=draft.get("payout_title", "—"),
            comments=draft.get("comments") or "—",
            base=price.base_total,
            method_markup=price.method_markup,
            payout_markup=price.payout_markup,
            total=price.total,
        )
        title = TEXTS.get("confirmation.title", language)
        await state.set_state(OrderStates.REVIEW)
        await message.answer(
            f"<b>{title}</b>\n\n{summary}",
            reply_markup=confirmation_keyboard(language),
        )

    async def show_success(message: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.PAYMENT)
        await message.answer(
            TEXTS.get("confirmation.ready", language),
            reply_markup=payment_keyboard(language),
        )
        instructions = TEXTS.get(
            "payment.instructions",
            language,
            wallet=config.wallet_trc20 or "—",
        )
        await message.answer(instructions)
        await message.answer(TEXTS.get("payment.view", language))

    async def start_additional_order(target: MessageLike, state: FSMContext, language: str) -> None:
        if isinstance(target, CallbackQuery):
            await target.answer()
            message = extract_message(target)
        else:
            message = target
        if message is None:
            return
        data = await state.get_data()
        draft = dict(data.get("draft", {}))
        geo = draft.get("geo") or data.get("last_geo")
        if not geo:
            await state.update_data(draft={"source": "tg"}, order_id=None)
            await send_geo_prompt(message, state, language)
            return
        await state.update_data(draft={"source": "tg", "geo": geo}, order_id=None)
        await send_method_prompt(message, state, language)

    def parse_geo_text(text: str) -> Optional[str]:
        for code in config.geo_whitelist:
            if text == format_country(code):
                return code
        return None

    async def send_last_order_status(message: Message, language: str) -> None:
        order = await repo.get_last_order(message.from_user.id)
        if not order:
            await message.answer(TEXTS.get("status.none", language))
            return
        total = order.price_eur or 0
        await message.answer(
            TEXTS.get(
                "status.last",
                language,
                order_id=order.order_id,
                status=order.status,
                total=total,
            )
        )

    async def notify_admins(message: Message, text: str) -> None:
        if not config.admin_ids:
            return
        for admin_id in config.admin_ids:
            try:
                await message.bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001
                continue

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext, command: CommandObject) -> None:
        await state.clear()
        lang = await get_language(state, message.from_user.id)
        payload_value = (command.args or "").strip() if command else ""
        draft: Dict[str, Any] = {"source": "tg"}
        if payload_value:
            try:
                parsed: PayloadParseResult = parse_payload(payload_value, config.payload_secret)
            except SignatureMismatchError:
                parsed = PayloadParseResult(ok=False, data=None, error="invalid_signature")
            if parsed.ok and parsed.data:
                if parsed.data.geo and parsed.data.geo in config.geo_whitelist:
                    draft["geo"] = parsed.data.geo
                if parsed.data.comments:
                    draft["comments"] = parsed.data.comments
                await state.update_data(draft=draft, lang=lang, last_geo=draft.get("geo"))
                if draft.get("geo"):
                    message_to_use = message
                    await send_method_prompt(message_to_use, state, lang)
                    return
        await state.update_data(draft=draft, lang=lang)
        await send_geo_prompt(message, state, lang)

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
        await send_last_order_status(message, lang)

    @router.message(OrderStates.GEO)
    async def geo_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await send_geo_prompt(message, state, lang)
            return
        code = parse_geo_text(text)
        if not code:
            await message.answer(
                TEXTS.get("wizard.invalid.geo", lang),
                reply_markup=geo_keyboard(config.geo_whitelist, lang),
            )
            return
        await update_draft(state, geo=code)
        await state.update_data(last_geo=code)
        await send_method_prompt(message, state, lang)

    @router.callback_query(OrderStates.METHOD, F.data.startswith("m:"))
    async def method_selection(callback: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, callback.from_user.id)
        data = (callback.data or "").split(":")
        action = data[1] if len(data) > 1 else ""
        if action == "cancel":
            await callback.answer()
            message = extract_message(callback)
            if message:
                await cancel_flow(message, state, lang)
            return
        if action == "back":
            await callback.answer()
            message = extract_message(callback)
            if message:
                await send_geo_prompt(message, state, lang)
            return
        if action == "add":
            await start_additional_order(callback, state, lang)
            return
        if action != "sel" or len(data) < 4:
            await callback.answer(TEXTS.get("wizard.invalid.method", lang))
            return
        geo_code = data[2]
        method_key = data[3]
        option = get_method_by_key(geo_code, method_key)
        if option is None:
            await callback.answer(TEXTS.get("wizard.invalid.method", lang))
            return
        await update_draft(
            state,
            payment_method=option.title,
            method_key=option.key,
            method_markup=option.markup_eur,
            geo=geo_code,
        )
        message = extract_message(callback)
        if message:
            await send_payout_prompt(message, state, lang)
        await callback.answer()

    @router.callback_query(OrderStates.PAYOUT, F.data.startswith("p:"))
    async def payout_selection(callback: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, callback.from_user.id)
        data = (callback.data or "").split(":")
        action = data[1] if len(data) > 1 else ""
        if action == "cancel":
            await callback.answer()
            message = extract_message(callback)
            if message:
                await cancel_flow(message, state, lang)
            return
        if action == "back":
            await callback.answer()
            message = extract_message(callback)
            if message:
                await send_method_prompt(message, state, lang)
            return
        if action != "sel" or len(data) < 3:
            await callback.answer()
            return
        option_key = data[2]
        option = get_payout_option(option_key)
        if option is None:
            await callback.answer()
            return
        await update_draft(
            state,
            payout_key=option.key,
            payout_title=option.title,
            payout_markup=option.markup_eur,
            withdraw_required=option.withdraw_required,
            kyc_required=option.kyc_required,
        )
        message = extract_message(callback)
        if message:
            await send_comments_prompt(message, state, lang)
        await callback.answer()

    @router.message(OrderStates.COMMENTS)
    async def comments_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            draft = await get_draft(state)
            if not draft.get("payment_method"):
                await send_method_prompt(message, state, lang)
            else:
                await send_payout_prompt(message, state, lang)
            return
        if is_button(text, "wizard.skip", lang):
            await update_draft(state, comments=None)
        else:
            if len(text) > 1000:
                await message.answer(TEXTS.get("wizard.invalid.comment", lang), reply_markup=skip_keyboard(lang))
                return
            await update_draft(state, comments=text)
        await show_review(message, state, lang)

    @router.message(OrderStates.REVIEW)
    async def review_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "wizard.back", lang):
            await send_comments_prompt(message, state, lang)
            return
        if is_button(text, "confirmation.add_order", lang):
            await start_additional_order(message, state, lang)
            return
        if not is_button(text, "confirmation.confirm", lang):
            await show_review(message, state, lang)
            return
        draft = await get_draft(state)
        price_data = await state.get_data()
        total = price_data.get("price_eur") or calculate_price(
            method_markup=int(draft.get("method_markup", 0)),
            payout_markup=int(draft.get("payout_markup", 0)),
            base_price=BASE_PRICE_PER_ORDER,
        ).total
        order_id = await repo.create_order(
            OrderCreate(
                user_id=message.from_user.id,
                username=message.from_user.username,
                source=draft.get("source", "tg"),
                geo=draft.get("geo", ""),
                method_user_text=draft.get("payment_method", ""),
                tests_count=1,
                withdraw_required=bool(draft.get("withdraw_required")),
                custom_test_required=False,
                custom_test_text=None,
                kyc_required=bool(draft.get("kyc_required")),
                comments=draft.get("comments"),
                site_url=None,
                login=None,
                password_enc=None,
                price_eur=total,
                status="awaiting_payment",
                payment_network="USDT TRC-20",
                payment_wallet=config.wallet_trc20,
            )
        )
        await state.update_data(order_id=order_id, last_geo=draft.get("geo"))
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
        await show_success(message, state, lang)

    @router.message(OrderStates.PAYMENT)
    async def payment_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "payment.button.new_order", lang):
            await start_additional_order(message, state, lang)
            return
        if is_button(text, "payment.button.view_orders", lang):
            await send_last_order_status(message, lang)
            return
        if is_button(text, "payment.button.done", lang):
            await message.answer(TEXTS.get("payment.done", lang), reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
        if text:
            if len(text) < 5:
                await message.answer(
                    TEXTS.get("payment.request.proof", lang),
                    reply_markup=payment_keyboard(lang),
                )
                return
            await handle_payment_proof(message, state, txid=text)
            return
        await message.answer(
            TEXTS.get("payment.instructions", lang, wallet=config.wallet_trc20 or "—"),
            reply_markup=payment_keyboard(lang),
        )

    @router.message(OrderStates.PAYMENT, F.photo)
    async def payment_photo(message: Message, state: FSMContext) -> None:
        await handle_payment_proof(message, state, file_id=message.photo[-1].file_id)

    @router.message(OrderStates.PAYMENT, F.document)
    async def payment_document(message: Message, state: FSMContext) -> None:
        await handle_payment_proof(message, state, file_id=message.document.file_id)

    async def handle_payment_proof(
        message: Message,
        state: FSMContext,
        *,
        file_id: Optional[str] = None,
        txid: Optional[str] = None,
    ) -> None:
        lang = await get_language(state, message.from_user.id)
        data = await state.get_data()
        order_id = data.get("order_id")
        if not order_id:
            await message.answer(TEXTS.get("payment.view", lang))
            return
        update_fields: Dict[str, Any] = {"status": "proof_received"}
        if file_id:
            update_fields["payment_proof_file_id"] = file_id
        if txid:
            update_fields["payment_txid"] = txid
        await repo.update_order(order_id, **update_fields)
        await notify_admins(message, TEXTS.get("admin.notify.payment", lang, order_id=order_id))
        await message.answer(TEXTS.get("payment.thanks", lang), reply_markup=ReplyKeyboardRemove())
        await state.clear()

    return router
