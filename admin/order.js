const ORDER_STATUS_BADGES = {
  awaiting_payment: { label: 'Ожидает оплаты', emoji: '⏳' },
  paid: { label: 'Оплачено', emoji: '💰' },
  in_progress: { label: 'В процессе', emoji: '🔄' },
  completed: { label: 'Завершено', emoji: '✅' },
  cancelled: { label: 'Отменено', emoji: '❌' }
};

const PACKAGE_LABELS = {
  single: 'Single Test',
  mini: 'Mini Audit',
  retainer: 'Retainer'
};

let orders = [];
let orderIndex = 0;
let activity = [];
let countries = {};
let testers = [];

function initOrderPage() {
  if (!window.PaymentQA_DATA) {
    console.error('Нет данных PaymentQA_DATA');
    return;
  }
  orders = window.PaymentQA_DATA.orders
    .map((order) => ({
      ...order,
      createdAt: new Date(order.createdAt),
      paidAt: order.paidAt ? new Date(order.paidAt) : null,
      startedAt: order.startedAt ? new Date(order.startedAt) : null,
      completedAt: order.completedAt ? new Date(order.completedAt) : null
    }))
    .sort((a, b) => a.createdAt - b.createdAt);
  testers = window.PaymentQA_DATA.testers;
  countries = window.PaymentQA_DATA.countries;
  activity = window.PaymentQA_DATA.activity.map((item) => ({ ...item, createdAt: new Date(item.createdAt) }));

  const params = new URLSearchParams(window.location.search);
  let orderNumber = params.get('order');
  const orderId = params.get('id');
  if (!orderNumber && orderId) {
    const foundById = orders.find((item) => String(item.id) === orderId);
    if (foundById) orderNumber = foundById.orderNumber;
  }
  if (!orderNumber) {
    const pathParts = window.location.pathname.split('/');
    const lastSegment = pathParts[pathParts.length - 1];
    if (lastSegment.includes('-')) {
      orderNumber = lastSegment;
    }
  }
  const idx = orders.findIndex((order) => order.orderNumber === orderNumber);
  orderIndex = idx >= 0 ? idx : orders.length - 1;

  document.getElementById('back-link').href = 'index.html#orders';
  document.getElementById('back-link').addEventListener('click', (event) => {
    event.preventDefault();
    window.location.href = 'index.html#orders';
  });

  document.getElementById('prev-order').addEventListener('click', () => navigate(-1));
  document.getElementById('next-order').addEventListener('click', () => navigate(1));
  document.getElementById('change-status').addEventListener('click', () => {
    document.getElementById('status-dialog').showModal();
  });
  document.getElementById('status-save').addEventListener('click', () => {
    document.getElementById('status-dialog').close();
    showToast('✅', 'Статус обновлён (демо)');
  });
  document.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => btn.closest('dialog').close()));

  renderOrder();
}

function navigate(direction) {
  orderIndex = (orderIndex + direction + orders.length) % orders.length;
  const order = orders[orderIndex];
  const url = new URL(window.location.href);
  url.searchParams.set('order', order.orderNumber);
  history.replaceState({}, '', url.toString());
  renderOrder();
}

function renderOrder() {
  const order = orders[orderIndex];
  if (!order) return;

  document.getElementById('order-title').textContent = `Заказ ${order.orderNumber}`;
  document.getElementById('order-subtitle').textContent = `${order.createdAt.toLocaleDateString('ru-RU')} • ${ORDER_STATUS_BADGES[order.status].label}`;
  document.getElementById('status-select').value = order.status;

  renderClientSection(order);
  renderStatusSection(order);
  renderDetailsSection(order);
  renderFilesSection(order);
  renderPaymentSection(order);
  renderTesterSection(order);
  renderActivitySection(order);
}

