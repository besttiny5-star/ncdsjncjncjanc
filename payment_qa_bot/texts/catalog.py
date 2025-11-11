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
                "Select a payment method for {geo}.\n"
                "The price may vary depending on the method.\n"
                "One method per order. Need multiple methods? Create an additional order."
            ),
            "wizard.comments": "Any specific comments or requests?",
            "wizard.skip": "Skip",
            "wizard.back": "◀️ Back",
            "wizard.cancel": "❌ Cancel",
            "wizard.yes": "Yes",
            "wizard.no": "No",
            "wizard.invalid.geo": "Please choose one of the suggested GEO buttons.",
            "wizard.invalid.method": "The payment method should be 2-100 characters long.",
            "wizard.invalid.comment": "Comments should not exceed 1000 characters.",
            "wizard.method.unavailable": "We don't have payment methods for this GEO yet. Please pick another country.",
            "wizard.method.invalid_choice": "Please select one of the suggested payment methods.",
            "wizard.method.selected": "Payment method selected.",
            "wizard.payout.prompt": "Please select payout option:",
            "wizard.payout.invalid_choice": "Please choose one of the payout options.",
            "wizard.payout.selected": "Payout option selected.",
            "confirmation.title": "Please confirm the order",
            "confirmation.body": (
                "<b>Order overview</b>\n"
                "Country/region: {geo}\n"
                "Payment method: {method}\n"
                "Payout option: {payout}\n"
                "Comments: {comments}\n\n"
                "<b>Pricing</b>\n"
                "Base service: {base_price}\n"
                "Method markup: {method_markup}\n"
                "Payout services: {payout_fee}\n"
                "Total: {total}\n\n"
                "Ready to confirm?"
            ),
            "confirmation.confirm": "✅ Confirm order",
            "confirmation.back": "⬅️ Back",
            "confirmation.add_order": "➕ Add another order",
            "confirmation.success": (
                "✅ Order successfully created.\n"
                "Want to use another payment method as well? Create an additional order for it."
            ),
            "confirmation.view_orders": "View my orders",
            "confirmation.done": "Done",
            "confirmation.cancelled": "Order cancelled. If you change your mind, start again with /start.",
            "confirmation.ready": "Great! Here are the payment details.",
            "confirmation.missing": "Some of the order details are missing. Please review them once more.",
            "payment.instructions": (
                "Send strictly via TRC-20 (Tron) network to: <code>{wallet}</code>.\n"
                "After sending, press ‘I've paid’ and attach your proof (screenshot or TXID)."
            ),
            "payment.button.paid": "✅ I've paid — send receipt",
            "payment.button.help": "❓ Payment help",
            "payment.button.support": "📞 Support",
            "payment.request.proof": "Please attach a screenshot, document or TXID to confirm the payment.",
            "payment.help": "If you need help with the payment, contact {contact}.",
            "payment.support": "Support: {contact}",
            "payment.thanks": "✅ Payment proof received! We will verify it shortly.",
            "payment.txid.saved": "Payment details received. We'll notify admins for review.",
            "status.none": "You don't have any orders yet.",
            "status.last": "Last order #{order_id}: status — {status}, total — €{total}.",
            "status.list.header": "Recent orders:",
            "status.list.item": "#{order_id} — {status} — €{total}",
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
            "wizard.geo": "Выберите страну/регион для тестирования",
            "wizard.method": (
                "Выберите платёжный метод для {geo}.\n"
                "Цена может отличаться в зависимости от метода.\n"
                "Один метод = один заказ. Нужно несколько? Создайте дополнительную заявку."
            ),
            "wizard.comments": "Есть ли дополнительные пожелания или комментарии?",
            "wizard.skip": "Пропустить",
            "wizard.back": "◀️ Назад",
            "wizard.cancel": "❌ Отмена",
            "wizard.yes": "Да",
            "wizard.no": "Нет",
            "wizard.invalid.geo": "Пожалуйста, выберите одну из предложенных стран.",
            "wizard.invalid.method": "Метод оплаты должен содержать от 2 до 100 символов.",
            "wizard.invalid.comment": "Комментарий не должен превышать 1000 символов.",
            "wizard.method.unavailable": "Для этого GEO пока нет доступных методов. Выберите другую страну.",
            "wizard.method.invalid_choice": "Пожалуйста, выберите один из предложенных методов.",
            "wizard.method.selected": "Метод оплаты выбран.",
            "wizard.payout.prompt": "Выберите опцию по выводу/KYC:",
            "wizard.payout.invalid_choice": "Пожалуйста, выберите одну из опций.",
            "wizard.payout.selected": "Опция выбрана.",
            "confirmation.title": "Подтвердите заявку",
            "confirmation.body": (
                "<b>Проверьте заявку</b>\n"
                "Страна/регион: {geo}\n"
                "Метод оплаты: {method}\n"
                "Опция вывода/KYC: {payout}\n"
                "Комментарий: {comments}\n\n"
                "<b>Стоимость</b>\n"
                "Базовая услуга: {base_price}\n"
                "Надбавка за метод: {method_markup}\n"
                "Услуги по выводу/KYC: {payout_fee}\n"
                "Итого: {total}\n\n"
                "Всё верно?"
            ),
            "confirmation.confirm": "✅ Подтвердить заказ",
            "confirmation.back": "⬅️ Назад",
            "confirmation.add_order": "➕ Добавить ещё заказ",
            "confirmation.success": (
                "✅ Заявка успешно создана.\n"
                "Нужен ещё один метод? Создайте дополнительную заявку."
            ),
            "confirmation.view_orders": "Мои заявки",
            "confirmation.done": "Готово",
            "confirmation.cancelled": "Заявка отменена. Если передумаете — начните заново через /start.",
            "confirmation.ready": "Отлично! Вот реквизиты для оплаты.",
            "confirmation.missing": "Не хватает данных. Проверьте заявку ещё раз.",
            "payment.instructions": (
                "Отправьте строго по сети TRC-20 (Tron) на кошелёк: <code>{wallet}</code>.\n"
                "После отправки нажмите «Я оплатил» и прикрепите чек или TXID."
            ),
            "payment.button.paid": "✅ Я оплатил — отправить чек",
            "payment.button.help": "❓ Помощь с оплатой",
            "payment.button.support": "📞 Поддержка",
            "payment.request.proof": "Пожалуйста, прикрепите скриншот, документ или укажите TXID платежа.",
            "payment.help": "Если нужна помощь с оплатой, напишите {contact}.",
            "payment.support": "Контакт поддержки: {contact}",
            "payment.thanks": "✅ Чек получен! Мы проверим оплату в ближайшее время.",
            "payment.txid.saved": "Детали оплаты получены. Сообщим администраторам.",
            "status.none": "У вас ещё нет заказов.",
            "status.last": "Последний заказ #{order_id}: статус — {status}, сумма — €{total}.",
            "status.list.header": "Последние заявки:",
            "status.list.item": "#{order_id} — {status} — €{total}",
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
