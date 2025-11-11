from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class TextCatalog:
    messages: Dict[str, Dict[str, str]]

    def get(self, key: str, language: str = "en", **kwargs: object) -> str:
        lang = language if language in self.messages else "en"
        template = self.messages.get(lang, {}).get(key)
        if template is None:
            template = self.messages.get("en", {}).get(key, key)
        return template.format(**kwargs)

    def button(self, key: str, language: str = "en") -> str:
        return self.get(key, language)


TEXTS = TextCatalog(
    messages={
        "en": {
            "start.site.invalid": "We could not read the order payload. Please open the link from the website again or start without parameters.",
            "start.tg": "Welcome! Let's create a new payment QA order. We'll guide you through the steps.",
            "wizard.geo": "Select your country/region for testing",
            "wizard.method": (
                "Select a payment method\n"
                "The price may vary depending on the method.\n"
                "One method per order. Need multiple methods? Create an additional order."
            ),
            "wizard.no_methods": "Payment methods for this country are not available yet. Please contact support.",
            "wizard.payout": "Please select payout option:",
            "wizard.comments": "Any specific comments or requests?",
            "wizard.skip": "Skip",
            "wizard.back": "◀️ Back",
            "wizard.cancel": "❌ Cancel",
            "wizard.yes": "Yes",
            "wizard.no": "No",
            "wizard.missing.custom_text": "Please describe the custom test scenario to continue.",
            "wizard.invalid.geo": "Please choose one of the suggested GEO buttons.",
            "wizard.invalid.method": "Please choose a payment method from the list.",
            "wizard.invalid.comment": "Comments should not exceed 1000 characters.",
            "confirmation.title": "Please review your order details before confirming.",
            "confirmation.body": (
                "<b>Order summary</b>\n"
                "Country/region: {geo}\n"
                "Payment method: {method}\n"
                "Payout option: {payout}\n"
                "Comments: {comments}\n"
                "Base price: €{base}\n"
                "Method markup: €{method_markup}\n"
                "Payout markup: €{payout_markup}\n"
                "Total: €{total}\n\n"
                "Want to use another payment method as well? Create an additional order for it."
            ),
            "confirmation.confirm": "Confirm ✅",
            "confirmation.add_order": "➕ Add another order",
            "confirmation.cancelled": "Order cancelled. If you change your mind, start again with /start.",
            "confirmation.ready": "✅ Order successfully created.",
            "payment.instructions": (
                "Send strictly via TRC-20 (Tron) network to: <code>{wallet}</code>.\n"
                "After sending, press ‘I've paid’ and attach your proof (screenshot or TXID)."
            ),
            "payment.button.new_order": "➕ Create another order (same GEO)",
            "payment.button.view_orders": "📄 View my orders",
            "payment.button.done": "✅ Done",
            "payment.request.proof": "Please attach a screenshot, document or TXID to confirm the payment.",
            "payment.help": "If you need help with the payment, contact {contact}.",
            "payment.support": "Support: {contact}",
            "payment.thanks": "✅ Payment proof received! We will verify it shortly.",
            "payment.view": "You can use /status to check your latest order status anytime.",
            "payment.done": "Thanks! If you need another order, send /start.",
            "payment.txid.saved": "Payment details received. We'll notify admins for review.",
            "status.none": "You don't have any orders yet.",
            "status.last": "Last order #{order_id}: status — {status}, total — €{total}.",
            "help.text": "Commands:\n/start — restart the wizard\n/status — last order status\n/cancel — cancel current flow\n/lang — switch language",
            "lang.updated": "Language switched to English.",
            "lang.prompt": "Send /lang to switch language anytime.",
            "admin.notify.new": "New order #{order_id} from @{username} ({geo}) — €{total}.",
            "admin.notify.payment": "Payment proof for order #{order_id} received.",
            "admin.stats.header": "Admin dashboard",
            "admin.stats.line": "{status}: {count}",
            "admin.no.orders": "No orders found.",
        },
        "ru": {
            "start.site.invalid": "Не удалось распознать параметры заявки. Откройте ссылку с сайта ещё раз или используйте /start без параметров.",
            "start.tg": "Привет! Давайте оформим заявку на QA платежей. Я помогу пройти все шаги.",
            "wizard.geo": "Выберите страну или регион для тестирования",
            "wizard.method": (
                "Выберите метод оплаты\n"
                "Стоимость может отличаться в зависимости от метода.\n"
                "Один метод — один заказ. Нужны несколько методов? Создайте дополнительный заказ."
            ),
            "wizard.no_methods": "Для этой страны пока нет доступных методов оплаты. Свяжитесь с поддержкой.",
            "wizard.payout": "Выберите опцию по выводу средств:",
            "wizard.comments": "Есть ли дополнительные комментарии или пожелания?",
            "wizard.skip": "Пропустить",
            "wizard.back": "◀️ Назад",
            "wizard.cancel": "❌ Отмена",
            "wizard.yes": "Да",
            "wizard.no": "Нет",
            "wizard.missing.custom_text": "Нужно описать сценарий, чтобы продолжить.",
            "wizard.invalid.geo": "Пожалуйста, выберите одну из предложенных стран.",
            "wizard.invalid.method": "Пожалуйста, выберите метод оплаты из списка.",
            "wizard.invalid.comment": "Комментарий не должен превышать 1000 символов.",
            "confirmation.title": "Проверьте данные заказа перед подтверждением.",
            "confirmation.body": (
                "<b>Итоги заказа</b>\n"
                "Страна/регион: {geo}\n"
                "Метод оплаты: {method}\n"
                "Опция по выводу: {payout}\n"
                "Комментарий: {comments}\n"
                "Базовая стоимость: €{base}\n"
                "Надбавка за метод: €{method_markup}\n"
                "Надбавка за вывод/KYC: €{payout_markup}\n"
                "Итого: €{total}\n\n"
                "Хотите протестировать ещё один метод? Создайте дополнительный заказ."
            ),
            "confirmation.confirm": "Подтвердить ✅",
            "confirmation.add_order": "➕ Добавить ещё один заказ",
            "confirmation.cancelled": "Заявка отменена. Если передумаете — начните заново через /start.",
            "confirmation.ready": "✅ Заказ успешно создан.",
            "payment.instructions": (
                "Отправьте строго по сети TRC-20 (Tron) на кошелёк: <code>{wallet}</code>.\n"
                "После отправки нажмите «Я оплатил» и прикрепите чек или TXID."
            ),
            "payment.button.new_order": "➕ Создать ещё один заказ (тот же GEO)",
            "payment.button.view_orders": "📄 Мои заказы",
            "payment.button.done": "✅ Готово",
            "payment.request.proof": "Пожалуйста, прикрепите скриншот, документ или укажите TXID платежа.",
            "payment.help": "Если нужна помощь с оплатой, напишите {contact}.",
            "payment.support": "Контакт поддержки: {contact}",
            "payment.thanks": "✅ Чек получен! Мы проверим оплату в ближайшее время.",
            "payment.view": "Используйте /status, чтобы в любой момент посмотреть последний заказ.",
            "payment.done": "Спасибо! Если понадобится новый заказ, отправьте /start.",
            "payment.txid.saved": "Детали оплаты получены. Сообщим администраторам.",
            "status.none": "У вас ещё нет заказов.",
            "status.last": "Последний заказ #{order_id}: статус — {status}, сумма — €{total}.",
            "help.text": "Команды:\n/start — начать заново\n/status — статус последнего заказа\n/cancel — отменить текущий шаг\n/lang — сменить язык",
            "lang.updated": "Язык переключен на русский.",
            "lang.prompt": "Отправьте /lang, чтобы сменить язык в любой момент.",
            "admin.notify.new": "Новый заказ #{order_id} от @{username} ({geo}) — €{total}.",
            "admin.notify.payment": "Получен платёжный чек по заказу #{order_id}.",
            "admin.stats.header": "Админ-панель",
            "admin.stats.line": "{status}: {count}",
            "admin.no.orders": "Заказов нет.",
        },
    }
)