function renderClientSection(order) {
  const section = document.getElementById('client-section');
  const totalOrders = orders.filter((item) => item.client.telegramId === order.client.telegramId).length;
  const spent = orders
    .filter((item) => item.client.telegramId === order.client.telegramId && ['paid', 'in_progress', 'completed'].includes(item.status))
    .reduce((acc, item) => acc + item.priceEur, 0);
  const firstOrder = orders
    .filter((item) => item.client.telegramId === order.client.telegramId)
    .sort((a, b) => a.createdAt - b.createdAt)[0];
  const lastOrder = orders
    .filter((item) => item.client.telegramId === order.client.telegramId)
    .sort((a, b) => b.createdAt - a.createdAt)[0];

  section.innerHTML = `
    <h4>Информация о клиенте</h4>
    <div class="order-grid">
      <div class="order-grid__item"><span>Username</span>${order.client.username ? '@' + order.client.username : '—'}</div>
      <div class="order-grid__item"><span>Telegram ID</span>${order.client.telegramId || '—'}</div>
      <div class="order-grid__item"><span>Email</span>${order.client.email || '—'}</div>
      <div class="order-grid__item"><span>Телефон</span>${order.client.phone || '—'}</div>
    </div>
    <div class="order-grid">
      <div class="order-grid__item"><span>Всего заказов</span>${totalOrders}</div>
      <div class="order-grid__item"><span>Всего потрачено</span>${currencyFormatter.format(spent)}</div>
      <div class="order-grid__item"><span>Первый заказ</span>${firstOrder ? firstOrder.createdAt.toLocaleDateString('ru-RU') : '—'}</div>
      <div class="order-grid__item"><span>Последний заказ</span>${lastOrder ? lastOrder.createdAt.toLocaleDateString('ru-RU') : '—'}</div>
    </div>
    <div class="order-grid">
      <button class="btn btn--soft" onclick="showToast('💬', 'Написать клиенту (демо)')">💬 Написать в Telegram</button>
      <button class="btn btn--ghost" onclick="showToast('📋', 'История заказов (демо)')">📋 История заказов</button>
      <button class="btn btn--danger" onclick="showToast('🚫', 'Клиент заблокирован (демо)')">🚫 Заблокировать клиента</button>
    </div>
  `;
}

function renderStatusSection(order) {
  const section = document.getElementById('status-section');
  const timeline = ['Создан', 'Оплачен', 'В работе', 'Завершён'];
  const timelineStatus = [true, Boolean(order.paidAt), Boolean(order.startedAt || order.status === 'completed'), Boolean(order.completedAt)];

  section.innerHTML = `
    <h4>Статус и прогресс</h4>
    <div class="order-status ${order.status}">${ORDER_STATUS_BADGES[order.status].emoji} ${ORDER_STATUS_BADGES[order.status].label}</div>
    <div class="progress">
      ${timeline
        .map((label, index) => `<div class="progress__step ${timelineStatus[index] ? 'progress__step--active' : ''}"><span>${label}</span></div>`)
        .join('')}
    </div>
    <p>Последнее обновление: ${order.completedAt || order.startedAt || order.paidAt || order.createdAt.toLocaleString('ru-RU')}</p>
  `;
}

function renderDetailsSection(order) {
  const section = document.getElementById('details-section');
  const country = countries[order.geo];
  section.innerHTML = `
    <h4>Детали заказа</h4>
    <div class="order-grid">
      <div class="order-grid__item"><span>Пакет</span>${PACKAGE_LABELS[order.packageType]}</div>
      <div class="order-grid__item"><span>GEO</span>${country ? `${country.flag} ${country.name}` : order.geo}</div>
      <div class="order-grid__item"><span>Сумма</span>${currencyFormatter.format(order.priceEur)}</div>
      <div class="order-grid__item"><span>Метод оплаты</span>${order.paymentMethod || '—'}</div>
    </div>
    <div class="order-grid">
      <div class="order-grid__item"><span>Сайт</span>${order.websiteUrl ? `<a href="${order.websiteUrl}" target="_blank">${order.websiteUrl}</a>` : '—'}</div>
      <div class="order-grid__item"><span>Логин</span>${order.credentials?.login || '—'}</div>
      <div class="order-grid__item"><span>Пароль</span>${order.credentials?.password || '—'}</div>
      <div class="order-grid__item"><span>Комментарий клиента</span>${order.comments || 'Нет комментариев'}</div>
    </div>
  `;
}

function renderFilesSection(order) {
  const section = document.getElementById('files-section');
  if (!order.attachments.length) {
    section.innerHTML = '<h4>Файлы от клиента</h4><p>Нет прикреплённых файлов</p>';
    return;
  }
  section.innerHTML = `
    <h4>Файлы от клиента (${order.attachments.length})</h4>
    <div class="files-grid">
      ${order.attachments
        .map((file) => {
          if (file.type === 'image') {
            return `<div class="file-card"><img src="${file.url}" alt="${file.fileName}" /><div>${file.fileName}</div><div class="file-card__actions"><a class="btn btn--soft" href="${file.url}" target="_blank">Просмотр</a><a class="btn btn--ghost" href="${file.url}" download>Скачать</a></div></div>`;
          }
          if (file.type === 'video') {
            return `<div class="file-card"><video src="${file.url}" controls></video><div>${file.fileName}</div><div class="file-card__actions"><a class="btn btn--ghost" href="${file.url}" download>Скачать</a></div></div>`;
          }
          return `<div class="file-card"><div>${file.fileName}</div><div class="file-card__actions"><a class="btn btn--ghost" href="${file.url}" target="_blank">Открыть</a></div></div>`;
        })
        .join('')}
    </div>
  `;
}

