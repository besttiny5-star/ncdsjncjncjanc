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
            "wizard.geo": "🌍 Step 1/6 — Select GEO\n\nChoose the country for testing:",
            "wizard.method": "💳 Step 2/6 — Payment method\n\nSelect the payment method to be tested from the list below.",
            "wizard.tests": "📦 Step 3/6 — Number of test runs\n\nSend a number from 1 to 25. Base price per test: €{base}.",
            "wizard.payout": "💼 Step 3/6 — Payout requirements\n\nPlease select payout option:",
            "wizard.invalid.payout": "Please choose one of the payout options.",
            "payout.option.none": "No payout needed (0 €)",
            "payout.option.withdraw": "Need payout (+10 €) — requires account with withdrawal capability",
            "payout.option.kyc": "Need full KYC verification (+25 €) — requires local tester data",
            "wizard.comments": "📝 Step 4/6 — Comments\n\nAny special comments or requests? Send text or choose Skip.",
            "wizard.site": "🔗 Step 5/6 — Website URL\n\nSend the checkout page URL starting with http:// or https://.",
            "wizard.login": "🔐 Step 6/6 — Login for testers\n\nSend the login if required or choose Skip.",
            "wizard.password": "Password for testers\n\nSend the password or choose Skip.",
            "wizard.skip": "Skip",
            "wizard.back": "◀️ Back",
            "wizard.cancel": "❌ Cancel",
            "wizard.yes": "Yes",
            "wizard.no": "No",
            "wizard.missing.custom_text": "Please describe the custom test scenario to continue.",
            "wizard.invalid.geo": "Please choose one of the suggested GEO buttons.",
            "wizard.invalid.method": "Please choose one of the available payment methods.",
            "wizard.invalid.tests": "Please send an integer from 1 to 25.",
            "wizard.invalid.url": "The URL must start with http:// or https://.",
            "wizard.invalid.comment": "Comments should not exceed 1000 characters.",
            "wizard.invalid.login": "Login must be between 2 and 120 characters.",
            "wizard.invalid.password": "Password must be between 2 and 120 characters.",
            "confirmation.title": "Please confirm the order",
            "confirmation.body": (
                "<b>Summary</b>\n"
                "GEO: {geo}\n"
                "Tests: {tests}\n"
                "Payment method: {method}\n"
                "Payout option: {payout}\n"
                "Website: {site}\n"
                "Login: {login}\n"
                "Comments: {comments}\n"
                "Total: €{total}\n\n"
                "Ready to continue?"
            ),
            "confirmation.confirm": "✅ Confirm and pay",
            "confirmation.edit": "✏️ Edit data",
            "confirmation.cancel": "❌ Cancel",
            "confirmation.cancelled": "Order cancelled. If you change your mind, start again with /start.",
            "confirmation.ready": "Great! Here are the payment details.",
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
            "order.accepted": "✅ Order #{order_id} saved. Total amount: €{total}.",
            "order.duplicate": "We already have order #{order_id} with the same parameters. Total: €{total}.",
            "help.text": "Commands:\n/start — restart the wizard\n/status — last order status\n/cancel — cancel current flow\n/lang — switch language",
            "lang.updated": "Language switched to English.",
            "lang.prompt": "Send /lang to switch language anytime.",
            "admin.notify.new": "New order #{order_id} from @{username} ({geo}) — €{total}.",
            "admin.notify.payment": "Payment proof for order #{order_id} received.",
            "admin.stats.header": "Admin dashboard",
            "admin.stats.line": "{status}: {count}",
            "admin.no.orders": "No orders found.",
            "group.restriction": "Please message the bot directly to place an order.",
            "group.button": "Open bot",
        },
        "ru": {
            "start.site.invalid": "Не удалось распознать параметры заявки. Откройте ссылку с сайта ещё раз или используйте /start без параметров.",
            "start.tg": "Привет! Давайте оформим заявку на QA платежей. Я помогу пройти все шаги.",
            "wizard.geo": "🌍 Шаг 1/6 — Выбор GEO\n\nВыберите страну для тестирования:",
            "wizard.method": "💳 Шаг 2/6 — Метод оплаты\n\nВыберите способ оплаты для теста из списка ниже.",
            "wizard.tests": "📦 Шаг 3/6 — Количество прогонов\n\nОтправьте число от 1 до 25. Базовая цена за тест: €{base}.",
            "wizard.payout": "💼 Шаг 3/6 — Требования к выплатам\n\nВыберите нужный вариант:",
            "wizard.invalid.payout": "Пожалуйста, выберите один из вариантов выплаты.",
            "payout.option.none": "Выплата не нужна (0 €)",
            "payout.option.withdraw": "Нужна выплата (+10 €) — требуется аккаунт с выводом",
            "payout.option.kyc": "Нужна полная KYC-верификация (+25 €) — требуется локальный тестер",
            "wizard.comments": "📝 Шаг 4/6 — Comments\n\nAny special comments or requests? Send text or choose Skip.",
            "wizard.site": "🔗 Шаг 5/6 — Сайт для теста\n\nОтправьте ссылку, начинающуюся с http:// или https://.",
            "wizard.login": "🔐 Шаг 6/6 — Логин для тестеров\n\nПришлите логин или пропустите.",
            "wizard.password": "Пароль для тестеров\n\nПришлите пароль или пропустите.",
            "wizard.skip": "Пропустить",
            "wizard.back": "◀️ Назад",
            "wizard.cancel": "❌ Отмена",
            "wizard.yes": "Да",
            "wizard.no": "Нет",
            "wizard.missing.custom_text": "Нужно описать сценарий, чтобы продолжить.",
            "wizard.invalid.geo": "Пожалуйста, выберите одну из предложенных стран.",
            "wizard.invalid.method": "Пожалуйста, выберите один из доступных способов оплаты.",
            "wizard.invalid.tests": "Количество тестов должно быть целым числом от 1 до 25.",
            "wizard.invalid.url": "Ссылка должна начинаться с http:// или https://.",
            "wizard.invalid.comment": "Комментарий не должен превышать 1000 символов.",
            "wizard.invalid.login": "Логин должен содержать от 2 до 120 символов.",
            "wizard.invalid.password": "Пароль должен содержать от 2 до 120 символов.",
            "confirmation.title": "Подтвердите заявку",
            "confirmation.body": (
                "<b>Проверьте детали</b>\n"
                "GEO: {geo}\n"
                "Тесты: {tests}\n"
                "Метод оплаты: {method}\n"
                "Вариант выплаты: {payout}\n"
                "Сайт: {site}\n"
                "Логин: {login}\n"
                "Комментарий: {comments}\n"
                "Итого: €{total}\n\n"
                "Всё верно?"
            ),
            "confirmation.confirm": "✅ Подтвердить и оплатить",
            "confirmation.edit": "✏️ Изменить данные",
            "confirmation.cancel": "❌ Отмена",
            "confirmation.cancelled": "Заявка отменена. Если передумаете — начните заново через /start.",
            "confirmation.ready": "Отлично! Вот реквизиты для оплаты.",
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
            "order.accepted": "✅ Заявка #{order_id} принята. Сумма к оплате: €{total}.",
            "order.duplicate": "У нас уже есть заявка #{order_id} с этими параметрами. Сумма: €{total}.",
            "help.text": "Команды:\n/start — начать заново\n/status — статус последнего заказа\n/cancel — отменить текущий шаг\n/lang — сменить язык",
            "lang.updated": "Язык переключен на русский.",
            "lang.prompt": "Отправьте /lang, чтобы сменить язык в любой момент.",
            "admin.notify.new": "Новый заказ #{order_id} от @{username} ({geo}) — €{total}.",
            "admin.notify.payment": "Получен платёжный чек по заказу #{order_id}.",
            "admin.stats.header": "Админ-панель",
            "admin.stats.line": "{status}: {count}",
            "admin.no.orders": "Заказов нет.",
            "group.restriction": "Пожалуйста, напишите боту в личные сообщения, чтобы оформить заказ.",
            "group.button": "Открыть бота",
        },
    }
)
