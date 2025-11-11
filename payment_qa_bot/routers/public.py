from __future__ import annotations

from typing import Any, Dict, Optional

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from payment_qa_bot.config import Config
from payment_qa_bot.keyboards.common import skip_keyboard
from payment_qa_bot.keyboards.geo import geo_keyboard
from payment_qa_bot.keyboards.order import (
    order_created_keyboard,
    payment_methods_keyboard,
    payout_options_keyboard,
    review_keyboard,
)
from payment_qa_bot.models.db import OrderCreate, OrdersRepository
from payment_qa_bot.services.geo import format_country
from payment_qa_bot.services.payment_methods import PaymentMethodOption, get_method, list_methods
from payment_qa_bot.services.payload import PayloadData, PayloadParseResult, SignatureMismatchError, parse_payload
from payment_qa_bot.services.pricing import calculate_price
from payment_qa_bot.services.security import CredentialEncryptor
from payment_qa_bot.states.order import OrderStates
from payment_qa_bot.texts.catalog import TEXTS


def _method_label(option: PaymentMethodOption) -> str:
    if option.markup_eur:
        return f"{option.title} (+{option.markup_eur} €)"
    return option.title


def get_public_router(
    config: Config,
    repo: OrdersRepository,
    encryptor: CredentialEncryptor,
) -> Router:
    router = Router()
    _ = encryptor  # kept for compatibility with existing wiring

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

    async def reset_draft(state: FSMContext, *, geo: Optional[str] = None) -> Dict[str, Any]:
        data = await state.get_data()
        current = dict(data.get("draft", {}))
        source = current.get("source", "tg")
        draft: Dict[str, Any] = {"source": source}
        if geo:
            draft["geo"] = geo
        await state.update_data(draft=draft, order_id=None)
        return draft

    async def cancel_flow(message: Message, state: FSMContext, language: str) -> None:
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            await repo.update_order(order_id, status="cancelled")
        await state.clear()
        await message.answer(TEXTS.get("confirmation.cancelled", language), reply_markup=ReplyKeyboardRemove())

    def payout_label(option: str, language: str) -> str:
        mapping = {
            "none": TEXTS.get("wizard.payout.option.none", language),
            "withdraw": TEXTS.get("wizard.payout.option.withdraw", language),
            "kyc": TEXTS.get("wizard.payout.option.kyc", language),
        }
        return mapping.get(option, option)

    def comments_display(value: Optional[str]) -> str:
        return value if value else "—"

    async def prompt_geo(message: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.GEO)
        await message.answer(
            TEXTS.get("wizard.geo", language),
            reply_markup=geo_keyboard(config.geo_whitelist, language),
        )

    async def prompt_method(target: Message, state: FSMContext, language: str) -> None:
        draft = await get_draft(state)
        geo = draft.get("geo")
        if not geo:
            await prompt_geo(target, state, language)
            return
        methods = list_methods(geo)
        if not methods:
            await target.answer(TEXTS.get("wizard.invalid.geo", language))
            await prompt_geo(target, state, language)
            return
        options = [(option.key, _method_label(option)) for option in methods]
        keyboard = payment_methods_keyboard(
            options,
            additional_text=TEXTS.get("wizard.method.additional", language),
            cancel_text=TEXTS.get("wizard.cancel", language),
        )
        text = TEXTS.get("wizard.method", language)
        text += f"\n\n{format_country(geo)}"
        await state.set_state(OrderStates.METHOD)
        await target.answer(text, reply_markup=keyboard)

    async def prompt_payout(target: Message, state: FSMContext, language: str) -> None:
        keyboard = payout_options_keyboard(
            [
                ("none", TEXTS.get("wizard.payout.option.none", language)),
                ("withdraw", TEXTS.get("wizard.payout.option.withdraw", language)),
                ("kyc", TEXTS.get("wizard.payout.option.kyc", language)),
            ],
            back_text=TEXTS.get("wizard.back", language),
            cancel_text=TEXTS.get("wizard.cancel", language),
        )
        await state.set_state(OrderStates.PAYOUT)
        await target.answer(TEXTS.get("wizard.payout", language), reply_markup=keyboard)

    async def prompt_comments(target: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.COMMENTS)
        await target.answer(TEXTS.get("wizard.comments", language), reply_markup=skip_keyboard(language))

    async def show_review(target: Message, state: FSMContext, language: str) -> None:
        draft = await get_draft(state)
        geo = draft.get("geo")
        method = draft.get("payment_method")
        payout_option = draft.get("payout_option")
        if not geo:
            await prompt_geo(target, state, language)
            return
        if not method:
            await prompt_method(target, state, language)
            return
        if not payout_option:
            await prompt_payout(target, state, language)
            return
        method_markup = int(draft.get("method_markup") or 0)
        price = calculate_price(payout_option, method_markup)
        await state.update_data(
            price_info={
                "base_price": price.base_price,
                "method_markup": price.method_markup,
                "payout_markup": price.payout_markup,
                "total": price.total,
            }
        )
        summary = TEXTS.get(
            "confirmation.body",
            language,
            geo=format_country(geo),
            method=method,
            payout=payout_label(payout_option, language),
            comments=comments_display(draft.get("comments")),
            base_price=price.base_price,
            method_markup=price.method_markup,
            payout_markup=price.payout_markup,
            total=price.total,
        )
        await state.set_state(OrderStates.REVIEW)
        await target.answer(
            f"<b>{TEXTS.get('confirmation.title', language)}</b>\n\n{summary}",
            reply_markup=review_keyboard(
                confirm_text=TEXTS.get("confirmation.confirm", language),
                back_text=TEXTS.get("confirmation.edit", language),
                additional_text=TEXTS.get("confirmation.additional", language),
                cancel_text=TEXTS.get("confirmation.cancel", language),
            ),
        )

    async def show_order_created(target: Message, state: FSMContext, language: str) -> None:
        await state.set_state(OrderStates.CONFIRM)
        await target.answer(
            TEXTS.get("confirmation.ready", language),
            reply_markup=order_created_keyboard(
                create_text=TEXTS.get("final.create", language),
                view_text=TEXTS.get("final.view", language),
                done_text=TEXTS.get("final.done", language),
            ),
        )

    async def start_additional_order(
        target: Message,
        state: FSMContext,
        language: str,
        *,
        geo: Optional[str] = None,
    ) -> None:
        data = await state.get_data()
        default_geo = geo or data.get("last_geo")
        draft = await reset_draft(state, geo=default_geo)
        if draft.get("geo"):
            await prompt_method(target, state, language)
        else:
            await prompt_geo(target, state, language)

    async def notify_admins(message: Message, text: str) -> None:
        if not config.admin_ids:
            return
        for admin_id in config.admin_ids:
            try:
                await message.bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001 - ignore notification errors
                continue

    async def finalize_order(
        origin: Message,
        state: FSMContext,
        language: str,
        *,
        schedule_additional: int = 0,
    ) -> None:
        data_before = await state.get_data()
        draft = dict(data_before.get("draft", {}))
        geo = draft.get("geo") or ""
        method_name = draft.get("payment_method") or ""
        payout_option = draft.get("payout_option", "none")
        method_markup = int(draft.get("method_markup") or 0)
        price = calculate_price(payout_option, method_markup)
        withdraw_required = payout_option in {"withdraw", "kyc"}
        kyc_required = payout_option == "kyc"
        source = draft.get("source", "tg")
        comments = draft.get("comments")
        order_id = await repo.create_order(
            OrderCreate(
                user_id=origin.from_user.id,
                username=origin.from_user.username,
                source=source,
                geo=geo,
                method_user_text=method_name,
                tests_count=1,
                withdraw_required=withdraw_required,
                custom_test_required=False,
                custom_test_text=None,
                kyc_required=kyc_required,
                comments=comments,
                site_url=None,
                login=None,
                password_enc=None,
                price_eur=price.total,
                status="awaiting_payment",
                payment_network="USDT TRC-20",
                payment_wallet=config.wallet_trc20,
            )
        )
        pending_additional = int(data_before.get("auto_additional_orders", 0) or 0) + schedule_additional
        await state.update_data(order_id=order_id, last_geo=geo, auto_additional_orders=pending_additional)
        await notify_admins(
            origin,
            TEXTS.get(
                "admin.notify.new",
                language,
                order_id=order_id,
                username=origin.from_user.username or origin.from_user.id,
                geo=format_country(geo),
                total=price.total,
            ),
        )
        await state.update_data(
            draft={"source": source, "geo": geo},
        )
        await show_order_created(origin, state, language)
        data = await state.get_data()
        auto_count = int(data.get("auto_additional_orders", 0) or 0)
        if auto_count > 0:
            await state.update_data(auto_additional_orders=auto_count - 1)
            await start_additional_order(origin, state, language, geo=geo)

    def map_payload_to_draft(data: PayloadData) -> Dict[str, Any]:
        draft: Dict[str, Any] = {"source": "site"}
        if data.geo:
            draft["geo"] = data.geo
        if data.payment_method:
            draft["payment_method"] = data.payment_method
            if data.geo:
                option = get_method(data.geo, data.payment_method.lower())
                if not option:
                    for candidate in list_methods(data.geo):
                        if candidate.title.lower() == data.payment_method.lower():
                            option = candidate
                            break
                if option:
                    draft["payment_method"] = option.title
                    draft["payment_method_key"] = option.key
                    draft["method_markup"] = option.markup_eur
        if data.comments is not None:
            draft["comments"] = data.comments
        if data.withdraw_required:
            draft["payout_option"] = "withdraw"
        if data.kyc_required:
            draft["payout_option"] = "kyc"
        if not data.withdraw_required and not data.kyc_required:
            draft["payout_option"] = "none"
        return draft

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
                draft = map_payload_to_draft(parsed.data)
                await state.update_data(draft=draft, lang=lang)
                await state.update_data(auto_additional_orders=0)
                if parsed.data.geo:
                    await state.update_data(last_geo=parsed.data.geo)
                if draft.get("geo") and draft.get("payment_method") and draft.get("payout_option"):
                    await show_review(message, state, lang)
                    return
                if draft.get("geo") and draft.get("payment_method"):
                    await prompt_payout(message, state, lang)
                    return
                if draft.get("geo"):
                    await state.set_state(OrderStates.METHOD)
                    await prompt_method(message, state, lang)
                    return
                await prompt_geo(message, state, lang)
                return
            await message.answer(TEXTS.get("start.site.invalid", lang), reply_markup=ReplyKeyboardRemove())
        await state.update_data(draft={"source": "tg"}, auto_additional_orders=0)
        await message.answer(TEXTS.get("start.tg", lang), reply_markup=ReplyKeyboardRemove())
        await prompt_geo(message, state, lang)

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
        if text == TEXTS.button("wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        code: Optional[str] = None
        for candidate in config.geo_whitelist:
            if text == format_country(candidate):
                code = candidate
                break
        if not code:
            await message.answer(TEXTS.get("wizard.invalid.geo", lang), reply_markup=geo_keyboard(config.geo_whitelist, lang))
            return
        await update_draft(state, geo=code)
        await state.update_data(last_geo=code)
        await prompt_method(message, state, lang)

    @router.callback_query(OrderStates.METHOD)
    async def method_step(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        data = query.data or ""
        if data == "method:cancel":
            await cancel_flow(query.message, state, lang)
            await query.answer()
            return
        if data == "method:add":
            info = await state.get_data()
            auto_count = int(info.get("auto_additional_orders", 0) or 0)
            await state.update_data(auto_additional_orders=auto_count + 1)
            await query.answer(TEXTS.get("wizard.method.additional", lang), show_alert=False)
            return
        if not data.startswith("method:"):
            await query.answer()
            return
        key = data.split(":", maxsplit=1)[1]
        draft = await get_draft(state)
        geo = draft.get("geo")
        if not geo:
            await query.answer()
            await prompt_geo(query.message, state, lang)
            return
        option = get_method(geo, key)
        if not option:
            await query.answer()
            await prompt_method(query.message, state, lang)
            return
        await update_draft(
            state,
            payment_method=option.title,
            payment_method_key=option.key,
            method_markup=option.markup_eur,
        )
        await query.answer()
        await prompt_payout(query.message, state, lang)

    @router.callback_query(OrderStates.PAYOUT)
    async def payout_step(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        data = query.data or ""
        if data == "payout:cancel":
            await cancel_flow(query.message, state, lang)
            await query.answer()
            return
        if data == "payout:back":
            await query.answer()
            await prompt_method(query.message, state, lang)
            return
        if not data.startswith("payout:"):
            await query.answer()
            return
        option = data.split(":", maxsplit=1)[1]
        await update_draft(
            state,
            payout_option=option,
            withdraw_required=option in {"withdraw", "kyc"},
            kyc_required=option == "kyc",
        )
        await query.answer()
        await prompt_comments(query.message, state, lang)

    @router.message(OrderStates.COMMENTS)
    async def comments_step(message: Message, state: FSMContext) -> None:
        lang = await get_language(state, message.from_user.id)
        text = (message.text or "").strip()
        if text == TEXTS.button("wizard.cancel", lang):
            await cancel_flow(message, state, lang)
            return
        if text == TEXTS.button("wizard.back", lang):
            await prompt_payout(message, state, lang)
            return
        if text == TEXTS.button("wizard.skip", lang):
            await update_draft(state, comments=None)
        else:
            if len(text) > 1000:
                await message.answer(TEXTS.get("wizard.invalid.comment", lang), reply_markup=skip_keyboard(lang))
                return
            await update_draft(state, comments=text)
        await show_review(message, state, lang)

    @router.callback_query(OrderStates.REVIEW)
    async def review_step(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        data = query.data or ""
        if data == "review:cancel":
            await cancel_flow(query.message, state, lang)
            await query.answer()
            return
        if data == "review:back":
            await query.message.edit_reply_markup()
            await query.answer()
            await prompt_comments(query.message, state, lang)
            return
        if data == "review:confirm":
            await query.message.edit_reply_markup()
            await query.answer()
            await finalize_order(query.message, state, lang)
            return
        if data == "review:add":
            await query.message.edit_reply_markup()
            await query.answer()
            await finalize_order(query.message, state, lang, schedule_additional=1)
            return
        await query.answer()

    @router.callback_query(OrderStates.CONFIRM)
    async def final_step(query: CallbackQuery, state: FSMContext) -> None:
        lang = await get_language(state, query.from_user.id)
        data = query.data or ""
        if data == "final:create":
            await query.message.edit_reply_markup()
            await query.answer()
            await start_additional_order(query.message, state, lang)
            return
        if data == "final:view":
            await query.answer()
            order = await repo.get_last_order(query.from_user.id)
            if not order:
                await query.message.answer(TEXTS.get("status.none", lang))
            else:
                total = order.price_eur or 0
                await query.message.answer(
                    TEXTS.get(
                        "status.last",
                        lang,
                        order_id=order.order_id,
                        status=order.status,
                        total=total,
                    )
                )
            return
        if data == "final:done":
            await query.answer()
            await state.clear()
            await query.message.answer(TEXTS.get("final.done.reply", lang), reply_markup=ReplyKeyboardRemove())
            return
        await query.answer()

    return router
