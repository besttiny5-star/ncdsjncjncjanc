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
            "wizard.method.additional": "➕ Create additional order (another method)",
            "wizard.payout": (
                "Please select payout option:\n"
                "• No payout needed (0 €)\n"
                "• Need payout verification (+10 €) — Requires account with withdrawal capability.\n"
                "• Need full KYC verification (+25 €) — Requires tester’s personal data for KYC."
            ),
            "wizard.payout.option.none": "No payout needed (0 €)",
            "wizard.payout.option.withdraw": "Need payout verification (+10 €)",
            "wizard.payout.option.kyc": "Need full KYC verification (+25 €)",
            "wizard.comments": "Any specific comments or requests?",
            "wizard.skip": "Skip",
            "wizard.back": "◀️ Back",
            "wizard.cancel": "❌ Cancel",
            "wizard.invalid.geo": "Please choose one of the suggested GEO buttons.",
            "wizard.invalid.comment": "Comments should not exceed 1000 characters.",
            "confirmation.title": "Please review your order details before confirming.",
            "confirmation.body": (
                "<b>Summary</b>\n"
                "GEO: {geo}\n"
                "Payment method: {method}\n"
                "Payout option: {payout}\n"
                "Comments: {comments}\n"
                "Base price: €{base_price}\n"
                "Method markup: €{method_markup}\n"
                "Payout markup: €{payout_markup}\n"
                "Total: €{total}\n\n"
                "Want to use another payment method as well? Create an additional order for it."
            ),
            "confirmation.confirm": "Confirm ✅",
            "confirmation.edit": "Back ⬅️",
            "confirmation.additional": "➕ Add another order",
            "confirmation.cancel": "❌ Cancel",
            "confirmation.cancelled": "Order cancelled. If you change your mind, start again with /start.",
            "confirmation.ready": "✅ Order successfully created.",
            "final.create": "➕ Create another order (same GEO)",
            "final.view": "📄 View my orders",
            "final.done": "✅ Done",
            "final.done.reply": "All set! If you need another order, send /start.",
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
            "start.tg": "Привет! Давайте оформим заявку на QA платежей. Я помогу пройти шаги.",
            "wizard.geo": "Выберите страну или регион для тестирования",
            "wizard.method": (
                "Выберите метод оплаты\n"
                "Стоимость может зависеть от выбранного метода.\n"
                "Один метод — один заказ. Нужно несколько? Создайте дополнительный заказ."
            ),
            "wizard.method.additional": "➕ Создать дополнительный заказ (другой метод)",
            "wizard.payout": (
                "Выберите опцию по выводу:\n"
                "• Без вывода (0 €)\n"
                "• Нужна проверка вывода (+10 €) — Требуется аккаунт с возможностью вывода.\n"
                "• Нужна полная верификация KYC (+25 €) — Требуются персональные данные тестера для KYC."
            ),
            "wizard.payout.option.none": "Без вывода (0 €)",
            "wizard.payout.option.withdraw": "Нужна проверка вывода (+10 €)",
            "wizard.payout.option.kyc": "Полный KYC (+25 €)",
            "wizard.comments": "Есть ли дополнительные комментарии или пожелания?",
            "wizard.skip": "Пропустить",
            "wizard.back": "◀️ Назад",
            "wizard.cancel": "❌ Отмена",
            "wizard.invalid.geo": "Пожалуйста, выберите одну из предложенных стран.",
            "wizard.invalid.comment": "Комментарий не должен превышать 1000 символов.",
            "confirmation.title": "Проверьте данные заказа перед подтверждением.",
            "confirmation.body": (
                "<b>Проверьте детали</b>\n"
                "GEO: {geo}\n"
                "Метод оплаты: {method}\n"
                "Опция по выводу: {payout}\n"
                "Комментарий: {comments}\n"
                "Базовая цена: €{base_price}\n"
                "Надбавка за метод: €{method_markup}\n"
                "Надбавка за вывод/KYC: €{payout_markup}\n"
                "Итого: €{total}\n\n"
                "Хотите протестировать ещё один метод? Создайте дополнительный заказ."
            ),
            "confirmation.confirm": "✅ Подтвердить",
            "confirmation.edit": "⬅️ Назад",
            "confirmation.additional": "➕ Дополнительный заказ",
            "confirmation.cancel": "❌ Отмена",
            "confirmation.cancelled": "Заявка отменена. Если передумаете — начните заново через /start.",
            "confirmation.ready": "✅ Заказ успешно создан.",
            "final.create": "➕ Создать ещё один заказ (тот же GEO)",
            "final.view": "📄 Посмотреть мои заказы",
            "final.done": "✅ Готово",
            "final.done.reply": "Готово! Если понадобится новый заказ, отправьте /start.",
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