function renderPaymentSection(order) {
  const section = document.getElementById('payment-section');
  if (!order.paymentProof) {
    const hoursWaiting = Math.round((Date.now() - order.createdAt.getTime()) / 36e5);
    section.innerHTML = `
      <h4>Подтверждение оплаты</h4>
      <p>⏳ Оплата не подтверждена. Прошло ${hoursWaiting} ч. с момента создания.</p>
      <button class="btn btn--soft" onclick="showToast('📣', 'Напоминание отправлено (демо)')">💬 Напомнить клиенту</button>
    `;
    return;
  }
  section.innerHTML = `
    <h4>Подтверждение оплаты</h4>
    <p>✅ Чек получен ${new Date(order.paymentProof.uploadedAt).toLocaleString('ru-RU')} от ${order.paymentProof.admin || '—'}</p>
    <img src="${order.paymentProof.url}" alt="Чек оплаты" style="max-height:260px;border-radius:12px;object-fit:cover;" />
  `;
}

function renderTesterSection(order) {
  const section = document.getElementById('tester-section');
  const tester = order.testerId ? testers.find((item) => item.id === order.testerId) : null;
  section.innerHTML = `
    <h4>Назначение тестера</h4>
    ${
      tester
        ? `<div class="order-grid">
            <div class="order-grid__item"><span>Имя</span>${tester.name}</div>
            <div class="order-grid__item"><span>GEO</span>${tester.geoFocus}</div>
            <div class="order-grid__item"><span>Выполнено тестов</span>${tester.completed}</div>
            <div class="order-grid__item"><span>Рейтинг</span>${tester.rating}</div>
          </div>
          <button class="btn btn--ghost" onclick="showToast('🚫', 'Тестер снят (демо)')">Снять тестера</button>`
        : '<p>Тестер не назначен.</p>'
    }
    <label class="input"><span>Назначить другого тестера</span><select id="detail-tester">${testers
      .map((item) => `<option value="${item.id}" ${item.id === order.testerId ? 'selected' : ''}>${item.name} (${item.geoFocus})</option>`)
      .join('')}</select></label>
    <button class="btn btn--primary" onclick="showToast('👩‍💻', 'Назначение сохранено (демо)')">Сохранить назначение</button>
  `;
}

function renderActivitySection(order) {
  const section = document.getElementById('activity-section');
  const items = activity
    .filter((item) => item.orderId === order.id)
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 5);
  if (!items.length) {
    section.innerHTML = '<h4>Активность по заказу</h4><p>События отсутствуют</p>';
    return;
  }
  section.innerHTML = `
    <h4>Активность по заказу</h4>
    <ul class="activity__list">
      ${items
        .map(
          (item) => `
            <li class="activity__item">
              <div class="activity-card">
                <div class="activity-card__header">
                  <div class="activity-card__meta"><span>${EVENT_ICONS[item.eventType] || '📌'}</span><span>${item.createdAt.toLocaleString('ru-RU')}</span></div>
                  <span class="badge">${item.eventType}</span>
                </div>
                <p>${item.description}</p>
              </div>
            </li>`
        )
        .join('')}
    </ul>
  `;
}

function showToast(icon, text) {
  const container = document.getElementById('toast');
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span class="toast__icon">${icon}</span><span class="toast__text">${text}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => container.removeChild(toast), 300);
  }, 2200);
}

const currencyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
});

const EVENT_ICONS = {
  order_created: '🆕',
  order_paid: '💰',
  payment_proof_received: '🧾',
  status_changed: '🔁',
  tester_assigned: '👩‍💻',
  tester_unassigned: '🚫',
  report_uploaded: '📄',
  order_completed: '✅',
  order_cancelled: '❌',
  note_added: '📝',
  tester_created: '➕',
  admin_action: '⚙️'
};

document.addEventListener('DOMContentLoaded', initOrderPage);
