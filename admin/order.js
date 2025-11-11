const ORDER_STATUS_BADGES = {
  awaiting_payment: { label: 'Ожидает оплаты', emoji: '⏳' },
  proof_received: { label: 'Чек получен', emoji: '🧾' },
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

const SOURCE_LABELS = {
  bot: 'Бот',
  site: 'Сайт',
  unknown: 'Неизвестно'
};

function formatSourceLabel(source) {
  if (!source) return SOURCE_LABELS.unknown;
  return SOURCE_LABELS[source] || SOURCE_LABELS.unknown;
}

let orders = [];
let orderIndex = 0;
let activity = [];
let countries = {};
let testers = [];
let isOrderPageInitialized = false;

function applyOrderData(data) {
  orders = (data.orders || [])
    .map((order) => ({
      ...order,
      createdAt: order.createdAt instanceof Date ? order.createdAt : new Date(order.createdAt),
      paidAt: order.paidAt ? (order.paidAt instanceof Date ? order.paidAt : new Date(order.paidAt)) : null,
      startedAt: order.startedAt ? (order.startedAt instanceof Date ? order.startedAt : new Date(order.startedAt)) : null,
      completedAt: order.completedAt ? (order.completedAt instanceof Date ? order.completedAt : new Date(order.completedAt)) : null
    }))
    .sort((a, b) => a.createdAt - b.createdAt);
  testers = Array.isArray(data.testers) ? data.testers : [];
  countries = data.countries || {};
  activity = Array.isArray(data.activity)
    ? data.activity
        .map((item) => ({
          ...item,
          createdAt: item.createdAt instanceof Date ? item.createdAt : new Date(item.createdAt)
        }))
        .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
    : [];
}

function resolveInitialOrderIndex() {
  if (!orders.length) return 0;
  const params = new URLSearchParams(window.location.search);
  let orderNumber = params.get('order');
  const orderId = params.get('id');
  if (!orderNumber && orderId) {
    const foundById = orders.find((item) => String(item.id) === orderId);
    if (foundById) return orders.indexOf(foundById);
  }
  if (!orderNumber) {
    const pathParts = window.location.pathname.split('/');
    const lastSegment = pathParts[pathParts.length - 1];
    if (lastSegment.includes('-')) {
      orderNumber = lastSegment;
    }
  }
  if (orderNumber) {
    const idx = orders.findIndex((order) => order.orderNumber === orderNumber);
    if (idx >= 0) return idx;
  }
  if (orderId) {
    const idx = orders.findIndex((item) => String(item.id) === orderId);
    if (idx >= 0) return idx;
  }
  return orders.length - 1;
}

function setupOrderPage() {
  if (isOrderPageInitialized) return;

  const backLink = document.getElementById('back-link');
  if (backLink) {
    backLink.href = 'index.html#orders';
    backLink.addEventListener('click', (event) => {
      event.preventDefault();
      window.location.href = 'index.html#orders';
    });
  }

  const prevButton = document.getElementById('prev-order');
  if (prevButton) prevButton.addEventListener('click', () => navigate(-1));

  const nextButton = document.getElementById('next-order');
  if (nextButton) nextButton.addEventListener('click', () => navigate(1));

  const changeStatus = document.getElementById('change-status');
  if (changeStatus) {
    changeStatus.addEventListener('click', () => {
      document.getElementById('status-dialog')?.showModal();
    });
  }

  const statusSave = document.getElementById('status-save');
  if (statusSave) {
    statusSave.addEventListener('click', () => {
      document.getElementById('status-dialog')?.close();
      showToast('✅', 'Статус обновлён (демо)');
    });
  }

  document.querySelectorAll('[data-close]').forEach((btn) =>
    btn.addEventListener('click', () => btn.closest('dialog')?.close())
  );

  isOrderPageInitialized = true;
}

function bootstrapOrderPage(data, { isUpdate = false } = {}) {
  const currentOrder = orders[orderIndex];
  const preferredId = currentOrder?.id;
  const preferredNumber = currentOrder?.orderNumber;

  applyOrderData(data);

  if (!isOrderPageInitialized) {
    setupOrderPage();
    orderIndex = resolveInitialOrderIndex();
  } else if (orders.length) {
    let nextIndex = -1;
    if (preferredId !== undefined) {
      nextIndex = orders.findIndex((order) => order.id === preferredId);
    }
    if (nextIndex === -1 && preferredNumber) {
      nextIndex = orders.findIndex((order) => order.orderNumber === preferredNumber);
    }
    if (nextIndex === -1) {
      nextIndex = Math.min(orderIndex, orders.length - 1);
    }
    orderIndex = Math.max(0, nextIndex);
  } else {
    orderIndex = 0;
  }

  renderOrder();
  if (isUpdate) {
    showToast('🔄', 'Данные обновлены');
  }
}

function navigate(direction) {
  if (!orders.length) return;
  orderIndex = (orderIndex + direction + orders.length) % orders.length;
  const order = orders[orderIndex];
  if (order) {
    const url = new URL(window.location.href);
    url.searchParams.set('order', order.orderNumber);
    history.replaceState({}, '', url.toString());
  }
  renderOrder();
}

function renderOrder() {
  const title = document.getElementById('order-title');
  const subtitle = document.getElementById('order-subtitle');
  const detailContainer = document.getElementById('order-detail');

  if (!orders.length) {
    if (title) title.textContent = 'Заказы отсутствуют';
    if (subtitle) subtitle.textContent = '';
    if (detailContainer) {
      detailContainer.innerHTML = '<p>Нет доступных заказов. Дождитесь новых заявок.</p>';
    }
    return;
  }

  orderIndex = Math.min(Math.max(orderIndex, 0), orders.length - 1);
  const order = orders[orderIndex];
  const statusMeta = ORDER_STATUS_BADGES[order.status] || { label: order.status, emoji: '❔' };
  const createdLabel = order.createdAt instanceof Date ? order.createdAt.toLocaleDateString('ru-RU') : '—';

  if (title) title.textContent = `Заказ ${order.orderNumber}`;
  if (subtitle) subtitle.textContent = `${createdLabel} • ${statusMeta.label}`;

  const statusSelect = document.getElementById('status-select');
  if (statusSelect) {
    if (!statusSelect.querySelector(`option[value="${order.status}"]`)) {
      const option = document.createElement('option');
      option.value = order.status;
      option.textContent = statusMeta.label;
      statusSelect.appendChild(option);
    }
    statusSelect.value = order.status;
  }

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
  const client = order.client || {};
  const isSameClient = (item) => {
    const other = item.client || {};
    if (client.telegramId && other.telegramId) return other.telegramId === client.telegramId;
    if (client.username && other.username) return other.username === client.username;
    return false;
  };
  const clientOrders = orders.filter(isSameClient);
  const totalOrders = clientOrders.length;
  const spent = clientOrders
    .filter((item) => ['paid', 'in_progress', 'completed'].includes(item.status))
    .reduce((acc, item) => acc + (item.priceEur || 0), 0);
  const sortedByCreated = [...clientOrders].sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
  const firstOrder = sortedByCreated[0];
  const lastOrder = sortedByCreated[sortedByCreated.length - 1];

  section.innerHTML = `
    <h4>Информация о клиенте</h4>
    <div class="order-grid">
      <div class="order-grid__item"><span>Username</span>${client.username ? '@' + client.username : '—'}</div>
      <div class="order-grid__item"><span>Telegram ID</span>${client.telegramId || '—'}</div>
      <div class="order-grid__item"><span>Email</span>${client.email || '—'}</div>
      <div class="order-grid__item"><span>Телефон</span>${client.phone || '—'}</div>
    </div>
    <div class="order-grid">
      <div class="order-grid__item"><span>Всего заказов</span>${totalOrders}</div>
      <div class="order-grid__item"><span>Всего потрачено</span>${currencyFormatter.format(spent)}</div>
      <div class="order-grid__item"><span>Первый заказ</span>${
        firstOrder && firstOrder.createdAt instanceof Date ? firstOrder.createdAt.toLocaleDateString('ru-RU') : '—'
      }</div>
      <div class="order-grid__item"><span>Последний заказ</span>${
        lastOrder && lastOrder.createdAt instanceof Date ? lastOrder.createdAt.toLocaleDateString('ru-RU') : '—'
      }</div>
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
  const timeline = ['Создан', 'Чек получен', 'Оплачен', 'В работе', 'Завершён'];
  const timelineStatus = [
    true,
    Boolean(order.paymentProof),
    Boolean(order.paidAt),
    Boolean(order.startedAt || order.status === 'completed'),
    Boolean(order.completedAt)
  ];

  section.innerHTML = `
    <h4>Статус и прогресс</h4>
    <div class="order-status ${order.status}">${
      (ORDER_STATUS_BADGES[order.status] || { emoji: '❔', label: order.status }).emoji
    } ${(ORDER_STATUS_BADGES[order.status] || { label: order.status }).label}</div>
    <div class="progress">
      ${timeline
        .map((label, index) => `<div class="progress__step ${timelineStatus[index] ? 'progress__step--active' : ''}"><span>${label}</span></div>`)
        .join('')}
    </div>
    <p>Последнее обновление: ${
      (order.completedAt instanceof Date && order.completedAt.toLocaleString('ru-RU')) ||
      (order.startedAt instanceof Date && order.startedAt.toLocaleString('ru-RU')) ||
      (order.paidAt instanceof Date && order.paidAt.toLocaleString('ru-RU')) ||
      (order.createdAt instanceof Date ? order.createdAt.toLocaleString('ru-RU') : '—')
    }</p>
  `;
}

function renderDetailsSection(order) {
  const section = document.getElementById('details-section');
  const country = countries[order.geo];
  const packageLabel = PACKAGE_LABELS[order.packageType] || order.packageType || '—';
  const amountLabel = Number.isFinite(order.priceEur) ? currencyFormatter.format(order.priceEur) : '—';
  const sourceLabel = formatSourceLabel(order.source);
  const credentials = order.credentials || {};
  section.innerHTML = `
    <h4>Детали заказа</h4>
    <div class="order-grid">
      <div class="order-grid__item"><span>Пакет</span>${packageLabel}</div>
      <div class="order-grid__item"><span>Источник</span>${sourceLabel}</div>
      <div class="order-grid__item"><span>GEO</span>${country ? `${country.flag} ${country.name}` : order.geo || '—'}</div>
      <div class="order-grid__item"><span>Сумма</span>${amountLabel}</div>
    </div>
    <div class="order-grid">
      <div class="order-grid__item"><span>Метод оплаты</span>${order.paymentMethod || '—'}</div>
      <div class="order-grid__item"><span>Сайт</span>${
        order.websiteUrl ? `<a href="${order.websiteUrl}" target="_blank">${order.websiteUrl}</a>` : '—'
      }</div>
      <div class="order-grid__item"><span>Логин</span>${credentials.login || '—'}</div>
      <div class="order-grid__item"><span>Пароль</span>${credentials.password ? '••••••' : '—'}</div>
    </div>
    <p><span class="badge">Комментарий клиента</span><br />${order.comments || 'Нет комментариев'}</p>
  `;
}

function renderFilesSection(order) {
  const section = document.getElementById('files-section');
  const attachments = Array.isArray(order.attachments) ? order.attachments : [];
  if (!attachments.length) {
    section.innerHTML = '<h4>Файлы от клиента</h4><p>Нет прикреплённых файлов</p>';
    return;
  }
  section.innerHTML = `
    <h4>Файлы от клиента (${attachments.length})</h4>
    <div class="files-grid">
      ${attachments
        .map((file) => {
          const fileName = file.fileName || file.title || 'Файл без имени';
          const fileUrl = file.url || '#';
          if (file.type === 'image') {
            return `<div class="file-card"><img src="${fileUrl}" alt="${fileName}" /><div>${fileName}</div><div class="file-card__actions"><a class="btn btn--soft" href="${fileUrl}" target="_blank">Просмотр</a><a class="btn btn--ghost" href="${fileUrl}" download>Скачать</a></div></div>`;
          }
          if (file.type === 'video') {
            return `<div class="file-card"><video src="${fileUrl}" controls></video><div>${fileName}</div><div class="file-card__actions"><a class="btn btn--ghost" href="${fileUrl}" download>Скачать</a></div></div>`;
          }
          return `<div class="file-card"><div>${fileName}</div><div class="file-card__actions"><a class="btn btn--ghost" href="${fileUrl}" target="_blank">Открыть</a></div></div>`;
        })
        .join('')}
    </div>
  `;
}

function renderPaymentSection(order) {
  const section = document.getElementById('payment-section');
  const proof = order.paymentProof;
  if (!proof) {
    const createdAt = order.createdAt instanceof Date ? order.createdAt.getTime() : Date.now();
    const hoursWaiting = Math.round((Date.now() - createdAt) / 36e5);
    section.innerHTML = `
      <h4>Подтверждение оплаты</h4>
      <p>⏳ Оплата не подтверждена. Прошло ${hoursWaiting} ч. с момента создания.</p>
      <button class="btn btn--soft" onclick="showToast('📣', 'Напоминание отправлено (демо)')">💬 Напомнить клиенту</button>
    `;
    return;
  }

  const uploadedAt = proof.uploadedAt instanceof Date ? proof.uploadedAt : proof.uploadedAt ? new Date(proof.uploadedAt) : null;
  const uploadedLabel = uploadedAt ? uploadedAt.toLocaleString('ru-RU') : 'дата неизвестна';
  const meta = [];
  if (proof.txid) meta.push(`<div class="order-grid__item"><span>TXID</span>${proof.txid}</div>`);
  if (proof.fileId) meta.push(`<div class="order-grid__item"><span>File ID</span>${proof.fileId}</div>`);
  const proofImage = proof.url
    ? `<img src="${proof.url}" alt="Чек оплаты" style="max-height:260px;border-radius:12px;object-fit:cover;" />`
    : '';

  section.innerHTML = `
    <h4>Подтверждение оплаты</h4>
    <p>🧾 Чек получен ${uploadedLabel}</p>
    ${meta.length ? `<div class="order-grid">${meta.join('')}</div>` : ''}
    ${proofImage}
  `;
}

function renderTesterSection(order) {
  const section = document.getElementById('tester-section');
  const tester = order.testerId ? testers.find((item) => item.id === order.testerId) : null;
  const testerOptions = testers.length
    ? testers
        .map(
          (item) =>
            `<option value="${item.id}" ${item.id === order.testerId ? 'selected' : ''}>${item.name} (${item.geoFocus || '—'})</option>`
        )
        .join('')
    : '<option value="">Нет доступных тестеров</option>';
  section.innerHTML = `
    <h4>Назначение тестера</h4>
    ${
      tester
        ? `<div class="order-grid">
            <div class="order-grid__item"><span>Имя</span>${tester.name}</div>
            <div class="order-grid__item"><span>GEO</span>${tester.geoFocus || '—'}</div>
            <div class="order-grid__item"><span>Выполнено тестов</span>${tester.completed ?? '—'}</div>
            <div class="order-grid__item"><span>Рейтинг</span>${tester.rating ?? '—'}</div>
          </div>
          <button class="btn btn--ghost" onclick="showToast('🚫', 'Тестер снят (демо)')">Снять тестера</button>`
        : '<p>Тестер не назначен.</p>'
    }
    <label class="input"><span>Назначить другого тестера</span><select id="detail-tester">${testerOptions}</select></label>
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
          (item) => {
            const timestamp = item.createdAt instanceof Date ? item.createdAt.toLocaleString('ru-RU') : '—';
            const description = item.description || 'Без описания';
            return `
            <li class="activity__item">
              <div class="activity-card">
                <div class="activity-card__header">
                  <div class="activity-card__meta"><span>${EVENT_ICONS[item.eventType] || '📌'}</span><span>${timestamp}</span></div>
                  <span class="badge">${item.eventType}</span>
                </div>
                <p>${description}</p>
              </div>
            </li>`;
          }
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

function scheduleOrderBootstrap(data, { isUpdate = false } = {}) {
  if (!data) return;
  const run = () => bootstrapOrderPage(data, { isUpdate });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true });
  } else {
    run();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupOrderPage();
  if (window.PaymentQA?.data) {
    bootstrapOrderPage(window.PaymentQA.data);
  } else {
    const container = document.getElementById('order-detail');
    if (container) container.innerHTML = '<p>Загрузка данных...</p>';
  }
});

window.addEventListener('paymentqa:data-ready', (event) => {
  scheduleOrderBootstrap(event.detail, { isUpdate: false });
});

window.addEventListener('paymentqa:data-updated', (event) => {
  scheduleOrderBootstrap(event.detail, { isUpdate: true });
});
