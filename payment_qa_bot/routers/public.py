from __future__ import annotations

from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from payment_qa_bot.config import Config
from payment_qa_bot.keyboards.common import (
    back_cancel_keyboard,
    confirmation_keyboard,
    payment_keyboard,
    skip_keyboard,
)
from payment_qa_bot.keyboards.geo import geo_keyboard
from payment_qa_bot.models.db import OrderCreate, OrdersRepository
from payment_qa_bot.services.geo import format_country
from payment_qa_bot.services.payload import PayloadData, PayloadParseResult, SignatureMismatchError, parse_payload
from payment_qa_bot.services.pricing import calculate_price, format_eur
from payment_qa_bot.services.security import CredentialEncryptor
from payment_qa_bot.states.order import OrderStates
from payment_qa_bot.texts.catalog import TEXTS
from payment_qa_bot.services.methods import PaymentMethodInfo, get_payment_methods
from payment_qa_bot.services.payout import PAYOUT_OPTIONS, PayoutOption, get_payout_option


STATE_FLOW = [
    OrderStates.GEO,
    OrderStates.METHOD,
    OrderStates.PAYOUT,
    OrderStates.COMMENTS,
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
            (OrderStates.PAYOUT, lambda d: bool(d.get("payout_option_id"))),
            (OrderStates.COMMENTS, lambda d: "comments" in d),
        ]
        for state, predicate in checks:
            if not predicate(draft):
                return state
        return None

    def build_method_keyboard(methods: List[PaymentMethodInfo], language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for idx, method in enumerate(methods):
            label = method.name
            if method.markup_eur:
                label += f" (+{format_eur(method.markup_eur)})"
            builder.button(text=label, callback_data=f"method:{idx}")
        builder.adjust(1)
        builder.row(
            InlineKeyboardButton(
                text=TEXTS.button("wizard.method.add_order", language),
                callback_data="method:add",
            )
        )
        return builder.as_markup()

    def build_payout_keyboard(selected: Optional[str], language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for option in PAYOUT_OPTIONS:
            marker = "✅" if option.option_id == selected else "⚪️"
            builder.button(
                text=f"{marker} {option.title(language)}",
                callback_data=f"payout:{option.option_id}",
            )
        builder.adjust(1)
        return builder.as_markup()

    def build_post_confirm_keyboard(language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(
            text=TEXTS.button("confirmation.add_order", language),
            callback_data="order:add_more",
        )
        builder.button(
            text=TEXTS.button("confirmation.view_orders", language),
            callback_data="order:view",
        )
        builder.button(
            text=TEXTS.button("confirmation.done", language),
            callback_data="order:done",
        )
        builder.adjust(1)
        return builder.as_markup()

    async def start_additional_order(message: Message, state: FSMContext, language: str) -> None:
        data = await state.get_data()
        draft = dict(data.get("draft", {}))
        base_geo = draft.get("geo") or data.get("last_geo")
        if not base_geo:
            await state.set_state(OrderStates.GEO)
            await ask_state(message, state, OrderStates.GEO, language)
            return
        source = draft.get("source", "tg")
        await state.update_data(
            draft={"source": source, "geo": base_geo},
            method_options=[],
            price_eur=None,
        )
        await set_mode(state, "wizard")
        await state.set_state(OrderStates.METHOD)
        await ask_state(message, state, OrderStates.METHOD, language)

    async def send_order_created_message(message: Message, language: str) -> None:
        await message.answer(
            TEXTS.get("confirmation.success", language),
            reply_markup=build_post_confirm_keyboard(language),
        )

    async def finalize_order_creation(message: Message, state: FSMContext, language: str) -> Optional[int]:
        draft = await get_draft(state)
        if not draft.get("geo") or not draft.get("payment_method") or not draft.get("payout_option_id"):
            await message.answer(TEXTS.get("confirmation.missing", language), reply_markup=confirmation_keyboard(language))
            return None
        method_markup = int(draft.get("payment_method_markup") or 0)
        payout_fee = int(draft.get("payout_fee_eur") or 0)
        price = calculate_price(1, method_markup, payout_fee)
        total = price.total
        encrypted_login = encryptor.encrypt(draft.get("login"))
        encrypted_password = encryptor.encrypt(draft.get("password"))
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
                login=encrypted_login,
                password_enc=encrypted_password,
                price_eur=total,
                status="awaiting_payment",
                payment_network="USDT TRC-20",
                payment_wallet=config.wallet_trc20,
            )
        )
        data = await state.get_data()
        pending_orders = list(data.get("pending_order_ids") or [])
        pending_orders.append(order_id)
        await state.update_data(
            order_id=order_id,
            pending_order_ids=pending_orders,
            last_geo=draft.get("geo"),
            draft={"source": draft.get("source", "tg"), "geo": draft.get("geo")},
            price_eur=total,
        )
        await state.set_state(OrderStates.CONFIRMED)
        await notify_admins(
            message,
            TEXTS.get(
                "admin.notify.new",
                language,
                order_id=order_id,
                username=message.from_user.username or message.from_user.id,
                geo=format_country(draft.get("geo", "")),
                total=total,
            ),
        )
        await send_order_created_message(message, language)
        return order_id

    async def ask_state(message: Message, state: FSMContext, target: OrderStates, language: str) -> None:
        draft = await get_draft(state)
        if target == OrderStates.GEO:
            await message.answer(
                TEXTS.get("wizard.geo", language),
                reply_markup=geo_keyboard(config.geo_whitelist, language),
            )
        elif target == OrderStates.METHOD:
            geo_code = draft.get("geo")
            if not geo_code:
                await state.set_state(OrderStates.GEO)
                await ask_state(message, state, OrderStates.GEO, language)
                return
            methods = get_payment_methods(geo_code)
            if not methods:
                await message.answer(
                    TEXTS.get("wizard.method.unavailable", language),
                    reply_markup=back_cancel_keyboard(language),
                )
                return
            await state.update_data(
                method_options=[{"name": option.name, "markup": option.markup_eur} for option in methods]
            )
            prompt = TEXTS.get(
                "wizard.method",
                language,
                geo=format_country(geo_code),
            )
            await message.answer(prompt, reply_markup=build_method_keyboard(methods, language))
        elif target == OrderStates.PAYOUT:
            selected = draft.get("payout_option_id")
            description_lines = [TEXTS.get("wizard.payout.prompt", language)]
            for option in PAYOUT_OPTIONS:
                line = f"• {option.title(language)}"
                details = option.description(language)
                if details:
                    line += f" — {details}"
                description_lines.append(line)
            await message.answer(
                "\n".join(description_lines),
                reply_markup=build_payout_keyboard(selected, language),
            )
        elif target == OrderStates.COMMENTS:
            await message.answer(
                TEXTS.get("wizard.comments", language),
                reply_markup=skip_keyboard(language),
            )

    async def show_confirmation(message: Message, state: FSMContext, language: str) -> None:
        draft = await get_draft(state)
        method_markup = int(draft.get("payment_method_markup") or 0)
        payout_fee = int(draft.get("payout_fee_eur") or 0)
        price = calculate_price(1, method_markup, payout_fee)
        payout_option = get_payout_option(draft.get("payout_option_id", ""))
        payout_label = payout_option.title(language) if payout_option else "—"
        summary = TEXTS.get(
            "confirmation.body",
            language,
            geo=format_country(draft.get("geo", "—")),
            method=draft.get("payment_method") or "—",
            payout=payout_label,
            comments=draft.get("comments") or "—",
            base_price=format_eur(price.base_total),
            method_markup=format_eur(price.method_markup_total)
            if price.method_markup_total
            else format_eur(0),
            payout_fee=format_eur(price.payout_total)
            if price.payout_total
            else format_eur(0),
            total=format_eur(price.total),
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
                if parsed.data.payment_method:
                    draft["payment_method"] = parsed.data.payment_method
                if parsed.data.comments is not None:
                    draft["comments"] = parsed.data.comments
                payout_option_id: Optional[str] = None
                if parsed.data.kyc_required:
                    payout_option_id = "full_kyc"
                elif parsed.data.withdraw_required:
                    payout_option_id = "payout_check"
                if payout_option_id:
                    option = get_payout_option(payout_option_id)
                    if option:
                        draft["payout_option_id"] = option.option_id
                        draft["payout_fee_eur"] = option.fee_eur
                        draft["withdraw_required"] = option.withdraw_required
                        draft["kyc_required"] = option.kyc_required
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

    @router.callback_query(OrderStates.METHOD, F.data.startswith("method:"))
    async def method_callback(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        payload = (query.data or "").split("method:", maxsplit=1)[-1]
        if payload == "add":
            await query.answer()
            if query.message:
                await query.message.edit_reply_markup(reply_markup=None)
                await start_additional_order(query.message, state, lang)
            return
        try:
            index = int(payload)
        except ValueError:
            await query.answer(TEXTS.get("wizard.method.invalid_choice", lang), show_alert=True)
            return
        data = await state.get_data()
        options = data.get("method_options") or []
        if index < 0 or index >= len(options):
            await query.answer(TEXTS.get("wizard.method.invalid_choice", lang), show_alert=True)
            return
        selected = options[index]
        await update_draft(
            state,
            payment_method=selected.get("name"),
            payment_method_markup=selected.get("markup", 0),
        )
        await query.answer(TEXTS.get("wizard.method.selected", lang))
        if query.message:
            await query.message.edit_reply_markup(reply_markup=None)
            await continue_flow(query.message, state, OrderStates.METHOD, lang)

    @router.callback_query(OrderStates.PAYOUT, F.data.startswith("payout:"))
    async def payout_callback(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        payload = (query.data or "").split("payout:", maxsplit=1)[-1]
        option = get_payout_option(payload)
        if option is None:
            await query.answer(TEXTS.get("wizard.payout.invalid_choice", lang), show_alert=True)
            return
        await update_draft(
            state,
            payout_option_id=option.option_id,
            payout_fee_eur=option.fee_eur,
            withdraw_required=option.withdraw_required,
            kyc_required=option.kyc_required,
        )
        await query.answer(TEXTS.get("wizard.payout.selected", lang))
        if query.message:
            await query.message.edit_reply_markup(
                reply_markup=build_payout_keyboard(option.option_id, lang)
            )
            await continue_flow(query.message, state, OrderStates.PAYOUT, lang)

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

    @router.message(OrderStates.CONFIRM)
    async def confirm_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if is_button(text, "wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if is_button(text, "confirmation.back", lang):
            await handle_back(message, state, OrderStates.CONFIRM, lang)
            return
        if is_button(text, "confirmation.add_order", lang):
            created = await finalize_order_creation(message, state, lang)
            if created is not None:
                await start_additional_order(message, state, lang)
            return
        if is_button(text, "confirmation.confirm", lang):
            await finalize_order_creation(message, state, lang)
            return
        await message.answer(TEXTS.get("confirmation.title", lang), reply_markup=confirmation_keyboard(lang))

    @router.callback_query(F.data == "order:add_more")
    async def order_add_more(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        await query.answer()
        if query.message:
            await query.message.edit_reply_markup(reply_markup=None)
            await start_additional_order(query.message, state, lang)

    @router.callback_query(F.data == "order:view")
    async def order_view(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        orders = await repo.list_user_orders(query.from_user.id, limit=5)
        if not orders:
            text = TEXTS.get("status.none", lang)
        else:
            lines = [TEXTS.get("status.list.header", lang)]
            for record in orders:
                total = record.price_eur or 0
                lines.append(
                    TEXTS.get(
                        "status.list.item",
                        lang,
                        order_id=record.order_id,
                        status=record.status,
                        total=total,
                    )
                )
            text = "\n".join(lines)
        await query.answer()
        if query.message:
            await query.message.answer(text)

    @router.callback_query(F.data == "order:done")
    async def order_done(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        await query.answer()
        if query.message:
            await show_payment(query.message, state, lang)

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
        pending_orders = list(data.get("pending_order_ids") or [])
        order_id = pending_orders.pop() if pending_orders else data.get("order_id")
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
